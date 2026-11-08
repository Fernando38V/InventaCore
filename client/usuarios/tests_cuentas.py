"""Pruebas de Usuarios y Roles y de Perfil, con la API simulada.

Comprueban lo que el cliente MANDA y cómo reacciona a lo que responde la API.
El recorrido contra la API real se hace a mano.

    python manage.py test usuarios
"""
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase

from catalogos.tests import ApiFalsa, pagina
from client.api import ApiError, SesionVencida

ROLES = [
    {'clave': 'ADMIN', 'nombre': 'Administrador', 'descripcion': 'Control total.'},
    {'clave': 'CONSULTA', 'nombre': 'Consulta', 'descripcion': 'Solo consulta.'},
]


def cuenta(num=2, username='maria', activo=True, rol='CONSULTA', rol_nombre='Consulta'):
    return {'num': num, 'username': username, 'activo': activo, 'personal': 7,
            'empleado': 'María López Ruiz', 'numero_empleado': 'E007',
            'puesto': 'Docente', 'rol': rol, 'rol_nombre': rol_nombre}


EMPLEADO = {'num': 7, 'numero_empleado': 'E007', 'nombre_completo': 'María López Ruiz',
            'puesto': 'Docente'}


class BaseCuentas(TestCase):
    def setUp(self):
        self.api = ApiFalsa()
        self.api.respuestas[('GET', 'roles/')] = ROLES
        for destino in ('usuarios.views_cuentas.llamar', 'client.utils.llamar'):
            parche = patch(destino, self.api)
            parche.start()
            self.addCleanup(parche.stop)

    def entrar(self, rol='ADMIN', num=1):
        sesion = self.client.session
        sesion['api_token'] = 'token'
        sesion['usuario'] = {'num': num, 'username': 'admin', 'empleado': 'Fernando Estrada',
                             'rol': rol, 'rol_nombre': 'Administrador' if rol == 'ADMIN' else 'Consulta'}
        sesion.save()

    def mensajes(self, respuesta):
        return [str(m) for m in get_messages(respuesta.wsgi_request)]


