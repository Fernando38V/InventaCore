from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from client.api import ApiError, llamar


def login_view(request):
    """M1 — Inicio de sesión contra POST /api/auth/login/."""
    if request.session.get('api_token'):
        return redirect('reportes:dashboard')

    error = None
    usuario = ''
    if request.method == 'POST':
        usuario = request.POST.get('usuario', '').strip()
        password = request.POST.get('password', '')
        if not usuario or not password:
            error = 'Escribe tu usuario y tu contraseña.'
        else:
            try:
                r = llamar(None, 'POST', 'auth/login/',
                           {'username': usuario, 'password': password})
            except ApiError as e:
                error = e.datos.get('detalle') or 'No se pudo iniciar sesión.'
            else:
                request.session.cycle_key()          # nueva sesión al entrar
                request.session['api_token'] = r['token']
                request.session['usuario'] = r['usuario']
                return redirect('reportes:dashboard')

    return render(request, 'auth/login.html', {'error': error, 'usuario_escrito': usuario})


@require_POST
def logout_view(request):
    """Invalida el token en la API y borra la sesión del cliente."""
    if request.session.get('api_token'):
        try:
            llamar(request, 'POST', 'auth/logout/')
        except ApiError:
            pass  # aunque la API no responda, la sesión local se cierra
    request.session.flush()
    return redirect('usuarios:login')