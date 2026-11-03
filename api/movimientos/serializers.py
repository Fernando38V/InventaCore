"""Forma del JSON de movimientos.

Las claves siguen las del frontend (client/movimientos/views.py, `_mov`):
`equipo`, `ubicacion_llegada`, `personal_asigna` (quien queda como
resguardante), `personal_entrega` (de quién lo recibe; solo si cambió la
persona), `nota` (el motivo) y `genera_resguardo` (= requiere_resguardo,
DEC-016).
"""
from django.utils import timezone
from rest_framework import serializers

from articulos.models import Articulo
from articulos.serializers import par, persona
from catalogos.models import TipoMovimiento


def _descripcion(a):
    texto = ' '.join(p for p in (a.marca, a.modelo) if p)
    return texto or a.descripcion


class MovimientoSerializer(serializers.BaseSerializer):
    """Solo lectura."""

    @staticmethod
    def optimizar(consulta):
        return consulta.select_related(
            'articulo', 'tipo_movimiento', 'ubicacion_origen', 'ubicacion_destino',
            'resguardante_anterior', 'resguardante_nuevo', 'usuario__personal')

    def to_representation(self, m):
        local = timezone.localtime(m.fecha_movimiento)
        cambio_persona = (m.resguardante_anterior_id is not None
                          and m.resguardante_anterior_id != m.resguardante_nuevo_id)
        return {
            'num': int(m.folio.rsplit('-', 1)[-1]),
            'folio': m.folio,
            'fecha': local.strftime('%Y-%m-%d %H:%M'),
            'fecha_dia': local.strftime('%Y-%m-%d'),
            'fecha_hora': local.strftime('%H:%M'),
            'tipo': par(m.tipo_movimiento),
            'genera_resguardo': m.requiere_resguardo,
            'equipo': {
                'num': m.articulo_id,
                'identificador': m.articulo.identificador,
                'descripcion': _descripcion(m.articulo),
            },
            'ubicacion_origen': par(m.ubicacion_origen) if m.ubicacion_origen else None,
            'ubicacion_llegada': par(m.ubicacion_destino),
            'personal_asigna': persona(m.resguardante_nuevo),
            'personal_entrega': persona(m.resguardante_anterior) if cambio_persona else None,
            'nota': m.motivo,
            'usuario': {'num': m.usuario_id, 'username': m.usuario.username},
        }


class MovimientoCrearSerializer(serializers.Serializer):
    """Entrada de "Nuevo movimiento". ALTA no se pide: se crea sola."""

    tipo = serializers.PrimaryKeyRelatedField(queryset=TipoMovimiento.objects.all())
    equipo = serializers.PrimaryKeyRelatedField(
        queryset=Articulo.objects.all(), error_messages={
            'does_not_exist': 'Selecciona el equipo.', 'required': 'Selecciona el equipo.'})
    ubicacion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    resguardante = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    motivo = serializers.CharField(max_length=255, error_messages={
        'blank': 'El motivo es obligatorio.', 'required': 'El motivo es obligatorio.'})
    fecha = serializers.DateField(required=False, allow_null=True)
    # Solo al recuperar un artículo No localizado (DEC-012): se reconfirma.
    estado_operativo = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_internal_value(self, data):
        # `articulo` es sinónimo de `equipo`.
        if 'equipo' not in data and 'articulo' in data:
            data = {**dict(data.items()), 'equipo': data['articulo']}
        return super().to_internal_value(data)

    def validate_fecha(self, fecha):
        if fecha and fecha > timezone.localdate():
            raise serializers.ValidationError('La fecha no puede ser futura.')
        return fecha
