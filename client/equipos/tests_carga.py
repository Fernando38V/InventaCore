"""Pruebas de la carga masiva en el cliente. La API se simula: estas pruebas
revisan qué se le manda, qué se guarda entre la vista previa y la
confirmación, y qué ve el usuario."""
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from catalogos.tests import BaseCliente
from client.api import ApiError

XLSX = b'PK\x03\x04 contenido de prueba'


def fila(hoja='Activos', numero=2, estado='valida', errores=None, **datos):
    base = {'identificador': 'M-1', 'categoria': 'Equipo de cómputo', 'tipo_articulo': 'Laptop',
            'marca': 'Dell', 'modelo': 'Latitude', 'num_serie': 'SN-1', 'color': 'Negro',
            'descripcion': 'Laptop', 'ubicacion': 'UBI-LAB1 · Laboratorio 1',
            'resguardante': 'E003 · Juan Pérez', 'estado_operativo': 'Útil',
            'fecha_adquisicion': '15/01/2024', 'costo_adquisicion': '12500', 'donado': 'No',
            'origen': 'Activo'}
    base.update(datos)
    return {'hoja': hoja, 'fila': numero, 'estado': estado, 'errores': errores or {},
            'datos': base}


def previa(**cambios):
    p = {
        'archivo': 'inventario.xlsx', 'hash': 'abc123', 'total': 2, 'validas': 1, 'con_error': 1,
        'ya_cargado': None, 'hojas_ignoradas': [],
        'hojas': [{'hoja': 'Activos', 'origen': 'Activo', 'filas': 2, 'validas': 1, 'con_error': 1}],
        'columnas': {'identificador': 'Marbete o folio', 'categoria': 'Categoría',
                     'num_serie': 'Número de serie'},
        'filas': [fila(),
                  fila(numero=3, estado='error', identificador='M-1', num_serie='SN-1',
                       errores={'identificador': 'Repetido: ya aparece en la fila 2 de la hoja Activos.'})],
    }
    p.update(cambios)
    return p


@override_settings(CARGA_MASIVA_DIR=None)
class BaseCarga(BaseCliente):
    def setUp(self):
        super().setUp()
        self.carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.carpeta, ignore_errors=True)
        ajuste = override_settings(CARGA_MASIVA_DIR=self.carpeta)
        ajuste.enable()
        self.addCleanup(ajuste.disable)
        self.enviar = MagicMock()
        self.descargar = MagicMock()
        for nombre, falso in (('enviar_archivo', self.enviar), ('descargar', self.descargar)):
            parche = patch('equipos.views_carga.' + nombre, falso)
            parche.start()
            self.addCleanup(parche.stop)

    def subir(self, nombre='inventario.xlsx', contenido=XLSX):
        return self.client.post('/articulos/carga-masiva/',
                                {'archivo': SimpleUploadedFile(nombre, contenido)})

    def copias(self):
        return os.listdir(self.carpeta)


class PermisosTests(BaseCarga):
    def test_consulta_no_entra(self):
        self.entrar('CONSULTA')
        for metodo, url in (('get', '/articulos/carga-masiva/'),
                            ('get', '/articulos/carga-masiva/plantilla/'),
                            ('post', '/articulos/carga-masiva/'),
                            ('post', '/articulos/carga-masiva/confirmar/')):
            r = getattr(self.client, metodo)(url)
            self.assertRedirects(r, '/articulos/', fetch_redirect_response=False)
        self.enviar.assert_not_called()
        self.descargar.assert_not_called()

    def test_boton_en_el_listado_solo_para_admin(self):
        self.api.respuestas[('GET', 'articulos/')] = {'count': 0, 'next': None, 'previous': None, 'results': []}
        for ruta in ('ubicaciones/', 'categorias/', 'origenes/', 'estados-operativos/', 'estados-registro/'):
            self.api.respuestas[('GET', ruta)] = []
        patch('equipos.views.llamar', self.api).start()
        self.addCleanup(patch.stopall)
        self.entrar()
        self.assertContains(self.client.get('/articulos/'), '/articulos/carga-masiva/')
        self.entrar('CONSULTA')
        self.assertNotContains(self.client.get('/articulos/'), '/articulos/carga-masiva/')


