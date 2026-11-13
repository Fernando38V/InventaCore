"""Bitácora de auditoría (RF-21). Solo Administrador y solo lectura.

Todo sale de la API (api/auditoria/views.py, contrato v14):
- GET /bitacora/?page=&q=&usuario=&modulo=&accion=&fecha_desde=&fecha_hasta=
               &tabla_afectada=&registro_id=
  paginada de 10 en 10, la más reciente primero. Un filtro inválido responde
  400 con {campo: mensaje}.

La API decide los permisos (Consulta recibe 403); el middleware ya bloquea
/auditoria/ para Consulta. Aquí no se crea, edita ni borra nada.
"""
import json
from datetime import date
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from client.api import ApiError, SesionVencida, llamar
from client.utils import contexto_paginacion, errores_api, listar_todo, numero_de_pagina

# Valores que la API escribe hoy en `modulo` (registrar(...) y `modulo = ...`
# de las vistas de api/). La API no publica la lista; si Adad agrega otro
# módulo hay que añadirlo aquí para que aparezca en el filtro.
MODULOS = [
    ('articulos', 'Artículos'),
    ('movimientos', 'Movimientos'),
    ('resguardos', 'Resguardos'),
    ('carga_masiva', 'Carga masiva'),
    ('personal', 'Personal'),
    ('departamentos', 'Departamentos'),
    ('categorias', 'Categorías'),
    ('tipos_articulo', 'Tipos de artículo'),
    ('ubicaciones', 'Ubicaciones'),
    ('usuarios', 'Usuarios'),
]
NOMBRE_MODULO = dict(MODULOS)

ACCIONES = [('INSERT', 'Alta'), ('UPDATE', 'Modificación'), ('DELETE', 'Baja lógica')]
TONO_ACCION = {'INSERT': 'verde', 'UPDATE': 'azul', 'DELETE': 'rojo'}

TABLAS = {
    'articulo': 'Artículo', 'movimiento': 'Movimiento', 'resguardo': 'Resguardo',
    'personal': 'Personal', 'departamento': 'Departamento', 'categoria': 'Categoría',
    'tipo_articulo': 'Tipo de artículo', 'ubicacion': 'Ubicación', 'usuario': 'Usuario',
}

FILTROS = ('q', 'usuario', 'modulo', 'accion', 'fecha_desde', 'fecha_hasta',
           'tabla_afectada', 'registro_id')
CAMPOS_FECHA = ('fecha_desde', 'fecha_hasta')


def _filtros(request):
    f = {k: request.GET.get(k, '').strip() for k in FILTROS}
    if f['accion'] not in dict(ACCIONES):
        f['accion'] = ''
    # Las fechas inválidas no se mandan a la API: el <input type="date"> ya
    # obliga el formato y así no se pierde el resto del listado.
    # Tampoco se aceptan fechas posteriores a hoy (no puede haber registros).
    hoy = timezone.localdate()
    for campo in CAMPOS_FECHA:
        try:
            if date.fromisoformat(f[campo]) > hoy:
                f[campo] = ''
        except ValueError:
            f[campo] = ''
    # El historial de un registro necesita las dos claves.
    if not (f['tabla_afectada'] and f['registro_id']):
        f['tabla_afectada'] = f['registro_id'] = ''
    return f, {k: v for k, v in f.items() if v}


# --- presentación de cada fila ---------------------------------------------

def _texto(valor):
    if valor is None or valor == '':
        return '—'
    if valor is True:
        return 'Sí'
    if valor is False:
        return 'No'
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    return str(valor)


def _etiqueta(campo):
    # La API guarda las llaves foráneas con su nombre de columna (tipo_articulo_id).
    if campo.endswith('_id') and campo != 'registro_id':
        campo = campo[:-3]
    return campo.replace('_', ' ').capitalize()


def _cambios(anterior, nuevo):
    """Lista de {campo, antes, despues} para la tabla de detalle. Si algún
    valor no llegó como objeto JSON (registro viejo), se muestra el texto tal
    cual en una sola fila."""
    if not isinstance(anterior, (dict, type(None))) or not isinstance(nuevo, (dict, type(None))):
        return [{'campo': 'Valor', 'antes': _texto(anterior), 'despues': _texto(nuevo)}]
    anterior, nuevo = anterior or {}, nuevo or {}
    campos = list(nuevo) + [c for c in anterior if c not in nuevo]
    return [{'campo': _etiqueta(c),
             'antes': _texto(anterior.get(c)) if c in anterior else '',
             'despues': _texto(nuevo.get(c)) if c in nuevo else ''}
            for c in campos]


