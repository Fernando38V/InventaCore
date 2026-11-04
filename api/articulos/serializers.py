"""Forma del JSON de artículos.

Las claves de la respuesta siguen las del frontend (client/equipos/views.py,
`_equipo`) para que solo cambie el origen de los datos. Lo nuevo respecto a
su ejemplo: `descripcion` (DEC-011), `tipo_articulo` y `faltantes`.
"""
from decimal import Decimal

from django.utils import timezone

from rest_framework import serializers

from catalogos.models import EstadoOperativo, Origen, TipoArticulo, Ubicacion
from personal.models import Personal

TONO_OPERATIVO = {'UTIL': 'azul', 'OBS': 'gris', 'NOLOC': 'ambar'}
TONO_REGISTRO = {'REG': 'verde', 'PEND': 'ambar', 'DON': 'azul'}


def par(objeto):
    return {'codigo': objeto.pk, 'nombre': objeto.nombre}


def persona(personal):
    if personal is None:
        return None
    return {'num': personal.num, 'numero_empleado': personal.numero_empleado,
            'nombre': personal.nombre_completo}


def faltantes_de(articulo):
    """Qué le falta a un artículo Pendiente (para avisarlo en pantalla)."""
    if articulo.estado_registro_id != 'PEND':
        return []
    faltan = []
    if articulo.costo_adquisicion is None:
        faltan.append('el costo de adquisición')
    if articulo.fecha_adquisicion is None:
        faltan.append('la fecha de adquisición')
    return faltan


class ArticuloSerializer(serializers.BaseSerializer):
    """Solo lectura."""

    def to_representation(self, a):
        tipo = a.tipo_articulo
        return {
            'num': a.num,
            'marbete_oficial': a.marbete_oficial,
            'folio_interno': a.folio_interno,
            'identificador': a.identificador,
            'marca': a.marca,
            'modelo': a.modelo,
            'num_serie': a.num_serie,
            'color': a.color,
            'descripcion': a.descripcion,
            'costo_adquisicion': (None if a.costo_adquisicion is None
                                  else '{:.2f}'.format(a.costo_adquisicion)),
            'fecha_adquisicion': (a.fecha_adquisicion.isoformat()
                                  if a.fecha_adquisicion else None),
            'fecha_alta': timezone.localtime(a.fecha_alta).date().isoformat(),
            'tipo_articulo': par(tipo),
            'categoria': par(tipo.categoria),
            'origen': par(a.origen),
            'ubicacion': par(a.ubicacion),
            'resguardante': persona(a.resguardante),
            'estado_operativo': dict(par(a.estado_operativo),
                                     tono=TONO_OPERATIVO.get(a.estado_operativo_id, 'gris')),
            'estado_registro': dict(par(a.estado_registro),
                                    tono=TONO_REGISTRO.get(a.estado_registro_id, 'gris')),
            'faltantes': faltantes_de(a),
        }


class _TextoOpcional(serializers.CharField):
    """Texto opcional: vacío o en blanco se guarda como NULL (nunca como '')."""

    def __init__(self, **kw):
        kw.setdefault('required', False)
        kw.setdefault('allow_null', True)
        kw.setdefault('allow_blank', True)
        super().__init__(**kw)

    def run_validation(self, dato=serializers.empty):
        # Con allow_blank, DRF devuelve '' sin pasar por to_internal_value.
        valor = super().run_validation(dato)
        return valor.strip() or None if isinstance(valor, str) else valor


