from rest_framework import serializers

from catalogos.codigos import CodigoAutomatico
from personal.models import Departamento, Personal


class DepartamentoSerializer(CodigoAutomatico, serializers.ModelSerializer):
    prefijo_codigo = 'DEP'

    class Meta:
        model = Departamento
        fields = ['codigo', 'nombre', 'descripcion', 'activo']


class PersonalSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True)
    articulos_a_cargo = serializers.SerializerMethodField()

    class Meta:
        model = Personal
        fields = ['num', 'numero_empleado', 'nombre_pila', 'primer_apellido',
                  'segundo_apellido', 'nombre_completo', 'puesto', 'activo',
                  'departamento', 'departamento_nombre', 'articulos_a_cargo']
        read_only_fields = ['num']

    def get_articulos_a_cargo(self, personal):
        # Un empleado dado de baja conserva sus artículos hasta un movimiento.
        return personal.articulos.count()

    def validate_departamento(self, departamento):
        if not departamento.activo and (
                self.instance is None or self.instance.departamento_id != departamento.pk):
            raise serializers.ValidationError('El departamento está desactivado.')
        return departamento
