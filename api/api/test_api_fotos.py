"""Foto del artículo (PEND-027)."""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from api.test_api_articulos_movimientos import Base
from articulos import fotos
from articulos.models import Articulo, ArticuloFoto
from auditoria.models import Bitacora


def imagen(formato='JPEG', tam=(300, 200), color=(200, 30, 30), modo='RGB', nombre=None, **extra):
    salida = BytesIO()
    Image.new(modo, tam, color).save(salida, formato, **extra)
    ext = {'JPEG': 'jpg', 'PNG': 'png', 'WEBP': 'webp', 'GIF': 'gif'}[formato]
    return SimpleUploadedFile(nombre or 'f.' + ext, salida.getvalue())


class FotosBase(Base):
    def setUp(self):
        super().setUp()
        self.a = self.alta()
        self.url = '/api/articulos/%d/foto/' % self.a['num']

    def subir(self, archivo, cliente=None, **extra):
        datos = dict(foto=archivo, **extra)
        return (cliente or self.c).post(self.url, datos, format='multipart')

    def filas(self):
        return ArticuloFoto.objects.filter(articulo_id=self.a['num']).count()

    def hash_actual(self):
        return ArticuloFoto.objects.get(articulo_id=self.a['num']).hash


class SubidaTests(FotosBase):
    def test_sin_foto_al_inicio(self):
        self.assertFalse(self.a['tiene_foto'])
        self.assertEqual(self.c.get(self.url).status_code, 404)

    def test_formatos_validos(self):
        for i, f in enumerate([imagen('JPEG'), imagen('PNG'), imagen('WEBP')]):
            r = self.subir(f, motivo='cambio %d' % i)
            self.assertEqual(r.status_code, 200, r.data)
            self.assertTrue(r.data['tiene_foto'])
            g = self.c.get(self.url)
            self.assertEqual(g.status_code, 200)
            self.assertEqual(g['Content-Type'], 'image/jpeg')
            self.assertEqual(Image.open(BytesIO(g.content)).format, 'JPEG')
            self.assertEqual(self.filas(), 1)

    def test_png_con_transparencia_queda_sobre_blanco(self):
        self.subir(imagen('PNG', modo='RGBA', color=(0, 0, 0, 0)))
        img = Image.open(BytesIO(self.c.get(self.url).content))
        self.assertEqual(img.getpixel((5, 5)), (255, 255, 255))

    def test_reduce_a_1200(self):
        self.subir(imagen('JPEG', tam=(3000, 1500)))
        img = Image.open(BytesIO(self.c.get(self.url).content))
        self.assertEqual(img.size, (1200, 600))

    def test_no_agranda_imagenes_chicas(self):
        self.subir(imagen('JPEG', tam=(300, 200)))
        self.assertEqual(Image.open(BytesIO(self.c.get(self.url).content)).size, (300, 200))

    def test_orientacion_exif_y_sin_metadatos(self):
        base = Image.new('RGB', (300, 100), (10, 10, 200))
        exif = Image.Exif()
        exif[0x0112] = 6   # rotar 90°
        exif[0x010F] = 'Marca'
        salida = BytesIO()
        base.save(salida, 'JPEG', exif=exif)
        self.subir(SimpleUploadedFile('c.jpg', salida.getvalue()))
        img = Image.open(BytesIO(self.c.get(self.url).content))
        self.assertEqual(img.size, (100, 300))
        self.assertEqual(len(img.getexif()), 0)

    def test_rechaza_lo_que_no_es_imagen(self):
        r = self.subir(SimpleUploadedFile('f.jpg', b'esto no es una imagen'))
        self.assertEqual(r.status_code, 400)
        self.assertIn('foto', r.data)
        self.assertEqual(self.filas(), 0)

    def test_rechaza_gif_aunque_se_llame_jpg(self):
        g = imagen('GIF', modo='P')
        r = self.subir(SimpleUploadedFile('f.jpg', g.read()))
        self.assertEqual(r.status_code, 400)

    def test_rechaza_mas_de_5_mb(self):
        r = self.subir(SimpleUploadedFile('f.jpg', b'0' * (5 * 1024 * 1024 + 1)))
        self.assertEqual(r.status_code, 400)
        self.assertIn('5 MB', r.data['foto'])

    def test_rechaza_archivo_vacio(self):
        self.assertEqual(self.subir(SimpleUploadedFile('f.jpg', b'')).status_code, 400)

    def test_pide_el_campo(self):
        r = self.c.post(self.url, {'motivo': 'x'}, format='multipart')
        self.assertEqual(r.status_code, 400)
        self.assertIn('foto', r.data)

    def test_articulo_inexistente(self):
        r = self.c.post('/api/articulos/9999/foto/', {'foto': imagen()}, format='multipart')
        self.assertEqual(r.status_code, 404)

    def test_sin_dimensiones_enormes(self):
        original = fotos.MAX_PIXELES
        fotos.MAX_PIXELES = 1000
        self.addCleanup(setattr, fotos, 'MAX_PIXELES', original)
        self.assertEqual(self.subir(imagen('JPEG', tam=(100, 100))).status_code, 400)


