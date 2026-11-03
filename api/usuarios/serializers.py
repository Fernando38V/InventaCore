import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as ErrorDjango
from rest_framework import serializers

from usuarios.models import Rol, Usuario

# Letras, números, punto, guion y guion bajo; sin espacios (RF-01: solo usuario y contraseña).
NOMBRE_USUARIO = re.compile(r'^[A-Za-z0-9._-]+$')


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['clave', 'nombre', 'descripcion']


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True)
    empleado = serializers.CharField(source='personal.nombre_completo', read_only=True)
    numero_empleado = serializers.CharField(source='personal.numero_empleado', read_only=True)
    puesto = serializers.CharField(source='personal.puesto', read_only=True)

    class Meta:
        model = Usuario
        fields = ['num', 'username', 'password', 'activo', 'personal', 'empleado',
                  'numero_empleado', 'puesto', 'rol', 'rol_nombre']
        read_only_fields = ['num']

    def get_extra_kwargs(self):
        extra = super().get_extra_kwargs()
        if self.instance is not None:
            # Al editar solo cambian el rol y el estado; el resto no se toca.
            for campo in ('username', 'personal', 'password'):
                extra.setdefault(campo, {})['read_only'] = True
        return extra

    def validate_username(self, valor):
        valor = valor.strip()
        if len(valor) < 3:
            raise serializers.ValidationError('Use al menos 3 caracteres.')
        if not NOMBRE_USUARIO.match(valor):
            raise serializers.ValidationError(
                'Solo letras, números, punto, guion y guion bajo; sin espacios.')
        return valor

    def validate_password(self, valor):
        # Sin la cuenta todavía: el parecido con el usuario se revisa en validate().
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
        if self.instance is None and 'password' in datos:
            personal = datos.get('personal')
            candidato = Usuario(username=datos.get('username', ''), personal=personal)
            try:
                validate_password(datos['password'], candidato)
            except ErrorDjango as e:
                raise serializers.ValidationError({'password': list(e.messages)})
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
        validate_password(valor, self.context.get('usuario'))
        return valor


class CambiarContrasenaSerializer(ContrasenaSerializer):
    password_actual = serializers.CharField(write_only=True)


class EmpleadoDisponibleSerializer(serializers.Serializer):
    """Empleado activo que todavía no tiene cuenta (opciones del alta)."""

    num = serializers.IntegerField()
    numero_empleado = serializers.CharField()
    nombre_completo = serializers.CharField()
    puesto = serializers.CharField()
