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


def fila(hoja='Activos', numero=2, estado='valida', errores=None, avisos=None, **datos):
    base = {'identificador': 'M-1', 'categoria': 'Equipo de cómputo', 'tipo_articulo': 'Laptop',
            'marca': 'Dell', 'modelo': 'Latitude', 'num_serie': 'SN-1', 'color': 'Negro',
            'descripcion': 'Laptop', 'ubicacion': 'UBI-LAB1 · Laboratorio 1',
            'resguardante': 'E003 · Juan Pérez', 'estado_operativo': 'Útil',
            'fecha_adquisicion': '15/01/2024', 'costo_adquisicion': '12500', 'donado': 'No',
            'origen': 'Activo'}
    base.update(datos)
    return {'hoja': hoja, 'fila': numero, 'estado': estado, 'errores': errores or {},
            'avisos': avisos or {}, 'datos': base}


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


def previa_con_folios(**cambios):
    """Dos Comodatos/Enseres sin folio y uno con folio propio."""
    datos = dict(
        total=3, validas=3, con_error=0,
        hojas=[{'hoja': 'Comodatos', 'origen': 'Comodato', 'filas': 2, 'validas': 2, 'con_error': 0},
               {'hoja': 'Enseres', 'origen': 'Enser', 'filas': 1, 'validas': 1, 'con_error': 0}],
        filas=[fila(hoja='Comodatos', numero=2, identificador=None, origen='Comodato'),
               fila(hoja='Comodatos', numero=3, identificador='COM-HIST-77', origen='Comodato'),
               fila(hoja='Enseres', numero=2, identificador=None, origen='Enser')])
    datos.update(cambios)
    return previa(**datos)


class FoliosNuevosTests(BaseCarga):
    def test_la_vista_previa_avisa_cuantos_folios_se_asignaran(self):
        self.entrar()
        self.enviar.return_value = previa_con_folios()
        r = self.subir()
        self.assertContains(r, 'Se asignarán 2 folios nuevos')
        self.assertContains(r, 'id="aceptoFolios"')
        self.assertContains(r, 'name="acepto_folios"')
        # El botón que abre la confirmación nace deshabilitado hasta marcar la casilla.
        self.assertRegex(r.content.decode(), r'id="btnAbrirCarga"[^>]*\bdisabled\b')
        self.assertEqual(self.client.session['carga_masiva']['sin_folio'],
                         [['Comodatos', 2], ['Enseres', 2]])

    def test_un_solo_folio_va_en_singular(self):
        self.entrar()
        self.enviar.return_value = previa_con_folios(
            filas=[fila(hoja='Comodatos', identificador=None, origen='Comodato')],
            total=1, validas=1)
        r = self.subir()
        self.assertContains(r, 'Se asignarán 1 folio nuevo')

    def test_sin_filas_sin_folio_no_hay_casilla_y_el_boton_esta_activo(self):
        self.entrar()
        self.enviar.return_value = previa()
        r = self.subir()
        self.assertNotContains(r, 'id="aceptoFolios"')
        self.assertNotRegex(r.content.decode(), r'id="btnAbrirCarga"[^>]*\bdisabled\b')

    def test_filas_con_error_sin_folio_no_cuentan(self):
        self.entrar()
        malo = fila(hoja='Enseres', numero=5, estado='error', identificador=None, origen='Enser',
                    errores={'color': 'Este dato es obligatorio.'})
        self.enviar.return_value = previa_con_folios(filas=[malo], total=1, validas=0, con_error=1)
        self.assertNotContains(self.subir(), 'Se asignarán')

    def test_activos_nunca_cuentan_como_sin_folio(self):
        self.entrar()
        self.enviar.return_value = previa(filas=[fila(identificador=None)], total=1, validas=1, con_error=0)
        self.assertNotContains(self.subir(), 'Se asignarán')

    def test_el_servidor_rechaza_confirmar_sin_la_casilla(self):
        self.entrar()
        self.enviar.return_value = previa_con_folios()
        self.subir()
        self.enviar.reset_mock()
        r = self.client.post('/articulos/carga-masiva/confirmar/', follow=True)
        self.assertContains(r, 'Marca la casilla que confirma la asignación de 2 folios nuevos')
        self.enviar.assert_not_called()

    def test_casilla_con_otro_valor_tampoco_cuenta(self):
        self.entrar()
        self.enviar.return_value = previa_con_folios()
        self.subir()
        self.enviar.reset_mock()
        self.client.post('/articulos/carga-masiva/confirmar/', {'acepto_folios': 'no'})
        self.enviar.assert_not_called()

    def test_con_la_casilla_marcada_se_carga_y_el_resultado_lista_los_folios(self):
        self.entrar()
        self.enviar.return_value = previa_con_folios()
        self.subir()
        self.enviar.return_value = {
            'archivo': 'inventario.xlsx', 'hash': 'abc123', 'total': 3, 'cargados': 3, 'rechazados': 0,
            'hojas': [], 'filas_rechazadas': [],
            'articulos': [
                {'hoja': 'Comodatos', 'fila': 2, 'num': 21, 'identificador': '021431126-001'},
                {'hoja': 'Comodatos', 'fila': 3, 'num': 22, 'identificador': 'COM-HIST-77'},
                {'hoja': 'Enseres', 'fila': 2, 'num': 23, 'identificador': '021431126-002'}]}
        self.enviar.reset_mock()
        r = self.client.post('/articulos/carga-masiva/confirmar/', {'acepto_folios': 'on'})
        self.enviar.assert_called_once()
        html = r.content.decode()
        self.assertContains(r, 'Folios asignados (2)')
        bloque = html[html.index('id="cargaFoliosAsignados"'):]
        bloque = bloque[:bloque.index('</table>')]
        self.assertIn('021431126-001', bloque)
        self.assertIn('021431126-002', bloque)
        self.assertNotIn('COM-HIST-77', bloque)               # ya traía su folio
        self.assertContains(r, 'badge-estado--azul">Folio asignado', count=2)

    def test_sin_folios_nuevos_el_resultado_no_tiene_la_seccion(self):
        self.entrar()
        self.enviar.return_value = previa()
        self.subir()
        self.enviar.return_value = {
            'archivo': 'x.xlsx', 'hash': 'abc123', 'total': 1, 'cargados': 1, 'rechazados': 0,
            'hojas': [], 'filas_rechazadas': [],
            'articulos': [{'hoja': 'Activos', 'fila': 2, 'num': 15, 'identificador': 'M-1'}]}
        r = self.client.post('/articulos/carga-masiva/confirmar/')
        self.assertNotContains(r, 'Folios asignados')

    def test_si_la_api_falla_se_olvida_la_copia(self):
        self.entrar()
        self.enviar.return_value = previa_con_folios()
        self.subir()
        self.enviar.side_effect = ApiError(400, {'archivo': 'No hay filas válidas que cargar.'})
        self.client.post('/articulos/carga-masiva/confirmar/', {'acepto_folios': 'on'})
        self.assertEqual(self.copias(), [])


