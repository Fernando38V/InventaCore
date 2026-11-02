from django.shortcuts import redirect

from client.api import SesionVencida

RUTAS_LIBRES = ('/cuentas/login/', '/static/')
# Secciones solo para el Administrador. El rol Consulta no las abre ni
# escribiendo la URL (los enlaces ya están ocultos en el menú).
# '/cuentas/' exacto es "Usuarios y Roles"; login, logout y perfil siguen libres.
RUTAS_ADMIN = ('/catalogos/', '/personal/', '/auditoria/')
RUTAS_ADMIN_EXACTAS = ('/cuentas/',)

class RequiereSesion:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (not request.session.get('api_token')
                and not request.path.startswith(RUTAS_LIBRES)):
            return redirect('usuarios:login')
        if self._solo_admin(request.path) and not self._es_admin(request):
            return redirect('reportes:dashboard')
        return self.get_response(request)

    @staticmethod
    def _solo_admin(ruta):
        return ruta.startswith(RUTAS_ADMIN) or ruta in RUTAS_ADMIN_EXACTAS

    @staticmethod
    def _es_admin(request):
        return (request.session.get('usuario') or {}).get('rol') == 'ADMIN'

    def process_exception(self, request, exception):
        if isinstance(exception, SesionVencida):
            request.session.flush()
            return redirect('usuarios:login')
        return None