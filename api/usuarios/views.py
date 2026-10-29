from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import serializers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permisos import SoloAdministrador
from auditoria.mixins import BitacoraMixin
from auditoria.servicios import registrar
from usuarios.models import Usuario
from usuarios.serializers import (
    CambiarContrasenaSerializer, ContrasenaSerializer, UsuarioSerializer)


def _perfil(usuario):
    return {
        'num': usuario.num, 'username': usuario.username,
        'empleado': usuario.personal.nombre_completo,
        'rol': usuario.rol_id, 'rol_nombre': usuario.rol.nombre,
    }


class LoginView(APIView):
    """Solo usuario y contraseña (sin correo). Cada inicio de sesión crea un
    token nuevo y descarta el anterior."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        usuario = authenticate(
            username=request.data.get('username'), password=request.data.get('password'))
        if usuario is None:
            raise serializers.ValidationError(
                {'detalle': 'Usuario o contraseña incorrectos.'})
        Token.objects.filter(user=usuario).delete()
        token = Token.objects.create(user=usuario)
        return Response({'token': token.key, 'usuario': _perfil(usuario)})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class YoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_perfil(request.user))


class CambiarContrasenaView(APIView):
    """Cualquier rol cambia su PROPIA contraseña (incluido el Observador)."""

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        datos = CambiarContrasenaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        if not request.user.check_password(datos.validated_data['password_actual']):
            raise serializers.ValidationError(
                {'password_actual': 'La contraseña actual no es correcta.'})
        request.user.set_password(datos.validated_data['password'])
        request.user.save(update_fields=['password'])
        registrar(request.user, 'usuarios', 'UPDATE', request.user,
                  anterior={'password': 'anterior'}, nuevo={'password': 'cambiada por el usuario'})
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UsuarioViewSet(BitacoraMixin, viewsets.ModelViewSet):
    """Solo el Administrador: crear cuentas, cambiar rol, dar de baja y
    restablecer contraseñas de otros."""

    modulo = 'usuarios'
    permission_classes = [SoloAdministrador]
    serializer_class = UsuarioSerializer
    queryset = Usuario.objects.select_related('personal', 'rol')

    @action(detail=True, methods=['post'], url_path='restablecer-password')
    @transaction.atomic
    def restablecer_password(self, request, pk=None):
        usuario = self.get_object()
        datos = ContrasenaSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        usuario.set_password(datos.validated_data['password'])
        usuario.save(update_fields=['password'])
        Token.objects.filter(user=usuario).delete()  # cierra sus sesiones
        registrar(request.user, 'usuarios', 'UPDATE', usuario,
                  anterior={'password': 'anterior'},
                  nuevo={'password': 'restablecida por el Administrador'},
                  motivo=str(request.data.get('motivo') or '')[:255] or None)
        return Response(status=status.HTTP_204_NO_CONTENT)
