"""Pruebas de la pantalla de resguardos (DEC-007, DEC-016, DEC-001, DEC-019)."""
from unittest.mock import MagicMock, patch

from catalogos.tests import BaseCliente, pagina
from client.api import ApiError

ANA = {'num': 1, 'numero_empleado': 'E-001', 'nombre': 'Ana López Ruiz'}
LUIS = {'num': 2, 'numero_empleado': 'E-002', 'nombre': 'Luis Mora'}


def asignacion(folio='MOV-0002', persona=ANA, articulo=7, entrega=None):
    return {
        'num': int(folio.split('-')[1]), 'folio': folio, 'fecha': '2026-11-04 10:00',
        'fecha_dia': '2026-11-04', 'fecha_hora': '10:00',
        'tipo': {'codigo': 'REUB', 'nombre': 'Reubicación'},
        'requiere_resguardo': True, 'resguardo': None,
        'articulo': {'num': articulo, 'identificador': 'M-%03d' % articulo, 'descripcion': 'Laptop'},
        'ubicacion_origen': {'codigo': 'UBI-LAB1', 'nombre': 'Laboratorio 1'},
        'ubicacion_llegada': {'codigo': 'UBI-OFI', 'nombre': 'Oficina'},
        'personal_asigna': persona, 'personal_entrega': entrega, 'nota': 'Cambio'}


def resguardo(folio='RES-0001', persona=ANA, bienes=('MOV-0002',)):
    return {
        'folio': folio, 'fecha_emision': '2026-11-05 09:30', 'resguardante': persona,
        'usuario_emisor': {'num': 1, 'username': 'admin'}, 'numero_bienes': len(bienes),
        'hash_pdf': 'x' * 64, 'pdf': '/api/resguardos/%s/pdf/' % folio,
        'articulos': [{'num': 7, 'identificador': 'M-007', 'descripcion': 'Laptop', 'movimiento': m}
                      for m in bienes]}


class BaseResguardos(BaseCliente):
    def setUp(self):
        super().setUp()
        self.descargar = MagicMock(return_value=b'%PDF-1.4 prueba')
        for destino, falso in (('movimientos.views_resguardos.llamar', self.api),
                               ('movimientos.views_resguardos.descargar', self.descargar)):
            parche = patch(destino, falso)
            parche.start()
            self.addCleanup(parche.stop)

    def pendientes(self, *movs):
        self.api.respuestas[('GET', 'resguardos/pendientes/')] = pagina(list(movs))


class PendientesTests(BaseResguardos):
    def test_agrupa_por_resguardante_y_preselecciona(self):
        self.entrar()
        self.pendientes(asignacion('MOV-0002', ANA), asignacion('MOV-0003', LUIS, 8),
                        asignacion('MOV-0004', ANA, 9))
        r = self.client.get('/movimientos/resguardos/?vista=pendientes')
        self.assertEqual([g['persona']['nombre'] for g in r.context['grupos']],
                         ['Ana López Ruiz', 'Luis Mora'])
        self.assertEqual(len(r.context['grupos'][0]['movimientos']), 2)
        self.assertContains(r, 'name="resguardante" value="1"')
        self.assertContains(r, 'name="movimientos" value="MOV-0004" checked')
        self.assertContains(r, 'Emitir resguardo', count=2)
        self.assertContains(r, 'Resguardos por emitir<span class="cat-tabs__contador">3</span>')

    def test_sin_vista_abre_pendientes_si_hay_y_si_no_emitidos(self):
        self.entrar()
        self.pendientes(asignacion())
        self.assertEqual(self.client.get('/movimientos/resguardos/').context['vista'], 'pendientes')
        self.pendientes()
        self.assertEqual(self.client.get('/movimientos/resguardos/').context['vista'], 'emitidos')

    def test_consulta_ve_pendientes_pero_no_puede_emitir(self):
        self.entrar('CONSULTA')
        self.pendientes(asignacion())
        r = self.client.get('/movimientos/resguardos/?vista=pendientes')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Ana López Ruiz')
        self.assertNotContains(r, 'name="movimientos" value=')
        self.assertNotContains(r, 'Emitir resguardo</button>')
        self.assertContains(r, 'Solo el Administrador emite resguardos.')

    def test_sin_pendientes(self):
        self.entrar()
        r = self.client.get('/movimientos/resguardos/?vista=pendientes')
        self.assertContains(r, 'No hay resguardos por emitir')

    def test_error_de_la_api_se_muestra(self):
        self.entrar()
        self.api.respuestas[('GET', 'resguardos/pendientes/')] = ApiError(0, {'detalle': 'No se pudo conectar con el servidor.'})
        r = self.client.get('/movimientos/resguardos/?vista=pendientes')
        self.assertContains(r, 'No se pudo conectar con el servidor.')


