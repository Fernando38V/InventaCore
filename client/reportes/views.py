"""Dashboard y reportes mínimos (DEC-020). Solo lectura: Administrador y Consulta.

Todo sale de la API (api/reportes/views.py):
- GET /dashboard/                      totales para el tablero
- GET /reportes/inventario/            inventario filtrable, sin paginar; ?formato=xlsx
- GET /reportes/resguardante/<num>/    artículos que tiene hoy una persona; ?formato=xlsx
- GET /reportes/historial/<num>/       artículo, todos sus movimientos y sus resguardos
El Excel lleva las columnas de DEC-018 y lo arma la API.
"""
from datetime import date
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from client.api import ApiError, SesionVencida, descargar, llamar
from client.inventario import nombre_articulo, opciones_catalogo
from client.utils import errores_api, listar_todo

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
FILTROS_INVENTARIO = ('ubicacion', 'resguardante', 'estado_operativo', 'estado_registro')
MAX_FILAS = 200          # en pantalla; el Excel lleva todo
MAX_UBICACIONES = 8      # en el tablero; el resto se suma en "otras"


# --- dashboard -----------------------------------------------------------

def _con_ancho(filas):
    """Agrega `ancho` (0-100) a cada fila para la barra, respecto al mayor."""
    mayor = max([f['total'] for f in filas] or [0])
    for f in filas:
        f['ancho'] = round(f['total'] * 100 / mayor) if mayor else 0
    return filas


def dashboard(request):
    try:
        d = llamar(request, 'GET', 'dashboard/')
    except SesionVencida:
        raise
    except ApiError as e:
        return render(request, 'reportes/dashboard.html', {'error_api': errores_api(e)[1]})

    ubicaciones = d['por_ubicacion']
    otras = ubicaciones[MAX_UBICACIONES:]
    pendientes = d['pendientes_de_datos']
    for a in pendientes['articulos']:
        a['nombre'] = nombre_articulo(a)
    nolocalizados = next((e['total'] for e in d['por_estado_operativo']
                          if e['codigo'] == 'NOLOC'), 0)
    return render(request, 'reportes/dashboard.html', {
        'd': d,
        'estado_operativo': _con_ancho(d['por_estado_operativo']),
        'estado_registro': _con_ancho(d['por_estado_registro']),
        'ubicaciones': _con_ancho(ubicaciones[:MAX_UBICACIONES]),
        'otras_ubicaciones': {'cuantas': len(otras), 'total': sum(u['total'] for u in otras)},
        'pendientes': pendientes,
        'nolocalizados': nolocalizados,
    })


# --- reportes ------------------------------------------------------------

def _filtros(request):
    return {k: request.GET.get(k, '').strip() for k in FILTROS_INVENTARIO}


def _excel(request, ruta, nombre):
    try:
        contenido = descargar(request, ruta)
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, 'No se pudo generar el Excel: ' + errores_api(e)[1])
        return None
    respuesta = HttpResponse(contenido, content_type=XLSX)
    respuesta['Content-Disposition'] = 'attachment; filename="%s"' % nombre
    return respuesta


def listado_reportes(request):
    """Tres reportes en pestañas: inventario, por resguardante e historial."""
    vista = request.GET.get('vista', 'inventario')
    if vista not in ('inventario', 'resguardante', 'historial'):
        vista = 'inventario'
    contexto = {'vista': vista, 'error_api': ''}
    try:
        if vista == 'inventario':
            contexto.update(_reporte_inventario(request))
        elif vista == 'resguardante':
            contexto.update(_reporte_resguardante(request))
        else:
            contexto.update(_reporte_historial(request))
    except SesionVencida:
        raise
    except ApiError as e:
        contexto['error_api'] = errores_api(e)[1]
    return render(request, 'reportes/reportes.html', contexto)


def _reporte_inventario(request):
    f = _filtros(request)
    params = {k: v for k, v in f.items() if v}
    contexto = {
        'f': f,
        'ubicaciones': opciones_catalogo(request, 'ubicaciones'),
        'personal': opciones_personal_todos(request),
        'estados_operativos': opciones_catalogo(request, 'estados-operativos'),
        'estados_registro': opciones_catalogo(request, 'estados-registro'),
        'generado': 'ver' in request.GET,
    }
    if contexto['generado']:
        datos = llamar(request, 'GET', 'reportes/inventario/?' + urlencode(params))
        contexto.update(_resultados(datos))
    return contexto


def opciones_personal_todos(request):
    """Para filtrar sirve también el personal inactivo: aún puede tener bienes."""
    opciones = [{'valor': str(p['num']),
                 'texto': '%s — %s%s' % (p['numero_empleado'], p['nombre_completo'],
                                          '' if p['activo'] else ' (inactivo)')}
                for p in listar_todo(request, 'personal')]
    return sorted(opciones, key=lambda o: o['texto'].lower())


def _resultados(datos):
    filas = datos['resultados']
    for a in filas[:MAX_FILAS]:
        a['nombre'] = nombre_articulo(a)
    return {'total': datos['total'], 'articulos': filas[:MAX_FILAS],
            'recortado': len(filas) > MAX_FILAS, 'max_filas': MAX_FILAS}


def _reporte_resguardante(request):
    num = request.GET.get('persona', '').strip()
    contexto = {'personal': opciones_personal_todos(request), 'persona': num}
    if num.isdigit():
        datos = llamar(request, 'GET', 'reportes/resguardante/%s/' % num)
        contexto['resguardante'] = datos['resguardante']
        contexto.update(_resultados(datos))
    return contexto


def _reporte_historial(request):
    q = request.GET.get('q', '').strip()
    num = request.GET.get('articulo', '').strip()
    contexto = {'q': q}
    if num.isdigit():
        datos = llamar(request, 'GET', 'reportes/historial/%s/' % num)
        datos['articulo']['nombre'] = nombre_articulo(datos['articulo'])
        contexto['historial'] = datos
    elif q:
        datos = llamar(request, 'GET', 'articulos/?' + urlencode({'q': q}))
        for a in datos['results']:
            a['nombre'] = nombre_articulo(a)
        contexto.update({'coincidencias': datos['results'], 'total_coincidencias': datos['count']})
    return contexto


def excel_inventario(request):
    params = {k: v for k, v in _filtros(request).items() if v}
    respuesta = _excel(request, 'reportes/inventario/?' + urlencode(dict(params, formato='xlsx')),
                       'inventario_%s.xlsx' % date.today().strftime('%Y%m%d'))
    return respuesta or redirect(reverse('reportes:listado') + '?' + urlencode(dict(params, ver=1)))


def excel_resguardante(request, num):
    respuesta = _excel(request, 'reportes/resguardante/%d/?formato=xlsx' % num,
                       'articulos_resguardante_%d.xlsx' % num)
    return respuesta or redirect(reverse('reportes:listado') + '?vista=resguardante&persona=%d' % num)