class AvisosTests(BaseCarga):
    def con_avisos(self):
        return previa(
            total=2, validas=2, con_error=0,
            filas=[fila(avisos={'marca': 'S/M se tomó como vacío.'}),
                   fila(numero=3, num_serie=None,
                        avisos={'identificador': 'Posible duplicado: coincide con la fila 2.'}),
                   ])

    def test_avisos_en_columna_aparte_de_los_errores(self):
        self.entrar()
        datos = self.con_avisos()
        datos['filas'][1]['estado'] = 'error'
        datos['filas'][1]['errores'] = {'color': 'Este dato es obligatorio.'}
        self.enviar.return_value = datos
        r = self.subir()
        html = r.content.decode()
        self.assertIn('<th>Avisos</th>', html)
        # El aviso está en su propia celda, no dentro de la lista de errores.
        self.assertContains(r, '<td data-label="Avisos">', count=2)
        self.assertContains(r, 'class="carga-avisos"', count=2)
        self.assertContains(r, 'Marca:</strong> S/M se tomó como vacío.')
        self.assertContains(r, 'Marbete o folio:</strong> Posible duplicado')
        errores = html[html.index('class="carga-errores"'):]
        errores = errores[:errores.index('</ul>')]
        self.assertNotIn('Posible duplicado', errores)

    def test_cuenta_las_filas_con_avisos_y_no_bloquea(self):
        self.entrar()
        self.enviar.return_value = self.con_avisos()
        r = self.subir()
        self.assertContains(r, 'Con avisos (no bloquean)')
        self.assertEqual(r.context['con_avisos'], 2)
        self.assertContains(r, 'Cargar 2 artículos')

    def test_sin_avisos_la_celda_va_vacia(self):
        self.entrar()
        self.enviar.return_value = previa()
        r = self.subir()
        self.assertEqual(r.context['con_avisos'], 0)
        self.assertNotContains(r, 'class="carga-avisos"')


class RedireccionTests(BaseCliente):
    def test_las_urls_viejas_de_equipos_redirigen(self):
        self.entrar()
        r = self.client.get('/equipos/detalle/7/?x=1')
        self.assertRedirects(r, '/articulos/detalle/7/?x=1', status_code=301,
                             fetch_redirect_response=False)
