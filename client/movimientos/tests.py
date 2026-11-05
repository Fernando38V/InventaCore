"""Pruebas de movimientos con la API simulada.

    python manage.py test movimientos
"""
from unittest.mock import patch

from catalogos.tests import ApiFalsa, BaseCliente, pagina
from client.api import ApiError
from equipos.tests import LAB1, NOLOC, RESG, UTIL, articulo

SIN_UBICAR = {'codigo': 'UBI-NOLOC', 'nombre': 'Sin ubicar'}


def movimiento(**cambios):
    m = {
        'num': 5, 'folio': 'MOV-0005', 'fecha': '2026-11-03 10:00', 'fecha_dia': '2026-11-03',
        'fecha_hora': '10:00', 'tipo': {'codigo': 'REUB', 'nombre': 'Reubicación'},
        'requiere_resguardo': False,
        'articulo': {'num': 7, 'identificador': 'M-100', 'descripcion': 'Dell Latitude'},
        'ubicacion_origen': LAB1, 'ubicacion_llegada': {'codigo': 'UBI-LAB2', 'nombre': 'Laboratorio 2'},
        'personal_asigna': RESG, 'personal_entrega': None, 'nota': 'Cambio de aula',
        'usuario': {'num': 1, 'username': 'admin'},
    }
    m.update(cambios)
    return m


class BaseMov(BaseCliente):
    def setUp(self):
        self.api = ApiFalsa()
        for destino in ('movimientos.views.llamar', 'client.utils.llamar'):
            parche = patch(destino, self.api)
            parche.start()
            self.addCleanup(parche.stop)
        r = self.api.respuestas
        r[('GET', 'ubicaciones/')] = pagina([
            {'codigo': 'UBI-LAB1', 'nombre': 'Laboratorio 1', 'activo': True},
            {'codigo': 'UBI-LAB2', 'nombre': 'Laboratorio 2', 'activo': True},
            {'codigo': 'UBI-NOLOC', 'nombre': 'Sin ubicar', 'activo': True}])
        r[('GET', 'personal/')] = pagina([
            {'num': 3, 'numero_empleado': 'E003', 'nombre_completo': 'Juan Pérez Vázquez',
             'activo': True}])
        r[('GET', 'tipos-movimiento/')] = [
            {'codigo': 'ALTA', 'nombre': 'Alta'}, {'codigo': 'REUB', 'nombre': 'Reubicación'},
            {'codigo': 'REPA', 'nombre': 'Envío a reparación'},
            {'codigo': 'RETE', 'nombre': 'Retorno de reparación'}]
        r[('GET', 'estados-operativos/')] = [
            {'codigo': 'UTIL', 'nombre': 'Útil'}, {'codigo': 'OBS', 'nombre': 'Obsoleto'},
            {'codigo': 'NOLOC', 'nombre': 'No localizado'}]
        r[('GET', 'articulos/7/')] = articulo()


