"""Foto del artículo en la ficha (PEND-027).

    python manage.py test equipos.tests_foto
"""
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from client import api
from client.api import ApiError
from equipos.tests import BaseEquipos, articulo


class EnviarFormularioTests(SimpleTestCase):
    def peticion(self, **kw):
        with patch('client.api._ejecutar', return_value=b'{"ok": true}') as ejecutar:
            r = api.enviar_formulario(None, **kw)
        return r, ejecutar.call_args[0][0]

    def test_multipart_con_archivo_y_campos(self):
        r, p = self.peticion(metodo='POST', ruta='articulos/7/foto/', campos={'motivo': 'cambio'},
                             archivo=('f"o\r\nto.jpg', b'\xff\xd8BYTES'), campo_archivo='foto')
        self.assertEqual(r, {'ok': True})
        self.assertEqual(p.get_method(), 'POST')
        self.assertTrue(p.full_url.endswith('/articulos/7/foto/'))
        self.assertIn('multipart/form-data; boundary=', p.get_header('Content-type'))
        cuerpo = p.data
        self.assertIn(b'name="motivo"\r\n\r\ncambio', cuerpo)
        self.assertIn(b'name="foto"; filename="foto.jpg"', cuerpo)     # sin comillas ni saltos
        self.assertIn(b'\xff\xd8BYTES', cuerpo)

    def test_delete_solo_con_campos(self):
        _, p = self.peticion(metodo='DELETE', ruta='articulos/7/foto/', campos={'motivo': 'x'})
        self.assertEqual(p.get_method(), 'DELETE')
        self.assertIn(b'name="motivo"\r\n\r\nx', p.data)
        self.assertNotIn(b'filename', p.data)
        self.assertTrue(p.data.rstrip().endswith(b'--'))

    def test_enviar_archivo_sigue_igual(self):
        with patch('client.api._ejecutar', return_value=b'{}') as ejecutar:
            api.enviar_archivo(None, 'carga-masiva/validar/', 'a.xlsx', b'DATOS', {'k': 'v'})
        cuerpo = ejecutar.call_args[0][0].data
        self.assertIn(b'name="archivo"; filename="a.xlsx"', cuerpo)
        self.assertIn(b'DATOS', cuerpo)
        self.assertIn(b'name="k"', cuerpo)


class FotoBase(BaseEquipos):
    def setUp(self):
        super().setUp()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo()
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = {'count': 0, 'results': []}
        self.envio = MagicMock(return_value=articulo(tiene_foto=True))
        self.descarga = MagicMock(return_value=b'\xff\xd8JPEG')
        for nombre, falso in (('enviar_formulario', self.envio), ('descargar', self.descarga)):
            parche = patch('equipos.views_foto.' + nombre, falso)
            parche.start()
            self.addCleanup(parche.stop)

    def ficha(self, **cambios):
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(**cambios)
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = {'count': 0, 'results': []}
        return self.client.get('/articulos/detalle/7/').content.decode()

    def archivo(self, nombre='foto.jpg', contenido=b'\xff\xd8DATOS'):
        return SimpleUploadedFile(nombre, contenido, content_type='image/jpeg')


class FichaTests(FotoBase):
    def test_sin_foto_el_admin_puede_agregar(self):
        self.entrar()
        html = self.ficha(tiene_foto=False)
        self.assertIn('todavía no tiene foto', html)
        self.assertIn('Agregar foto', html)
        self.assertNotIn('Quitar foto', html)
        self.assertNotIn('class="foto-articulo__img"', html)

    def test_con_foto_se_ve_y_el_admin_puede_cambiar_y_quitar(self):
        self.entrar()
        html = self.ficha(tiene_foto=True)
        self.assertIn('src="/articulos/detalle/7/foto/"', html)
        self.assertIn('Cambiar foto', html)
        self.assertIn('Quitar foto', html)
        self.assertIn('id="modalFotoGrande"', html)
        self.assertIn('data-url="/articulos/detalle/7/foto/quitar/"', html)

    def test_cambiar_exige_motivo_y_agregar_no(self):
        self.entrar()
        self.assertNotRegex(self.ficha(tiene_foto=False).split('id="fotoMotivo"')[1].split('>')[0], 'required')
        self.assertRegex(self.ficha(tiene_foto=True).split('id="fotoMotivo"')[1].split('>')[0], 'required')

    def test_consulta_ve_la_foto_sin_botones(self):
        self.entrar(rol='CONSULTA')
        html = self.ficha(tiene_foto=True)
        self.assertIn('src="/articulos/detalle/7/foto/"', html)
        for ajeno in ('Cambiar foto', 'Quitar foto', 'Agregar foto', 'id="modalFoto"'):
            self.assertNotIn(ajeno, html)
        self.assertNotIn('Agregar foto', self.ficha(tiene_foto=False))

    def test_respuesta_vieja_sin_tiene_foto_no_rompe(self):
        self.entrar()
        a = articulo(); a.pop('tiene_foto', None)
        self.api.respuestas[('GET', 'articulos/7/')] = a
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = {'count': 0, 'results': []}
        self.assertEqual(self.client.get('/articulos/detalle/7/').status_code, 200)


