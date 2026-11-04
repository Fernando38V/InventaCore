"""Forma del JSON de movimientos.

Las claves siguen las decisiones del proyecto: `articulo` (DEC-002) y
`requiere_resguardo` (DEC-016). `personal_asigna` es quien queda como
resguardante, `personal_entrega` de quién lo recibe (solo si cambió la
persona) y `nota` es el motivo. Al crear se acepta `equipo` como sinónimo de
`articulo` (nombre anterior del frontend).
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
            'resguardante_anterior', 'resguardante_nuevo', 'usuario__personal',
            'detalle_resguardo')

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
            'requiere_resguardo': m.requiere_resguardo,
            # Folio del resguardo que ya documenta esta asignación (o null).
            'resguardo': (m.detalle_resguardo.resguardo_id
                          if hasattr(m, 'detalle_resguardo') else None),
            'articulo': {
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

    tipo = serializers.PrimaryKeyRelatedField(
        queryset=TipoMovimiento.objects.all(),
        error_messages={'does_not_exist': 'Selecciona el tipo de movimiento.',
                        'required': 'Selecciona el tipo de movimiento.'})
    articulo = serializers.PrimaryKeyRelatedField(
        queryset=Articulo.objects.all(), error_messages={
            'does_not_exist': 'Selecciona el artículo.', 'required': 'Selecciona el artículo.',
            'incorrect_type': 'Selecciona el artículo.'})
    ubicacion = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    resguardante = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    motivo = serializers.CharField(max_length=255, error_messages={
        'blank': 'El motivo es obligatorio.', 'required': 'El motivo es obligatorio.'})
    fecha = serializers.DateField(required=False, allow_null=True)
    # Solo al recuperar un artículo No localizado (DEC-012): se reconfirma.
    estado_operativo = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def to_internal_value(self, data):
        # `equipo` es sinónimo de `articulo` (nombre anterior del frontend).
        if 'articulo' not in data and 'equipo' in data:
            data = {**dict(data.items()), 'articulo': data['equipo']}
        return super().to_internal_value(data)

    def validate_fecha(self, fecha):
        if fecha and fecha > timezone.localdate():
            raise serializers.ValidationError('La fecha no puede ser futura.')
        return fecha


class ResguardoSerializer(serializers.BaseSerializer):
    """Solo lectura. `pdf` es la ruta de descarga del archivo original."""

    @staticmethod
    def optimizar(consulta):
        return consulta.select_related(
            'resguardante', 'usuario_emisor').prefetch_related(
            'detalles__movimiento__articulo')

    def to_representation(self, r):
        detalles = list(r.detalles.all())
        return {
            'folio': r.folio,
            'fecha_emision': timezone.localtime(r.fecha_emision).strftime('%Y-%m-%d %H:%M'),
            'resguardante': persona(r.resguardante),
            'usuario_emisor': {'num': r.usuario_emisor_id, 'username': r.usuario_emisor.username},
            'numero_bienes': len(detalles),
            'hash_pdf': r.hash_pdf,
            'pdf': '/api/resguardos/%s/pdf/' % r.folio,
            'articulos': [{
                'num': d.movimiento.articulo_id,
                'identificador': d.movimiento.articulo.identificador,
                'descripcion': _descripcion(d.movimiento.articulo),
                'movimiento': d.movimiento_id,
            } for d in detalles],
        }


class ResguardoCrearSerializer(serializers.Serializer):
    resguardante = serializers.IntegerField(error_messages={
        'required': 'Seleccione al resguardante.', 'invalid': 'Seleccione al resguardante.'})
    movimientos = serializers.ListField(
        child=serializers.RegexField(r'^MOV-\d+$', error_messages={
            'invalid': 'Folio de movimiento no válido.'}),
        allow_empty=False, error_messages={
            'required': 'Seleccione al menos un movimiento.',
            'empty': 'Seleccione al menos un movimiento.'})