class ListadoTests(BaseCuentas):
    def test_pide_a_la_api_la_pagina_y_los_filtros(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = pagina([cuenta()], total=11)
        r = self.client.get('/cuentas/?q=mar&rol=CONSULTA&activo=true&page=2')
        self.assertEqual(r.status_code, 200)
        ruta = [ll[1] for ll in self.api.llamadas if ll[1].startswith('usuarios/')][0]
        self.assertIn('q=mar', ruta)
        self.assertIn('rol=CONSULTA', ruta)
        self.assertIn('activo=true', ruta)
        self.assertIn('page=2', ruta)

    def test_filtro_activo_invalido_no_llega_a_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = pagina([cuenta()])
        self.client.get('/cuentas/?activo=quizas')
        ruta = [ll[1] for ll in self.api.llamadas if ll[1].startswith('usuarios/')][0]
        self.assertNotIn('activo=', ruta)

    def test_muestra_usuario_empleado_rol_y_acciones(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = pagina([cuenta()])
        r = self.client.get('/cuentas/')
        self.assertContains(r, 'maria')
        self.assertContains(r, 'María López Ruiz')
        self.assertContains(r, 'Núm. E007')
        self.assertContains(r, 'Cambiar rol')
        self.assertContains(r, '/cuentas/usuarios/2/password/')
        self.assertContains(r, 'Desactivar')

    def test_la_cuenta_propia_no_ofrece_cambiar_rol_ni_desactivar(self):
        self.entrar(num=2)
        self.api.respuestas[('GET', 'usuarios/')] = pagina([cuenta(num=2)])
        r = self.client.get('/cuentas/')
        self.assertContains(r, 'Tu cuenta')
        self.assertNotContains(r, 'Cambiar rol')
        self.assertNotContains(r, '/cuentas/usuarios/2/estado/')

    def test_cuenta_inactiva_ofrece_activar(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = pagina([cuenta(activo=False)])
        r = self.client.get('/cuentas/')
        self.assertContains(r, 'Inactiva')
        self.assertContains(r, 'Activar')

    def test_api_caida_muestra_aviso_y_no_rompe(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = ApiError(0, {'detalle': 'No se pudo conectar.'})
        r = self.client.get('/cuentas/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'No se pudo conectar.')

    def test_pagina_que_ya_no_existe_vuelve_a_la_primera(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = ApiError(404, {'detail': 'Página inválida.'})
        r = self.client.get('/cuentas/?page=9')
        self.assertEqual(r.status_code, 302)

    def test_sesion_vencida_lleva_al_login(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = SesionVencida(401, {})
        r = self.client.get('/cuentas/')
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)


class AltaTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/empleados-disponibles/')] = [EMPLEADO]

    def test_muestra_empleados_disponibles_y_roles(self):
        r = self.client.get('/cuentas/usuarios/nuevo/')
        self.assertContains(r, 'E007 — María López Ruiz')
        self.assertContains(r, 'Administrador')
        self.assertContains(r, 'Solo consulta.')

    def test_la_busqueda_se_manda_a_la_api(self):
        self.client.get('/cuentas/usuarios/nuevo/?q=mar')
        self.assertTrue(any(ll[1] == 'usuarios/empleados-disponibles/?q=mar'
                            for ll in self.api.llamadas))

    def test_alta_manda_los_campos_y_no_manda_la_confirmacion(self):
        self.api.respuestas[('POST', 'usuarios/')] = cuenta()
        r = self.client.post('/cuentas/usuarios/nuevo/', {
            'personal': '7', 'username': 'maria', 'rol': 'CONSULTA',
            'password': 'Clave-Segura-2026', 'confirmar': 'Clave-Segura-2026'})
        self.assertRedirects(r, '/cuentas/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [('POST', 'usuarios/', {
            'personal': 7, 'username': 'maria', 'rol': 'CONSULTA',
            'password': 'Clave-Segura-2026'})])
        self.assertIn('Cuenta «maria» creada para María López Ruiz con el rol Consulta.',
                      self.mensajes(r))

    def test_campos_obligatorios_vacios_no_llaman_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/nuevo/', {})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Este campo es obligatorio.', count=4)

    def test_contrasenas_distintas_no_llaman_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/nuevo/', {
            'personal': '7', 'username': 'maria', 'rol': 'CONSULTA',
            'password': 'Clave-Segura-2026', 'confirmar': 'otra-cosa'})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Las contraseñas no coinciden.')

    def test_error_de_la_api_en_un_campo_conserva_lo_escrito_pero_no_la_contrasena(self):
        self.api.respuestas[('POST', 'usuarios/')] = ApiError(
            400, {'username': 'Ya existe una cuenta con ese usuario.'})
        r = self.client.post('/cuentas/usuarios/nuevo/', {
            'personal': '7', 'username': 'maria', 'rol': 'CONSULTA',
            'password': 'Clave-Segura-2026', 'confirmar': 'Clave-Segura-2026'})
        self.assertContains(r, 'Ya existe una cuenta con ese usuario.')
        self.assertContains(r, 'value="maria"')
        self.assertNotContains(r, 'Clave-Segura-2026')

    def test_error_de_contrasena_debil_va_en_su_campo(self):
        self.api.respuestas[('POST', 'usuarios/')] = ApiError(
            400, {'password': 'Esta contraseña es demasiado común.'})
        r = self.client.post('/cuentas/usuarios/nuevo/', {
            'personal': '7', 'username': 'maria', 'rol': 'CONSULTA',
            'password': '12345678', 'confirmar': '12345678'})
        self.assertContains(r, 'Esta contraseña es demasiado común.')

    def test_error_500_no_rompe_el_formulario(self):
        self.api.respuestas[('POST', 'usuarios/')] = ApiError(500, {'detalle': 'Error 500 en el servidor.'})
        r = self.client.post('/cuentas/usuarios/nuevo/', {
            'personal': '7', 'username': 'maria', 'rol': 'CONSULTA',
            'password': 'Clave-Segura-2026', 'confirmar': 'Clave-Segura-2026'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Error 500 en el servidor.')

    def test_sin_empleados_disponibles_lo_dice(self):
        self.api.respuestas[('GET', 'usuarios/empleados-disponibles/')] = []
        r = self.client.get('/cuentas/usuarios/nuevo/')
        self.assertContains(r, 'No hay empleados activos sin cuenta')

    def test_con_50_empleados_avisa_que_use_el_buscador(self):
        self.api.respuestas[('GET', 'usuarios/empleados-disponibles/')] = [
            dict(EMPLEADO, num=i, numero_empleado='E%03d' % i) for i in range(50)]
        r = self.client.get('/cuentas/usuarios/nuevo/')
        self.assertContains(r, 'primeros 50')


class EdicionTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/2/')] = cuenta()

    def test_manda_solo_el_rol_y_el_motivo(self):
        self.api.respuestas[('PATCH', 'usuarios/2/')] = cuenta(rol='ADMIN')
        r = self.client.post('/cuentas/usuarios/2/editar/',
                             {'rol': 'ADMIN', 'motivo': 'Pasa a administrar'})
        self.assertRedirects(r, '/cuentas/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(),
                         [('PATCH', 'usuarios/2/', {'rol': 'ADMIN', 'motivo': 'Pasa a administrar'})])

    def test_sin_cambio_no_llama_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/2/editar/', {'rol': 'CONSULTA', 'motivo': 'x'})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'No hiciste ningún cambio.')

    def test_sin_motivo_no_llama_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/2/editar/', {'rol': 'ADMIN', 'motivo': ' '})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Indica el motivo del cambio.')

    def test_la_propia_cuenta_no_se_edita(self):
        self.entrar(num=2)
        r = self.client.get('/cuentas/usuarios/2/editar/')
        self.assertRedirects(r, '/cuentas/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [])

    def test_cuenta_inexistente_es_404(self):
        self.api.respuestas[('GET', 'usuarios/9/')] = ApiError(404, {'detail': 'No encontrado.'})
        self.assertEqual(self.client.get('/cuentas/usuarios/9/editar/').status_code, 404)

    def test_rechazo_de_la_api_se_muestra(self):
        self.api.respuestas[('PATCH', 'usuarios/2/')] = ApiError(
            400, {'detalle': 'Debe quedar al menos un Administrador activo.'})
        r = self.client.post('/cuentas/usuarios/2/editar/', {'rol': 'ADMIN', 'motivo': 'x'})
        self.assertContains(r, 'Debe quedar al menos un Administrador activo.')


class EstadoTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_desactivar_manda_activo_false_y_motivo(self):
        self.api.respuestas[('PATCH', 'usuarios/2/')] = cuenta(activo=False)
        r = self.client.post('/cuentas/usuarios/2/estado/', {'activar': '0', 'motivo': 'Ya no trabaja aquí'})
        self.assertRedirects(r, '/cuentas/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(),
                         [('PATCH', 'usuarios/2/', {'activo': False, 'motivo': 'Ya no trabaja aquí'})])
        self.assertIn('Cuenta «maria» desactivada.', self.mensajes(r))

    def test_activar_manda_activo_true(self):
        self.api.respuestas[('PATCH', 'usuarios/2/')] = cuenta()
        self.client.post('/cuentas/usuarios/2/estado/', {'activar': '1', 'motivo': 'Regresa'})
        self.assertEqual(self.api.escrituras()[0][2]['activo'], True)

    def test_sin_motivo_no_llama_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/2/estado/', {'activar': '0', 'motivo': ''})
        self.assertEqual(self.api.escrituras(), [])
        self.assertIn('Indica el motivo del cambio.', self.mensajes(r))

    def test_la_propia_cuenta_no_se_desactiva(self):
        self.entrar(num=2)
        r = self.client.post('/cuentas/usuarios/2/estado/', {'activar': '0', 'motivo': 'x'})
        self.assertEqual(self.api.escrituras(), [])
        self.assertIn('No puedes desactivar tu propia cuenta.', self.mensajes(r))

    def test_rechazo_de_la_api_se_muestra_como_aviso(self):
        self.api.respuestas[('PATCH', 'usuarios/2/')] = ApiError(
            400, {'detalle': 'Debe quedar al menos un Administrador activo.'})
        r = self.client.post('/cuentas/usuarios/2/estado/', {'activar': '0', 'motivo': 'x'})
        self.assertIn('Debe quedar al menos un Administrador activo.', self.mensajes(r))

    def test_no_regresa_a_otro_sitio(self):
        self.api.respuestas[('PATCH', 'usuarios/2/')] = cuenta()
        r = self.client.post('/cuentas/usuarios/2/estado/', {
            'activar': '0', 'motivo': 'x', 'volver': 'https://otro.example/robo'})
        self.assertRedirects(r, '/cuentas/', fetch_redirect_response=False)

    def test_solo_acepta_post(self):
        self.assertEqual(self.client.get('/cuentas/usuarios/2/estado/').status_code, 405)


class RestablecerTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/2/')] = cuenta()

    def test_manda_contrasena_y_motivo(self):
        r = self.client.post('/cuentas/usuarios/2/password/', {
            'password': 'Nueva-Clave-2026', 'confirmar': 'Nueva-Clave-2026',
            'motivo': 'Olvidó su contraseña'})
        self.assertRedirects(r, '/cuentas/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [(
            'POST', 'usuarios/2/restablecer-password/',
            {'password': 'Nueva-Clave-2026', 'motivo': 'Olvidó su contraseña'})])

    def test_sin_motivo_no_llama_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/2/password/', {
            'password': 'Nueva-Clave-2026', 'confirmar': 'Nueva-Clave-2026', 'motivo': ''})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Este campo es obligatorio.')

    def test_contrasenas_distintas_no_llaman_a_la_api(self):
        r = self.client.post('/cuentas/usuarios/2/password/', {
            'password': 'Nueva-Clave-2026', 'confirmar': 'otra', 'motivo': 'x'})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Las contraseñas no coinciden.')

    def test_la_contrasena_no_se_vuelve_a_mostrar(self):
        self.api.respuestas[('POST', 'usuarios/2/restablecer-password/')] = ApiError(
            400, {'password': 'Esta contraseña es demasiado corta.'})
        r = self.client.post('/cuentas/usuarios/2/password/', {
            'password': 'Corta-1', 'confirmar': 'Corta-1', 'motivo': 'x'})
        self.assertContains(r, 'Esta contraseña es demasiado corta.')
        self.assertNotContains(r, 'Corta-1')

    def test_la_propia_cuenta_se_cambia_desde_perfil(self):
        self.entrar(num=2)
        r = self.client.get('/cuentas/usuarios/2/password/')
        self.assertRedirects(r, '/cuentas/perfil/', fetch_redirect_response=False)


