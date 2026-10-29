from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from api.inmutable import RegistroInmutable
from articulos.tests import crear, crear_personal
from movimientos.models import Movimiento, Resguardo
from personal.models import Personal
from usuarios.models import Rol, Usuario


class BaseMovimientos(TestCase):
    def setUp(self):
        self.ana = crear_personal('E001')
        self.beto = Personal.objects.create(
            numero_empleado='E002', nombre_pila='Beto', primer_apellido='Ruiz',
            puesto='Docente', departamento_id='DEP-INF')
        self.usuario = Usuario.objects.create_user(
            username='admin', password='Contr4sena-Segura!', personal=self.ana,
            rol=Rol.objects.get(pk='ADMIN'))
        self.articulo = crear(resguardante=self.ana)

    def mov(self, folio='MOV-0001', tipo='REUB', **cambios):
        datos = dict(
            folio=folio, tipo_movimiento_id=tipo, motivo='Prueba', articulo=self.articulo,
            ubicacion_origen_id='UBI-OFI', ubicacion_destino_id='UBI-LAB1',
            resguardante_anterior=self.ana, resguardante_nuevo=self.ana,
            usuario=self.usuario)
        datos.update(cambios)
        if 'requiere_resguardo' not in datos:
            nuevo, anterior = datos['resguardante_nuevo'], datos['resguardante_anterior']
            datos['requiere_resguardo'] = (
                tipo == 'ALTA' or (tipo == 'REUB' and nuevo != anterior))
        return Movimiento.objects.create(**datos)

    def rechaza(self, **cambios):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.mov(**cambios)


class MovimientoValidosTests(BaseMovimientos):
    def test_alta(self):
        self.mov(tipo='ALTA', ubicacion_origen_id=None, ubicacion_destino_id='UBI-OFI',
                 resguardante_anterior=None)

    def test_reubicacion_solo_ubicacion(self):
        self.mov()

    def test_cambio_solo_de_resguardante(self):
        self.mov(ubicacion_destino_id='UBI-OFI', resguardante_nuevo=self.beto)

    def test_cambio_combinado(self):
        self.mov(resguardante_nuevo=self.beto)

    def test_reparacion_y_retorno(self):
        self.mov('MOV-0001', 'REPA', ubicacion_destino_id='UBI-OFI')
        self.mov('MOV-0002', 'RETE', ubicacion_destino_id='UBI-LAB1')

    def test_el_movimiento_registra_cuando_se_capturo(self):
        self.assertIsNotNone(self.mov().fecha_registro)


class MovimientoRechazadosTests(BaseMovimientos):
    def test_alta_con_origen(self):
        self.rechaza(tipo='ALTA', resguardante_anterior=None)

    def test_alta_con_resguardante_anterior(self):
        self.rechaza(tipo='ALTA', ubicacion_origen_id=None)

    def test_reub_sin_ningun_cambio(self):
        self.rechaza(ubicacion_destino_id='UBI-OFI')

    def test_reub_sin_origen(self):
        self.rechaza(ubicacion_origen_id=None)

    def test_reub_sin_resguardante_anterior(self):
        self.rechaza(resguardante_anterior=None)

    def test_reparacion_cambiando_de_resguardante(self):
        self.rechaza(tipo='REPA', resguardante_nuevo=self.beto)

    def test_folio_repetido(self):
        self.mov()
        self.rechaza()


class MovimientoRequiereResguardoTests(BaseMovimientos):
    def test_alta_requiere(self):
        m = self.mov(tipo='ALTA', ubicacion_origen_id=None, ubicacion_destino_id='UBI-OFI',
                     resguardante_anterior=None)
        self.assertTrue(m.requiere_resguardo)

    def test_cambio_de_resguardante_requiere(self):
        self.assertTrue(self.mov(resguardante_nuevo=self.beto).requiere_resguardo)

    def test_solo_ubicacion_no_requiere(self):
        self.assertFalse(self.mov().requiere_resguardo)

    def test_reparacion_no_requiere(self):
        self.assertFalse(self.mov(tipo='REPA').requiere_resguardo)


class MovimientoRegla016Tests(BaseMovimientos):
    def test_reub_con_cambio_de_persona_sin_marcar_se_rechaza(self):
        self.rechaza(resguardante_nuevo=self.beto, requiere_resguardo=False)

    def test_reub_sin_cambio_de_persona_marcado_se_rechaza(self):
        self.rechaza(requiere_resguardo=True)

    def test_repa_o_rete_marcados_se_rechazan(self):
        self.rechaza(tipo='REPA', requiere_resguardo=True)
        self.rechaza(tipo='RETE', requiere_resguardo=True)

    def test_baja_es_un_movimiento_sin_resguardo(self):
        self.mov(tipo='BAJA', ubicacion_destino_id='UBI-OFI')
        self.rechaza(folio='MOV-0002', tipo='BAJA', ubicacion_destino_id='UBI-OFI',
                     requiere_resguardo=True)


class MovimientoInmutableTests(BaseMovimientos):
    def test_no_se_edita(self):
        m = self.mov()
        m.motivo = 'Cambiado'
        with self.assertRaises(RegistroInmutable):
            m.save()

    def test_no_se_borra(self):
        m = self.mov()
        with self.assertRaises(RegistroInmutable):
            m.delete()

    def test_no_se_edita_ni_borra_en_masa(self):
        self.mov()
        with self.assertRaises(RegistroInmutable):
            Movimiento.objects.update(motivo='x')
        with self.assertRaises(RegistroInmutable):
            Movimiento.objects.all().delete()
        self.assertEqual(Movimiento.objects.get().motivo, 'Prueba')

    def test_no_se_borra_el_articulo_con_historial(self):
        self.mov()
        with self.assertRaises(ProtectedError):
            self.articulo.delete()

    def test_no_se_borra_al_usuario_que_hizo_un_movimiento(self):
        self.mov()
        with self.assertRaises(ProtectedError):
            self.usuario.delete()


class ResguardoTests(BaseMovimientos):
    def test_un_resguardo_por_movimiento(self):
        m = self.mov(resguardante_nuevo=self.beto)
        Resguardo.objects.create(folio='RES-0001', movimiento=m)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Resguardo.objects.create(folio='RES-0002', movimiento=m)

    def test_la_ruta_del_pdf_puede_faltar_y_llenarse_despues(self):
        r = Resguardo.objects.create(
            folio='RES-0001', movimiento=self.mov(resguardante_nuevo=self.beto))
        self.assertIsNone(r.ruta_pdf)
        r.ruta_pdf = 'resguardos/RES-0001.pdf'
        r.save()
        self.assertEqual(Resguardo.objects.get().ruta_pdf, 'resguardos/RES-0001.pdf')

    def test_no_se_borra(self):
        r = Resguardo.objects.create(
            folio='RES-0001', movimiento=self.mov(resguardante_nuevo=self.beto))
        with self.assertRaises(RegistroInmutable):
            r.delete()

    def test_no_se_borra_un_movimiento_con_resguardo(self):
        m = self.mov(resguardante_nuevo=self.beto)
        Resguardo.objects.create(folio='RES-0001', movimiento=m)
        with self.assertRaises(RegistroInmutable):
            m.delete()

