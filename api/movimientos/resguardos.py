"""Emisión y consulta de resguardos (RF-18, DEC-007, DEC-016).

Un resguardo documenta una o varias asignaciones (movimientos que lo
requieren) del mismo resguardante. El PDF se guarda en RESGUARDOS_DIR sin
sobrescribir nada y la reimpresión entrega el archivo original.
"""
import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from auditoria.servicios import datos_de, registrar
from catalogos.folios import siguiente_folio_resguardo
from movimientos.models import Movimiento, Resguardo, ResguardoDetalle
from movimientos.resguardo_pdf import generar_pdf
from personal.models import Personal


class ArchivoDeResguardoAlterado(Exception):
    """El PDF guardado ya no coincide con su hash, o no existe."""


def carpeta():
    return Path(getattr(settings, 'RESGUARDOS_DIR', Path(settings.BASE_DIR) / 'resguardos_pdf'))


def nombre_contadora():
    nombre = (getattr(settings, 'CONTADORA_NOMBRE', '') or '').strip()
    if not nombre:
        raise ValidationError({'detalle': (
            'Falta configurar el nombre de la Contadora (CONTADORA_NOMBRE en settings.py).')})
    return nombre


def pendientes(resguardante=None):
    """Movimientos que requieren resguardo y todavía no están en ninguno."""
    consulta = Movimiento.objects.filter(
        requiere_resguardo=True, detalle_resguardo__isnull=True).select_related(
        'articulo', 'tipo_movimiento', 'resguardante_nuevo', 'ubicacion_destino')
    if resguardante is not None:
        consulta = consulta.filter(resguardante_nuevo_id=resguardante)
    return consulta.order_by('fecha_movimiento', 'folio')


@transaction.atomic
def emitir_resguardo(resguardante_num, folios, usuario):
    if not folios:
        raise ValidationError({'movimientos': 'Seleccione al menos un movimiento.'})
    if len(set(folios)) != len(folios):
        raise ValidationError({'movimientos': 'Hay movimientos repetidos.'})
    try:
        resguardante = Personal.objects.select_related('departamento').get(pk=resguardante_num)
    except (Personal.DoesNotExist, ValueError, TypeError):
        raise ValidationError({'resguardante': 'El resguardante no existe.'})
    contadora = nombre_contadora()

    movimientos = list(Movimiento.objects.select_for_update().select_related(
        'articulo__tipo_articulo__categoria', 'articulo__origen').filter(folio__in=folios))
    por_folio = {m.folio: m for m in movimientos}
    errores = []
    for folio in folios:
        m = por_folio.get(folio)
        if m is None:
            errores.append('%s no existe.' % folio)
        elif not m.requiere_resguardo:
            errores.append('%s no requiere resguardo.' % folio)
        elif m.resguardante_nuevo_id != resguardante.pk:
            errores.append('%s es una asignación de otra persona.' % folio)
        elif ResguardoDetalle.objects.filter(movimiento=m).exists():
            errores.append('%s ya está documentado en otro resguardo.' % folio)
        elif m.articulo.resguardante_id != resguardante.pk:
            errores.append('%s: %s ya no está a cargo de este resguardante.' % (
                folio, m.articulo.identificador))
    if errores:
        raise ValidationError({'movimientos': errores})

    ordenados = [por_folio[f] for f in folios]
    articulos = [m.articulo for m in ordenados]
    folio = siguiente_folio_resguardo()
    ahora = timezone.now()
    resguardo = Resguardo(folio=folio, fecha_emision=ahora, resguardante=resguardante,
                          usuario_emisor=usuario, ruta_pdf='%s.pdf' % folio, hash_pdf='')
    contenido = generar_pdf(resguardo, resguardante, articulos, contadora,
                            getattr(settings, 'INSTITUCION_NOMBRE', 'CONALEP Plantel Tijuana II'))
    resguardo.hash_pdf = hashlib.sha256(contenido).hexdigest()
    resguardo.save()
    for m in ordenados:
        ResguardoDetalle.objects.create(resguardo=resguardo, movimiento=m)

    destino = carpeta()
    destino.mkdir(parents=True, exist_ok=True)
    try:
        with open(destino / resguardo.ruta_pdf, 'xb') as archivo:  # nunca sobrescribe
            archivo.write(contenido)
    except FileExistsError:
        raise ValidationError({'detalle': 'Ya existe un archivo para %s; no se sobrescribe.' % folio})

    registrar(usuario, 'resguardos', 'INSERT', resguardo,
              nuevo=dict(datos_de(resguardo), movimientos=folios))
    return resguardo


def contenido_original(resguardo):
    """Bytes del PDF emitido, verificados contra su hash."""
    ruta = carpeta() / resguardo.ruta_pdf
    try:
        datos = ruta.read_bytes()
    except OSError:
        raise ArchivoDeResguardoAlterado('El archivo del resguardo no se encuentra en el servidor.')
    if hashlib.sha256(datos).hexdigest() != resguardo.hash_pdf:
        raise ArchivoDeResguardoAlterado('El archivo del resguardo no coincide con el emitido.')
    return datos
