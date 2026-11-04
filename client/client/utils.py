"""Ayudas compartidas por las pantallas de catálogos y de personal."""
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme

from client.api import llamar

# La API pagina de 10 en 10 y no acepta otro tamaño (PAGE_SIZE en
# api/api/settings.py). Si Adad lo cambia, hay que cambiarlo aquí también.
TAM_PAGINA = 10


def es_admin(request):
    """Solo decide qué se muestra. La seguridad real la valida la API (403)."""
    return (request.session.get('usuario') or {}).get('rol') == 'ADMIN'


def numero_de_pagina(request):
    texto = request.GET.get('page', '')
    if texto.isascii() and texto.isdigit() and int(texto) > 0:
        return int(texto)
    return 1


def listar_todo(request, ruta, **filtros):
    """Recorre todas las páginas de un listado de la API y devuelve la lista
    completa. Sirve para llenar selects (categorías, departamentos, personal)."""
    resultados, pagina = [], 1
    while True:
        consulta = urlencode(dict(filtros, page=pagina))
        datos = llamar(request, 'GET', '%s/?%s' % (ruta, consulta))
        if isinstance(datos, list):     # catálogos fijos: lista simple, sin páginas
            return datos
        resultados.extend(datos['results'])
        if not datos.get('next'):
            return resultados
        pagina += 1


def errores_api(error, campos=()):
    """Separa un ApiError en ({campo: mensaje}, mensaje_general).

    La API responde {campo: mensaje} en los 400 (api/api/errores.py) y
    {'detail': ...} en 403/404. Todo lo que no sea un campo del formulario
    pasa al mensaje general. Un 500 llega como {'detalle': 'Error 500...'}.
    """
    datos = error.datos if isinstance(error.datos, dict) else {}
    por_campo, general = {}, []
    for clave, valor in datos.items():
        if clave in campos:
            por_campo[clave] = str(valor)
        else:
            general.append(str(valor))
    if not por_campo and not general:
        general.append('No se pudo completar la operación.')
    return por_campo, ' '.join(general)


def contexto_paginacion(request, total, pagina):
    """Variables que usa el bloque de paginación de las plantillas, con el
    mismo nombre que en equipos y movimientos. La API ya entregó la página
    pedida; Paginator solo calcula los números de página."""
    paginator = Paginator(range(total), TAM_PAGINA)
    page_obj = paginator.get_page(pagina)
    params = request.GET.copy()
    params.pop('page', None)
    filtros_qs = params.urlencode()
    return {
        'page_obj': page_obj,
        'total': total,
        'qs_prefijo': '?{}&'.format(filtros_qs) if filtros_qs else '?',
        'rango_paginas': list(paginator.get_elided_page_range(
            page_obj.number, on_each_side=1, on_ends=1)),
        'pagina_elipsis': paginator.ELLIPSIS,
    }


def destino_seguro(request, destino, por_defecto):
    """Evita redirigir a otro sitio con un campo 'volver' manipulado."""
    if destino and url_has_allowed_host_and_scheme(
            destino, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return destino
    return por_defecto
