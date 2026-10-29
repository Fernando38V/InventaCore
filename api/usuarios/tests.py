from io import StringIO

from django.contrib.auth import authenticate
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from personal.models import Personal
from usuarios.models import Rol, Usuario

CLAVE = 'Contr4sena-Segura!'


def crear_personal(numero='E001'):
    return Personal.objects.create(
        numero_empleado=numero, nombre_pila='Ana', primer_apellido='López',
        puesto='Jefa de Informática', departamento_id='DEP-INF')


class RolesInicialesTests(TestCase):
    def test_existen_los_dos_roles_y_no_el_de_contadora(self):
        self.assertEqual(
            set(Rol.objects.values_list('clave', 'nombre')),
            {('ADMIN', 'Administrador'), ('CONSULTA', 'Consulta')})
        self.assertFalse(Rol.objects.filter(pk='CONT').exists())


class UsuarioTests(TestCase):
    def setUp(self):
        self.personal = crear_personal()
        self.admin = Rol.objects.get(pk='ADMIN')
        self.usuario = Usuario.objects.create_user(
            username='ana', password=CLAVE, personal=self.personal, rol=self.admin)

    def test_la_contrasena_se_guarda_con_hash(self):
        self.assertNotEqual(self.usuario.password, CLAVE)
        self.assertNotIn(CLAVE, self.usuario.password)
        self.assertTrue(self.usuario.check_password(CLAVE))

    def test_iniciar_sesion_correcto(self):
        self.assertEqual(authenticate(username='ana', password=CLAVE), self.usuario)

    def test_contrasena_incorrecta(self):
        self.assertIsNone(authenticate(username='ana', password='otra'))

    def test_una_cuenta_dada_de_baja_no_puede_iniciar_sesion(self):
        self.usuario.activo = False
        self.usuario.save()
        self.assertIsNone(authenticate(username='ana', password=CLAVE))

    def test_dar_de_baja_no_borra_la_cuenta(self):
        self.usuario.activo = False
        self.usuario.save()
        self.assertTrue(Usuario.objects.filter(pk=self.usuario.pk).exists())

    def test_un_empleado_tiene_una_sola_cuenta(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create_user(
                username='otra', password=CLAVE, personal=self.personal,
                rol=Rol.objects.get(pk='CONSULTA'))

    def test_el_nombre_de_usuario_es_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.create_user(
                username='ana', password=CLAVE, personal=crear_personal('E002'),
                rol=Rol.objects.get(pk='CONSULTA'))

    def test_no_se_puede_borrar_un_empleado_con_cuenta(self):
        with self.assertRaises(ProtectedError):
            self.personal.delete()

    def test_no_se_puede_borrar_un_rol_en_uso(self):
        with self.assertRaises(ProtectedError):
            self.admin.delete()

    def test_no_se_guarda_el_ultimo_acceso(self):
        with self.assertRaises(FieldDoesNotExist):
            Usuario._meta.get_field('last_login')

    def test_el_login_de_django_funciona_sin_last_login(self):
        # force_login pasa por django.contrib.auth.login(), que antes
        # intentaba guardar last_login.
        self.client.force_login(self.usuario)
        self.assertIn('_auth_user_id', self.client.session)

    def test_propiedades_de_rol(self):
        self.assertTrue(self.usuario.es_administrador)
        self.assertFalse(self.usuario.es_consulta)
        consulta = Usuario.objects.create_user(
            username='laura', password=CLAVE, personal=crear_personal('E002'),
            rol=Rol.objects.get(pk='CONSULTA'))
        self.assertTrue(consulta.es_consulta)
        self.assertFalse(consulta.es_administrador)
        self.assertFalse(self.usuario.es_consulta)

    def test_create_user_exige_usuario_y_contrasena(self):
        with self.assertRaises(ValueError):
            Usuario.objects.create_user('', CLAVE, crear_personal('E003'), self.admin)
        with self.assertRaises(ValueError):
            Usuario.objects.create_user('x', '', crear_personal('E004'), self.admin)


class CrearAdminInicialTests(TestCase):
    def llamar(self, **cambios):
        datos = {
            'username': 'admin', 'password': CLAVE, 'numero_empleado': 'E001',
            'nombre': 'Luis', 'primer_apellido': 'Pérez',
        }
        datos.update(cambios)
        salida = StringIO()
        call_command('crear_admin_inicial', stdout=salida, **datos)
        return salida.getvalue()

    def test_crea_el_empleado_y_el_administrador(self):
        self.llamar()
        usuario = Usuario.objects.get(username='admin')
        self.assertTrue(usuario.es_administrador)
        self.assertEqual(usuario.personal.numero_empleado, 'E001')
        self.assertEqual(usuario.personal.departamento_id, 'DEP-INF')
        self.assertTrue(usuario.check_password(CLAVE))

    def test_el_administrador_creado_puede_iniciar_sesion(self):
        self.llamar()
        self.assertIsNotNone(authenticate(username='admin', password=CLAVE))

    def test_se_niega_si_ya_hay_un_administrador(self):
        self.llamar()
        with self.assertRaises(CommandError):
            self.llamar(username='otro', numero_empleado='E002')
        self.assertEqual(Usuario.objects.count(), 1)

    def test_rechaza_una_contrasena_debil(self):
        with self.assertRaises(CommandError):
            self.llamar(password='123')
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Personal.objects.count(), 0)

    def test_departamento_inexistente_no_deja_nada_creado(self):
        with self.assertRaises(CommandError):
            self.llamar(departamento='DEP-NO-EXISTE')
        self.assertEqual(Usuario.objects.count(), 0)
        self.assertEqual(Personal.objects.count(), 0)
