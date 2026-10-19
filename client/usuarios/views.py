from django.shortcuts import render


def login_view(request):
    """M1 — Inicio de sesión (mockup).

    La autenticación real se conectará al backend cuando Adad publique
    el endpoint: POST /api/usuarios/login/
    """
    return render(request, 'auth/login.html')