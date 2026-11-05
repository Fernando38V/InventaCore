"""Resguardos (RF-18, DEC-007, DEC-016).

Un resguardo reúne una o varias asignaciones pendientes del mismo
resguardante en un solo documento con dos firmas (la Contadora y el
resguardante). La API arma el PDF, lo guarda y lo entrega igual en cada
reimpresión. Emitir es solo del Administrador; Consulta ve y descarga
(DEC-001).

Vive dentro de Movimientos (/movimientos/resguardos/) porque cada resguardo
documenta movimientos, y así Consulta sigue viendo solo los cuatro módulos
de DEC-019.
"""
from collections import OrderedDict
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from client.api import ApiError, SesionVencida, descargar, llamar
from client.utils import (
    contexto_paginacion, errores_api, es_admin, listar_todo, numero_de_pagina)

FOLIO_RESGUARDO = r'RES-\d+'


def _agrupar(movimientos):
    """Asignaciones pendientes agrupadas por resguardante (orden por nombre)."""
    grupos = OrderedDict()
    for m in movimientos:
        p = m.get('personal_asigna') or {}
        if p.get('num') is None:
            continue
        g = grupos.setdefault(p['num'], {'persona': p, 'movimientos': []})
        g['movimientos'].append(m)
    return sorted(grupos.values(), key=lambda g: (g['persona'].get('nombre') or '').lower())


def resguardos(request):
    """Dos pestañas: asignaciones pendientes de resguardo y resguardos emitidos."""
    vista = request.GET.get('vista', '')
    contexto = {'error_api': ''}

    try:
        pendientes = listar_todo(request, 'resguardos/pendientes')
    except SesionVencida:
        raise
    except ApiError as e:
        pendientes = []
        contexto['error_api'] = errores_api(e)[1]
    if vista not in ('pendientes', 'emitidos'):
        vista = 'pendientes' if pendientes else 'emitidos'

    contexto.update({'vista': vista, 'total_pendientes': len(pendientes),
                     'grupos': _agrupar(pendientes),
                     'resguardo_nuevo': request.session.pop('resguardo_nuevo', '')})

    if vista == 'emitidos':
        q = request.GET.get('q', '').strip()
        pagina = numero_de_pagina(request)
        params = {'page': pagina}
        if q:
            params['q'] = q
        try:
            datos = llamar(request, 'GET', 'resguardos/?' + urlencode(params))
        except SesionVencida:
            raise
        except ApiError as e:
            datos = {'count': 0, 'results': []}
            contexto['error_api'] = errores_api(e)[1]
        contexto.update({'emitidos': datos['results'], 'q': q})
        contexto.update(contexto_paginacion(request, datos['count'], pagina))

    return render(request, 'movimientos/resguardos.html', contexto)


@require_POST
def emitir_resguardo(request):
    """POST /resguardos/ con el resguardante y las asignaciones elegidas."""
    url_pendientes = reverse('movimientos:resguardos') + '?vista=pendientes'
    if not es_admin(request):
        messages.error(request, 'Solo el Administrador emite resguardos.')
        return redirect(url_pendientes)

    resguardante = request.POST.get('resguardante', '').strip()
    folios = [f.strip() for f in request.POST.getlist('movimientos') if f.strip()]
    if not resguardante.isdigit():
        messages.error(request, 'Falta el resguardante.')
        return redirect(url_pendientes)
    if not folios:
        messages.error(request, 'Selecciona al menos una asignación para el resguardo.')
        return redirect(url_pendientes)

    try:
        r = llamar(request, 'POST', 'resguardos/',
                   {'resguardante': int(resguardante), 'movimientos': folios})
    except SesionVencida:
        raise
    except ApiError as e:
        datos = e.datos if isinstance(e.datos, dict) else {}
        mensaje = ' '.join(' '.join(map(str, v)) if isinstance(v, list) else str(v)
                           for v in datos.values()) or errores_api(e)[1]
        messages.error(request, 'No se emitió el resguardo. ' + mensaje)
        return redirect(url_pendientes)

    messages.success(request, 'Se emitió el resguardo %s de %s con %d bien%s. Imprímelo para '
                     'recabar las dos firmas.' % (
                         r['folio'], r['resguardante']['nombre'], r['numero_bienes'],
                         '' if r['numero_bienes'] == 1 else 'es'))
    request.session['resguardo_nuevo'] = r['folio']
    return redirect(reverse('movimientos:resguardos') + '?vista=emitidos')


def pdf_resguardo(request, folio):
    """El PDF emitido, tal cual lo guardó la API. ?descargar=1 lo baja como archivo."""
    try:
        contenido = descargar(request, 'resguardos/%s/pdf/' % folio)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 409:
            mensaje = ('El archivo del resguardo %s no coincide con el que se emitió o ya no está '
                       'en el servidor. Avisa al administrador del sistema.' % folio)
        elif e.status == 404:
            mensaje = 'No existe el resguardo %s.' % folio
        else:
            mensaje = errores_api(e)[1]
        messages.error(request, mensaje)
        return redirect(reverse('movimientos:resguardos') + '?vista=emitidos')
    respuesta = HttpResponse(contenido, content_type='application/pdf')
    modo = 'attachment' if request.GET.get('descargar') else 'inline'
    respuesta['Content-Disposition'] = '%s; filename="%s.pdf"' % (modo, folio)
    return respuesta
