"""Escáner de QR y búsqueda rápida (RF-20, RF-23). Cualquier rol con sesión.

La cámara y la lectura del QR ocurren en el navegador (html5-qrcode, guardada en
static/vendor). Al leer un código el navegador solo manda el texto a `resolver`;
aquí se valida el formato y se confirma con la API que el artículo existe antes
de abrir su ficha. No se guarda nada del escaneo.
"""
from django.contrib import messages
from django.shortcuts import redirect, render

from client.api import ApiError, SesionVencida, llamar
from client.utils import errores_api

from . import qr


def escanear(request):
    return render(request, 'equipos/escanear.html')


def resolver(request):
    num = qr.leer(request.GET.get('codigo', ''))
    if num is None:
        messages.error(request, 'Ese código no es de InventaCore. Prueba con otro o busca el '
                                'artículo por su marbete o folio.')
        return redirect('equipos:escanear')
    try:
        llamar(request, 'GET', 'articulos/%d/' % num)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404:
            messages.error(request, 'No existe un artículo con ese código.')
        else:
            messages.error(request, errores_api(e)[1])
        return redirect('equipos:escanear')
    return redirect('equipos:detalle', num=num)
