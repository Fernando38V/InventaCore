"""
Simulación de sesión mientras no existe login conectado al backend.

Permite previsualizar el layout con cualquiera de los dos roles usando
un parámetro en la URL, sin necesitar un sistema de autenticación real:

    /equipos/detalle/1/?rol=ADMIN
    /equipos/detalle/1/?rol=CONT

El rol elegido se guarda en sesión para no repetir el parámetro en
cada clic. Cuando el login real esté integrado, este archivo se
reemplaza para leer el usuario autenticado de verdad.
"""

ROLES_DEMO = {
    'ADMIN': {
        'rol': 'ADMIN',
        'rol_nombre': 'Administrador',
        'nombre_completo': 'Anwar Martínez',
    },
    'CONT': {
        'rol': 'CONT',
        'rol_nombre': 'Contadora',
        'nombre_completo': 'Laura Sánchez',
    },
}


def usuario_sesion(request):
    rol_param = request.GET.get('rol')
    if rol_param in ROLES_DEMO:
        request.session['rol_demo'] = rol_param

    rol_actual = request.session.get('rol_demo', 'ADMIN')
    datos = ROLES_DEMO.get(rol_actual, ROLES_DEMO['ADMIN'])

    return {'usuario': datos}