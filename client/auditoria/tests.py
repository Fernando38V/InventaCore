"""Pruebas de la Bitácora (RF-21), con la API simulada.

Comprueban lo que el cliente pide a GET /bitacora/ y cómo muestra lo que
responde. El recorrido contra la API real se hace a mano.

    python manage.py test auditoria
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from catalogos.tests import ApiFalsa, pagina
from client.api import ApiError, SesionVencida


def registro(**cambios):
    b = {
        'num': 3, 'fecha_hora': '2026-11-11T10:18:52.530987-08:00',
        'usuario': {'num': 1, 'username': 'admin', 'nombre': 'Admin Prueba'},
        'modulo': 'articulos', 'accion': 'UPDATE', 'accion_nombre': 'Modificación',
        'tabla_afectada': 'articulo', 'registro_id': '12', 'motivo': 'Marca mal capturada',
        'valor_anterior': {'marca': 'Dell'}, 'valor_nuevo': {'marca': 'HP'},
    }
    b.update(cambios)
    return b


CUENTAS = [{'num': 1, 'username': 'admin', 'empleado': 'Admin Prueba'},
           {'num': 2, 'username': 'maria', 'empleado': 'María López Ruiz'}]


class BaseBitacora(TestCase):
    def setUp(self):
        self.api = ApiFalsa()
        self.api.respuestas[('GET', 'usuarios/')] = pagina(CUENTAS)
        for destino in ('auditoria.views.llamar', 'client.utils.llamar'):
            parche = patch(destino, self.api)
            parche.start()
            self.addCleanup(parche.stop)

    def entrar(self, rol='ADMIN'):
        sesion = self.client.session
        sesion['api_token'] = 'token'
        sesion['usuario'] = {'num': 1, 'username': 'admin', 'empleado': 'Admin Prueba',
                             'rol': rol, 'rol_nombre': rol.title()}
        sesion.save()

    def ruta_bitacora(self):
        return [ll[1] for ll in self.api.llamadas if ll[1].startswith('bitacora/')][0]


class PermisosTests(BaseBitacora):
    def test_sin_sesion_va_al_login(self):
        r = self.client.get('/auditoria/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/cuentas/login/', r['Location'])

    def test_consulta_no_entra_ni_llama_a_la_api(self):
        self.entrar('CONSULTA')
        r = self.client.get('/auditoria/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.api.llamadas, [])

    def test_administrador_entra(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()])
        r = self.client.get('/auditoria/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Bitácora')

    def test_la_pantalla_no_escribe_nada(self):
        self.entrar()
        self.client.get('/auditoria/')
        self.assertEqual(self.api.escrituras(), [])

    def test_403_de_la_api_se_muestra(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = ApiError(
            403, {'detail': 'No tiene permiso para realizar esta acción.'})
        r = self.client.get('/auditoria/')
        self.assertContains(r, 'No tiene permiso')
        self.assertContains(r, 'No se pudo cargar la bitácora')


class FiltrosTests(BaseBitacora):
    def test_manda_pagina_y_todos_los_filtros(self):
        self.entrar()
        hoy = timezone.localdate()
        desde, hasta = (hoy - timedelta(days=10)).isoformat(), hoy.isoformat()
        self.client.get('/auditoria/?q=dell&usuario=2&modulo=articulos&accion=UPDATE'
                        '&fecha_desde=%s&fecha_hasta=%s&page=2' % (desde, hasta))
        ruta = self.ruta_bitacora()
        for parte in ('q=dell', 'usuario=2', 'modulo=articulos', 'accion=UPDATE',
                      'fecha_desde=' + desde, 'fecha_hasta=' + hasta, 'page=2'):
            self.assertIn(parte, ruta)

    def test_sin_filtros_solo_pide_la_pagina(self):
        self.entrar()
        self.client.get('/auditoria/')
        self.assertEqual(self.ruta_bitacora(), 'bitacora/?page=1')

    def test_accion_y_fechas_invalidas_no_llegan_a_la_api(self):
        self.entrar()
        self.client.get('/auditoria/?accion=BORRAR&fecha_desde=11/11/2026&fecha_hasta=ayer')
        ruta = self.ruta_bitacora()
        self.assertNotIn('accion=', ruta)
        self.assertNotIn('fecha_', ruta)

    def test_historial_de_un_registro(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()])
        r = self.client.get('/auditoria/?tabla_afectada=articulo&registro_id=12')
        ruta = self.ruta_bitacora()
        self.assertIn('tabla_afectada=articulo', ruta)
        self.assertIn('registro_id=12', ruta)
        self.assertContains(r, 'Historial de')
        self.assertContains(r, 'Ver toda la bitácora')

    def test_historial_del_articulo_muestra_marbete_y_descripcion(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()])
        self.api.respuestas[('GET', 'articulos/12/')] = {
            'num': 12, 'marbete_oficial': 'M-0456', 'folio_interno': None,
            'descripcion': 'Laptop Dell Latitude'}
        r = self.client.get('/auditoria/?tabla_afectada=articulo&registro_id=12')
        self.assertContains(r, 'Marbete M-0456')
        self.assertContains(r, 'Laptop Dell Latitude')
        self.assertContains(r, 'href="/articulos/detalle/12/"')
        self.assertNotContains(r, 'Historial de <strong>Artículo 12')

    def test_historial_de_comodato_usa_el_folio_interno(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/12/')] = {
            'num': 12, 'marbete_oficial': None, 'folio_interno': 'COM-0003', 'descripcion': 'Silla'}
        r = self.client.get('/auditoria/?tabla_afectada=articulo&registro_id=12')
        self.assertContains(r, 'Folio interno COM-0003')

    def test_historial_sin_datos_del_articulo_cae_al_numero(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/12/')] = ApiError(404, {'detail': 'No encontrado.'})
        r = self.client.get('/auditoria/?tabla_afectada=articulo&registro_id=12')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Artículo 12')

    def test_historial_de_otra_tabla_no_consulta_articulos(self):
        self.entrar()
        self.client.get('/auditoria/?tabla_afectada=movimiento&registro_id=MOV-0007')
        self.assertFalse([ll for ll in self.api.llamadas if ll[1].startswith('articulos/')])

    def test_fechas_futuras_no_se_envian_y_los_campos_limitan_a_hoy(self):
        self.entrar()
        hoy = timezone.localdate()
        manana = (hoy + timedelta(days=1)).isoformat()
        r = self.client.get('/auditoria/?fecha_desde=%s&fecha_hasta=%s' % (manana, manana))
        self.assertNotIn('fecha_', self.ruta_bitacora())
        self.assertContains(r, 'max="%s"' % hoy.isoformat())

    def test_fecha_de_hoy_si_se_envia(self):
        self.entrar()
        hoy = timezone.localdate().isoformat()
        self.client.get('/auditoria/?fecha_hasta=%s' % hoy)
        self.assertIn('fecha_hasta=%s' % hoy, self.ruta_bitacora())

    def test_historial_incompleto_se_ignora(self):
        self.entrar()
        r = self.client.get('/auditoria/?registro_id=12')
        self.assertNotIn('registro_id', self.ruta_bitacora())
        self.assertNotContains(r, 'Historial de')

    def test_error_400_de_un_filtro_se_muestra(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = ApiError(
            400, {'fecha_hasta': 'La fecha final no puede ser anterior a la inicial.'})
        r = self.client.get('/auditoria/?fecha_desde=2026-11-10&fecha_hasta=2026-11-01')   # al revés: decide la API
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'La fecha final no puede ser anterior a la inicial.')

    def test_selector_de_usuarios_y_modulos(self):
        self.entrar()
        r = self.client.get('/auditoria/?usuario=2')
        self.assertContains(r, 'maria · María López Ruiz')
        self.assertContains(r, '<option value="2" selected>', html=False)
        self.assertContains(r, 'Carga masiva')
        self.assertContains(r, 'Baja lógica')

    def test_sin_lista_de_usuarios_la_pantalla_sigue(self):
        self.entrar()
        self.api.respuestas[('GET', 'usuarios/')] = ApiError(500, {'detalle': 'Error 500'})
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()])
        r = self.client.get('/auditoria/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Todos los usuarios')
        self.assertContains(r, 'Marca mal capturada')


class FilasTests(BaseBitacora):
    def test_muestra_fecha_local_usuario_accion_y_motivo(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()])
        r = self.client.get('/auditoria/')
        self.assertContains(r, '11/11/2026')
        self.assertContains(r, '10:18')
        self.assertContains(r, 'admin')
        self.assertContains(r, 'Admin Prueba')
        self.assertContains(r, 'Modificación')
        self.assertContains(r, 'Marca mal capturada')
        self.assertContains(r, 'Artículos')

    def test_cambio_muestra_antes_y_despues(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()])
        r = self.client.get('/auditoria/')
        self.assertContains(r, '1 campo<')
        self.assertContains(r, 'Antes')
        self.assertContains(r, 'Dell')
        self.assertContains(r, 'HP')

    def test_alta_muestra_solo_los_valores_nuevos(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro(
            accion='INSERT', accion_nombre='Alta', motivo=None, valor_anterior=None,
            valor_nuevo={'marca': 'Dell', 'donado': False, 'tipo_articulo_id': 'TIP-001'})])
        r = self.client.get('/auditoria/')
        self.assertContains(r, '3 campos')
        self.assertNotContains(r, '<th>Antes</th>', html=False)
        self.assertContains(r, 'Alta')
        self.assertContains(r, '<td>No</td>', html=False)      # booleano legible
        self.assertContains(r, '<td>Tipo articulo</td>', html=False)  # sin el _id

    def test_valor_que_no_es_json_se_muestra_tal_cual(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro(
            valor_anterior='texto viejo', valor_nuevo={'marca': 'HP'})])
        r = self.client.get('/auditoria/')
        self.assertContains(r, 'texto viejo')

    def test_no_interpreta_html_de_los_valores(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro(
            motivo='<script>alert(1)</script>', valor_nuevo={'marca': '<b>x</b>'})])
        r = self.client.get('/auditoria/')
        self.assertNotContains(r, '<script>alert(1)</script>', html=False)
        self.assertContains(r, '&lt;script&gt;')

    def test_enlaces_a_la_ficha_movimiento_pdf_e_historial(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([
            registro(),
            registro(num=4, modulo='movimientos', tabla_afectada='movimiento', registro_id='MOV-0007'),
            registro(num=5, modulo='resguardos', tabla_afectada='resguardo', registro_id='RES-0001'),
            registro(num=6, modulo='carga_masiva', tabla_afectada='articulo',
                     registro_id='lote-abc123'),
        ])
        r = self.client.get('/auditoria/')
        self.assertContains(r, 'href="/articulos/detalle/12/"')
        self.assertContains(r, 'href="/movimientos/?q=MOV-0007"')
        self.assertContains(r, 'href="/movimientos/resguardos/RES-0001/pdf/"')
        self.assertContains(r, '?tabla_afectada=articulo&amp;registro_id=12')
        self.assertNotContains(r, '/articulos/detalle/lote')     # el lote no tiene ficha

    def test_listado_vacio(self):
        self.entrar()
        r = self.client.get('/auditoria/')
        self.assertContains(r, 'Todavía no hay registros')

    def test_paginacion(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = pagina([registro()] * 10, total=25)
        r = self.client.get('/auditoria/?modulo=articulos')
        self.assertContains(r, '25')
        self.assertContains(r, 'page=2')

    def test_pagina_inexistente_regresa_a_la_primera_con_filtros(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = ApiError(404, {'detail': 'Página inválida.'})
        r = self.client.get('/auditoria/?modulo=articulos&page=9')
        self.assertRedirects(r, '/auditoria/?modulo=articulos', fetch_redirect_response=False)

    def test_sesion_vencida_va_al_login(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = SesionVencida(401, {})
        r = self.client.get('/auditoria/')
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)

    def test_api_apagada(self):
        self.entrar()
        self.api.respuestas[('GET', 'bitacora/')] = ApiError(0, {'detalle': 'No se pudo conectar con la API.'})
        r = self.client.get('/auditoria/')
        self.assertContains(r, 'No se pudo conectar con la API.')