class ReemplazoYBajaTests(FotosBase):
    def test_primera_foto_no_pide_motivo_y_queda_en_bitacora(self):
        self.assertEqual(self.subir(imagen()).status_code, 200)
        b = Bitacora.objects.filter(tabla_afectada='articulo', accion='UPDATE').latest('num')
        self.assertEqual(b.motivo, 'Foto agregada')
        self.assertIn('foto', b.valor_nuevo)
        self.assertEqual(b.valor_nuevo, '{"foto": "%s"}' % self.hash_actual()[:12])
        self.assertEqual(b.valor_anterior, '{"foto": null}')

    def test_reemplazar_pide_motivo_y_sustituye_la_anterior(self):
        self.subir(imagen(color=(255, 0, 0)))
        vieja = self.hash_actual()
        r = self.subir(imagen(color=(0, 255, 0)))
        self.assertEqual(r.status_code, 400)
        self.assertIn('motivo', r.data)
        self.assertEqual(self.hash_actual(), vieja)
        r = self.subir(imagen(color=(0, 255, 0)), motivo='Foto más clara')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self.filas(), 1)
        self.assertNotEqual(self.hash_actual(), vieja)
        b = Bitacora.objects.filter(tabla_afectada='articulo', accion='UPDATE').latest('num')
        self.assertEqual(b.motivo, 'Foto más clara')
        self.assertIn(vieja[:12], b.valor_anterior)

    def test_misma_foto_da_400(self):
        f = imagen()
        contenido = f.read()
        self.subir(SimpleUploadedFile('a.jpg', contenido))
        r = self.subir(SimpleUploadedFile('a.jpg', contenido), motivo='otra vez')
        self.assertEqual(r.status_code, 400)

    def test_quitar_pide_motivo(self):
        self.subir(imagen())
        r = self.c.delete(self.url)
        self.assertEqual(r.status_code, 400)
        self.assertIn('motivo', r.data)

    def test_quitar(self):
        self.subir(imagen())
        r = self.c.delete(self.url, {'motivo': 'Era de otro equipo'}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['tiene_foto'])
        self.assertEqual(self.filas(), 0)
        self.assertEqual(self.c.get(self.url).status_code, 404)
        b = Bitacora.objects.filter(tabla_afectada='articulo', accion='UPDATE').latest('num')
        self.assertEqual(b.motivo, 'Era de otro equipo')
        self.assertEqual(b.valor_nuevo, '{"foto": null}')

    def test_quitar_sin_foto(self):
        r = self.c.delete(self.url, {'motivo': 'x'}, format='multipart')
        self.assertEqual(r.status_code, 400)

    def test_si_falla_la_bitacora_no_queda_la_foto(self):
        from unittest import mock
        with mock.patch('articulos.fotos.registrar', side_effect=RuntimeError('x')):
            with self.assertRaises(RuntimeError):
                self.subir(imagen())
        self.assertEqual(self.filas(), 0)

    def test_la_bitacora_no_guarda_los_bytes(self):
        self.subir(imagen())
        for b in Bitacora.objects.all():
            self.assertLess(len(b.valor_nuevo or '') + len(b.valor_anterior or ''), 2000)


class PermisosYSeguridadTests(FotosBase):
    def test_consulta_ve_pero_no_modifica(self):
        self.subir(imagen())
        c = self.cliente(self.obs)
        self.assertEqual(c.get(self.url).status_code, 200)
        self.assertEqual(self.subir(imagen(), cliente=c, motivo='x').status_code, 403)
        self.assertEqual(c.delete(self.url, {'motivo': 'x'}, format='multipart').status_code, 403)
        self.assertEqual(self.filas(), 1)

    def test_sin_sesion(self):
        from rest_framework.test import APIClient
        self.subir(imagen())
        anon = APIClient()
        self.assertEqual(anon.get(self.url).status_code, 401)
        self.assertEqual(anon.post(self.url, {'foto': imagen()}, format='multipart').status_code, 401)

    def test_cabeceras_de_la_imagen(self):
        self.subir(imagen())
        g = self.c.get(self.url)
        self.assertEqual(g['X-Content-Type-Options'], 'nosniff')
        self.assertIn('private', g['Cache-Control'])

    def test_no_se_puede_borrar_el_articulo(self):
        self.assertEqual(self.c.delete('/api/articulos/%d/' % self.a['num']).status_code, 405)

    def test_tiene_foto_en_ficha_y_lista(self):
        self.subir(imagen())
        self.assertTrue(self.c.get('/api/articulos/%d/' % self.a['num']).data['tiene_foto'])
        self.assertTrue(self.c.get('/api/articulos/').data['results'][0]['tiene_foto'])
        self.assertTrue(self.c.get('/api/articulos/todos/').data[0]['tiene_foto'])


class RendimientoTests(FotosBase):
    def test_la_lista_no_lee_los_bytes_ni_hace_una_consulta_por_fila(self):
        for i in range(3):
            a = self.alta(marbete_oficial='02-520-1%04d' % i, num_serie='SNX%d' % i)
            self.c.post('/api/articulos/%d/foto/' % a['num'],
                        {'foto': imagen(color=(i * 40, 9, 9))}, format='multipart')
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as q:
            r = self.c.get('/api/articulos/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(x['tiene_foto'] for x in r.data['results'] if x['num'] != self.a['num']))
        self.assertFalse(any('imagen' in x['sql'] for x in q.captured_queries))
        self.assertLess(len(q.captured_queries), 8)
