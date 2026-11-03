"""Alta de artículos: todo en una sola transacción (artículo, movimiento ALTA
y bitácora). Si algo falla no queda nada a medias ni se consume un folio."""
from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from articulos.models import Articulo
from auditoria.servicios import datos_de, registrar
from catalogos.folios import FolioAgotado, siguiente_folio_interno, siguiente_folio_movimiento
from catalogos.models import EstadoOperativo, EstadoRegistro, TipoMovimiento
from movimientos.models import Movimiento

UBICACION_NO_LOCALIZADO = 'UBI-NOLOC'


def estado_de_registro(donado, costo, fecha):
    """DEC-008: Donado manda; con fecha y costo es Registrado; si no, Pendiente."""
    if donado:
        return 'DON'
    return 'REG' if costo is not None and fecha is not None else 'PEND'


def _duplicado(campo, valor, mensaje):
    if valor and Articulo.objects.filter(**{campo: valor}).exists():
        raise ValidationError({campo: mensaje})


@transaction.atomic
def alta_articulo(datos, usuario):
    origen = datos['origen']
    _duplicado('marbete_oficial', datos.get('marbete_oficial'), 'Ese marbete ya está registrado.')
    _duplicado('num_serie', datos.get('num_serie'), 'Ese número de serie ya está registrado.')

    folio = None
    if origen.pk in ('COM', 'ENS'):
        try:
            folio = siguiente_folio_interno()
        except FolioAgotado as error:
            raise ValidationError({'origen': str(error)})

    ubicacion = datos['ubicacion']
    estado_operativo = (EstadoOperativo.objects.get(pk='NOLOC')
                        if ubicacion.pk == UBICACION_NO_LOCALIZADO
                        else datos.get('estado_operativo')
                        or EstadoOperativo.objects.get(pk='UTIL'))
    costo, fecha = datos.get('costo_adquisicion'), datos.get('fecha_adquisicion')

    try:
        articulo = Articulo.objects.create(
            origen=origen, tipo_articulo=datos['tipo_articulo'], ubicacion=ubicacion,
            resguardante=datos['resguardante'], estado_operativo=estado_operativo,
            estado_registro=EstadoRegistro.objects.get(
                pk=estado_de_registro(datos.get('donado', False), costo, fecha)),
            marbete_oficial=datos.get('marbete_oficial') if origen.pk == 'ACT' else None,
            folio_interno=folio, marca=datos.get('marca'), modelo=datos.get('modelo'),
            num_serie=datos.get('num_serie'), color=datos['color'],
            descripcion=datos['descripcion'], fecha_adquisicion=fecha,
            costo_adquisicion=costo)
    except IntegrityError:
        raise ValidationError({'detalle': 'No se pudo registrar: revise marbete y número de serie.'})
    registrar(usuario, 'articulos', 'INSERT', articulo, nuevo=datos_de(articulo))

    # ALTA automática (DEC-006). PEND-001: las altas históricas de un bien no
    # localizado no generan resguardo; el resto sí.
    movimiento = Movimiento.objects.create(
        folio=siguiente_folio_movimiento(),
        motivo='Alta del artículo en el sistema',
        articulo=articulo, tipo_movimiento=TipoMovimiento.objects.get(pk='ALTA'),
        ubicacion_origen=None, ubicacion_destino=ubicacion,
        resguardante_anterior=None, resguardante_nuevo=articulo.resguardante,
        requiere_resguardo=ubicacion.pk != UBICACION_NO_LOCALIZADO,
        usuario=usuario)
    registrar(usuario, 'movimientos', 'INSERT', movimiento, nuevo=datos_de(movimiento))
    return articulo
