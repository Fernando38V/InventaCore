"""Equipos (artículos) conectados a la API: listado, ficha, alta, corrección
desde la ficha y cambio de estado Útil/Obsoleto.

La API decide los permisos y las reglas; aquí solo se oculta lo que el rol no
puede usar, se valida lo evidente para responder rápido y se muestran los
errores de la API junto a cada campo.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from urllib.parse import urlencode

import qrcode
from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from client.api import ApiError, SesionVencida, llamar
from client.inventario import (
    ESTADO_NOLOC, UBICACION_NOLOC, marca_modelo, nombre_articulo, opciones_catalogo,
    opciones_personal, opciones_tipos, resumen_movimiento)
from client.utils import contexto_paginacion, errores_api, es_admin, numero_de_pagina

FILTROS = ('categoria', 'ubicacion', 'estado_operativo', 'estado_registro', 'origen')

# Campos del alta y su nombre en la API (ArticuloCrearSerializer).
CAMPOS_ALTA = ('origen', 'tipo_articulo', 'ubicacion', 'resguardante', 'estado_operativo',
               'marbete_oficial', 'marca', 'modelo', 'num_serie', 'color', 'descripcion',
               'fecha_adquisicion', 'costo_adquisicion')

# Campos de la corrección desde la ficha (DEC-013, ArticuloCorregirSerializer).
# El costo es opcional también en un bien Donado (DEC-021): vacío se guarda
# como vacío (null), nunca como 0.
CAMPOS_CORRECCION = [
    {'nombre': 'marca', 'etiqueta': 'Marca', 'nulo': True, 'max': 50},
    {'nombre': 'modelo', 'etiqueta': 'Modelo', 'nulo': True, 'max': 60},
    {'nombre': 'num_serie', 'etiqueta': 'Número de serie', 'nulo': True, 'max': 50},
    {'nombre': 'color', 'etiqueta': 'Color', 'requerido': True, 'max': 25},
    {'nombre': 'fecha_adquisicion', 'etiqueta': 'Fecha de adquisición', 'tipo': 'date',
     'nulo': True},
    {'nombre': 'costo_adquisicion', 'etiqueta': 'Costo de adquisición (MXN)', 'tipo': 'costo',
     'nulo': True, 'ayuda': 'Opcional. Déjalo vacío si no se conoce; no se guarda como 0.'},
    {'nombre': 'descripcion', 'etiqueta': 'Descripción', 'tipo': 'textarea',
     'requerido': True, 'max': 150, 'completo': True},
]
CAMPO_MARBETE = {'nombre': 'marbete_oficial', 'etiqueta': 'Marbete oficial',
                 'requerido': True, 'max': 25,
                 'ayuda': 'Solo los activos llevan marbete. Corregirlo no cambia el QR.'}


# --- QR (sin cambios) ---------------------------------------------------

def _url_equipo(request, num):
    """Arma la URL completa del equipo para codificarla en el QR.

    Si existe BASE_URL_SISTEMA en settings.py se usa esa (util para la
    etiqueta imprimible, porque esa direccion queda fija en papel y no
    debe cambiar aunque el servidor se mueva de maquina). Si no esta
    definida, se usa el host real de la peticion, que ya es correcto
    para ver el QR dentro del navegador.
    """
    base = getattr(settings, 'BASE_URL_SISTEMA', None)
    if not base:
        base = '{}://{}'.format(request.scheme, request.get_host())
    return '{}{}'.format(base, reverse('equipos:detalle', args=[num]))


def qr_equipo(request, num):
    """RF-19 — genera el codigo QR del equipo al vuelo, sin guardarlo en disco.

    GET /articulos/detalle/<num>/qr/             -> muestra el PNG
    GET /articulos/detalle/<num>/qr/?descargar=1 -> lo fuerza como descarga
    """
    url = _url_equipo(request, num)
    imagen = qrcode.make(url, box_size=8, border=2)

    buffer = BytesIO()
    imagen.save(buffer, format='PNG')
    buffer.seek(0)

    respuesta = HttpResponse(buffer.getvalue(), content_type='image/png')
    if request.GET.get('descargar'):
        respuesta['Content-Disposition'] = (
            'attachment; filename="QR-equipo-{}.png"'.format(num))
    return respuesta


# --- auxiliares ---------------------------------------------------------

def _sin_permiso(request, destino='equipos:listado', *args):
    messages.error(request, 'Solo el Administrador puede hacer esto.')
    return redirect(destino, *args)


def _obtener_articulo(request, num):
    try:
        return llamar(request, 'GET', 'articulos/%d/' % num)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404:
            raise Http404
        raise


def _norm(valor):
    return '' if valor is None else str(valor)


def _costo_texto(valor):
    """Costo para el formulario: sin ceros de más ('12000.00' → '12000')."""
    if valor in (None, ''):
        return ''
    try:
        d = Decimal(str(valor))
    except InvalidOperation:
        return str(valor)
    return format(d.normalize(), 'f')


def _costo_valido(texto):
    """'' si el costo es un número igual o mayor a cero; si no, el mensaje."""
    try:
        if Decimal(texto.replace(',', '')) < 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        return 'El costo debe ser un número igual o mayor a cero.'
    return ''


def _fecha_valida(texto):
    """'' si es válida y no futura; si no, el mensaje de error."""
    try:
        fecha = datetime.strptime(texto, '%Y-%m-%d').date()
    except ValueError:
        return 'La fecha no es válida.'
    if fecha > timezone.localdate():
        return 'La fecha no puede ser futura.'
    return ''


# --- listado ------------------------------------------------------------

def listado_equipos(request):
    pagina = numero_de_pagina(request)
    f = {'q': request.GET.get('q', '').strip()}
    for nombre in FILTROS:
        f[nombre] = request.GET.get(nombre, '').strip()
    params = {k: v for k, v in f.items() if v}

    error = ''
    datos = {'count': 0, 'results': []}
    try:
        datos = llamar(request, 'GET', 'articulos/?' + urlencode(dict(params, page=pagina)))
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404 and pagina > 1:          # página que ya no existe
            return redirect(reverse('equipos:listado')
                            + ('?' + urlencode(params) if params else ''))
        error = errores_api(e)[1]

    opciones = {'categorias': [], 'ubicaciones': [], 'origenes': [],
                'estados_operativos': [], 'estados_registro': []}
    try:
        opciones = {
            'categorias': opciones_catalogo(request, 'categorias'),
            'ubicaciones': opciones_catalogo(request, 'ubicaciones'),
            'origenes': opciones_catalogo(request, 'origenes'),
            'estados_operativos': opciones_catalogo(request, 'estados-operativos'),
            'estados_registro': opciones_catalogo(request, 'estados-registro'),
        }
    except SesionVencida:
        raise
    except ApiError as e:
        error = error or errores_api(e)[1]

    equipos = []
    for a in datos['results']:
        equipos.append(dict(a, nombre=marca_modelo(a)))     # vacío: la plantilla dice «Sin especificar»

    contexto = {
        'equipos': equipos,
        'hay_filtros': any(params.values()),
        'f': f,
        'error_api': error,
    }
    contexto.update(opciones)
    contexto.update(contexto_paginacion(request, datos['count'], pagina))
    return render(request, 'equipos/listado.html', contexto)


# --- ficha --------------------------------------------------------------

def detalle_equipo(request, num):
    equipo = _obtener_articulo(request, num)

    historial, total_movimientos, error = [], 0, ''
    try:
        movs = llamar(request, 'GET', 'articulos/%d/movimientos/' % num)
    except SesionVencida:
        raise
    except ApiError as e:
        error = 'No se pudo cargar el historial: ' + errores_api(e)[1]
    else:
        total_movimientos = movs['count']
        for m in movs['results']:
            historial.append({
                'tipo': m['tipo']['nombre'], 'folio': m['folio'], 'fecha': m['fecha'],
                'detalle': resumen_movimiento(m), 'nota': m['nota'],
                'usuario': m['usuario']['username'],
                'requiere_resguardo': m['requiere_resguardo'],
            })

    equipo = dict(equipo, nombre=nombre_articulo(equipo))
    return render(request, 'equipos/detalle.html', {
        'equipo': equipo,
        'historial': historial,
        'total_movimientos': total_movimientos,
        'hay_mas_movimientos': total_movimientos > len(historial),
        'error_historial': error,
        'esta_util': equipo['estado_operativo']['codigo'] == 'UTIL',
        'esta_obsoleto': equipo['estado_operativo']['codigo'] == 'OBS',
        'esta_noloc': equipo['estado_operativo']['codigo'] == ESTADO_NOLOC,
        'ubicacion_noloc': UBICACION_NOLOC,
    })


@require_POST
def cambiar_estado_equipo(request, num):
    """Útil <-> Obsoleto desde la ficha, con motivo y bitácora (DEC-013).
    Volver de Obsoleto a Útil es excepcional (DEC-012) pero la API lo permite."""
    if not es_admin(request):
        return _sin_permiso(request, 'equipos:detalle', num)

    nuevo = 'UTIL' if request.POST.get('activar') == '1' else 'OBS'
    motivo = request.POST.get('motivo', '').strip()
    if not motivo:
        messages.error(request, 'Indica el motivo del cambio.')
        return redirect('equipos:detalle', num=num)
    try:
        r = llamar(request, 'PATCH', 'articulos/%d/' % num,
                   {'estado_operativo': nuevo, 'motivo': motivo})
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
    else:
        ident = (r or {}).get('identificador', '')
        messages.success(request, 'Artículo %s %s.' % (
            ident, 'marcado como Obsoleto' if nuevo == 'OBS' else 'regresado a Útil'))
    return redirect('equipos:detalle', num=num)


# --- alta ---------------------------------------------------------------

def _validar_alta(v):
    """Validación previa a la API (que vuelve a validar todo)."""
    errores = {}
    if v['origen'] not in ('ACT', 'COM', 'ENS'):
        errores['origen'] = 'Selecciona el origen del artículo.'
    for campo, mensaje in (('tipo_articulo', 'Selecciona el tipo de artículo.'),
                           ('ubicacion', 'Selecciona la ubicación.'),
                           ('resguardante', 'Selecciona el resguardante.'),
                           ('color', 'Escribe el color.'),
                           ('descripcion', 'Escribe la descripción.')):
        if not v[campo]:
            errores[campo] = mensaje
    if v['origen'] == 'ACT' and not v['marbete_oficial']:
        errores['marbete_oficial'] = 'Los activos llevan marbete oficial.'
    if v['fecha_adquisicion']:
        mensaje = _fecha_valida(v['fecha_adquisicion'])
        if mensaje:
            errores['fecha_adquisicion'] = mensaje
    if v['costo_adquisicion']:
        try:
            if Decimal(v['costo_adquisicion'].replace(',', '')) < 0:
                raise InvalidOperation
        except InvalidOperation:
            errores['costo_adquisicion'] = 'El costo debe ser un número igual o mayor a cero.'
    # DEC-012: No localizado y UBI-NOLOC van juntos (la API también lo valida).
    if v['ubicacion'] == UBICACION_NOLOC and v['estado_operativo'] != ESTADO_NOLOC:
        errores['estado_operativo'] = (
            'Un artículo en "Sin ubicar" tiene el estado No localizado.')
    elif v['ubicacion'] and v['ubicacion'] != UBICACION_NOLOC \
            and v['estado_operativo'] == ESTADO_NOLOC:
        errores['estado_operativo'] = (
            'El estado No localizado va con la ubicación "Sin ubicar".')
    return errores


def _cuerpo_alta(v):
    cuerpo = {
        'origen': v['origen'],
        'tipo_articulo': v['tipo_articulo'],
        'ubicacion': v['ubicacion'],
        'resguardante': int(v['resguardante']) if v['resguardante'].isdigit() else v['resguardante'],
        'estado_operativo': v['estado_operativo'] or 'UTIL',
        'marca': v['marca'] or None,
        'modelo': v['modelo'] or None,
        'num_serie': v['num_serie'] or None,
        'color': v['color'],
        'descripcion': v['descripcion'],
        'fecha_adquisicion': v['fecha_adquisicion'] or None,
        # Donado: el costo ni se exige ni se bloquea (DEC-021); lo que se capture se guarda.
        'costo_adquisicion': v['costo_adquisicion'].replace(',', '') or None,
        'donado': v['donado'],
    }
    if v['origen'] == 'ACT':
        cuerpo['marbete_oficial'] = v['marbete_oficial']
    return cuerpo


def registrar_equipo(request):
    if not es_admin(request):
        return _sin_permiso(request)

    v = {campo: '' for campo in CAMPOS_ALTA}
    v.update(origen='ACT', estado_operativo='UTIL', donado=False)
    errores, general = {}, ''

    if request.method == 'POST':
        for campo in CAMPOS_ALTA:
            v[campo] = request.POST.get(campo, '').strip()
        v['donado'] = request.POST.get('donado') == 'on'
        if v['ubicacion'] == UBICACION_NOLOC and not v['estado_operativo']:
            v['estado_operativo'] = ESTADO_NOLOC      # el select viene bloqueado
        v['estado_operativo'] = v['estado_operativo'] or 'UTIL'

        errores = _validar_alta(v)
        if not errores:
            try:
                creado = llamar(request, 'POST', 'articulos/', _cuerpo_alta(v))
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(e, CAMPOS_ALTA)
                errores.update(por_campo)
            else:
                ident = creado['identificador']
                registro = creado['estado_registro']['codigo']
                if registro == 'PEND':
                    messages.warning(request, 'Artículo %s registrado; queda en estado '
                                     'Pendiente. Falta %s.' % (ident, ' y '.join(creado['faltantes'])))
                elif registro == 'DON':
                    messages.success(request, 'Artículo %s registrado como Donado.' % ident)
                else:
                    messages.success(request, 'Artículo %s registrado.' % ident)
                return redirect('equipos:detalle', num=creado['num'])

    categorias, tipos, ubicaciones, personal, origenes, estados = [], [], [], [], [], []
    try:
        categorias, tipos = opciones_tipos(request, actual=v['tipo_articulo'])
        ubicaciones = opciones_catalogo(request, 'ubicaciones', v['ubicacion'], solo_activos=True)
        personal = opciones_personal(request, actual=v['resguardante'])
        origenes = opciones_catalogo(request, 'origenes')
        estados = opciones_catalogo(request, 'estados-operativos')
    except SesionVencida:
        raise
    except ApiError as e:
        general = general or errores_api(e)[1]

    for t in tipos:                                  # categoría del tipo elegido
        if t['codigo'] == v['tipo_articulo']:
            v['categoria'] = t['categoria']

    return render(request, 'equipos/registrar.html', {
        'errores': errores, 'v': v, 'general': general,
        'hoy': timezone.localdate().isoformat(),
        'categorias': categorias, 'tipos': tipos, 'ubicaciones': ubicaciones,
        'personal': personal, 'origenes': origenes, 'estados_operativos': estados,
        'ubicacion_noloc': UBICACION_NOLOC, 'estado_noloc': ESTADO_NOLOC,
    })


# --- corrección desde la ficha -------------------------------------------

def corregir_equipo(request, num):
    """DEC-013: marca, modelo, serie, color, descripción, fecha de adquisición
    (y el marbete de un Activo) se corrigen con motivo y bitácora. Ubicación y
    resguardante solo cambian con un movimiento."""
    if not es_admin(request):
        return _sin_permiso(request, 'equipos:detalle', num)

    equipo = _obtener_articulo(request, num)
    campos = list(CAMPOS_CORRECCION)
    if equipo['origen']['codigo'] == 'ACT':
        campos.insert(0, CAMPO_MARBETE)

    def actual(c):
        v = equipo.get(c['nombre'])
        return _costo_texto(v) if c['nombre'] == 'costo_adquisicion' else _norm(v)

    valores = {c['nombre']: actual(c) for c in campos}
    errores, general, motivo = {}, '', ''

    if request.method == 'POST':
        valores = {c['nombre']: request.POST.get(c['nombre'], '').strip() for c in campos}
        motivo = request.POST.get('motivo', '').strip()
        if valores.get('costo_adquisicion'):
            valores['costo_adquisicion'] = valores['costo_adquisicion'].replace(',', '')

        for c in campos:
            if c.get('requerido') and not valores[c['nombre']]:
                errores[c['nombre']] = 'Este campo es obligatorio.'
        if valores.get('fecha_adquisicion'):
            mensaje = _fecha_valida(valores['fecha_adquisicion'])
            if mensaje:
                errores['fecha_adquisicion'] = mensaje
        if valores.get('costo_adquisicion'):
            mensaje = _costo_valido(valores['costo_adquisicion'])
            if mensaje:
                errores['costo_adquisicion'] = mensaje
            else:       # '1500.50' y '1500.5' son lo mismo: no cuenta como cambio
                valores['costo_adquisicion'] = _costo_texto(valores['costo_adquisicion'])

        # Solo se mandan los campos que cambiaron (la bitácora guarda esos).
        cambios = {}
        for c in campos:
            nuevo = valores[c['nombre']]
            if nuevo != actual(c):
                cambios[c['nombre']] = None if (nuevo == '' and c.get('nulo')) else nuevo
        if not errores and not cambios:
            general = 'No hiciste ningún cambio.'
        elif cambios and not motivo:
            errores['motivo'] = 'Indica el motivo del cambio.'

        if not errores and not general:
            try:
                llamar(request, 'PATCH', 'articulos/%d/' % num, dict(cambios, motivo=motivo))
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(
                    e, [c['nombre'] for c in campos] + ['motivo'])
                errores.update(por_campo)
            else:
                messages.success(request, 'Artículo %s actualizado.' % equipo['identificador'])
                return redirect('equipos:detalle', num=num)

    campos_ctx = [dict(c, tipo=c.get('tipo', 'text'), valor=valores[c['nombre']],
                       error=errores.get(c['nombre'])) for c in campos]
    return render(request, 'equipos/corregir.html', {
        'equipo': dict(equipo, nombre=nombre_articulo(equipo)),
        'campos': campos_ctx, 'general': general, 'motivo': motivo,
        'error_motivo': errores.get('motivo'),
        'hoy': timezone.localdate().isoformat(),
    })
