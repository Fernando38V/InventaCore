"""Usuarios y Roles (solo Administrador) y Perfil (todos los roles).

Todo sale de la API (api/usuarios/views.py):
- GET/POST /usuarios/, GET/PATCH /usuarios/<num>/   cuentas (PATCH: rol o activo, con motivo)
- GET /usuarios/empleados-disponibles/?q=           empleados activos sin cuenta
- POST /usuarios/<num>/restablecer-password/        nueva contraseña de otra persona
- GET /roles/                                       roles para el formulario
- GET /auth/yo/, POST /auth/cambiar-password/       perfil propio

La API decide los permisos; aquí solo se ocultan los botones. Una cuenta no puede
cambiarse el rol, desactivarse ni restablecerse la contraseña a sí misma desde
esta pantalla: la API cierra las sesiones de la cuenta que cambia y el
Administrador se quedaría fuera a mitad de la operación. Su contraseña la
cambia desde Perfil.
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from client.api import ApiError, SesionVencida, llamar
from client.utils import (
    contexto_paginacion, destino_seguro, errores_api, listar_todo, numero_de_pagina)


def _num_propio(request):
    return (request.session.get('usuario') or {}).get('num')


def _es_propia(request, num):
    return str(_num_propio(request)) == str(num)


def _roles(request):
    return listar_todo(request, 'roles')


def _usuario_o_404(request, num):
    try:
        return llamar(request, 'GET', 'usuarios/%s/' % num)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404:
            raise Http404
        raise


# listado

def _filtros(request):
    actuales = {
        'q': request.GET.get('q', '').strip(),
        'rol': request.GET.get('rol', '').strip(),
        'activo': request.GET.get('activo', '').strip(),
    }
    if actuales['activo'] not in ('true', 'false'):
        actuales['activo'] = ''
    return actuales, {k: v for k, v in actuales.items() if v}


def _fila(request, u):
    propia = _es_propia(request, u['num'])
    activo = u['activo']
    return {
        'num': u['num'], 'username': u['username'], 'empleado': u['empleado'],
        'numero_empleado': u['numero_empleado'], 'puesto': u['puesto'],
        'rol': u['rol'], 'rol_nombre': u['rol_nombre'], 'activo': activo,
        'propia': propia,
        'aviso': ('Ya no podrá iniciar sesión y se cerrarán sus sesiones abiertas. '
                  'La cuenta no se borra.' if activo else
                  'Podrá volver a iniciar sesión con su usuario y contraseña.'),
        'url_editar': reverse('usuarios:editar', args=[u['num']]),
        'url_estado': reverse('usuarios:estado', args=[u['num']]),
        'url_password': reverse('usuarios:restablecer', args=[u['num']]),
    }


def lista(request):
    pagina = numero_de_pagina(request)
    actuales, params = _filtros(request)
    error = ''
    datos = {'count': 0, 'results': []}
    roles = []
    try:
        datos = llamar(request, 'GET', 'usuarios/?' + urlencode(dict(params, page=pagina)))
        roles = _roles(request)
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404 and pagina > 1:
            return redirect(reverse('usuarios:listado') + ('?' + urlencode(params) if params else ''))
        error = errores_api(e)[1]

    contexto = {
        'filas': [_fila(request, u) for u in datos['results']],
        'roles': roles,
        'f': actuales,
        'hay_filtros': any(actuales.values()),
        'error_api': error,
    }
    contexto.update(contexto_paginacion(request, datos['count'], pagina))
    return render(request, 'usuarios/lista.html', contexto)


# alta

def _campos_obligatorios(valores, nombres):
    return {n: 'Este campo es obligatorio.' for n in nombres if not valores.get(n)}


def nuevo(request):
    """Alta de cuenta: se elige un empleado activo sin cuenta, un rol y se fija
    el usuario y la contraseña inicial."""
    buscar = request.GET.get('q', '').strip()
    valores = {'personal': '', 'username': '', 'rol': ''}
    errores, general = {}, ''

    if request.method == 'POST':
        valores = {c: request.POST.get(c, '').strip() for c in valores}
        password = request.POST.get('password', '')
        confirmar = request.POST.get('confirmar', '')
        errores = _campos_obligatorios(dict(valores, password=password),
                                       ('personal', 'username', 'rol', 'password'))
        if not errores.get('password') and password != confirmar:
            errores['confirmar'] = 'Las contraseñas no coinciden.'
        if not errores:
            try:
                creada = llamar(request, 'POST', 'usuarios/', {
                    'personal': int(valores['personal']) if valores['personal'].isdigit()
                    else valores['personal'],
                    'username': valores['username'], 'rol': valores['rol'],
                    'password': password})
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(
                    e, ['personal', 'username', 'rol', 'password'])
                errores.update(por_campo)
            else:
                messages.success(request, 'Cuenta «%s» creada para %s con el rol %s.' % (
                    creada['username'], creada['empleado'], creada['rol_nombre']))
                return redirect('usuarios:listado')

    empleados, roles = [], []
    try:
        empleados = llamar(request, 'GET', 'usuarios/empleados-disponibles/?' + urlencode(
            {'q': buscar} if buscar else {}))
        roles = _roles(request)
    except SesionVencida:
        raise
    except ApiError as e:
        general = general or errores_api(e)[1]

    return render(request, 'usuarios/form.html', {
        'editando': False, 'valores': valores, 'errores': errores, 'general': general,
        'empleados': empleados, 'roles': roles, 'buscar': buscar,
        'hay_mas_empleados': len(empleados) >= 50,
    })


# edición (rol)

def editar(request, num):
    if _es_propia(request, num):
        messages.error(request, 'No puedes cambiar tu propio rol. Pídeselo a otro Administrador.')
        return redirect('usuarios:listado')
    try:
        cuenta = _usuario_o_404(request, num)
        roles = _roles(request)
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
        return redirect('usuarios:listado')

    valores = {'rol': cuenta['rol']}
    motivo, errores, general = '', {}, ''
    if request.method == 'POST':
        valores['rol'] = request.POST.get('rol', '').strip()
        motivo = request.POST.get('motivo', '').strip()
        if not valores['rol']:
            errores['rol'] = 'Este campo es obligatorio.'
        elif valores['rol'] == cuenta['rol']:
            general = 'No hiciste ningún cambio.'
        elif not motivo:
            errores['motivo'] = 'Indica el motivo del cambio.'
        if not errores and not general:
            try:
                llamar(request, 'PATCH', 'usuarios/%s/' % num,
                       {'rol': valores['rol'], 'motivo': motivo})
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(e, ['rol', 'motivo'])
                errores.update(por_campo)
            else:
                messages.success(request, 'Se cambió el rol de «%s». Sus sesiones abiertas se cerraron.'
                                 % cuenta['username'])
                return redirect('usuarios:listado')

    return render(request, 'usuarios/form.html', {
        'editando': True, 'cuenta': cuenta, 'valores': valores, 'errores': errores,
        'general': general, 'roles': roles, 'motivo': motivo,
    })


# activar / desactivar 

@require_POST
def cambiar_estado(request, num):
    volver = destino_seguro(request, request.POST.get('volver'), reverse('usuarios:listado'))
    if _es_propia(request, num):
        messages.error(request, 'No puedes desactivar tu propia cuenta.')
        return redirect(volver)
    activar = request.POST.get('activar') == '1'
    motivo = request.POST.get('motivo', '').strip()
    if not motivo:
        messages.error(request, 'Indica el motivo del cambio.')
        return redirect(volver)
    try:
        cuenta = llamar(request, 'PATCH', 'usuarios/%s/' % num,
                        {'activo': activar, 'motivo': motivo})
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
    else:
        messages.success(request, 'Cuenta «%s» %s.' % (
            (cuenta or {}).get('username', ''), 'activada' if activar else 'desactivada'))
    return redirect(volver)


# restablecer contraseña de otra persona

def restablecer(request, num):
    if _es_propia(request, num):
        messages.error(request, 'Tu propia contraseña se cambia desde Perfil.')
        return redirect('usuarios:perfil')
    try:
        cuenta = _usuario_o_404(request, num)
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
        return redirect('usuarios:listado')

    motivo, errores, general = '', {}, ''
    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirmar = request.POST.get('confirmar', '')
        motivo = request.POST.get('motivo', '').strip()
        errores = _campos_obligatorios({'password': password, 'motivo': motivo},
                                       ('password', 'motivo'))
        if not errores.get('password') and password != confirmar:
            errores['confirmar'] = 'Las contraseñas no coinciden.'
        if not errores:
            try:
                llamar(request, 'POST', 'usuarios/%s/restablecer-password/' % num,
                       {'password': password, 'motivo': motivo})
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(e, ['password', 'motivo'])
                errores.update(por_campo)
            else:
                messages.success(request, 'Se restableció la contraseña de «%s». '
                                 'Sus sesiones abiertas se cerraron.' % cuenta['username'])
                return redirect('usuarios:listado')

    return render(request, 'usuarios/password.html', {
        'cuenta': cuenta, 'errores': errores, 'general': general, 'motivo': motivo})


# perfil

def perfil(request):
    """Datos de la cuenta que inició sesión y cambio de su contraseña."""
    errores, general = {}, ''
    if request.method == 'POST':
        actual = request.POST.get('password_actual', '')
        password = request.POST.get('password', '')
        confirmar = request.POST.get('confirmar', '')
        errores = _campos_obligatorios(
            {'password_actual': actual, 'password': password},
            ('password_actual', 'password'))
        if not errores.get('password') and password != confirmar:
            errores['confirmar'] = 'Las contraseñas no coinciden.'
        if not errores:
            try:
                llamar(request, 'POST', 'auth/cambiar-password/',
                       {'password_actual': actual, 'password': password})
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(e, ['password_actual', 'password'])
                errores.update(por_campo)
            else:
                # La API cierra todas las sesiones de la cuenta, incluida esta.
                request.session.flush()
                messages.success(request, 'Tu contraseña se cambió. Inicia sesión con la nueva.')
                return redirect('usuarios:login')

    yo = request.session.get('usuario') or {}
    try:
        yo = llamar(request, 'GET', 'auth/yo/')
    except SesionVencida:
        raise
    except ApiError:
        pass    # se muestran los datos guardados al iniciar sesión
    return render(request, 'usuarios/perfil.html', {
        'yo': yo, 'errores': errores, 'general': general})