class ListadoTests(BaseMov):
    def test_pide_a_la_api_los_filtros_y_la_pagina(self):
        self.entrar()
        self.api.respuestas[('GET', 'movimientos/')] = pagina([movimiento()], total=30)
        r = self.client.get('/movimientos/?q=aula&tipo=REUB&ubicacion=UBI-LAB1&articulo=7&page=2')
        self.assertEqual(r.status_code, 200)
        ruta = self.api.llamadas[0][1]
        for parte in ('q=aula', 'tipo=REUB', 'ubicacion=UBI-LAB1', 'articulo=7', 'page=2'):
            self.assertIn(parte, ruta)
        self.assertContains(r, 'MOV-0005')
        self.assertContains(r, 'M-100')
        self.assertContains(r, 'Cambio de aula')

    def test_filtro_por_articulo_muestra_el_chip(self):
        self.entrar()
        self.api.respuestas[('GET', 'movimientos/')] = pagina([movimiento()])
        r = self.client.get('/movimientos/?articulo=7')
        self.assertContains(r, 'Artículo:')

    def test_articulo_no_numerico_se_ignora(self):
        self.entrar()
        self.api.respuestas[('GET', 'movimientos/')] = pagina([])
        self.client.get('/movimientos/?articulo=abc')
        self.assertNotIn('articulo=', self.api.llamadas[0][1])

    def test_requiere_resguardo_se_indica_y_no_hay_baja(self):
        self.entrar()
        self.api.respuestas[('GET', 'movimientos/')] = pagina([movimiento(requiere_resguardo=True)])
        r = self.client.get('/movimientos/')
        self.assertContains(r, 'Resguardo pendiente')
        self.assertNotContains(r, 'Baja del inventario')

    def test_boton_mover_por_fila_solo_para_admin(self):
        self.api.respuestas[('GET', 'movimientos/')] = pagina([movimiento()])
        self.entrar('ADMIN')
        self.assertContains(self.client.get('/movimientos/'), '/movimientos/nuevo/?articulo=7')
        self.entrar('CONSULTA')
        self.assertNotContains(self.client.get('/movimientos/'), '/movimientos/nuevo/?articulo=7')

    def test_solo_admin_ve_nuevo_movimiento(self):
        self.api.respuestas[('GET', 'movimientos/')] = pagina([])
        self.entrar('ADMIN')
        self.assertContains(self.client.get('/movimientos/'), 'Nuevo movimiento')
        self.entrar('CONSULTA')
        self.assertNotContains(self.client.get('/movimientos/'), 'Nuevo movimiento')

    def test_error_de_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'movimientos/')] = ApiError(500, {'detalle': 'Falla'})
        self.assertContains(self.client.get('/movimientos/'), 'Falla')


