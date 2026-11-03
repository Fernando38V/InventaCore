"""Pruebas de la API: sesión, permisos por rol, catálogos, personal, usuarios."""
import json
from datetime import timedelta

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from auditoria.models import Bitacora
from catalogos.models import Categoria
from personal.models import Personal
from usuarios.models import Rol, Usuario

CLAVE = 'Contr4sena-Segura!'


def crear_usuario(username, rol, numero):
    personal = Personal.objects.create(
        numero_empleado=numero, nombre_pila=username.title(), primer_apellido='Prueba',
        puesto='Prueba', departamento_id='DEP-INF')
    return Usuario.objects.create_user(
        username=username, password=CLAVE, personal=personal, rol=Rol.objects.get(pk=rol))


class BaseAPI(APITestCase):
    def setUp(self):
        self.admin = crear_usuario('admin', 'ADMIN', 'E001')
        self.obs = crear_usuario('obs', 'CONSULTA', 'E002')

    def cliente(self, usuario):
        c = APIClient()
        token, _ = Token.objects.get_or_create(user=usuario)
        c.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        return c


class SesionTests(BaseAPI):
    def test_login_correcto_devuelve_token_y_perfil(self):
        r = APIClient().post('/api/auth/login/', {'username': 'admin', 'password': CLAVE})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['usuario']['rol'], 'ADMIN')
        self.assertTrue(Token.objects.filter(key=r.data['token']).exists())

    def test_login_incorrecto(self):
        r = APIClient().post('/api/auth/login/', {'username': 'admin', 'password': 'mal'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, {'detalle': 'Usuario o contraseña incorrectos.'})

    def test_cuenta_dada_de_baja_no_entra(self):
        self.obs.activo = False
        self.obs.save()
        r = APIClient().post('/api/auth/login/', {'username': 'obs', 'password': CLAVE})
        self.assertEqual(r.status_code, 400)

    def test_un_nuevo_login_invalida_el_token_anterior(self):
        c = APIClient()
        t1 = c.post('/api/auth/login/', {'username': 'admin', 'password': CLAVE}).data['token']
        c.post('/api/auth/login/', {'username': 'admin', 'password': CLAVE})
        c.credentials(HTTP_AUTHORIZATION='Token ' + t1)
        self.assertEqual(c.get('/api/auth/yo/').status_code, 401)

    def test_sin_token_no_se_entra(self):
        self.assertEqual(APIClient().get('/api/categorias/').status_code, 401)

    def test_el_token_vence_a_las_24_horas(self):
        c = self.cliente(self.admin)
        Token.objects.filter(user=self.admin).update(created=timezone.now() - timedelta(hours=25))
        self.assertEqual(c.get('/api/auth/yo/').status_code, 401)

    def test_logout_cierra_la_sesion(self):
        c = self.cliente(self.admin)
        self.assertEqual(c.post('/api/auth/logout/').status_code, 204)
        self.assertEqual(c.get('/api/auth/yo/').status_code, 401)

    def test_cada_quien_cambia_su_propia_contrasena_incluido_consulta(self):
        c = self.cliente(self.obs)
        r = c.post('/api/auth/cambiar-password/',
                   {'password_actual': CLAVE, 'password': 'Otra-Clave-9876'})
        self.assertEqual(r.status_code, 204)
        self.obs.refresh_from_db()
        self.assertTrue(self.obs.check_password('Otra-Clave-9876'))

    def test_cambiar_contrasena_pide_la_actual(self):
        r = self.cliente(self.obs).post(
            '/api/auth/cambiar-password/', {'password_actual': 'mal', 'password': 'Otra-Clave-9876'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('password_actual', r.data)


class PermisosPorRolTests(BaseAPI):
    def test_consulta_consulta_todo(self):
        c = self.cliente(self.obs)
        for ruta in ('categorias', 'tipos-articulo', 'ubicaciones', 'departamentos',
                     'personal', 'origenes', 'estados-operativos', 'estados-registro',
                     'tipos-movimiento'):
            self.assertEqual(c.get('/api/%s/' % ruta).status_code, 200, ruta)

    def test_consulta_no_escribe(self):
        c = self.cliente(self.obs)
        r = c.post('/api/categorias/', {'nombre': 'LIBROS'})
        self.assertEqual(r.status_code, 403)
        r = c.patch('/api/categorias/CAT-001/', {'nombre': 'X', 'motivo': 'x'})
        self.assertEqual(r.status_code, 403)

    def test_consulta_no_ve_ni_administra_usuarios(self):
        c = self.cliente(self.obs)
        self.assertEqual(c.get('/api/usuarios/').status_code, 403)

    def test_nadie_borra(self):
        r = self.cliente(self.admin).delete('/api/categorias/CAT-001/')
        self.assertEqual(r.status_code, 405)


class CatalogosAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.c = self.cliente(self.admin)

    def crear_categoria(self, nombre='OTROS EQUIPOS'):
        r = self.c.post('/api/categorias/', {'nombre': nombre})
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_agregar_categoria_genera_codigo_y_queda_en_bitacora(self):
        cat = self.crear_categoria('LIBROS')
        self.assertEqual(cat['codigo'], 'CAT-001')
        b = Bitacora.objects.get(tabla_afectada='categoria', registro_id='CAT-001')
        self.assertEqual((b.accion, b.usuario), ('INSERT', self.admin))
        self.assertEqual(json.loads(b.valor_nuevo)['nombre'], 'LIBROS')

    def test_el_codigo_que_manda_el_cliente_se_ignora(self):
        r = self.c.post('/api/categorias/', {'codigo': 'CAT-999', 'nombre': 'LIBROS'})
        self.assertEqual(r.data['codigo'], 'CAT-001')

    def test_los_codigos_siguen_la_serie(self):
        self.crear_categoria('A')
        self.assertEqual(self.crear_categoria('B')['codigo'], 'CAT-002')

    def test_editar_exige_motivo(self):
        self.crear_categoria()
        r = self.c.patch('/api/categorias/CAT-001/', {'descripcion': 'x'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, {'motivo': 'Indique el motivo del cambio.'})

    def test_editar_guarda_solo_lo_que_cambio(self):
        self.crear_categoria()
        r = self.c.patch('/api/categorias/CAT-001/',
                         {'descripcion': 'Nueva', 'motivo': 'Aclaración'})
        self.assertEqual(r.status_code, 200)
        b = Bitacora.objects.filter(accion='UPDATE').get()
        self.assertEqual(json.loads(b.valor_anterior), {'descripcion': None})
        self.assertEqual(json.loads(b.valor_nuevo), {'descripcion': 'Nueva'})
        self.assertEqual(b.motivo, 'Aclaración')

    def test_el_codigo_no_cambia(self):
        self.crear_categoria()
        self.c.patch('/api/categorias/CAT-001/', {'codigo': 'CAT-099', 'descripcion': 'x', 'motivo': 'm'})
        self.assertTrue(Bitacora.objects.filter(registro_id='CAT-001', accion='UPDATE').exists())
        self.assertFalse(Categoria.objects.filter(pk='CAT-099').exists())

    def test_nombre_repetido_da_mensaje_por_campo(self):
        self.crear_categoria()
        r = self.c.post('/api/categorias/', {'nombre': 'OTROS EQUIPOS'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(list(r.data), ['nombre'])
        self.assertIsInstance(r.data['nombre'], str)

    def test_desactivar_en_vez_de_borrar(self):
        self.crear_categoria()
        r = self.c.patch('/api/categorias/CAT-001/', {'activo': False, 'motivo': 'Ya no se usa'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.data['activo'])

    def test_filtrar_catalogo_por_activo(self):
        self.crear_categoria('A')
        self.crear_categoria('B')
        self.c.patch('/api/categorias/CAT-001/', {'activo': False, 'motivo': 'm'})
        r = self.c.get('/api/categorias/?activo=true')
        self.assertEqual(r.data['count'], 1)

    def test_tipo_de_articulo_por_categoria(self):
        self.crear_categoria('MUEBLES')
        self.crear_categoria('AUDIOVISUAL')
        r = self.c.post('/api/tipos-articulo/', {'nombre': 'Cámara', 'categoria': 'CAT-002'})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['codigo'], 'TIP-001')
        self.assertEqual(r.data['categoria_nombre'], 'AUDIOVISUAL')
        r = self.c.get('/api/tipos-articulo/?categoria=CAT-001')
        self.assertEqual(r.data['count'], 0)
        r = self.c.get('/api/tipos-articulo/?categoria=CAT-002')
        self.assertEqual(r.data['count'], 1)

    def test_tipo_sin_categoria_se_rechaza(self):
        r = self.c.post('/api/tipos-articulo/', {'nombre': 'Cámara'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('categoria', r.data)

    def test_ubicacion_no_localizado_no_se_desactiva_ni_renombra(self):
        r = self.c.patch('/api/ubicaciones/UBI-NOLOC/', {'activo': False, 'motivo': 'm'})
        self.assertEqual(r.status_code, 400)
        r = self.c.patch('/api/ubicaciones/UBI-NOLOC/', {'nombre': 'Otra', 'motivo': 'm'})
        self.assertEqual(r.status_code, 400)

    def test_agregar_ubicacion(self):
        r = self.c.post('/api/ubicaciones/', {'nombre': 'Biblioteca'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['codigo'], 'UBI-001')
        self.assertEqual(self.c.get('/api/ubicaciones/').data['count'], 5)

    def test_ubicacion_con_responsable_dado_de_baja_se_rechaza(self):
        self.obs.personal.activo = False
        self.obs.personal.save()
        r = self.c.patch('/api/ubicaciones/UBI-OFI/',
                         {'responsable': self.obs.personal.pk, 'motivo': 'm'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('responsable', r.data)


class DepartamentosYPersonalAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.c = self.cliente(self.admin)

    def test_agregar_departamento(self):
        r = self.c.post('/api/departamentos/',
                        {'nombre': 'Dirección', 'descripcion': 'Dirección del plantel'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['codigo'], 'DEP-001')
        self.assertTrue(Bitacora.objects.filter(tabla_afectada='departamento').exists())

    def test_departamento_desactivado_no_acepta_personal_nuevo(self):
        self.c.patch('/api/departamentos/DEP-INF/', {'activo': False, 'motivo': 'm'})
        r = self.c.post('/api/personal/', {
            'numero_empleado': 'E100', 'nombre_pila': 'Ana', 'primer_apellido': 'López',
            'puesto': 'Docente', 'departamento': 'DEP-INF'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('departamento', r.data)

    def test_alta_de_empleado_y_busqueda(self):
        r = self.c.post('/api/personal/', {
            'numero_empleado': 'E100', 'nombre_pila': 'Zulema', 'primer_apellido': 'Mitre',
            'segundo_apellido': 'Padilla', 'puesto': 'Docente', 'departamento': 'DEP-INF'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['nombre_completo'], 'Zulema Mitre Padilla')
        self.assertEqual(r.data['articulos_a_cargo'], 0)
        self.assertEqual(self.c.get('/api/personal/?q=mitre').data['count'], 1)
        self.assertEqual(self.c.get('/api/personal/?q=E100').data['count'], 1)

    def test_numero_de_empleado_repetido(self):
        r = self.c.post('/api/personal/', {
            'numero_empleado': 'E001', 'nombre_pila': 'X', 'primer_apellido': 'Y',
            'puesto': 'Z', 'departamento': 'DEP-INF'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('numero_empleado', r.data)

    def test_la_paginacion_es_de_10(self):
        for n in range(15):
            Personal.objects.create(
                numero_empleado='P%d' % n, nombre_pila='N', primer_apellido='A',
                puesto='x', departamento_id='DEP-INF')
        r = self.c.get('/api/personal/')
        self.assertEqual(len(r.data['results']), 10)
        self.assertEqual(r.data['count'], 17)


class UsuariosAPITests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.c = self.cliente(self.admin)
        self.nuevo_personal = Personal.objects.create(
            numero_empleado='E050', nombre_pila='Laura', primer_apellido='Gil',
            puesto='Contadora', departamento_id='DEP-INF')

    def test_el_admin_crea_una_cuenta_y_la_contrasena_no_se_expone(self):
        r = self.c.post('/api/usuarios/', {
            'username': 'laura', 'password': CLAVE, 'personal': self.nuevo_personal.pk,
            'rol': 'ADMIN'})
        self.assertEqual(r.status_code, 201)
        self.assertNotIn('password', r.data)
        self.assertTrue(Usuario.objects.get(username='laura').check_password(CLAVE))
        b = Bitacora.objects.get(tabla_afectada='usuario', registro_id=str(r.data['num']))
        self.assertNotIn('password', b.valor_nuevo)

    def test_contrasena_debil_se_rechaza(self):
        r = self.c.post('/api/usuarios/', {
            'username': 'laura', 'password': '123', 'personal': self.nuevo_personal.pk,
            'rol': 'CONSULTA'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data)

    def test_un_empleado_una_cuenta(self):
        r = self.c.post('/api/usuarios/', {
            'username': 'otro', 'password': CLAVE, 'personal': self.admin.personal.pk,
            'rol': 'CONSULTA'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('personal', r.data)

    def test_no_se_puede_quitar_al_ultimo_administrador(self):
        r = self.c.patch('/api/usuarios/%d/' % self.admin.pk, {'activo': False, 'motivo': 'm'})
        self.assertEqual(r.status_code, 400)
        r = self.c.patch('/api/usuarios/%d/' % self.admin.pk, {'rol': 'CONSULTA', 'motivo': 'm'})
        self.assertEqual(r.status_code, 400)

    def test_con_dos_administradores_se_puede_dar_de_baja_a_uno(self):
        otro = crear_usuario('otro', 'ADMIN', 'E060')
        r = self.c.patch('/api/usuarios/%d/' % otro.pk, {'activo': False, 'motivo': 'Baja'})
        self.assertEqual(r.status_code, 200)

    def test_cambiar_rol_a_consulta(self):
        r = self.c.patch('/api/usuarios/%d/' % self.obs.pk, {'rol': 'ADMIN', 'motivo': 'Promoción'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['rol'], 'ADMIN')

    def test_restablecer_contrasena_de_otro_cierra_sus_sesiones(self):
        co = self.cliente(self.obs)
        r = self.c.post('/api/usuarios/%d/restablecer-password/' % self.obs.pk,
                        {'password': 'Nueva-Clave-4321', 'motivo': 'Olvidó la suya'})
        self.assertEqual(r.status_code, 204)
        self.obs.refresh_from_db()
        self.assertTrue(self.obs.check_password('Nueva-Clave-4321'))
        self.assertEqual(co.get('/api/auth/yo/').status_code, 401)
        b = Bitacora.objects.filter(tabla_afectada='usuario', accion='UPDATE').last()
        self.assertNotIn('Nueva-Clave', b.valor_nuevo)
        self.assertEqual(b.motivo, 'Olvidó la suya')

    def test_no_se_edita_el_nombre_de_usuario(self):
        self.c.patch('/api/usuarios/%d/' % self.obs.pk, {'username': 'hack', 'motivo': 'm'})
        self.obs.refresh_from_db()
        self.assertEqual(self.obs.username, 'obs')


class UsuariosAdministracionTests(BaseAPI):
    """Filtros, roles, empleados disponibles, nombre de usuario y cierre de sesiones."""

    def setUp(self):
        super().setUp()
        self.c = self.cliente(self.admin)
        self.libre = Personal.objects.create(
            numero_empleado='E070', nombre_pila='Marta', primer_apellido='Ruiz',
            puesto='Docente', departamento_id='DEP-INF')

    def test_roles_solo_para_el_administrador(self):
        r = self.c.get('/api/roles/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual({x['clave'] for x in r.data}, {'ADMIN', 'CONSULTA'})
        self.assertEqual(self.cliente(self.obs).get('/api/roles/').status_code, 403)

    def test_empleados_disponibles_excluye_a_los_que_ya_tienen_cuenta(self):
        r = self.c.get('/api/usuarios/empleados-disponibles/')
        self.assertEqual(r.status_code, 200)
        nums = {x['num'] for x in r.data}
        self.assertIn(self.libre.num, nums)
        self.assertNotIn(self.admin.personal.num, nums)
        r = self.c.get('/api/usuarios/empleados-disponibles/?q=marta')
        self.assertEqual([x['numero_empleado'] for x in r.data], ['E070'])

    def test_filtros_de_la_lista(self):
        r = self.c.get('/api/usuarios/?rol=CONSULTA')
        self.assertEqual([u['username'] for u in r.data['results']], ['obs'])
        r = self.c.get('/api/usuarios/?q=admin')
        self.assertEqual([u['username'] for u in r.data['results']], ['admin'])
        r = self.c.get('/api/usuarios/?activo=false')
        self.assertEqual(r.data['count'], 0)

    def test_la_lista_trae_numero_de_empleado_y_puesto(self):
        r = self.c.get('/api/usuarios/?q=obs')
        u = r.data['results'][0]
        self.assertEqual(u['numero_empleado'], 'E002')
        self.assertEqual(u['puesto'], 'Prueba')

    def test_nombre_de_usuario_invalido(self):
        for malo in ('ab', 'con espacio', 'a/b'):
            r = self.c.post('/api/usuarios/', {
                'username': malo, 'password': CLAVE, 'personal': self.libre.pk,
                'rol': 'CONSULTA'})
            self.assertEqual(r.status_code, 400, malo)
            self.assertIn('username', r.data)

    def test_contrasena_parecida_al_usuario_se_rechaza(self):
        r = self.c.post('/api/usuarios/', {
            'username': 'marta.ruiz', 'password': 'marta.ruiz1', 'personal': self.libre.pk,
            'rol': 'CONSULTA'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.data)

    def test_dar_de_baja_o_cambiar_rol_cierra_sus_sesiones(self):
        co = self.cliente(self.obs)
        self.assertEqual(co.get('/api/auth/yo/').status_code, 200)
        r = self.c.patch('/api/usuarios/%d/' % self.obs.pk, {'activo': False, 'motivo': 'Baja'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(co.get('/api/auth/yo/').status_code, 401)

    def test_editar_sin_cambiar_activo_ni_rol_no_cierra_sesion(self):
        co = self.cliente(self.obs)
        self.c.patch('/api/usuarios/%d/' % self.obs.pk, {'rol': 'CONSULTA', 'motivo': 'Igual'})
        self.assertEqual(co.get('/api/auth/yo/').status_code, 200)

    def test_consulta_no_administra_usuarios(self):
        co = self.cliente(self.obs)
        self.assertEqual(co.get('/api/usuarios/').status_code, 403)
        self.assertEqual(co.get('/api/usuarios/empleados-disponibles/').status_code, 403)
