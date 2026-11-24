"""Marbete imprimible desde la ficha.

    python manage.py test equipos.tests_marbete
"""
import re
from unittest.mock import patch

from django.test import SimpleTestCase

from client.api import ApiError
from equipos import marbete
from equipos.tests import BaseEquipos, articulo, pagina


class MedidasTests(SimpleTestCase):
    def test_la_hoja_es_carta_y_las_10_etiquetas_caben(self):
        self.assertEqual(len(marbete.posiciones()), 10)
        arriba, izquierda = marbete.coordenadas(10)
        self.assertLessEqual(izquierda + marbete.ANCHO_MM, marbete.HOJA_ANCHO_MM)
        self.assertLessEqual(arriba + marbete.ALTO_MM, marbete.HOJA_ALTO_MM)

    def test_coordenadas_por_renglon(self):
        self.assertEqual(marbete.coordenadas(1), (12.7, 4.0))
        self.assertEqual(marbete.coordenadas(2), (12.7, 110.4))   # 4 + 101.6 + 4.8
        self.assertEqual(marbete.coordenadas(3), (63.5, 4.0))     # segundo renglón

    def test_posicion_invalida_regresa_1(self):
        for valor in (None, '', 'x', '0', '11', '-3'):
            self.assertEqual(marbete.leer_posicion(valor), 1)
        self.assertEqual(marbete.leer_posicion('7'), 7)


