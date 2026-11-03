"""Alta de movimientos (REUB, REPA y RETE). Todo en una transacción: se bloquea
el artículo, se valida contra su estado actual, se actualiza, se crea el
movimiento y se escribe la bitácora.

ALTA se crea sola al registrar el artículo. No existe el movimiento BAJA ni el
estado "Autorizado para baja" (DEC-006, DEC-012): Obsoleto se marca desde la
ficha, sin movimiento (DEC-013).

Regla propia, no escrita en DECISIONES.md: REPA y RETE van en pareja (no hay
RETE sin una REPA abierta ni dos REPA seguidas). El estado operativo no cambia
con la reparación (no existe "En reparación").
"""
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from articulos.models import Articulo
from auditoria.servicios import datos_de, registrar
from catalogos.folios import siguiente_folio_movimiento
from catalogos.models import EstadoOperativo, Ubicacion
from movimientos.models import Movimiento
from personal.models import Personal

UBICACION_NO_LOCALIZADO = 'UBI-NOLOC'
TIPOS_MANUALES = ('REUB', 'REPA', 'RETE')
ESTADOS_AL_RECUPERAR = ('UTIL', 'OBS')


def _fecha_hora(fecha):
    """Hoy: el momento actual. Fecha pasada: mediodía local (solo se pide el día)."""
    if fecha is None or fecha == timezone.localdate():
        return timezone.now()
    return timezone.make_aware(datetime.combine(fecha, time(12, 0)))


def _ubicacion(valor):
    if not valor:
        return None
    try:
        ubicacion = Ubicacion.objects.get(pk=valor)
    except Ubicacion.DoesNotExist:
        raise ValidationError({'ubicacion': 'La ubicación no existe.'})
    if not ubicacion.activo:
        raise ValidationError({'ubicacion': 'La ubicación está desactivada.'})
    return ubicacion


def _resguardante(valor):
    if not valor:
        return None
    try:
        personal = Personal.objects.get(pk=int(valor))
    except (Personal.DoesNotExist, ValueError):
        raise ValidationError({'resguardante': 'El resguardante no existe.'})
    if not personal.activo:
        raise ValidationError({'resguardante': 'El resguardante está dado de baja.'})
    return personal


@transaction.atomic
def registrar_movimiento(datos, usuario):
    tipo = datos['tipo']
    if tipo.pk not in TIPOS_MANUALES:
        raise ValidationError({'tipo': 'Selecciona el tipo de movimiento.'})
    articulo = Articulo.objects.select_for_update().get(pk=datos['articulo'].pk)

    ubicacion_pedida = _ubicacion(datos.get('ubicacion'))
    resguardante_pedido = _resguardante(datos.get('resguardante'))
    estado_pedido = datos.get('estado_operativo') or None
    sin_localizar = articulo.estado_operativo_id == 'NOLOC'

    destino = ubicacion_pedida or articulo.ubicacion
    resguardante_nuevo = resguardante_pedido or articulo.resguardante
    estado_nuevo = articulo.estado_operativo_id

    if tipo.pk == 'REUB':
        cambia_ubicacion = destino.pk != articulo.ubicacion_id
        cambia_persona = resguardante_nuevo.pk != articulo.resguardante_id
        if not (cambia_ubicacion or cambia_persona):
            raise ValidationError({'ubicacion': (
                'Especifica una nueva ubicación, un nuevo resguardante, o ambos.')})
        if destino.pk == UBICACION_NO_LOCALIZADO:
            estado_nuevo = 'NOLOC'  # la pérdida se registra con REUB (DEC-012)
        elif sin_localizar:
            # Recuperación: se elige la ubicación real y se reconfirma el estado.
            estado_nuevo = estado_pedido or 'UTIL'
            if estado_nuevo not in ESTADOS_AL_RECUPERAR:
                raise ValidationError({'estado_operativo': (
                    'Al recuperar el artículo elige su estado: Útil u Obsoleto.')})
        if estado_pedido and not (sin_localizar and destino.pk != UBICACION_NO_LOCALIZADO):
            raise ValidationError({'estado_operativo': (
                'El estado solo se indica al recuperar un artículo No localizado.')})
    else:
        if resguardante_pedido and resguardante_pedido.pk != articulo.resguardante_id:
            raise ValidationError({'resguardante': 'Este movimiento no cambia el resguardante.'})
        if estado_pedido:
            raise ValidationError({'estado_operativo': 'Este movimiento no cambia el estado.'})
        if sin_localizar:
            raise ValidationError({'articulo': (
                'El artículo está No localizado: primero se recupera con una reubicación.')})
        ultimo = (Movimiento.objects.filter(
            articulo=articulo, tipo_movimiento__in=['REPA', 'RETE'])
            .order_by('-fecha_movimiento', '-folio').first())
        en_reparacion = ultimo is not None and ultimo.tipo_movimiento_id == 'REPA'
        if tipo.pk == 'REPA':
            if en_reparacion:
                raise ValidationError({'articulo': 'El artículo ya está en reparación.'})
        elif tipo.pk == 'RETE':
            if not en_reparacion:
                raise ValidationError({'articulo': 'El artículo no está en reparación.'})
            if ubicacion_pedida is None:
                raise ValidationError({'ubicacion': 'Indica dónde se reintegra el artículo.'})
        if tipo.pk in ('REPA', 'RETE') and destino.pk == UBICACION_NO_LOCALIZADO:
            raise ValidationError({'ubicacion': (
                'Para marcar un artículo como No localizado usa una reubicación.')})

    movimiento = Movimiento(
        folio=siguiente_folio_movimiento(), fecha_movimiento=_fecha_hora(datos.get('fecha')),
        motivo=datos['motivo'].strip(), articulo=articulo, tipo_movimiento=tipo,
        ubicacion_origen=articulo.ubicacion, ubicacion_destino=destino,
        resguardante_anterior=articulo.resguardante, resguardante_nuevo=resguardante_nuevo,
        requiere_resguardo=(tipo.pk == 'REUB'
                            and resguardante_nuevo.pk != articulo.resguardante_id),
        usuario=usuario)
    if not movimiento.motivo:
        raise ValidationError({'motivo': 'El motivo es obligatorio.'})

    anterior = datos_de(articulo)
    articulo.ubicacion = destino
    articulo.resguardante = resguardante_nuevo
    articulo.estado_operativo = EstadoOperativo.objects.get(pk=estado_nuevo)
    articulo.save(update_fields=['ubicacion', 'resguardante', 'estado_operativo'])
    registrar(usuario, 'articulos', 'UPDATE', articulo, anterior=anterior,
              nuevo=datos_de(articulo), motivo=movimiento.motivo[:255])

    movimiento.save(force_insert=True)
    registrar(usuario, 'movimientos', 'INSERT', movimiento, nuevo=datos_de(movimiento))
    return movimiento
