from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from personal.models import Departamento, Personal


def crear_personal(**extra):
    datos = {
        'numero_empleado': 'E001',
        'nombre_pila': 'Ana',
        'primer_apellido': 'López',
        'segundo_apellido': 'Ruiz',
        'puesto': 'Docente',
        'departamento_id': 'DEP-INF',
    }
    datos.update(extra)
    return Personal.objects.create(**datos)


class DepartamentoInicialTests(TestCase):
    def test_informatica_viene_precargado_y_activo(self):
        departamento = Departamento.objects.get(pk='DEP-INF')
        self.assertEqual(departamento.nombre, 'Informática')
        self.assertTrue(departamento.activo)

    def test_se_pueden_agregar_departamentos(self):
        Departamento.objects.create(codigo='DEP-002', nombre='Dirección', descripcion='Dirección del plantel')
        self.assertEqual(Departamento.objects.count(), 2)

    def test_el_nombre_es_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Departamento.objects.create(codigo='DEP-002', nombre='Informática', descripcion='Repetido')


class PersonalTests(TestCase):
    def test_nombre_completo(self):
        self.assertEqual(crear_personal().nombre_completo, 'Ana López Ruiz')

    def test_nombre_completo_sin_segundo_apellido(self):
        personal = crear_personal(segundo_apellido=None)
        self.assertEqual(personal.nombre_completo, 'Ana López')

    def test_nuevo_empleado_esta_activo(self):
        self.assertTrue(crear_personal().activo)

    def test_el_numero_de_empleado_es_unico(self):
        crear_personal()
        with self.assertRaises(IntegrityError), transaction.atomic():
            crear_personal(nombre_pila='Otra')

    def test_el_consecutivo_interno_se_asigna_solo(self):
        primero = crear_personal()
        segundo = crear_personal(numero_empleado='E002')
        self.assertEqual(segundo.num, primero.num + 1)

    def test_dar_de_baja_no_borra_al_empleado(self):
        personal = crear_personal()
        personal.activo = False
        personal.save()
        self.assertTrue(Personal.objects.filter(pk=personal.pk, activo=False).exists())

    def test_no_se_puede_borrar_un_departamento_con_personal(self):
        crear_personal()
        with self.assertRaises(ProtectedError):
            Departamento.objects.get(pk='DEP-INF').delete()
