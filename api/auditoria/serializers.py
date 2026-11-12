"""Salida de la bitácora (RF-21): una fila por acción registrada."""
import json

from rest_framework import serializers

from auditoria.models import Bitacora


def _como_json(texto):
    """Los valores se guardan como texto JSON; se devuelven ya convertidos.
    Si alguno no es JSON válido se devuelve tal cual, sin fallar."""
    if texto is None:
        return None
    try:
        return json.loads(texto)
    except ValueError:
        return texto


class BitacoraSerializer(serializers.ModelSerializer):
    usuario = serializers.SerializerMethodField()
    accion_nombre = serializers.CharField(source='get_accion_display', read_only=True)
    valor_anterior = serializers.SerializerMethodField()
    valor_nuevo = serializers.SerializerMethodField()

    class Meta:
        model = Bitacora
        fields = ['num', 'fecha_hora', 'usuario', 'modulo', 'accion', 'accion_nombre',
                  'tabla_afectada', 'registro_id', 'motivo', 'valor_anterior', 'valor_nuevo']
        read_only_fields = fields

    @staticmethod
    def optimizar(consulta):
        return consulta.select_related('usuario__personal')

    def get_usuario(self, b):
        u = b.usuario
        return {'num': u.pk, 'username': u.username, 'nombre': u.personal.nombre_completo}

    def get_valor_anterior(self, b):
        return _como_json(b.valor_anterior)

    def get_valor_nuevo(self, b):
        return _como_json(b.valor_nuevo)
