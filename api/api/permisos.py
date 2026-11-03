from rest_framework.permissions import SAFE_METHODS, BasePermission


class AdminEscribeConsultaLee(BasePermission):
    """Administrador: todo. Consulta: solo consultar (GET, HEAD, OPTIONS)."""

    message = 'Su rol solo permite consultar.'

    def has_permission(self, request, view):
        usuario = request.user
        if not (usuario and usuario.is_authenticated):
            return False
        if usuario.es_administrador:
            return True
        return usuario.es_consulta and request.method in SAFE_METHODS


# Nombre anterior (DEC-001 renombró el rol Observador a Consulta). Se conserva
# para que un settings.py que aún lo cite siga funcionando.
AdminEscribeObservadorLee = AdminEscribeConsultaLee


class SoloAdministrador(BasePermission):
    message = 'Solo el Administrador puede hacer esto.'

    def has_permission(self, request, view):
        usuario = request.user
        return bool(usuario and usuario.is_authenticated and usuario.es_administrador)