class PlantillaTests(BaseCarga):
    def test_descarga_la_plantilla_de_la_api(self):
        self.entrar()
        self.descargar.return_value = XLSX
        r = self.client.get('/articulos/carga-masiva/plantilla/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, XLSX)
        self.assertIn('plantilla_carga_masiva.xlsx', r['Content-Disposition'])
        self.assertEqual(self.descargar.call_args[0][1], 'carga-masiva/plantilla/')

    def test_error_de_la_api_regresa_con_aviso(self):
        self.entrar()
        self.descargar.side_effect = ApiError(0, {'detalle': 'No se pudo conectar con el servidor.'})
        r = self.client.get('/articulos/carga-masiva/plantilla/', follow=True)
        self.assertContains(r, 'No se pudo descargar la plantilla')


class SubirTests(BaseCarga):
    def test_pantalla_inicial(self):
        self.entrar()
        r = self.client.get('/articulos/carga-masiva/')
        self.assertContains(r, 'Descargar plantilla')
        self.assertContains(r, 'enctype="multipart/form-data"')

    def test_sin_archivo_o_con_otra_extension_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/articulos/carga-masiva/')
        self.assertContains(r, 'Elige el archivo de Excel')
        r = self.subir('inventario.csv')
        self.assertContains(r, 'debe ser de Excel (.xlsx)')
        self.enviar.assert_not_called()

    def test_archivo_de_mas_de_5_mb(self):
        self.entrar()
        r = self.subir(contenido=b'PK' + b'0' * (5 * 1024 * 1024))
        self.assertContains(r, 'pesa más de 5 MB')
        self.enviar.assert_not_called()

    def test_vista_previa_muestra_resumen_filas_y_errores(self):
        self.entrar()
        self.enviar.return_value = previa()
        r = self.subir()
        args = self.enviar.call_args[0]
        self.assertEqual(args[1:4], ('carga-masiva/validar/', 'inventario.xlsx', XLSX))
        self.assertContains(r, 'Vista previa')
        self.assertContains(r, 'Con error (1)')
        self.assertContains(r, 'Válidas (1)')
        self.assertContains(r, 'Marbete o folio:</strong> Repetido: ya aparece en la fila 2')
        self.assertContains(r, 'class="celda-error"', count=1)
        self.assertContains(r, 'Cargar 1 artículo')
        # Se guarda una copia para confirmar sin volver a subirlo.
        self.assertEqual(len(self.copias()), 1)
        self.assertEqual(self.client.session['carga_masiva']['hash'], 'abc123')

    def test_folio_vacio_en_comodato_lo_asigna_el_sistema(self):
        self.entrar()
        self.enviar.return_value = previa(filas=[fila(hoja='Comodatos', identificador=None, origen='Comodato')],
                                          total=1, validas=1, con_error=0)
        self.assertContains(self.subir(), 'Lo asigna el sistema')

    def test_error_del_archivo_se_muestra(self):
        self.entrar()
        self.enviar.side_effect = ApiError(400, {'archivo': 'Faltan columnas en la hoja "Activos": Color.'})
        r = self.subir()
        self.assertContains(r, 'Faltan columnas en la hoja')
        self.assertEqual(self.copias(), [])

    def test_archivo_ya_cargado_no_deja_confirmar(self):
        self.entrar()
        self.enviar.return_value = previa(ya_cargado={'fecha': '2026-11-04 10:00', 'usuario': 'admin'})
        r = self.subir()
        self.assertContains(r, 'ya se cargó el 2026-11-04 10:00')
        self.assertNotContains(r, 'data-bs-target="#modalCarga"')

    def test_sin_filas_validas_no_deja_confirmar(self):
        self.entrar()
        self.enviar.return_value = previa(validas=0, con_error=2)
        self.assertContains(self.subir(), 'No hay filas válidas')

    def test_hojas_ignoradas(self):
        self.entrar()
        self.enviar.return_value = previa(hojas_ignoradas=['Hoja1'])
        self.assertContains(self.subir(), 'Se ignoraron estas hojas')

    def test_subir_otro_archivo_borra_la_copia_anterior(self):
        self.entrar()
        self.enviar.return_value = previa()
        self.subir()
        primera = self.copias()
        self.subir()
        self.assertEqual(len(self.copias()), 1)
        self.assertNotEqual(self.copias(), primera)


class ConfirmarTests(BaseCarga):
    def preparar(self):
        self.entrar()
        self.enviar.return_value = previa()
        self.subir()
        self.enviar.reset_mock()

    def test_manda_el_mismo_archivo_con_su_hash_y_muestra_el_resultado(self):
        self.preparar()
        self.enviar.return_value = {
            'archivo': 'inventario.xlsx', 'hash': 'abc123', 'total': 2, 'cargados': 1, 'rechazados': 1,
            'hojas': [], 'articulos': [{'hoja': 'Activos', 'fila': 2, 'num': 15, 'identificador': 'M-1'}],
            'filas_rechazadas': [fila(numero=3, estado='error', errores={'num_serie': 'Duplicado.'})]}
        r = self.client.post('/articulos/carga-masiva/confirmar/')
        args = self.enviar.call_args[0]
        self.assertEqual(args[1:], ('carga-masiva/confirmar/', 'inventario.xlsx', XLSX, {'hash': 'abc123'}))
        self.assertContains(r, 'Se cargaron <strong>1</strong> artículo')
        self.assertContains(r, '/articulos/detalle/15/')
        self.assertContains(r, 'Número de serie:</strong> Duplicado.')
        self.assertEqual(self.copias(), [])
        self.assertNotIn('carga_masiva', self.client.session)

    def test_sin_vista_previa_pide_subirlo_de_nuevo(self):
        self.entrar()
        r = self.client.post('/articulos/carga-masiva/confirmar/', follow=True)
        self.assertContains(r, 'Sube el archivo de nuevo')
        self.enviar.assert_not_called()

    def test_confirmar_por_get_no_se_permite(self):
        self.entrar()
        self.assertEqual(self.client.get('/articulos/carga-masiva/confirmar/').status_code, 405)

    def test_error_de_la_api_regresa_al_paso_1(self):
        self.preparar()
        self.enviar.side_effect = ApiError(400, {'archivo': 'El archivo no es el mismo que se revisó.'})
        r = self.client.post('/articulos/carga-masiva/confirmar/', follow=True)
        self.assertContains(r, 'El archivo no es el mismo que se revisó.')
        self.assertEqual(self.copias(), [])

    def test_sin_conexion_avisa_que_revise_el_listado(self):
        self.preparar()
        self.enviar.side_effect = ApiError(0, {'detalle': 'El servidor tardó demasiado en responder.'})
        r = self.client.post('/articulos/carga-masiva/confirmar/', follow=True)
        self.assertContains(r, 'Revisa en el listado si los artículos se cargaron')


class RedireccionTests(BaseCliente):
    def test_las_urls_viejas_de_equipos_redirigen(self):
        self.entrar()
        r = self.client.get('/equipos/detalle/7/?x=1')
        self.assertRedirects(r, '/articulos/detalle/7/?x=1', status_code=301,
                             fetch_redirect_response=False)
