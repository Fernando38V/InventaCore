"""Movimientos conectados a la API: listado y nuevo movimiento (REUB, REPA y RETE).

El ALTA se crea sola al registrar el artículo y no hay BAJA (DEC-006, DEC-012).
Las reglas las decide la API (api/movimientos/servicios.py); aquí se valida lo
evidente para responder rápido y se muestran sus errores junto a cada campo.
"""
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render, reverse
from django.utils import timezone

from client.api import ApiError, SesionVencida, llamar
from client.inventario import (
    ESTADO_NOLOC, UBICACION_NOLOC, nombre_articulo, opciones_catalogo, opciones_personal)
from client.utils import TAM_PAGINA, contexto_paginacion, errores_api, es_admin, numero_de_pagina

TIPOS_MANUALES = ('REUB', 'REPA', 'RETE')
ESTADOS_AL_RECUPERAR = ('UTIL', 'OBS')
CAMPOS_MOVIMIENTO = ('tipo', 'ubicacion', 'resguardante', 'motivo', 'fecha',
                     'estado_operativo', 'articulo')


# --- listado ------------------------------------------------------------

def listado_movimientos(request):
    pagina = numero_de_pagina(request)
    f = {k: request.GET.get(k, '').strip() for k in ('q', 'tipo', 'ubicacion', 'articulo')}
    if not f['articulo'].isdigit():
        f['articulo'] = ''
    params = {k: v for k, v in f.items() if v}

    error = ''
    datos = {'count': 0, 'results': []}
    try:
        datos = llamar(request, 'GET', 'movimientos/?' + urlencode(dict(params, page=pagina)))
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404 and pagina > 1:
            return redirect(reverse('movimientos:listado')
                            + ('?' + urlencode(params) if params else ''))
        error = errores_api(e)[1]

    tipos, ubicaciones = [], []
    try:
        tipos = opciones_catalogo(request, 'tipos-movimiento')
        ubicaciones = opciones_catalogo(request, 'ubicaciones')
    except SesionVencida:
        raise
    except ApiError as e:
        error = error or errores_api(e)[1]

    articulo_filtro = None                       # chip «Artículo X» cuando se filtra por uno
    if f['articulo']:
        try:
            a = llamar(request, 'GET', 'articulos/%s/' % f['articulo'])
            articulo_filtro = {'num': a['num'], 'identificador': a['identificador'],
                               'nombre': nombre_articulo(a)}
        except SesionVencida:
            raise
        except ApiError:
            articulo_filtro = {'num': f['articulo'], 'identificador': 'Artículo %s' % f['articulo'],
                               'nombre': ''}

    contexto = {
        'movimientos': datos['results'],
        'hay_filtros': bool(params),
        'f': f,
        'tipos': tipos,
        'ubicaciones': ubicaciones,
        'articulo_filtro': articulo_filtro,
        'error_api': error,
    }
    contexto.update(contexto_paginacion(request, datos['count'], pagina))
    return render(request, 'movimientos/listado.html', contexto)


# --- nuevo movimiento ----------------------------------------------------

def _validar(v, articulo):
    """Espejo de lo evidente de la API. Devuelve {campo: mensaje}."""
    errores = {}
    tipo = v['tipo']
    sin_localizar = articulo['estado_operativo']['codigo'] == ESTADO_NOLOC

    if tipo not in TIPOS_MANUALES:
        errores['tipo'] = 'Selecciona el tipo de movimiento.'
    elif sin_localizar and tipo != 'REUB':
        errores['tipo'] = 'El artículo está No localizado: primero se recupera con una reubicación.'
    elif tipo == 'REUB' and not v['ubicacion'] and not v['resguardante']:
        errores['ubicacion'] = 'Especifica una nueva ubicación, un nuevo resguardante, o ambos.'
    elif tipo == 'RETE' and not v['ubicacion']:
        errores['ubicacion'] = 'Indica dónde se reintegra el artículo.'
    elif tipo in ('REPA', 'RETE') and v['ubicacion'] == UBICACION_NOLOC:
        errores['ubicacion'] = 'Para marcar un artículo como No localizado usa una reubicación.'

    if tipo == 'REUB':
        # Una reubicación debe cambiar algo: no se ofrece lo que el artículo ya tiene.
        if 'ubicacion' not in errores and v['ubicacion'] \
                and v['ubicacion'] == (articulo.get('ubicacion') or {}).get('codigo'):
            errores['ubicacion'] = 'El artículo ya está en esa ubicación.'
        if v['resguardante'] and v['resguardante'] == _num_resguardante(articulo):
            errores['resguardante'] = 'Esa persona ya es el resguardante del artículo.'

    if tipo in ('REPA', 'RETE') and v['resguardante']:
        errores['resguardante'] = 'Este movimiento no cambia el resguardante.'

    if _recupera(v, articulo) and v['estado_operativo'] not in ESTADOS_AL_RECUPERAR:
        errores['estado_operativo'] = 'Confirma el estado del artículo: Útil u Obsoleto.'

    if not v['motivo']:
        errores['motivo'] = 'El motivo es obligatorio.'
    if v['fecha']:
        try:
            if datetime.strptime(v['fecha'], '%Y-%m-%d').date() > timezone.localdate():
                errores['fecha'] = 'La fecha no puede ser futura.'
        except ValueError:
            errores['fecha'] = 'La fecha no es válida.'
    return errores


def _num_resguardante(articulo):
    r = articulo.get('resguardante')
    return str(r['num']) if r and r.get('num') is not None else ''