class BusquedaTests(BaseMov):
    def test_sin_articulo_muestra_la_busqueda_y_sugiere_los_ultimos(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo()])
        r = self.client.get('/movimientos/nuevo/')
        self.assertContains(r, 'Qué artículo vas a mover')
        self.assertContains(r, 'Últimos artículos registrados')
        self.assertContains(r, '/movimientos/nuevo/?articulo=7')

    def test_los_sugeridos_vienen_de_la_ultima_pagina_del_mas_nuevo_al_mas_viejo(self):
        self.entrar()
        primera = pagina([articulo(num=1, identificador='M-001')], total=25)
        ultima = pagina([articulo(num=24, identificador='M-024'),
                         articulo(num=25, identificador='M-025')], total=25)
        pedidas = []

        def llamar(request, metodo, ruta, datos=None):
            pedidas.append(ruta)
            return ultima if 'page=3' in ruta else primera

        with patch('movimientos.views.llamar', llamar):
            r = self.client.get('/movimientos/nuevo/')
        self.assertTrue(any('page=3' in ruta for ruta in pedidas))
        html = r.content.decode()
        self.assertLess(html.index('M-025'), html.index('M-024'))
        self.assertNotIn('M-001', html)

    def test_busca_en_la_api_y_enlaza_al_formulario(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo()])
        r = self.client.get('/movimientos/nuevo/?q=dell')
        self.assertIn('q=dell', self.api.llamadas[0][1])
        self.assertContains(r, '/movimientos/nuevo/?articulo=7')

    def test_consulta_no_puede_entrar(self):
        self.entrar('CONSULTA')
        self.assertEqual(self.client.get('/movimientos/nuevo/').status_code, 302)

    def test_articulo_inexistente_da_404(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/99/')] = ApiError(404, {'detail': 'No encontrado'})
        self.assertEqual(self.client.get('/movimientos/nuevo/?articulo=99').status_code, 404)


def datos(**cambios):
    d = {'articulo': '7', 'tipo': 'REUB', 'ubicacion': 'UBI-LAB2', 'resguardante': '',
         'motivo': 'Cambio de aula', 'fecha': '2026-11-03', 'estado_operativo': ''}
    d.update(cambios)
    return d


class NuevoTests(BaseMov):
    def enviar(self, **cambios):
        return self.client.post('/movimientos/nuevo/', datos(**cambios))

    def test_formulario_ofrece_reub_repa_y_rete_sin_baja(self):
        self.entrar()
        r = self.client.get('/movimientos/nuevo/?articulo=7')
        for codigo in ('REUB', 'REPA', 'RETE'):
            self.assertContains(r, 'value="%s"' % codigo)
        self.assertNotContains(r, 'value="BAJA"')
        self.assertNotContains(r, 'value="ALTA"')

    def test_reubicacion_manda_el_cuerpo(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = movimiento()
        r = self.enviar()
        self.assertRedirects(r, '/movimientos/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [('POST', 'movimientos/', {
            'tipo': 'REUB', 'articulo': 7, 'motivo': 'Cambio de aula',
            'ubicacion': 'UBI-LAB2', 'fecha': '2026-11-03'})])

    def test_cambio_de_resguardante_avisa_del_resguardo(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = movimiento(requiere_resguardo=True)
        self.api.respuestas[('GET', 'movimientos/')] = pagina([])
        r = self.client.post('/movimientos/nuevo/', datos(ubicacion='', resguardante='4'),
                             follow=True)
        self.assertContains(r, 'falta el resguardo con las dos firmas')
        self.assertEqual(self.api.escrituras()[0][2]['resguardante'], '4')
        self.assertNotIn('ubicacion', self.api.escrituras()[0][2])

    def test_reub_sin_ubicacion_ni_resguardante(self):
        self.entrar()
        r = self.enviar(ubicacion='')
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Especifica una nueva ubicación')

    def test_reub_a_la_ubicacion_actual_se_rechaza(self):
        self.entrar()
        r = self.enviar(ubicacion='UBI-LAB1')          # el artículo ya está en LAB1
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'ya está en esa ubicación')

    def test_reub_al_resguardante_actual_se_rechaza(self):
        self.entrar()
        r = self.enviar(ubicacion='', resguardante='3')  # RESG num 3
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'ya es el resguardante')

    def test_repa_y_rete_si_aceptan_la_misma_ubicacion(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = movimiento()
        self.enviar(tipo='REPA', ubicacion='UBI-LAB1')
        self.assertEqual(self.api.escrituras()[0][2]['ubicacion'], 'UBI-LAB1')

    def test_formulario_lleva_la_ubicacion_y_el_resguardante_actuales(self):
        self.entrar()
        r = self.client.get('/movimientos/nuevo/?articulo=7')
        self.assertContains(r, 'data-ubicacion-actual="UBI-LAB1"')
        self.assertContains(r, 'data-resguardante-actual="3"')

    def test_rete_exige_ubicacion(self):
        self.entrar()
        r = self.enviar(tipo='RETE', ubicacion='')
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Indica dónde se reintegra')

    def test_repa_no_cambia_resguardante_ni_va_a_sin_ubicar(self):
        self.entrar()
        r = self.enviar(tipo='REPA', resguardante='3')
        self.assertContains(r, 'no cambia el resguardante')
        r = self.enviar(tipo='REPA', ubicacion='UBI-NOLOC')
        self.assertContains(r, 'usa una reubicación')
        self.assertEqual(self.api.escrituras(), [])

    def test_motivo_y_fecha(self):
        self.entrar()
        self.assertContains(self.enviar(motivo=' '), 'El motivo es obligatorio.')
        self.assertContains(self.enviar(fecha='2999-01-01'), 'La fecha no puede ser futura.')
        self.assertEqual(self.api.escrituras(), [])

    def test_perdida_con_reub_a_sin_ubicar_no_pide_estado(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = movimiento()
        self.enviar(ubicacion='UBI-NOLOC')
        cuerpo = self.api.escrituras()[0][2]
        self.assertEqual(cuerpo['ubicacion'], 'UBI-NOLOC')
        self.assertNotIn('estado_operativo', cuerpo)

    def test_error_de_la_api_en_el_artículo_se_muestra(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = ApiError(
            400, {'articulo': 'El artículo ya está en reparación.'})
        r = self.enviar(tipo='REPA', ubicacion='')
        self.assertContains(r, 'El artículo ya está en reparación.')
        self.assertContains(r, 'Cambio de aula')                 # conserva el motivo

    def test_consulta_no_escribe(self):
        self.entrar('CONSULTA')
        r = self.enviar()
        self.assertEqual(self.api.escrituras(), [])
        self.assertEqual(r.status_code, 302)


class AtajosTests(BaseMov):
    def setUp(self):
        super().setUp()
        parche = patch('equipos.views.llamar', self.api)     # las pruebas de ficha
        parche.start()
        self.addCleanup(parche.stop)

    def test_tipo_y_ubicacion_por_url_llegan_preseleccionados(self):
        self.entrar()
        r = self.client.get('/movimientos/nuevo/?articulo=7&tipo=REUB&ubicacion=UBI-NOLOC')
        self.assertContains(r, '<option value="REUB" selected>')
        self.assertContains(r, '<option value="UBI-NOLOC" selected>')

    def test_tipo_invalido_por_url_se_ignora(self):
        self.entrar()
        r = self.client.get('/movimientos/nuevo/?articulo=7&tipo=BAJA')
        self.assertNotContains(r, 'selected>Baja')
        self.assertNotContains(r, 'value="BAJA"')

    def test_ficha_ofrece_marcar_como_no_localizado(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])
        r = self.client.get('/articulos/detalle/7/')
        self.assertContains(r, 'Marcar como No localizado')
        self.assertContains(r, '/movimientos/nuevo/?articulo=7&amp;tipo=REUB&amp;ubicacion=UBI-NOLOC')

    def test_ficha_de_un_no_localizado_ofrece_recuperar(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            estado_operativo=NOLOC, ubicacion=SIN_UBICAR)
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])
        r = self.client.get('/articulos/detalle/7/')
        self.assertContains(r, 'Recuperar artículo')
        self.assertNotContains(r, 'Marcar como No localizado')

    def test_consulta_no_ve_los_atajos(self):
        self.entrar('CONSULTA')
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])
        r = self.client.get('/articulos/detalle/7/')
        self.assertNotContains(r, 'Marcar como No localizado')