class VerFotoTests(FotoBase):
    def test_entrega_la_imagen_de_la_api(self):
        self.entrar(rol='CONSULTA')
        r = self.client.get('/articulos/detalle/7/foto/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'image/jpeg')
        self.assertEqual(r.content, b'\xff\xd8JPEG')
        self.assertIn('no-cache', r['Cache-Control'])
        self.assertEqual(r['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.descarga.call_args[0][1], 'articulos/7/foto/')

    def test_sin_foto_es_404(self):
        self.entrar()
        self.descarga.side_effect = ApiError(404, {'detail': 'No encontrado.'})
        self.assertEqual(self.client.get('/articulos/detalle/7/foto/').status_code, 404)

    def test_api_caida_no_es_404(self):
        self.entrar()
        self.descarga.side_effect = ApiError(0, {'detalle': 'No se pudo conectar.'})
        self.assertEqual(self.client.get('/articulos/detalle/7/foto/').status_code, 502)

    def test_sin_sesion_pide_iniciar(self):
        r = self.client.get('/articulos/detalle/7/foto/')
        self.assertEqual(r.status_code, 302)
        self.descarga.assert_not_called()


class SubirTests(FotoBase):
    URL = '/articulos/detalle/7/foto/subir/'

    def test_sube_con_motivo(self):
        self.entrar()
        r = self.client.post(self.URL, {'foto': self.archivo(), 'motivo': ' Mejor foto '}, follow=True)
        self.assertContains(r, 'Foto guardada.')
        args = self.envio.call_args[0]
        self.assertEqual(args[1:3], ('POST', 'articulos/7/foto/'))
        self.assertEqual(args[3], {'motivo': 'Mejor foto'})
        self.assertEqual(args[4], ('foto.jpg', b'\xff\xd8DATOS'))
        self.assertEqual(args[5], 'foto')

    def test_sin_archivo_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post(self.URL, {'motivo': 'x'}, follow=True)
        self.assertContains(r, 'Elige una foto del artículo.')
        self.envio.assert_not_called()

    def test_mas_de_5_mb_se_rechaza_antes_de_enviar(self):
        self.entrar()
        grande = self.archivo(contenido=b'0' * (5 * 1024 * 1024 + 1))
        r = self.client.post(self.URL, {'foto': grande}, follow=True)
        self.assertContains(r, 'pesa más de 5 MB')
        self.envio.assert_not_called()

    def test_muestra_el_error_de_la_api(self):
        self.entrar()
        self.envio.side_effect = ApiError(400, {'motivo': 'Indique el motivo para reemplazar la foto.'})
        r = self.client.post(self.URL, {'foto': self.archivo()}, follow=True)
        self.assertContains(r, 'Indique el motivo para reemplazar la foto.')
        self.assertNotContains(r, 'Foto guardada.')

    def test_consulta_no_puede(self):
        self.entrar(rol='CONSULTA')
        r = self.client.post(self.URL, {'foto': self.archivo()}, follow=True)
        self.assertContains(r, 'Solo el Administrador')
        self.envio.assert_not_called()

    def test_solo_post(self):
        self.entrar()
        self.assertEqual(self.client.get(self.URL).status_code, 405)


class QuitarTests(FotoBase):
    URL = '/articulos/detalle/7/foto/quitar/'

    def test_quita_con_motivo(self):
        self.entrar()
        r = self.client.post(self.URL, {'motivo': 'Era de otro equipo'}, follow=True)
        self.assertContains(r, 'Foto quitada.')
        args = self.envio.call_args[0]
        self.assertEqual(args[1:4], ('DELETE', 'articulos/7/foto/', {'motivo': 'Era de otro equipo'}))

    def test_sin_motivo_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post(self.URL, {'motivo': '  '}, follow=True)
        self.assertContains(r, 'Indica el motivo')
        self.envio.assert_not_called()

    def test_consulta_no_puede(self):
        self.entrar(rol='CONSULTA')
        r = self.client.post(self.URL, {'motivo': 'x'}, follow=True)
        self.assertContains(r, 'Solo el Administrador')
        self.envio.assert_not_called()

    def test_muestra_el_error_de_la_api(self):
        self.entrar()
        self.envio.side_effect = ApiError(400, {'detalle': 'El artículo no tiene foto.'})
        r = self.client.post(self.URL, {'motivo': 'x'}, follow=True)
        self.assertContains(r, 'El artículo no tiene foto.')
