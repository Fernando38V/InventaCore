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
def alta_articulo(datos, usuario, requiere_resguardo=None, folio_interno=None, motivo=None):
    """Alta con su movimiento ALTA.

    `requiere_resguardo` lo decide el sistema (verdadero salvo que el bien entre
    No localizado). La carga masiva (DEC-007, DEC-017) lo manda en falso porque
    no genera comprobante, respeta el folio que el bien ya tiene
    (`folio_interno`, RF-06) y pone su propio `motivo` en el movimiento ALTA.
    """
    origen = datos['origen']
    _duplicado('marbete_oficial', datos.get('marbete_oficial'), 'Ese marbete ya está registrado.')
    _duplicado('num_serie', datos.get('num_serie'), 'Ese número de serie ya está registrado.')

    folio = None
    if origen.pk in ('COM', 'ENS'):
        if folio_interno:
            _duplicado('folio_interno', folio_interno, 'Ese folio ya está registrado.')
            folio = folio_interno
        else:
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
        motivo=motivo or 'Alta del artículo en el sistema',
        articulo=articulo, tipo_movimiento=TipoMovimiento.objects.get(pk='ALTA'),
        ubicacion_origen=None, ubicacion_destino=ubicacion,
        resguardante_anterior=None, resguardante_nuevo=articulo.resguardante,
        requiere_resguardo=(ubicacion.pk != UBICACION_NO_LOCALIZADO
                            if requiere_resguardo is None else requiere_resguardo),
        usuario=usuario)
    registrar(usuario, 'movimientos', 'INSERT', movimiento, nuevo=datos_de(movimiento))
    return articulo


CAMPOS_CORREGIBLES = ('marbete_oficial', 'marca', 'modelo', 'num_serie', 'color',
                      'descripcion', 'fecha_adquisicion', 'estado_operativo')


@transaction.atomic
def corregir_articulo(articulo, datos, usuario):
    """Corrige datos de la ficha con motivo y bitácora (DEC-013).

    - Marbete (solo Activos), marca, modelo, serie, color, descripción, fecha
      y costo de adquisición. Si cambia la fecha o el costo, el estado de
      registro se recalcula (DEC-008); en un bien Donado el costo también se puede
      capturar o corregir y sigue siendo Donado (DEC-021).
    - Estado operativo: solo Útil <-> Obsoleto, con motivo. Un artículo No
      localizado no pasa a Obsoleto (DEC-012): se recupera con una reubicación.
    - Ubicación y resguardante no se tocan aquí: solo cambian por movimiento.
    """
    articulo = Articulo.objects.select_for_update().get(pk=articulo.pk)
    anterior = datos_de(articulo)
    errores = {}

    if 'marbete_oficial' in datos:
        marbete = datos['marbete_oficial'].strip()
        if articulo.origen_id != 'ACT':
            errores['marbete_oficial'] = 'Solo los activos llevan marbete oficial.'
        elif not marbete:
            errores['marbete_oficial'] = 'Los activos llevan marbete oficial.'
        elif Articulo.objects.filter(marbete_oficial=marbete).exclude(pk=articulo.pk).exists():
            errores['marbete_oficial'] = 'Ese marbete ya está registrado.'
        else:
            articulo.marbete_oficial = marbete
    if datos.get('num_serie') and Articulo.objects.filter(
            num_serie=datos['num_serie']).exclude(pk=articulo.pk).exists():
        errores['num_serie'] = 'Ese número de serie ya está registrado.'

    for campo in ('marca', 'modelo', 'num_serie'):
        if campo in datos:
            setattr(articulo, campo, datos[campo])
    for campo in ('color', 'descripcion'):
        if campo in datos:
            valor = datos[campo].strip()
            if not valor:
                errores[campo] = 'Este campo no puede quedar vacío.'
            else:
                setattr(articulo, campo, valor)
    if 'fecha_adquisicion' in datos:
        articulo.fecha_adquisicion = datos['fecha_adquisicion']
    if 'costo_adquisicion' in datos:
        # DEC-021: el costo de un Donado también se captura o corrige (vacío = NULL, no 0);
        # el estado de registro de un Donado sigue siendo Donado.
        articulo.costo_adquisicion = datos['costo_adquisicion']

    if 'estado_operativo' in datos:
        nuevo = datos['estado_operativo']
        if nuevo not in ('UTIL', 'OBS', 'NOLOC'):
            errores['estado_operativo'] = 'Elige Útil u Obsoleto.'
        elif articulo.estado_operativo_id == 'NOLOC':
            errores['estado_operativo'] = (
                'El artículo está No localizado: se recupera con una reubicación.')
        elif nuevo == 'NOLOC':
            errores['estado_operativo'] = (
                'No localizado se asigna con una reubicación a "Sin ubicar".')
        elif nuevo != articulo.estado_operativo_id:
            articulo.estado_operativo = EstadoOperativo.objects.get(pk=nuevo)
    if errores:
        raise ValidationError(errores)

    if articulo.estado_registro_id != 'DON':
        articulo.estado_registro_id = estado_de_registro(
            False, articulo.costo_adquisicion, articulo.fecha_adquisicion)

    nuevo = datos_de(articulo)
    if nuevo == anterior:
        raise ValidationError({'detalle': 'No hay cambios que guardar.'})
    try:
        articulo.save()
    except IntegrityError:
        raise ValidationError({'detalle': 'No se pudo guardar: revise marbete y número de serie.'})
    registrar(usuario, 'articulos', 'UPDATE', articulo, anterior=anterior, nuevo=nuevo,
              motivo=datos['motivo'].strip()[:255])
    return articulo