class PerfilTests(BaseCuentas):
    def setUp(self):
        super().setUp()
        self.api.respuestas[('GET', 'auth/yo/')] = {
            'num': 1, 'username': 'admin', 'empleado': 'Fernando Estrada',
            'rol': 'ADMIN', 'rol_nombre': 'Administrador'}

    def test_consulta_tambien_abre_su_perfil(self):
        self.entrar('CONSULTA')
        r = self.client.get('/cuentas/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Fernando Estrada')
        self.assertContains(r, 'admin')

    def test_si_la_api_no_responde_muestra_los_datos_de_la_sesion(self):
        self.entrar()
        self.api.respuestas[('GET', 'auth/yo/')] = ApiError(0, {'detalle': 'sin conexión'})
        r = self.client.get('/cuentas/perfil/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Fernando Estrada')

    def test_cambio_correcto_cierra_la_sesion_y_pide_entrar_de_nuevo(self):
        self.entrar()
        r = self.client.post('/cuentas/perfil/', {
            'password_actual': 'Vieja-Clave-2026', 'password': 'Nueva-Clave-2026',
            'confirmar': 'Nueva-Clave-2026'})
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [(
            'POST', 'auth/cambiar-password/',
            {'password_actual': 'Vieja-Clave-2026', 'password': 'Nueva-Clave-2026'})])
        self.assertNotIn('api_token', self.client.session)
        entrada = self.client.get('/cuentas/login/')
        self.assertContains(entrada, 'Tu contraseña se cambió')

    def test_contrasena_actual_incorrecta_conserva_la_sesion(self):
        self.entrar()
        self.api.respuestas[('POST', 'auth/cambiar-password/')] = ApiError(
            400, {'password_actual': 'La contraseña actual no es correcta.'})
        r = self.client.post('/cuentas/perfil/', {
            'password_actual': 'mal', 'password': 'Nueva-Clave-2026',
            'confirmar': 'Nueva-Clave-2026'})
        self.assertContains(r, 'La contraseña actual no es correcta.')
        self.assertNotContains(r, 'Nueva-Clave-2026')
        self.assertIn('api_token', self.client.session)

    def test_contrasenas_distintas_no_llaman_a_la_api(self):
        self.entrar()
        r = self.client.post('/cuentas/perfil/', {
            'password_actual': 'x', 'password': 'Nueva-Clave-2026', 'confirmar': 'otra'})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Las contraseñas no coinciden.')

    def test_campos_vacios_no_llaman_a_la_api(self):
        self.entrar()
        r = self.client.post('/cuentas/perfil/', {})
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Este campo es obligatorio.', count=2)


class PermisosTests(BaseCuentas):
    def test_consulta_no_abre_usuarios_y_roles_ni_escribiendo_la_url(self):
        self.entrar('CONSULTA')
        for ruta in ('/cuentas/', '/cuentas/usuarios/nuevo/', '/cuentas/usuarios/2/editar/',
                     '/cuentas/usuarios/2/password/'):
            r = self.client.get(ruta)
            self.assertEqual(r.status_code, 302, ruta)
            self.assertIn('dashboard', r.url, ruta)
        r = self.client.post('/cuentas/usuarios/2/estado/', {'activar': '0', 'motivo': 'x'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.api.escrituras(), [])

    def test_sin_sesion_pide_login(self):
        r = self.client.get('/cuentas/')
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)