class MarbeteTests(BaseEquipos):
    URL = '/articulos/detalle/7/marbete/'

    def setUp(self):
        super().setUp()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            marbete_oficial='0214300701-150', identificador='0214300701-150',
            descripcion='Está en buen estado, trae su cargador',
            tipo_articulo={'codigo': 'TIP-002', 'nombre': 'Monitor'},
            resguardante={'num': 3, 'numero_empleado': 'E003', 'nombre': 'Martha Cecilia Arévalo Mendoza'})

    def ver(self, url=None):
        self.entrar()
        r = self.client.get(url or self.URL)
        self.assertEqual(r.status_code, 200)
        return r, r.content.decode()

    def test_contenido_del_marbete(self):
        r, html = self.ver()
        self.assertTemplateUsed(r, 'equipos/marbete.html')
        self.assertIn('Colegio de Educación Profesional', html)
        self.assertIn('Técnica del Estado de Baja', html)
        self.assertIn('marbete__identificador">0214300701-150<', html)
        self.assertIn('marbete__nombre">Monitor<', html)      # el tipo de artículo, no la descripción
        self.assertIn('marbete__resguardante">Martha Cecilia Arévalo Mendoza<', html)
        self.assertIn('src="/articulos/detalle/7/qr/"', html)   # el QR de siempre: IC:7

    def test_no_lleva_datos_fuera_del_formato(self):
        _, html = self.ver()
        cuerpo = html.split('class="marbete-hoja"', 1)[1]
        for ajeno in ('Dell', 'Latitude', 'Negro', '12000', 'E003', 'Laboratorio 1',
                      'buen estado', 'cargador'):
            self.assertNotIn(ajeno, cuerpo)

    def test_folio_interno_cuando_no_hay_marbete(self):
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            marbete_oficial=None, folio_interno='021431126-004', identificador='021431126-004')
        _, html = self.ver()
        self.assertIn('marbete__identificador">021431126-004<', html)

    def test_sin_resguardante(self):
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(resguardante=None)
        _, html = self.ver()
        self.assertIn('marbete__resguardante"><', html)
        self.assertIn('no tiene resguardante', html)
        self.assertNotIn('Medidas provisionales', html)

    def test_numero_de_serie_solo_si_el_articulo_lo_tiene(self):
        _, html = self.ver()                                        # el artículo de prueba trae serie SN1
        self.assertIn('marbete__serie">SN1<', html)
        self.assertLess(html.index('marbete__identificador'), html.index('marbete__serie'))
        self.assertLess(html.index('marbete__serie'), html.index('marbete__nombre'))
        for vacio in (None, '', '   '):
            self.api.respuestas[('GET', 'articulos/7/')] = articulo(num_serie=vacio)
            _, html = self.ver()
            self.assertNotIn('marbete__serie"', html.split('class="marbete-hoja"', 1)[1])

    def test_nombre_largo_baja_a_letra_chica(self):
        for largo, chico in ((30, False), (31, True)):
            self.api.respuestas[('GET', 'articulos/7/')] = articulo(
                tipo_articulo={'codigo': 'T', 'nombre': 'X' * largo})
            _, html = self.ver()
            self.assertEqual('marbete__nombre--chico' in html.split('class="marbete-hoja"', 1)[1], chico, largo)

    def test_medidas_en_mm_con_punto_decimal(self):
        # es-mx usa coma decimal; en CSS sería inválido.
        _, html = self.ver()
        self.assertIn('--m-ancho: 101.6mm', html)
        self.assertIn('--m-alto: 50.8mm', html)
        self.assertIn('@page { size: letter; margin: 0; }', html)
        self.assertNotRegex(html, r'\d,\dmm')

    def test_lugar_en_la_hoja(self):
        _, html = self.ver(self.URL + '?posicion=4')
        self.assertIn('data-posicion="4"', html)
        self.assertIn('top: 63.5mm; left: 110.4mm;', html)
        self.assertIn('<option value="4" selected>', html)
        _, html = self.ver(self.URL + '?posicion=99')
        self.assertIn('data-posicion="1"', html)

    def test_sin_logos_no_hay_imagenes_rotas(self):
        with patch('equipos.views.finders.find', return_value=None):
            _, html = self.ver()
        self.assertNotIn('marbete__logo', html.split('class="marbete-hoja"', 1)[1])

    def test_con_logos_los_muestra(self):
        with patch('equipos.views.finders.find', return_value='/ruta/logo.png'):
            _, html = self.ver()
        self.assertIn('img/marbete/logo_izquierdo.png', html)
        self.assertIn('img/marbete/logo_derecho.png', html)

    def test_los_logos_de_la_institucion_vienen_en_el_proyecto(self):
        # sin parchear: los dos archivos existen en static/img/marbete y el marbete los usa
        _, html = self.ver()
        hoja = html.split('class="marbete-hoja"', 1)[1]
        self.assertIn('/static/img/marbete/logo_izquierdo.png', hoja)
        self.assertIn('/static/img/marbete/logo_derecho.png', hoja)

    def test_consulta_tambien_puede_imprimir(self):
        self.entrar(rol='CONSULTA')
        self.assertEqual(self.client.get(self.URL).status_code, 200)

    def test_articulo_inexistente_404(self):
        self.api.respuestas[('GET', 'articulos/7/')] = ApiError(404, {'detail': 'No encontrado.'})
        self.entrar()
        self.assertEqual(self.client.get(self.URL).status_code, 404)

    def test_el_boton_abre_el_marbete_en_la_misma_pestana(self):
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = {'count': 0, 'results': []}
        self.entrar()
        html = self.client.get('/articulos/detalle/7/').content.decode()
        boton = re.search(r'<a[^>]*href="/articulos/detalle/7/marbete/"[^>]*>', html).group(0)
        self.assertNotIn('target=', boton)     # así "Volver a la ficha" y Atrás no dejan pestañas abiertas

    def test_boton_en_la_ficha(self):
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = {'count': 0, 'results': []}
        self.entrar()
        html = self.client.get('/articulos/detalle/7/').content.decode()
        self.assertTrue(re.search(r'href="/articulos/detalle/7/marbete/"[^>]*>\s*<svg[^>]*>.*?</svg>\s*Imprimir marbete',
                                  html, re.S))


