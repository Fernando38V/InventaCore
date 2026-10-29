from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from usuarios.models import Rol, Usuario


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['clave', 'nombre', 'descripcion']


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True)
    empleado = serializers.CharField(source='personal.nombre_completo', read_only=True)

    class Meta:
        model = Usuario
        fields = ['num', 'username', 'password', 'activo', 'personal', 'empleado',
                  'rol', 'rol_nombre']
        read_only_fields = ['num']

    def get_extra_kwargs(self):
        extra = super().get_extra_kwargs()
        if self.instance is not None:
            # Al editar solo cambian el rol y el estado; el resto no se toca.
            for campo in ('username', 'personal', 'password'):
                extra.setdefault(campo, {})['read_only'] = True
        return extra

    def validate_password(self, valor):
        validate_password(valor)
        return valor

    def validate_personal(self, personal):
        if not personal.activo:
            raise serializers.ValidationError('El empleado está dado de baja.')
        return personal

    def validate_rol(self, rol):
        if not rol.activo:
            raise serializers.ValidationError('El rol no está disponible.')
        return rol

    def validate(self, datos):
        # Siempre debe quedar al menos un Administrador activo.
        if self.instance is not None and self.instance.es_administrador and self.instance.activo:
            deja_de_ser = (datos.get('activo') is False
                           or ('rol' in datos and datos['rol'].pk != 'ADMIN'))
            if deja_de_ser and not Usuario.objects.filter(
                    rol_id='ADMIN', activo=True).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError(
                    'Debe quedar al menos un Administrador activo.')
        return datos

    def create(self, datos):
        return Usuario.objects.create_user(
            username=datos['username'], password=datos['password'],
            personal=datos['personal'], rol=datos['rol'],
            activo=datos.get('activo', True))


class ContrasenaSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def validate_password(self, valor):
        validate_password(valor)
        return valor


class CambiarContrasenaSerializer(ContrasenaSerializer):
    password_actual = serializers.CharField(write_only=True)
