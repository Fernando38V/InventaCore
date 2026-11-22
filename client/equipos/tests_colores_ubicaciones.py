"""Colores sugeridos (datalist) y orden natural de ubicaciones.

    python manage.py test equipos.tests_colores_ubicaciones
"""
import csv
import re
import unittest
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from catalogos.tests import ApiFalsa, pagina
from client.inventario import COLORES_SUGERIDOS, clave_natural, opciones_catalogo
from equipos.tests import BaseEquipos, articulo

CSV_COLORES = settings.BASE_DIR.parent / 'api' / 'catalogos' / 'datos' / 'colores_sugeridos.csv'


class ColoresSugeridosTests(SimpleTestCase):
    def test_son_32_y_caben_en_el_campo(self):
        self.assertEqual(len(COLORES_SUGERIDOS), 32)
        self.assertEqual(len(set(COLORES_SUGERIDOS)), 32)
        self.assertTrue(all(0 < len(c) <= 25 for c in COLORES_SUGERIDOS))

    @unittest.skipUnless(CSV_COLORES.exists(), 'Sin api/ junto al cliente (despliegue solo de client/).')
    def test_coinciden_con_el_csv_de_la_api(self):
        with open(CSV_COLORES, encoding='utf-8-sig', newline='') as archivo:
            del_csv = [fila['color'].strip() for fila in csv.DictReader(archivo)]
        self.assertEqual(list(COLORES_SUGERIDOS), del_csv)


class ColorEnFormulariosTests(BaseEquipos):
    def opciones_del_datalist(self, html):
        bloque = re.search(r'<datalist id="colores-sugeridos">(.*?)</datalist>', html, re.S)
        self.assertIsNotNone(bloque, 'No está el datalist de colores')
        return re.findall(r'<option value="([^"]*)">', bloque.group(1))

    def test_registrar_ofrece_los_colores_sin_bloquear_otros(self):
        self.entrar()
        r = self.client.get('/articulos/registrar/')
        html = r.content.decode()
        self.assertEqual(len(self.opciones_del_datalist(html)), 32)
        campo = re.search(r'<input[^>]*name="color"[^>]*>', html).group(0)
        self.assertIn('list="colores-sugeridos"', campo)
        self.assertIn('maxlength="25"', campo)
        self.assertNotIn('pattern=', campo)

    def test_registrar_acepta_un_color_que_no_esta_en_la_lista(self):
        from equipos.tests import VALIDO
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = articulo(num=9)
        r = self.client.post('/articulos/registrar/', dict(VALIDO, color='Turquesa metálico'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.api.escrituras()[0][2]['color'], 'Turquesa metálico')

    def test_corregir_ofrece_los_colores_solo_en_el_campo_color(self):
        self.api.respuestas[('GET', 'articulos/7/')] = articulo()
        self.entrar()
        html = self.client.get('/articulos/detalle/7/corregir/').content.decode()
        self.assertEqual(len(self.opciones_del_datalist(html)), 32)
        self.assertEqual(html.count('list="colores-sugeridos"'), 1)
        campo = re.search(r'<input[^>]*name="color"[^>]*>', html).group(0)
        self.assertIn('list="colores-sugeridos"', campo)


class OrdenNaturalTests(SimpleTestCase):
    def test_clave_natural(self):
        nombres = ['Salón 10', 'Salón 2', 'Área de torniquetes', 'Salón 1', 'Biblioteca',
                   'Laboratorio de Informática 2', 'Laboratorio de Informática 1', 'Salón 11']
        self.assertEqual(sorted(nombres, key=clave_natural), [
            'Área de torniquetes', 'Biblioteca', 'Laboratorio de Informática 1',
            'Laboratorio de Informática 2', 'Salón 1', 'Salón 2', 'Salón 10', 'Salón 11'])

    def test_ubicaciones_salen_en_orden_natural_sin_cambiar_codigos(self):
        api = ApiFalsa()
        api.respuestas[('GET', 'ubicaciones/')] = pagina([
            {'codigo': 'UBI-%03d' % n, 'nombre': 'Salón %d' % n, 'activo': True}
            for n in (1, 10, 11, 2, 3)])
        with patch('client.utils.llamar', api):
            opciones = opciones_catalogo(None, 'ubicaciones')
        self.assertEqual([o['nombre'] for o in opciones],
                         ['Salón 1', 'Salón 2', 'Salón 3', 'Salón 10', 'Salón 11'])
        self.assertEqual(opciones[0]['codigo'], 'UBI-001')

    def test_otros_catalogos_conservan_el_orden_de_la_api(self):
        api = ApiFalsa()
        api.respuestas[('GET', 'categorias/')] = pagina([
            {'codigo': 'B', 'nombre': 'Tipo 10', 'activo': True},
            {'codigo': 'A', 'nombre': 'Tipo 2', 'activo': True}])
        with patch('client.utils.llamar', api):
            opciones = opciones_catalogo(None, 'categorias')
        self.assertEqual([o['codigo'] for o in opciones], ['B', 'A'])


class OrdenEnFormularioTests(BaseEquipos):
    def test_desplegable_de_ubicacion_en_registrar(self):
        self.api.respuestas[('GET', 'ubicaciones/')] = pagina([
            {'codigo': 'UBI-S10', 'nombre': 'Salón 10', 'activo': True},
            {'codigo': 'UBI-S2', 'nombre': 'Salón 2', 'activo': True},
            {'codigo': 'UBI-S1', 'nombre': 'Salón 1', 'activo': True}])
        self.entrar()
        html = self.client.get('/articulos/registrar/').content.decode()
        posiciones = [html.index('value="%s"' % c) for c in ('UBI-S1', 'UBI-S2', 'UBI-S10')]
        self.assertEqual(posiciones, sorted(posiciones))


class DonadoVioletaTests(BaseEquipos):
    """El tono lo manda la API ('violeta' para DON); el listado y la ficha lo usan tal cual."""
    DONADO = {'codigo': 'DON', 'nombre': 'Donado', 'tono': 'violeta'}

    def test_listado_y_ficha_pintan_donado_en_violeta(self):
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo(estado_registro=self.DONADO)])
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(estado_registro=self.DONADO)
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])
        self.entrar()
        for url in ('/articulos/', '/articulos/detalle/7/'):
            r = self.client.get(url)
            self.assertContains(r, 'badge-estado--violeta">Donado')
            self.assertNotContains(r, 'badge-estado--azul">Donado')
