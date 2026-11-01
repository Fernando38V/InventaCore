def usuario_sesion(request):
    """Usuario real devuelto por la API al iniciar sesión."""
    datos = request.session.get('usuario')
    if not datos:
        return {'usuario': None}
    return {'usuario': {
        'num': datos.get('num'),
        'username': datos.get('username'),
        'nombre_completo': datos.get('empleado'),
        'rol': datos.get('rol'),             # 'ADMIN' o 'CONSULTA'
        'rol_nombre': datos.get('rol_nombre'),
    }}