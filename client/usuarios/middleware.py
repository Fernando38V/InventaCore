from django.shortcuts import redirect

from client.api import SesionVencida

RUTAS_LIBRES = ('/cuentas/login/', '/static/')


class RequiereSesion:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (not request.session.get('api_token')
                and not request.path.startswith(RUTAS_LIBRES)):
            return redirect('usuarios:login')
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, SesionVencida):
            request.session.flush()
            return redirect('usuarios:login')
        return None