class EmitirTests(BaseResguardos):
    def test_manda_resguardante_y_folios_y_avisa(self):
        self.entrar()
        self.api.respuestas[('POST', 'resguardos/')] = resguardo(bienes=('MOV-0002', 'MOV-0004'))
        r = self.client.post('/movimientos/resguardos/emitir/',
                             {'resguardante': '1', 'movimientos': ['MOV-0002', 'MOV-0004']})
        self.assertRedirects(r, '/movimientos/resguardos/?vista=emitidos', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [
            ('POST', 'resguardos/', {'resguardante': 1, 'movimientos': ['MOV-0002', 'MOV-0004']})])
        self.api.respuestas[('GET', 'resguardos/')] = pagina([resguardo(bienes=('MOV-0002', 'MOV-0004'))])
        r = self.client.get('/movimientos/resguardos/?vista=emitidos')
        self.assertContains(r, 'Se emitió el resguardo RES-0001 de Ana López Ruiz con 2 bienes')
        self.assertContains(r, 'class="fila-nueva"')
        # El resaltado se ve una sola vez.
        r = self.client.get('/movimientos/resguardos/?vista=emitidos')
        self.assertNotContains(r, 'class="fila-nueva"')

    def test_consulta_no_puede_emitir_aunque_mande_el_post(self):
        self.entrar('CONSULTA')
        r = self.client.post('/movimientos/resguardos/emitir/',
                             {'resguardante': '1', 'movimientos': ['MOV-0002']}, follow=True)
        self.assertContains(r, 'Solo el Administrador emite resguardos.')
        self.assertEqual(self.api.escrituras(), [])

    def test_sin_asignaciones_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/movimientos/resguardos/emitir/', {'resguardante': '1'}, follow=True)
        self.assertContains(r, 'Selecciona al menos una asignación')
        self.assertEqual(self.api.escrituras(), [])

    def test_sin_resguardante_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/movimientos/resguardos/emitir/', {'movimientos': ['MOV-0002']}, follow=True)
        self.assertContains(r, 'Falta el resguardante.')
        self.assertEqual(self.api.escrituras(), [])

    def test_errores_de_la_api_se_muestran(self):
        self.entrar()
        self.api.respuestas[('POST', 'resguardos/')] = ApiError(
            400, {'movimientos': ['MOV-0002 ya está documentado en otro resguardo.']})
        r = self.client.post('/movimientos/resguardos/emitir/',
                             {'resguardante': '1', 'movimientos': ['MOV-0002']}, follow=True)
        self.assertContains(r, 'No se emitió el resguardo. MOV-0002 ya está documentado en otro resguardo.')

    def test_falta_la_contadora_en_settings(self):
        self.entrar()
        self.api.respuestas[('POST', 'resguardos/')] = ApiError(
            400, {'detalle': 'Falta CONTADORA_NOMBRE en settings.py.'})
        r = self.client.post('/movimientos/resguardos/emitir/',
                             {'resguardante': '1', 'movimientos': ['MOV-0002']}, follow=True)
        self.assertContains(r, 'CONTADORA_NOMBRE')

    def test_emitir_por_get_no_se_permite(self):
        self.entrar()
        self.assertEqual(self.client.get('/movimientos/resguardos/emitir/').status_code, 405)