def _enlace(tabla, registro):
    """Adónde llevar desde la fila, si el registro tiene pantalla propia."""
    if tabla == 'articulo' and registro.isdigit():
        return reverse('equipos:detalle', args=[int(registro)]), 'Ver ficha'
    if tabla == 'movimiento':
        return reverse('movimientos:listado') + '?' + urlencode({'q': registro}), 'Ver movimiento'
    if tabla == 'resguardo' and registro.startswith('RES-'):
        return reverse('movimientos:pdf_resguardo', args=[registro]), 'Ver PDF'
    return '', ''


def _fila(b):
    fecha = parse_datetime(b.get('fecha_hora') or '')
    if fecha is not None and timezone.is_aware(fecha):
        fecha = timezone.localtime(fecha)
    usuario = b.get('usuario') or {}
    tabla, registro = b.get('tabla_afectada') or '', str(b.get('registro_id') or '')
    url, texto_enlace = _enlace(tabla, registro)
    anterior, nuevo = b.get('valor_anterior'), b.get('valor_nuevo')
    return {
        'num': b.get('num'),
        'fecha': fecha,
        'fecha_texto': b.get('fecha_hora') if fecha is None else '',
        'usuario': usuario.get('username', ''),
        'usuario_nombre': usuario.get('nombre', ''),
        'modulo': NOMBRE_MODULO.get(b.get('modulo'), b.get('modulo') or ''),
        'accion': b.get('accion'),
        'accion_nombre': b.get('accion_nombre') or b.get('accion') or '',
        'tono': TONO_ACCION.get(b.get('accion'), 'gris'),
        'tabla': TABLAS.get(tabla, tabla),
        'registro': registro,
        'motivo': b.get('motivo') or '',
        'cambios': _cambios(anterior, nuevo) if (anterior or nuevo) else [],
        'es_alta': anterior is None,
        'url': url,
        'texto_enlace': texto_enlace,
        'url_historial': reverse('auditoria:listado') + '?' + urlencode(
            {'tabla_afectada': tabla, 'registro_id': registro}),
    }


def _articulo_del_historial(request, f):
    """Datos para identificar el artículo cuyo historial se está viendo: marbete o
    folio interno (no el número interno), descripción y enlace a la ficha. Si la
    API no lo entrega, el encabezado cae al número."""
    if f['tabla_afectada'] != 'articulo' or not f['registro_id'].isdigit():
        return {}
    try:
        a = llamar(request, 'GET', 'articulos/%s/' % f['registro_id'])
    except SesionVencida:
        raise
    except ApiError:
        return {}
    marbete = a.get('marbete_oficial')
    return {
        'descripcion': a.get('descripcion') or '',
        'identificador': ('Marbete %s' % marbete) if marbete
                         else ('Folio interno %s' % a.get('folio_interno', '')),
        'url': reverse('equipos:detalle', args=[int(f['registro_id'])]),
    }


# --- listado -----------------------------------------------------------------

def listado_auditoria(request):
    pagina = numero_de_pagina(request)
    f, params = _filtros(request)
    error, errores = '', {}
    datos = {'count': 0, 'results': []}
    try:
        datos = llamar(request, 'GET', 'bitacora/?' + urlencode(dict(params, page=pagina)))
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404 and pagina > 1:
            return redirect(reverse('auditoria:listado')
                            + ('?' + urlencode(params) if params else ''))
        errores, error = errores_api(e, FILTROS)
        if errores and not error:
            error = 'Revisa los filtros: ' + ' '.join(errores.values())

    usuarios = []
    try:
        usuarios = listar_todo(request, 'usuarios')
    except SesionVencida:
        raise
    except ApiError:
        pass            # sin la lista, el filtro por usuario simplemente no aparece

    contexto = {
        'filas': [_fila(b) for b in datos['results']],
        'f': f,
        'modulos': MODULOS,
        'acciones': ACCIONES,
        'usuarios': usuarios,
        'historial': dict({'tabla': TABLAS.get(f['tabla_afectada'], f['tabla_afectada']),
                           'registro': f['registro_id']},
                          **_articulo_del_historial(request, f)) if f['registro_id'] else None,
        'hoy': timezone.localdate().isoformat(),
        'hay_filtros': bool(params),
        'error_api': error,
    }
    contexto.update(contexto_paginacion(request, datos['count'], pagina))
    return render(request, 'auditoria/listado.html', contexto)