class RepartirTests(SimpleTestCase):
    def test_primera_hoja_desde_el_lugar_indicado_y_las_demas_desde_1(self):
        hojas = marbete.repartir(list('abcdefghijkl'), inicio=8)      # 12 etiquetas
        self.assertEqual([len(h) for h in hojas], [3, 9])
        self.assertEqual([x['posicion'] for x in hojas[0]], [8, 9, 10])
        self.assertEqual(hojas[1][0]['posicion'], 1)
        self.assertEqual(hojas[1][0]['etiqueta'], 'd')

    def test_veinte_etiquetas_son_dos_hojas_llenas(self):
        hojas = marbete.repartir(range(20))
        self.assertEqual([len(h) for h in hojas], [10, 10])

    def test_sin_etiquetas_no_hay_hojas(self):
        self.assertEqual(marbete.repartir([]), [])

    def test_inicio_invalido_es_1(self):
        self.assertEqual(marbete.repartir([1], inicio='x')[0][0]['posicion'], 1)


class LoteTests(BaseEquipos):
    URL = '/articulos/marbetes/'

    def setUp(self):
        super().setUp()
        for n in range(1, 13):
            self.api.respuestas[('GET', 'articulos/%d/' % n)] = articulo(
                num=n, marbete_oficial='0214300705-%03d' % n, identificador='0214300705-%03d' % n,
                tipo_articulo={'codigo': 'TIP-002', 'nombre': 'Monitor'})

    def ver(self, query):
        self.entrar()
        r = self.client.get(self.URL + query)
        return r, r.content.decode()

    def test_varias_etiquetas_en_hojas_de_10(self):
        _, html = self.ver('?' + '&'.join('num=%d' % n for n in range(1, 13)))
        self.assertEqual(html.count('class="marbete-hoja"'), 2)
        self.assertEqual(html.count('class="marbete" '), 12)
        self.assertIn('12 etiquetas en 2 hojas', html)
        for n in (1, 12):
            self.assertIn('src="/articulos/detalle/%d/qr/"' % n, html)

    def test_lugar_de_inicio_en_la_primera_hoja(self):
        _, html = self.ver('?num=1&num=2&num=3&posicion=9')
        self.assertEqual(html.count('class="marbete-hoja"'), 2)
        self.assertIn('data-posicion="9"', html)
        self.assertIn('data-posicion="10"', html)
        self.assertIn('<option value="9" selected>', html)
        self.assertIn('name="num" value="3"', html)            # el cambio de lugar conserva la selección

    def test_repetidos_e_invalidos_se_ignoran(self):
        _, html = self.ver('?num=1&num=1&num=abc&num=2')
        self.assertEqual(html.count('class="marbete" '), 2)

    def test_sin_seleccion_regresa_al_listado(self):
        r, _ = self.ver('')
        self.assertRedirects(r, '/articulos/', fetch_redirect_response=False)

    def test_un_articulo_inexistente_se_omite_con_aviso(self):
        self.api.respuestas[('GET', 'articulos/5/')] = ApiError(404, {'detail': 'No encontrado.'})
        _, html = self.ver('?num=1&num=5')
        self.assertEqual(html.count('class="marbete" '), 1)
        self.assertIn('se omitieron', html)

    def test_tope_de_50(self):
        for n in range(1, 61):
            self.api.respuestas[('GET', 'articulos/%d/' % n)] = articulo(num=n)
        _, html = self.ver('?' + '&'.join('num=%d' % n for n in range(1, 61)))
        self.assertEqual(html.count('class="marbete" '), 50)
        self.assertIn('Solo se imprimen los primeros 50', html)

    def test_consulta_tambien_puede_imprimir_lotes(self):
        self.entrar(rol='CONSULTA')
        self.assertEqual(self.client.get(self.URL + '?num=1').status_code, 200)

    def test_listado_trae_casillas_y_barra(self):
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo(num=1), articulo(num=2)])
        self.entrar()
        html = self.client.get('/articulos/').content.decode()
        self.assertEqual(html.count('class="form-check-input marcar-marbete"'), 2)
        self.assertIn('id="marcarPagina"', html)
        self.assertIn('id="barraMarbetes"', html)
        self.assertIn('href="/articulos/marbetes/"', html)