class EmitidosTests(BaseResguardos):
    def test_lista_con_ver_y_descargar(self):
        self.entrar('CONSULTA')
        self.api.respuestas[('GET', 'resguardos/')] = pagina([resguardo()])
        r = self.client.get('/movimientos/resguardos/?vista=emitidos')
        self.assertContains(r, 'RES-0001')
        self.assertContains(r, 'href="/movimientos/resguardos/RES-0001/pdf/" target="_blank"')
        self.assertContains(r, 'href="/movimientos/resguardos/RES-0001/pdf/?descargar=1"')

    def test_busqueda_y_pagina_van_a_la_api(self):
        self.entrar()
        self.client.get('/movimientos/resguardos/?vista=emitidos&q=Ana&page=2')
        rutas = [ll[1] for ll in self.api.llamadas if ll[1].startswith('resguardos/?')]
        self.assertEqual(rutas, ['resguardos/?page=2&q=Ana'])


class PdfTests(BaseResguardos):
    def test_consulta_ve_el_pdf_en_linea(self):
        self.entrar('CONSULTA')
        r = self.client.get('/movimientos/resguardos/RES-0001/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertEqual(r['Content-Disposition'], 'inline; filename="RES-0001.pdf"')
        self.assertEqual(r.content, b'%PDF-1.4 prueba')
        self.assertEqual(self.descargar.call_args[0][1], 'resguardos/RES-0001/pdf/')

    def test_descargar_lo_baja_como_archivo(self):
        self.entrar()
        r = self.client.get('/movimientos/resguardos/RES-0001/pdf/?descargar=1')
        self.assertEqual(r['Content-Disposition'], 'attachment; filename="RES-0001.pdf"')

    def test_archivo_alterado_409(self):
        self.entrar()
        self.descargar.side_effect = ApiError(409, {'detalle': 'El archivo no coincide.'})
        r = self.client.get('/movimientos/resguardos/RES-0001/pdf/', follow=True)
        self.assertContains(r, 'no coincide con el que se emitió')

    def test_folio_con_otro_formato_no_existe(self):
        self.entrar()
        self.assertEqual(self.client.get('/movimientos/resguardos/../pdf/').status_code, 404)
        self.assertEqual(self.client.get('/movimientos/resguardos/ABC/pdf/').status_code, 404)
        self.descargar.assert_not_called()


class ListadoMovimientosTests(BaseResguardos):
    def test_pestanas_y_enlace_al_resguardo(self):
        self.entrar('CONSULTA')
        patch('movimientos.views.llamar', self.api).start()
        self.addCleanup(patch.stopall)
        self.api.respuestas[('GET', 'movimientos/')] = pagina([
            asignacion('MOV-0002'), dict(asignacion('MOV-0003'), resguardo='RES-0001')])
        self.api.respuestas[('GET', 'resguardos/pendientes/')] = dict(pagina([asignacion()]), count=1)
        r = self.client.get('/movimientos/')
        self.assertContains(r, 'Resguardos emitidos')
        self.assertContains(r, 'Resguardo pendiente')
        self.assertContains(r, 'href="/movimientos/resguardos/RES-0001/pdf/"')

    def test_menu_de_consulta_sigue_con_cuatro_modulos(self):
        self.entrar('CONSULTA')
        patch('movimientos.views.llamar', self.api).start()
        self.addCleanup(patch.stopall)
        r = self.client.get('/movimientos/resguardos/')
        html = r.content.decode()
        menu = html[html.index('sidebar__nav'):html.index('sidebar__footer')]
        self.assertEqual(menu.count('class="sidebar__link'), 4)
