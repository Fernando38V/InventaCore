from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from catalogos.models import (
    ContadorFolio,
    Categoria, EstadoOperativo, EstadoRegistro, Origen, TipoArticulo, TipoMovimiento,
    Ubicacion)
from personal.models import Personal


def codigos(modelo):
    return set(modelo.objects.values_list('codigo', flat=True))


class CatalogosInicialesTests(TestCase):
    def test_categorias_y_tipos_arrancan_vacios(self):
        self.assertEqual(Categoria.objects.count(), 0)
        self.assertEqual(TipoArticulo.objects.count(), 0)

    def test_origenes_fijos(self):
        self.assertEqual(codigos(Origen), {'ACT', 'COM', 'ENS'})

    def test_estados_operativos_del_frontend(self):
        self.assertEqual(codigos(EstadoOperativo), {'UTIL', 'OBS', 'NOLOC'})

    def test_estados_de_registro(self):
        self.assertEqual(codigos(EstadoRegistro), {'PEND', 'REG', 'DON'})

    def test_tipos_de_movimiento(self):
        self.assertEqual(codigos(TipoMovimiento), {'ALTA', 'REUB', 'REPA', 'RETE'})

    def test_ya_no_existen_baja_ni_autb(self):
        self.assertFalse(TipoMovimiento.objects.filter(pk='BAJA').exists())
        self.assertFalse(EstadoOperativo.objects.filter(pk='AUTB').exists())

    def test_ubicaciones_de_rf11_mas_no_localizado(self):
        self.assertEqual(codigos(Ubicacion), {'UBI-OFI', 'UBI-LAB1', 'UBI-LAB2', 'UBI-NOLOC'})

    def test_las_ubicaciones_iniciales_estan_activas_y_sin_responsable(self):
        for ubicacion in Ubicacion.objects.all():
            self.assertTrue(ubicacion.activo)
            self.assertIsNone(ubicacion.responsable)

    def test_todo_el_catalogo_inicial_esta_activo(self):
        for modelo in (EstadoOperativo, EstadoRegistro, TipoMovimiento):
            self.assertFalse(modelo.objects.filter(activo=False).exists(), modelo.__name__)


