"""Foto del artículo (PEND-027): ver, agregar o cambiar y quitar desde la ficha.

La imagen vive en la base de datos de la API. El navegador no puede mandar el token
en un <img>, así que el client la pide a la API y la entrega por su propia ruta
(`equipos:foto`). La API vuelve a validar y a reducir todo lo que llega.
"""
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from client.api import ApiError, SesionVencida, descargar, enviar_formulario
from client.utils import errores_api, es_admin

MAX_BYTES = 5 * 1024 * 1024     # el mismo tope que la API


def foto_equipo(request, num):
    """GET /articulos/detalle/<num>/foto/ -> la imagen del artículo (404 si no tiene)."""
    try:
        contenido = descargar(request, 'articulos/%d/foto/' % num)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404:
            raise Http404
        return HttpResponse(status=502)
    respuesta = HttpResponse(contenido, content_type='image/jpeg')
    respuesta['Cache-Control'] = 'private, no-cache'     # al cambiarla se ve la nueva
    respuesta['X-Content-Type-Options'] = 'nosniff'
    return respuesta


def _solo_admin(request, num):
    if es_admin(request):
        return None
    messages.error(request, 'Solo el Administrador puede hacer esto.')
    return redirect('equipos:detalle', num=num)


@require_POST
def foto_subir(request, num):
    """Agrega o reemplaza la foto. El motivo es opcional la primera vez y lo exige la API
    al reemplazar (DEC-004)."""
    bloqueado = _solo_admin(request, num)
    if bloqueado:
        return bloqueado
    archivo = request.FILES.get('foto')
    if archivo is None:
        messages.error(request, 'Elige una foto del artículo.')
        return redirect('equipos:detalle', num=num)
    if archivo.size > MAX_BYTES:
        messages.error(request, 'La foto pesa más de 5 MB.')
        return redirect('equipos:detalle', num=num)
    motivo = request.POST.get('motivo', '').strip()
    try:
        enviar_formulario(request, 'POST', 'articulos/%d/foto/' % num, {'motivo': motivo},
                          (archivo.name, archivo.read()), 'foto')
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
    else:
        messages.success(request, 'Foto guardada.')
    return redirect('equipos:detalle', num=num)


@require_POST
def foto_quitar(request, num):
    bloqueado = _solo_admin(request, num)
    if bloqueado:
        return bloqueado
    motivo = request.POST.get('motivo', '').strip()
    if not motivo:
        messages.error(request, 'Indica el motivo para quitar la foto.')
        return redirect('equipos:detalle', num=num)
    try:
        enviar_formulario(request, 'DELETE', 'articulos/%d/foto/' % num, {'motivo': motivo})
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
    else:
        messages.success(request, 'Foto quitada.')
    return redirect('equipos:detalle', num=num)
