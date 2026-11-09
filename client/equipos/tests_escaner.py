"""Pruebas del QR sin URL, del escáner y de la búsqueda rápida (DEC-005, RF-19, RF-20, RF-23).

La lectura con la cámara ocurre en el navegador y no se puede probar aquí; esa
parte se probó a mano con un navegador real (ver PENDIENTES.md, PEND-025).

    python manage.py test equipos
"""
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase

from catalogos.tests import ApiFalsa, BaseCliente
from client.api import ApiError, SesionVencida

from . import qr


class FormatoQrTests(SimpleTestCase):
    def test_el_contenido_es_ic_y_la_clave(self):
        self.assertEqual(qr.contenido(7), 'IC:7')

    def test_lee_el_formato_valido(self):
        self.assertEqual(qr.leer('IC:12'), 12)
        self.assertEqual(qr.leer('  IC:12\n'), 12)

    def test_rechaza_lo_que_no_es_de_inventacore(self):
        for texto in ('', None, 'IC:', 'IC:abc', 'IC:12abc', 'ic:12', 'IC:-1', 'IC: 12',
                      'IC:12\nIC:13', 'IC:1234567890',
                      'http://127.0.0.1:8001/articulos/detalle/12/', '12',
                      'https://ejemplo.com/IC:12'):
            self.assertIsNone(qr.leer(texto), repr(texto))


class ImagenQrTests(BaseCliente):
    def setUp(self):
        super().setUp()
        self.entrar()

    def test_el_qr_codifica_solo_el_identificador_sin_url(self):
        with patch('equipos.views.qrcode.make', wraps=__import__('qrcode').make) as hacer:
            r = self.client.get('/articulos/detalle/7/qr/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/png')
        self.assertEqual(hacer.call_args[0][0], 'IC:7')
        self.assertNotIn('http', hacer.call_args[0][0])

    def test_la_descarga_se_nombra_como_articulo(self):
        r = self.client.get('/articulos/detalle/7/qr/?descargar=1')
        self.assertIn('QR-articulo-7.png', r['Content-Disposition'])

    def test_sin_sesion_no_entrega_el_qr(self):
        self.client.logout()
        sesion = self.client.session
        sesion.flush()
        self.assertEqual(self.client.get('/articulos/detalle/7/qr/').status_code, 302)


class EscanerTests(TestCase):
    def setUp(self):
        self.api = ApiFalsa()
        for destino in ('equipos.views_escaner.llamar', 'client.utils.llamar'):
            parche = patch(destino, self.api)
            parche.start()
            self.addCleanup(parche.stop)

    def entrar(self, rol='ADMIN'):
        sesion = self.client.session
        sesion['api_token'] = 'token'
        sesion['usuario'] = {'num': 1, 'username': 'u', 'empleado': 'Prueba Uno',
                             'rol': rol, 'rol_nombre': rol.title()}
        sesion.save()

    def mensajes(self, r):
        return [str(m) for m in get_messages(r.wsgi_request)]

    def test_la_pagina_abre_para_administrador_y_consulta(self):
        for rol in ('ADMIN', 'CONSULTA'):
            self.entrar(rol)
            r = self.client.get('/articulos/escanear/')
            self.assertEqual(r.status_code, 200, rol)
            self.assertContains(r, 'Iniciar cámara')
            self.assertContains(r, 'Elegir o tomar foto')
            self.assertContains(r, '/static/vendor/html5-qrcode/html5-qrcode.min.js')

    def test_la_libreria_esta_guardada_en_el_proyecto_y_no_en_un_cdn(self):
        self.assertIsNotNone(finders.find('vendor/html5-qrcode/html5-qrcode.min.js'))
        self.assertIsNotNone(finders.find('vendor/html5-qrcode/LICENSE'))
        self.entrar()
        r = self.client.get('/articulos/escanear/')
        self.assertNotContains(r, 'cdn.')
        self.assertNotContains(r, 'unpkg')

    def test_sin_sesion_pide_login(self):
        for ruta in ('/articulos/escanear/', '/articulos/escanear/resolver/?codigo=IC:7'):
            r = self.client.get(ruta)
            self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)

    def test_un_codigo_valido_abre_la_ficha(self):
        self.entrar('CONSULTA')
        self.api.respuestas[('GET', 'articulos/7/')] = {'num': 7}
        r = self.client.get('/articulos/escanear/resolver/?codigo=IC:7')
        self.assertRedirects(r, '/articulos/detalle/7/', fetch_redirect_response=False)
        self.assertEqual(self.api.llamadas, [('GET', 'articulos/7/', None)])

    def test_un_codigo_con_url_o_de_otro_sistema_se_rechaza_sin_llamar_a_la_api(self):
        self.entrar()
        for codigo in ('http://127.0.0.1:8001/articulos/detalle/7/', 'WIFI:S:red;;', 'IC:7;DROP', ''):
            r = self.client.get('/articulos/escanear/resolver/', {'codigo': codigo})
            self.assertRedirects(r, '/articulos/escanear/', fetch_redirect_response=False)
            self.assertIn('Ese código no es de InventaCore', self.mensajes(r)[0])
        self.assertEqual(self.api.llamadas, [])

    def test_el_mensaje_de_rechazo_no_repite_el_texto_leido(self):
        self.entrar()
        r = self.client.get('/articulos/escanear/resolver/', {'codigo': '<script>alert(1)</script>'})
        self.assertNotIn('script', ' '.join(self.mensajes(r)))

    def test_un_articulo_que_no_existe_se_avisa(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/99/')] = ApiError(404, {'detail': 'No encontrado.'})
        r = self.client.get('/articulos/escanear/resolver/?codigo=IC:99')
        self.assertRedirects(r, '/articulos/escanear/', fetch_redirect_response=False)
        self.assertEqual(self.mensajes(r), ['No existe un artículo con ese código.'])

    def test_un_error_de_la_api_se_avisa_sin_romper(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/')] = ApiError(500, {'detalle': 'Error 500 en el servidor.'})
        r = self.client.get('/articulos/escanear/resolver/?codigo=IC:7')
        self.assertRedirects(r, '/articulos/escanear/', fetch_redirect_response=False)
        self.assertIn('Error 500 en el servidor.', self.mensajes(r))

    def test_sesion_vencida_lleva_al_login(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/')] = SesionVencida(401, {})
        r = self.client.get('/articulos/escanear/resolver/?codigo=IC:7')
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)

    def test_consulta_sigue_sin_ver_los_modulos_de_administrador(self):
        # El escáner está bajo /articulos/: no abre puertas de administración.
        self.entrar('CONSULTA')
        self.assertEqual(self.client.get('/personal/').status_code, 302)
        self.assertEqual(self.client.get('/cuentas/').status_code, 302)