class ArticuloCorregirSerializer(serializers.Serializer):
    """Corrección desde la ficha (DEC-013, DEC-010). Solo lo que se manda
    cambia. `motivo` es obligatorio. Ubicación y resguardante no están aquí:
    solo cambian por movimiento."""

    marbete_oficial = serializers.CharField(max_length=25, required=False)
    marca = _TextoOpcional(max_length=50)
    modelo = _TextoOpcional(max_length=60)
    num_serie = _TextoOpcional(max_length=50)
    color = serializers.CharField(max_length=25, required=False)
    descripcion = serializers.CharField(max_length=150, required=False)
    fecha_adquisicion = serializers.DateField(required=False, allow_null=True)
    costo_adquisicion = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
        min_value=Decimal('0'))
    estado_operativo = serializers.CharField(required=False)
    motivo = serializers.CharField(max_length=255, error_messages={
        'blank': 'Indique el motivo del cambio.', 'required': 'Indique el motivo del cambio.'})

    def validate_fecha_adquisicion(self, fecha):
        if fecha and fecha > timezone.localdate():
            raise serializers.ValidationError('La fecha no puede ser futura.')
        return fecha


class ArticuloCrearSerializer(serializers.Serializer):
    """Entrada del alta. El folio interno (Comodato/Enser), el estado de
    registro y el movimiento ALTA los pone el sistema (DEC-007, DEC-008)."""

    origen = serializers.PrimaryKeyRelatedField(queryset=Origen.objects.all())
    tipo_articulo = serializers.PrimaryKeyRelatedField(queryset=TipoArticulo.objects.all())
    ubicacion = serializers.PrimaryKeyRelatedField(queryset=Ubicacion.objects.all())
    resguardante = serializers.PrimaryKeyRelatedField(queryset=Personal.objects.all())
    marbete_oficial = _TextoOpcional(max_length=25)
    marca = _TextoOpcional(max_length=50)
    modelo = _TextoOpcional(max_length=60)
    num_serie = _TextoOpcional(max_length=50)
    color = serializers.CharField(max_length=25)
    descripcion = serializers.CharField(max_length=150)
    fecha_adquisicion = serializers.DateField(required=False, allow_null=True)
    costo_adquisicion = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
        min_value=Decimal('0'))
    donado = serializers.BooleanField(required=False, default=False)
    estado_operativo = serializers.PrimaryKeyRelatedField(
        queryset=EstadoOperativo.objects.all(), required=False)

    def validate_fecha_adquisicion(self, fecha):
        if fecha and fecha > timezone.localdate():
            raise serializers.ValidationError('La fecha no puede ser futura.')
        return fecha

    def validate_tipo_articulo(self, tipo):
        if not tipo.activo or not tipo.categoria.activo:
            raise serializers.ValidationError('El tipo de artículo está desactivado.')
        return tipo

    def validate_ubicacion(self, ubicacion):
        if not ubicacion.activo:
            raise serializers.ValidationError('La ubicación está desactivada.')
        return ubicacion

    def validate_resguardante(self, personal):
        if not personal.activo:
            raise serializers.ValidationError('El resguardante está dado de baja.')
        return personal

    def validate_estado_operativo(self, estado):
        if not estado.activo:
            raise serializers.ValidationError('El estado operativo está desactivado.')
        return estado

    def validate(self, datos):
        errores = {}
        origen = datos['origen'].pk
        marbete = datos.get('marbete_oficial')
        if origen == 'ACT':
            if not marbete:
                errores['marbete_oficial'] = 'Los activos llevan marbete oficial.'
        elif marbete:
            errores['marbete_oficial'] = (
                'Los comodatos y enseres no llevan marbete: reciben un folio interno.')
        if datos.get('num_serie') is None:
            datos['num_serie'] = None
        sin_localizar = datos['ubicacion'].pk == 'UBI-NOLOC'
        estado = datos.get('estado_operativo')
        if estado is not None:
            if sin_localizar and estado.pk != 'NOLOC':
                errores['estado_operativo'] = (
                    'Un artículo en "Sin ubicar" tiene el estado No localizado.')
            elif not sin_localizar and estado.pk == 'NOLOC':
                errores['estado_operativo'] = (
                    'El estado No localizado va con la ubicación "Sin ubicar".')
        if errores:
            raise serializers.ValidationError(errores)
        return datos