class RestriccionesTests(TestCase):
    def test_el_nombre_de_una_categoria_es_unico(self):
        Categoria.objects.create(codigo='CAT-001', nombre='OTROS EQUIPOS')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Categoria.objects.create(codigo='CAT-002', nombre='OTROS EQUIPOS')

    def test_se_pueden_agregar_categorias(self):
        Categoria.objects.create(codigo='CAT-001', nombre='LIBROS Y MATERIAL BIBLIOGRÁFICO')
        self.assertEqual(Categoria.objects.count(), 1)

    def test_el_nombre_de_una_cuenta_puede_ser_largo(self):
        nombre = 'X' * 100
        Categoria.objects.create(codigo='CAT-009', nombre=nombre)
        self.assertEqual(Categoria.objects.get(pk='CAT-009').nombre, nombre)

    def test_el_nombre_de_una_ubicacion_es_unico(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ubicacion.objects.create(codigo='UBI-X', nombre='Oficina de Informática')

    def test_no_se_puede_borrar_al_responsable_de_una_ubicacion(self):
        responsable = Personal.objects.create(
            numero_empleado='E001', nombre_pila='Luis', primer_apellido='Pérez',
            puesto='Jefe', departamento_id='DEP-INF')
        Ubicacion.objects.filter(pk='UBI-OFI').update(responsable=responsable)
        with self.assertRaises(ProtectedError):
            responsable.delete()


class TipoArticuloTests(TestCase):
    def setUp(self):
        Categoria.objects.create(codigo='CAT-001', nombre='MUEBLES')
        Categoria.objects.create(codigo='CAT-002', nombre='AUDIOVISUAL')

    def test_pertenece_a_una_categoria(self):
        tipo = TipoArticulo.objects.create(
            codigo='TIP-001', nombre='Cámara', categoria_id='CAT-002')
        self.assertEqual(Categoria.objects.get(pk='CAT-002').tipos.get(), tipo)

    def test_no_se_repite_dentro_de_una_categoria(self):
        TipoArticulo.objects.create(codigo='TIP-001', nombre='Cámara', categoria_id='CAT-002')
        with self.assertRaises(IntegrityError), transaction.atomic():
            TipoArticulo.objects.create(codigo='TIP-002', nombre='Cámara', categoria_id='CAT-002')

    def test_el_mismo_nombre_en_otra_categoria_si_se_puede(self):
        TipoArticulo.objects.create(codigo='TIP-001', nombre='Otros', categoria_id='CAT-002')
        TipoArticulo.objects.create(codigo='TIP-002', nombre='Otros', categoria_id='CAT-001')

    def test_no_se_borra_una_categoria_con_tipos(self):
        TipoArticulo.objects.create(codigo='TIP-001', nombre='Cámara', categoria_id='CAT-002')
        with self.assertRaises(ProtectedError):
            Categoria.objects.get(pk='CAT-002').delete()


class CodigosAutomaticosTests(TestCase):
    def test_siguiente_codigo_sigue_la_serie(self):
        from catalogos.codigos import siguiente_codigo
        self.assertEqual(siguiente_codigo(Categoria, 'CAT'), 'CAT-001')
        self.assertEqual(siguiente_codigo(Categoria, 'CAT'), 'CAT-002')

    def test_arranca_despues_de_los_codigos_numericos_existentes(self):
        from catalogos.codigos import siguiente_codigo
        # UBI-OFI, UBI-LAB1... no son numéricos y no estorban.
        self.assertEqual(siguiente_codigo(Ubicacion, 'UBI'), 'UBI-001')
        Departamento = Personal._meta.get_field('departamento').related_model
        self.assertEqual(siguiente_codigo(Departamento, 'DEP'), 'DEP-001')

    def test_respeta_el_mayor_existente(self):
        from catalogos.codigos import siguiente_codigo
        Categoria.objects.create(codigo='CAT-007', nombre='X')
        self.assertEqual(siguiente_codigo(Categoria, 'CAT'), 'CAT-008')


class FoliosTests(TestCase):
    def fecha(self, *args):
        from datetime import datetime, timezone as tz
        return datetime(*args, tzinfo=tz.utc)

    def test_primer_folio_interno_del_mes(self):
        from catalogos.folios import siguiente_folio_interno
        # 23 de octubre de 2026: el ejemplo de la contadora.
        self.assertEqual(siguiente_folio_interno(self.fecha(2026, 10, 23, 18)), '021431026-001')
        self.assertEqual(siguiente_folio_interno(self.fecha(2026, 10, 24, 18)), '021431026-002')

    def test_el_conteo_se_reinicia_cada_mes(self):
        from catalogos.folios import siguiente_folio_interno
        siguiente_folio_interno(self.fecha(2026, 10, 23, 18))
        self.assertEqual(siguiente_folio_interno(self.fecha(2026, 11, 3, 18)), '021431126-001')

    def test_el_conteo_se_reinicia_en_enero(self):
        from catalogos.folios import siguiente_folio_interno
        siguiente_folio_interno(self.fecha(2026, 12, 31, 18))
        self.assertEqual(siguiente_folio_interno(self.fecha(2027, 1, 4, 18)), '021430127-001')

    def test_mismo_mes_de_otro_año_es_otra_serie(self):
        from catalogos.folios import siguiente_folio_interno
        siguiente_folio_interno(self.fecha(2026, 10, 23, 18))
        self.assertEqual(siguiente_folio_interno(self.fecha(2027, 10, 1, 18)), '021431027-001')

    def test_usa_el_mes_local_y_no_el_utc(self):
        from catalogos.folios import siguiente_folio_interno
        # 1 nov 05:00 UTC = 31 oct 22:00 en Tijuana: todavía es octubre.
        self.assertEqual(siguiente_folio_interno(self.fecha(2026, 11, 1, 5)), '021431026-001')

    def test_llega_a_999_y_el_1000_se_rechaza(self):
        from catalogos.folios import FolioAgotado, siguiente_folio_interno
        f = self.fecha(2026, 10, 23, 18)
        ContadorFolio.objects.create(clave='FI-1026', ultimo=998)
        self.assertEqual(siguiente_folio_interno(f), '021431026-999')
        with self.assertRaises(FolioAgotado):
            siguiente_folio_interno(f)

    def test_si_el_guardado_falla_el_numero_no_se_consume(self):
        from catalogos.folios import siguiente_folio_interno
        f = self.fecha(2026, 10, 23, 18)
        try:
            with transaction.atomic():
                siguiente_folio_interno(f)
                raise RuntimeError('falló el guardado')
        except RuntimeError:
            pass
        self.assertEqual(siguiente_folio_interno(f), '021431026-001')

    def test_no_repite_un_identificador_que_ya_existe(self):
        from articulos.tests import crear
        from catalogos.folios import siguiente_folio_interno
        f = self.fecha(2026, 10, 23, 18)
        # Un artículo histórico ya tiene el 001 y el 002 de ese mes.
        crear(marbete_oficial=None, folio_interno='021431026-001', origen_id='COM')
        crear(marbete_oficial=None, folio_interno='021431026-002', origen_id='ENS', num_serie='S2')
        self.assertEqual(siguiente_folio_interno(f), '021431026-003')

    def test_folios_de_movimiento_y_resguardo_son_series_separadas(self):
        from catalogos.folios import siguiente_folio_movimiento, siguiente_folio_resguardo
        self.assertEqual(siguiente_folio_movimiento(), 'MOV-0001')
        self.assertEqual(siguiente_folio_movimiento(), 'MOV-0002')
        self.assertEqual(siguiente_folio_resguardo(), 'RES-0001')

    def test_el_folio_cabe_en_la_columna_y_en_el_articulo(self):
        from articulos.tests import crear
        from catalogos.folios import siguiente_folio_interno
        folio = siguiente_folio_interno()
        self.assertLessEqual(len(folio), 25)
        crear(marbete_oficial=None, folio_interno=folio, origen_id='COM')