def _recupera(v, articulo):
    """DEC-012: un No localizado que sale de «Sin ubicar» se reconfirma."""
    return (articulo['estado_operativo']['codigo'] == ESTADO_NOLOC and v['tipo'] == 'REUB'
            and v['ubicacion'] not in ('', UBICACION_NOLOC))


def _cuerpo(v, articulo):
    cuerpo = {'tipo': v['tipo'], 'articulo': articulo['num'], 'motivo': v['motivo']}
    for campo in ('ubicacion', 'resguardante', 'fecha'):
        if v[campo]:
            cuerpo[campo] = v[campo]
    if _recupera(v, articulo):
        cuerpo['estado_operativo'] = v['estado_operativo']
    return cuerpo


def _ultimos_articulos(request):
    """Sin búsqueda se sugieren los últimos artículos registrados (la API los
    entrega del más antiguo al más reciente: se pide la última página)."""
    try:
        datos = llamar(request, 'GET', 'articulos/')
        if datos['count'] > TAM_PAGINA:
            ultima = -(-datos['count'] // TAM_PAGINA)
            datos = llamar(request, 'GET', 'articulos/?' + urlencode({'page': ultima}))
    except SesionVencida:
        raise
    except ApiError as e:
        return [], errores_api(e)[1]
    return [dict(a, nombre=nombre_articulo(a)) for a in reversed(datos['results'])], ''


def _buscar_articulos(request, q):
    """Primer paso: buscar el artículo por marbete, folio, serie, marca, etc."""
    if not q:
        return [], ''
    try:
        datos = llamar(request, 'GET', 'articulos/?' + urlencode({'q': q}))
    except SesionVencida:
        raise
    except ApiError as e:
        return [], errores_api(e)[1]
    return [dict(a, nombre=nombre_articulo(a)) for a in datos['results']], ''


def nuevo_movimiento(request):
    if not es_admin(request):
        messages.error(request, 'Tu rol no puede registrar movimientos.')
        return redirect('movimientos:listado')

    num = (request.POST.get('articulo') if request.method == 'POST'
           else request.GET.get('articulo', '')) or ''
    num = num.strip()

    # Paso 1: sin artículo elegido, se busca uno.
    if not num.isdigit():
        q = request.GET.get('q', '').strip()
        if q:
            encontrados, error = _buscar_articulos(request, q)
        else:
            encontrados, error = _ultimos_articulos(request)
        return render(request, 'movimientos/nuevo.html', {
            'paso_busqueda': True, 'q': q, 'encontrados': encontrados, 'error_busqueda': error,
            'buscado': bool(q), 'sugeridos': not q,
        })

    try:
        articulo = llamar(request, 'GET', 'articulos/%s/' % num)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404:
            raise Http404
        raise
    articulo = dict(articulo, nombre=nombre_articulo(articulo))
    sin_localizar = articulo['estado_operativo']['codigo'] == ESTADO_NOLOC

    v = {campo: '' for campo in CAMPOS_MOVIMIENTO}
    v['articulo'] = num
    v['fecha'] = timezone.localdate().isoformat()
    errores, general = {}, ''

    if request.method == 'GET':
        # Atajos desde la ficha (Marcar como No localizado / Recuperar).
        if request.GET.get('tipo') in TIPOS_MANUALES:
            v['tipo'] = request.GET['tipo']
        if request.GET.get('ubicacion'):
            v['ubicacion'] = request.GET['ubicacion'].strip()

    if request.method == 'POST':
        for campo in CAMPOS_MOVIMIENTO:
            v[campo] = request.POST.get(campo, '').strip()
        errores = _validar(v, articulo)
        if not errores:
            try:
                creado = llamar(request, 'POST', 'movimientos/', _cuerpo(v, articulo))
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(e, CAMPOS_MOVIMIENTO)
                errores.update(por_campo)
            else:
                texto = 'Movimiento %s registrado.' % creado['folio']
                if creado.get('requiere_resguardo'):
                    texto += ' Cambió el resguardante: falta el resguardo con las dos firmas.'
                messages.success(request, texto)
                return redirect('movimientos:listado')

    ubicaciones, personal, estados = [], [], []
    try:
        ubicaciones = opciones_catalogo(request, 'ubicaciones', v['ubicacion'], solo_activos=True)
        personal = opciones_personal(request, actual=v['resguardante'])
        estados = [e for e in opciones_catalogo(request, 'estados-operativos')
                   if e['codigo'] in ESTADOS_AL_RECUPERAR]
    except SesionVencida:
        raise
    except ApiError as e:
        general = general or errores_api(e)[1]

    tipos = [{'codigo': 'REUB', 'nombre': 'Reubicación y/o cambio de resguardante'}]
    if not sin_localizar:
        tipos += [{'codigo': 'REPA', 'nombre': 'Envío a reparación'},
                  {'codigo': 'RETE', 'nombre': 'Retorno de reparación'}]
    try:                                   # nombres tal como los publica la API
        nombres = {t['codigo']: t['nombre'] for t in opciones_catalogo(request, 'tipos-movimiento')}
        for t in tipos:
            t['nombre'] = nombres.get(t['codigo'], t['nombre'])
    except SesionVencida:
        raise
    except ApiError:
        pass

    return render(request, 'movimientos/nuevo.html', {
        'paso_busqueda': False, 'articulo': articulo, 'sin_localizar': sin_localizar,
        'errores': errores, 'v': v, 'general': general,
        'tipos': tipos, 'ubicaciones': ubicaciones, 'personal': personal, 'estados': estados,
        'ubicacion_noloc': UBICACION_NOLOC,
        'ubicacion_actual': (articulo.get('ubicacion') or {}).get('codigo', ''),
        'resguardante_actual': _num_resguardante(articulo), 'hoy': timezone.localdate().isoformat(),
    })
