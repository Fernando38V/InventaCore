from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase

from articulos.models import Articulo
from catalogos.models import Categoria, TipoArticulo
from personal.models import Personal


def crear_personal(numero='E001'):
    return Personal.objects.create(
        numero_empleado=numero, nombre_pila='Ana', primer_apellido='López',
        puesto='Docente', departamento_id='DEP-INF')


def tipo_de_prueba(categoria='CAT-T1', tipo='TIP-T1'):
    """Los catálogos arrancan vacíos (DEC-005): cada prueba crea lo que necesita."""
    Categoria.objects.get_or_create(codigo=categoria, defaults={'nombre': 'Categoría ' + categoria})
    TipoArticulo.objects.get_or_create(
        codigo=tipo, defaults={'nombre': 'Tipo ' + tipo, 'categoria_id': categoria})
    return tipo


def datos_articulo(**cambios):
    """Un Activo válido, Registrado. Cada prueba cambia solo lo que quiere probar."""
    datos = {
        'marbete_oficial': 'M-0001', 'color': 'Negro', 'descripcion': 'Escritorio',
        'fecha_adquisicion': date(2024, 1, 15), 'costo_adquisicion': Decimal('1500.00'),
        'ubicacion_id': 'UBI-OFI', 'origen_id': 'ACT',
        'estado_operativo_id': 'UTIL', 'estado_registro_id': 'REG',
    }
    datos.update(cambios)
    datos.setdefault('tipo_articulo_id', tipo_de_prueba())
    if 'resguardante_id' not in datos:
        datos['resguardante'] = Personal.objects.filter(numero_empleado='E001').first() \
            or crear_personal()
    return datos


def crear(**cambios):
    return Articulo.objects.create(**datos_articulo(**cambios))


def rechaza(prueba, **cambios):
    with prueba.assertRaises(IntegrityError), transaction.atomic():
        crear(**cambios)


class ArticuloValidosTests(TestCase):
    def test_activo_con_marbete(self):
        articulo = crear()
        self.assertEqual(articulo.identificador, 'M-0001')

    def test_comodato_y_enser_con_folio(self):
        crear(marbete_oficial=None, folio_interno='021430126-001', origen_id='COM')
        crear(marbete_oficial=None, folio_interno='021430126-002', origen_id='ENS')
        self.assertEqual(Articulo.objects.count(), 2)

    def test_marca_modelo_y_serie_son_opcionales(self):
        articulo = crear()
        self.assertIsNone(articulo.marca)
        self.assertIsNone(articulo.modelo)
        self.assertIsNone(articulo.num_serie)

    def test_varios_sin_serie_no_chocan(self):
        crear(marbete_oficial='M-1')
        crear(marbete_oficial='M-2')
        self.assertEqual(Articulo.objects.filter(num_serie__isnull=True).count(), 2)

    def test_donado_con_costo_se_acepta_mientras_PEND_004_siga_abierto(self):
        crear(estado_registro_id='DON')

    def test_donado_sin_costo_y_sin_fecha(self):
        crear(estado_registro_id='DON', costo_adquisicion=None, fecha_adquisicion=None)

    def test_pendiente_sin_costo_o_sin_fecha(self):
        crear(marbete_oficial='M-1', estado_registro_id='PEND', costo_adquisicion=None)
        crear(marbete_oficial='M-2', estado_registro_id='PEND', fecha_adquisicion=None)

    def test_no_localizado_va_con_su_ubicacion(self):
        crear(ubicacion_id='UBI-NOLOC', estado_operativo_id='NOLOC')

    def test_la_categoria_sale_del_tipo(self):
        articulo = crear(tipo_articulo_id=tipo_de_prueba('CAT-X', 'TIP-X'))
        self.assertEqual(articulo.categoria.codigo, 'CAT-X')

    def test_color_y_descripcion_son_obligatorios(self):
        rechaza(self, color='')
        rechaza(self, descripcion='')


class ArticuloRechazadosTests(TestCase):
    def test_activo_sin_marbete(self):
        rechaza(self, marbete_oficial=None)

    def test_activo_con_folio(self):
        rechaza(self, folio_interno='021430126-003')

    def test_comodato_con_marbete(self):
        rechaza(self, origen_id='COM', folio_interno='021430126-001')

    def test_enser_sin_folio(self):
        rechaza(self, marbete_oficial=None, origen_id='ENS')

    def test_marbete_vacio(self):
        rechaza(self, marbete_oficial='')

    def test_serie_vacia(self):
        rechaza(self, num_serie='')

    def test_serie_repetida(self):
        crear(num_serie='SN-1')
        rechaza(self, marbete_oficial='M-2', num_serie='SN-1')

    def test_marbete_repetido(self):
        crear()
        rechaza(self)

    def test_costo_negativo(self):
        rechaza(self, costo_adquisicion=Decimal('-1'))

    def test_registrado_sin_costo(self):
        rechaza(self, costo_adquisicion=None)

    def test_registrado_sin_fecha(self):
        rechaza(self, fecha_adquisicion=None)


    def test_pendiente_con_todo_completo(self):
        rechaza(self, estado_registro_id='PEND')

    def test_nolocalizado_sin_ubicacion_nolocalizado(self):
        rechaza(self, estado_operativo_id='NOLOC')

    def test_ubicacion_nolocalizado_sin_estado(self):
        rechaza(self, ubicacion_id='UBI-NOLOC')


class ArticuloProteccionTests(TestCase):
    def test_no_se_borra_el_tipo_en_uso(self):
        crear()
        with self.assertRaises(ProtectedError):
            TipoArticulo.objects.get(pk='TIP-T1').delete()

    def test_no_se_borra_al_resguardante(self):
        articulo = crear()
        with self.assertRaises(ProtectedError):
            articulo.resguardante.delete()
