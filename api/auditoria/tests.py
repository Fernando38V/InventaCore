from django.db.models import ProtectedError
from django.test import TestCase

from api.inmutable import RegistroInmutable
from auditoria.models import Bitacora
from personal.models import Personal
from usuarios.models import Rol, Usuario


class BitacoraTests(TestCase):
    def setUp(self):
        personal = Personal.objects.create(
            numero_empleado='E001', nombre_pila='Ana', primer_apellido='López',
            puesto='Jefa', departamento_id='DEP-INF')
        self.usuario = Usuario.objects.create_user(
            username='ana', password='Contr4sena-Segura!', personal=personal,
            rol=Rol.objects.get(pk='ADMIN'))
        self.registro = Bitacora.objects.create(
            modulo='articulos', accion='UPDATE', tabla_afectada='articulo',
            registro_id='1', valor_anterior='{"estado_operativo": "UTIL"}',
            valor_nuevo='{"estado_operativo": "OBS"}', motivo='Revisión',
            usuario=self.usuario)

    def test_se_guarda_con_fecha_y_usuario(self):
        self.assertIsNotNone(self.registro.fecha_hora)
        self.assertEqual(self.registro.usuario, self.usuario)

    def test_valores_y_motivo_pueden_faltar(self):
        Bitacora.objects.create(
            modulo='usuarios', accion='INSERT', tabla_afectada='usuario',
            registro_id='2', usuario=self.usuario)

    def test_no_se_edita(self):
        self.registro.motivo = 'Otro'
        with self.assertRaises(RegistroInmutable):
            self.registro.save()

    def test_no_se_borra(self):
        with self.assertRaises(RegistroInmutable):
            self.registro.delete()

    def test_no_se_edita_ni_borra_en_masa(self):
        with self.assertRaises(RegistroInmutable):
            Bitacora.objects.update(motivo='x')
        with self.assertRaises(RegistroInmutable):
            Bitacora.objects.all().delete()
        self.assertEqual(Bitacora.objects.count(), 1)

    def test_no_se_borra_al_usuario_con_bitacora(self):
        with self.assertRaises(ProtectedError):
            self.usuario.delete()
