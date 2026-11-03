from django.contrib.auth import authenticate
from django.db import transaction
from django.db.models import Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permisos import SoloAdministrador
from auditoria.mixins import BitacoraMixin
from auditoria.servicios import registrar
from personal.models import Personal
from usuarios.models import Rol, Usuario
from usuarios.serializers import (
    CambiarContrasenaSerializer, ContrasenaSerializer, EmpleadoDisponibleSerializer,
    RolSerializer, UsuarioSerializer)


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
    """Cualquier rol cambia su PROPIA contraseña (incluido el rol Consulta)."""

    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        datos = CambiarContrasenaSerializer(data=request.data, context={'usuario': request.user})
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

    def get_queryset(self):
        """Filtros: q (usuario, nombre o número de empleado, palabra por palabra),
        rol y activo."""
        consulta = super().get_queryset()
        p = self.request.query_params
        for palabra in (p.get('q') or '').split():
            consulta = consulta.filter(
                Q(username__icontains=palabra)
                | Q(personal__numero_empleado__icontains=palabra)
                | Q(personal__nombre_pila__icontains=palabra)
                | Q(personal__primer_apellido__icontains=palabra)
                | Q(personal__segundo_apellido__icontains=palabra))
        if p.get('rol'):
            consulta = consulta.filter(rol_id=p['rol'])
        if p.get('activo') in ('true', 'false'):
            consulta = consulta.filter(activo=p['activo'] == 'true')
        return consulta

    @transaction.atomic
    def perform_update(self, serializer):
        antes = (serializer.instance.activo, serializer.instance.rol_id)
        super().perform_update(serializer)
        usuario = serializer.instance
        # Una baja o un cambio de rol cierran sus sesiones abiertas.
        if (usuario.activo, usuario.rol_id) != antes:
            Token.objects.filter(user=usuario).delete()

    @action(detail=False, methods=['get'], url_path='empleados-disponibles')
    def empleados_disponibles(self, request):
        """Empleados activos sin cuenta, para el formulario de alta. ?q= filtra."""
        consulta = Personal.objects.filter(activo=True, usuario__isnull=True)
        for palabra in (request.query_params.get('q') or '').split():
            consulta = consulta.filter(
                Q(numero_empleado__icontains=palabra) | Q(nombre_pila__icontains=palabra)
                | Q(primer_apellido__icontains=palabra) | Q(segundo_apellido__icontains=palabra))
        datos = [{'num': e.num, 'numero_empleado': e.numero_empleado,
                  'nombre_completo': e.nombre_completo, 'puesto': e.puesto}
                 for e in consulta.order_by('primer_apellido', 'nombre_pila')[:50]]
        return Response(EmpleadoDisponibleSerializer(datos, many=True).data)

    @action(detail=True, methods=['post'], url_path='restablecer-password')
    @transaction.atomic
    def restablecer_password(self, request, pk=None):
        usuario = self.get_object()
        datos = ContrasenaSerializer(data=request.data, context={'usuario': usuario})
        datos.is_valid(raise_exception=True)
        usuario.set_password(datos.validated_data['password'])
        usuario.save(update_fields=['password'])
        Token.objects.filter(user=usuario).delete()  # cierra sus sesiones
        registrar(request.user, 'usuarios', 'UPDATE', usuario,
                  anterior={'password': 'anterior'},
                  nuevo={'password': 'restablecida por el Administrador'},
                  motivo=str(request.data.get('motivo') or '')[:255] or None)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RolViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Roles disponibles para el formulario de usuarios (solo lectura)."""

    permission_classes = [SoloAdministrador]
    serializer_class = RolSerializer
    queryset = Rol.objects.filter(activo=True)
    pagination_class = None
