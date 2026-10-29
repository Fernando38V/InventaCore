from rest_framework import serializers

from catalogos.models import (
    Categoria, EstadoOperativo, EstadoRegistro, Origen, TipoArticulo, TipoMovimiento,
    Ubicacion)
from catalogos.codigos import CodigoAutomatico

UBICACION_NO_LOCALIZADO = 'UBI-NOLOC'


class CategoriaSerializer(CodigoAutomatico, serializers.ModelSerializer):
    prefijo_codigo = 'CAT'

    class Meta:
        model = Categoria
        fields = ['codigo', 'nombre', 'descripcion', 'activo']


class TipoArticuloSerializer(CodigoAutomatico, serializers.ModelSerializer):
    prefijo_codigo = 'TIP'

    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)

    class Meta:
        model = TipoArticulo
        fields = ['codigo', 'nombre', 'descripcion', 'categoria', 'categoria_nombre', 'activo']

    def validate_categoria(self, categoria):
        if self.instance is not None and categoria.pk != self.instance.categoria_id:
            if self.instance.articulos.exists():
                raise serializers.ValidationError(
                    'No se puede cambiar de categoría: ya hay artículos de este tipo.')
        if not categoria.activo and self.instance is None:
            raise serializers.ValidationError('La categoría está desactivada.')
        return categoria


class UbicacionSerializer(CodigoAutomatico, serializers.ModelSerializer):
    prefijo_codigo = 'UBI'

    responsable_nombre = serializers.CharField(
        source='responsable.nombre_completo', read_only=True, default=None)

    class Meta:
        model = Ubicacion
        fields = ['codigo', 'nombre', 'descripcion', 'responsable',
                  'responsable_nombre', 'activo']

    def validate(self, datos):
        # UBI-NOLOC es del sistema: no se renombra ni se desactiva.
        if self.instance is not None and self.instance.pk == UBICACION_NO_LOCALIZADO:
            if datos.get('activo') is False:
                raise serializers.ValidationError(
                    {'activo': 'La ubicación de no localizados no se puede desactivar.'})
            if 'nombre' in datos and datos['nombre'] != self.instance.nombre:
                raise serializers.ValidationError(
                    {'nombre': 'La ubicación de no localizados no se puede renombrar.'})
        return datos

    def validate_responsable(self, personal):
        if personal is not None and not personal.activo:
            raise serializers.ValidationError('El empleado está dado de baja.')
        return personal


class CatalogoSimpleSerializer(serializers.ModelSerializer):
    """Catálogos fijos de solo lectura: origen, estados y tipos de movimiento."""

    class Meta:
        fields = ['codigo', 'nombre']


def _simple(modelo):
    class _S(CatalogoSimpleSerializer):
        class Meta(CatalogoSimpleSerializer.Meta):
            model = modelo
    return _S


OrigenSerializer = _simple(Origen)
EstadoOperativoSerializer = _simple(EstadoOperativo)
EstadoRegistroSerializer = _simple(EstadoRegistro)
TipoMovimientoSerializer = _simple(TipoMovimiento)