class RecuperarNoLocalizadoTests(BaseMov):
    def setUp(self):
        super().setUp()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            estado_operativo=NOLOC, ubicacion=SIN_UBICAR)

    def test_solo_ofrece_reubicacion_y_pide_confirmar_el_estado(self):
        self.entrar()
        r = self.client.get('/movimientos/nuevo/?articulo=7')
        self.assertContains(r, 'value="REUB"')
        self.assertNotContains(r, 'value="REPA"')
        self.assertNotContains(r, 'value="RETE"')
        self.assertContains(r, 'name="estado_operativo" value="UTIL"')
        self.assertContains(r, 'name="estado_operativo" value="OBS"')
        self.assertNotContains(r, 'name="estado_operativo" value="NOLOC"')

    def test_recuperar_sin_confirmar_el_estado_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/movimientos/nuevo/', datos(estado_operativo=''))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Confirma el estado del artículo')

    def test_recuperar_manda_el_estado_confirmado(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = movimiento()
        self.client.post('/movimientos/nuevo/', datos(estado_operativo='OBS'))
        self.assertEqual(self.api.escrituras()[0][2]['estado_operativo'], 'OBS')

    def test_estado_invalido_no_pasa(self):
        self.entrar()
        r = self.client.post('/movimientos/nuevo/', datos(estado_operativo='NOLOC'))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Confirma el estado del artículo')

    def test_repa_o_rete_de_un_no_localizado_se_rechaza(self):
        self.entrar()
        r = self.client.post('/movimientos/nuevo/', datos(tipo='REPA', ubicacion=''))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'primero se recupera con una reubicación')

    def test_solo_cambio_de_resguardante_no_pide_estado(self):
        self.entrar()
        self.api.respuestas[('POST', 'movimientos/')] = movimiento()
        self.client.post('/movimientos/nuevo/', datos(ubicacion='', resguardante='4'))
        self.assertNotIn('estado_operativo', self.api.escrituras()[0][2])

    def test_estado_no_se_manda_si_el_articulo_esta_localizado(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(estado_operativo=UTIL)
        self.api.respuestas[('POST', 'movimientos/')] = movimiento()
        self.client.post('/movimientos/nuevo/', datos(estado_operativo='OBS'))
        self.assertNotIn('estado_operativo', self.api.escrituras()[0][2])
