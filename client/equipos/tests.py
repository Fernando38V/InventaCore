"""Pruebas de equipos (artículos) con la API simulada.

Comprueban lo que el cliente MANDA a la API y cómo reacciona a sus respuestas.
El recorrido contra la API real se hace aparte (ver el resumen de la tarea).

    python manage.py test equipos
"""
from unittest.mock import patch

from django.test import SimpleTestCase

from catalogos.tests import ApiFalsa, BaseCliente, pagina
from client.api import ApiError, SesionVencida
from client.utils import listar_todo

UTIL = {'codigo': 'UTIL', 'nombre': 'Útil', 'tono': 'verde'}
OBS = {'codigo': 'OBS', 'nombre': 'Obsoleto', 'tono': 'ambar'}
NOLOC = {'codigo': 'NOLOC', 'nombre': 'No localizado', 'tono': 'rojo'}
LAB1 = {'codigo': 'UBI-LAB1', 'nombre': 'Laboratorio 1'}
RESG = {'num': 3, 'numero_empleado': 'E003', 'nombre': 'Juan Pérez Vázquez'}


def articulo(**cambios):
    a = {
        'num': 7, 'marbete_oficial': 'M-100', 'folio_interno': None, 'identificador': 'M-100',
        'marca': 'Dell', 'modelo': 'Latitude', 'num_serie': 'SN1', 'color': 'Negro',
        'descripcion': 'Laptop de laboratorio', 'costo_adquisicion': '12000.00',
        'fecha_adquisicion': '2026-01-10', 'fecha_alta': '2026-11-03',
        'tipo_articulo': {'codigo': 'TIP-001', 'nombre': 'Laptop'},
        'categoria': {'codigo': 'CAT-001', 'nombre': 'Equipo de cómputo'},
        'origen': {'codigo': 'ACT', 'nombre': 'Activo'},
        'ubicacion': LAB1, 'resguardante': RESG, 'estado_operativo': UTIL,
        'estado_registro': {'codigo': 'REG', 'nombre': 'Registrado', 'tono': 'verde'},
        'faltantes': [],
    }
    a.update(cambios)
    return a


class BaseEquipos(BaseCliente):
    def setUp(self):
        self.api = ApiFalsa()
        for destino in ('equipos.views.llamar', 'client.utils.llamar'):
            parche = patch(destino, self.api)
            parche.start()
            self.addCleanup(parche.stop)
        r = self.api.respuestas
        r[('GET', 'ubicaciones/')] = pagina([
            {'codigo': 'UBI-LAB1', 'nombre': 'Laboratorio 1', 'activo': True},
            {'codigo': 'UBI-NOLOC', 'nombre': 'Sin ubicar', 'activo': True}])
        r[('GET', 'categorias/')] = pagina([
            {'codigo': 'CAT-001', 'nombre': 'Equipo de cómputo', 'activo': True}])
        r[('GET', 'tipos-articulo/')] = pagina([
            {'codigo': 'TIP-001', 'nombre': 'Laptop', 'categoria': 'CAT-001', 'activo': True}])
        r[('GET', 'personal/')] = pagina([
            {'num': 3, 'numero_empleado': 'E003', 'nombre_completo': 'Juan Pérez Vázquez',
             'activo': True}])
        r[('GET', 'origenes/')] = [{'codigo': 'ACT', 'nombre': 'Activo'},
                                   {'codigo': 'COM', 'nombre': 'Comodato'},
                                   {'codigo': 'ENS', 'nombre': 'Enser'}]
        r[('GET', 'estados-operativos/')] = [
            {'codigo': 'UTIL', 'nombre': 'Útil'}, {'codigo': 'OBS', 'nombre': 'Obsoleto'},
            {'codigo': 'NOLOC', 'nombre': 'No localizado'}]
        r[('GET', 'estados-registro/')] = [{'codigo': 'REG', 'nombre': 'Registrado'}]


class ListarTodoTests(SimpleTestCase):
    def test_acepta_la_lista_simple_de_los_catalogos_de_solo_lectura(self):
        api = ApiFalsa()
        api.respuestas[('GET', 'origenes/')] = [{'codigo': 'ACT', 'nombre': 'Activo'}]
        with patch('client.utils.llamar', api):
            self.assertEqual(listar_todo(None, 'origenes'),
                             [{'codigo': 'ACT', 'nombre': 'Activo'}])


class ListadoTests(BaseEquipos):
    def test_pide_a_la_api_la_pagina_y_los_filtros(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo()], total=25)
        r = self.client.get('/articulos/?q=dell&ubicacion=UBI-LAB1&estado_operativo=UTIL&page=2')
        self.assertEqual(r.status_code, 200)
        metodo, ruta, _ = self.api.llamadas[0]
        self.assertEqual(metodo, 'GET')
        for parte in ('q=dell', 'ubicacion=UBI-LAB1', 'estado_operativo=UTIL', 'page=2'):
            self.assertIn(parte, ruta)
        self.assertContains(r, 'M-100')
        self.assertContains(r, 'Dell Latitude')

    def test_el_modulo_se_llama_articulos(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo()])
        r = self.client.get('/articulos/')
        self.assertContains(r, '<span>Artículos</span>')
        self.assertContains(r, '<title>Artículos · InventaCore</title>')
        self.assertNotContains(r, '<span>Equipos</span>')

    def test_sin_marca_ni_modelo_no_usa_la_descripcion_como_nombre(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = pagina(
            [articulo(marca=None, modelo=None, descripcion='Silla de oficina en buen estado')])
        r = self.client.get('/articulos/')
        self.assertContains(r, 'Sin especificar')
        self.assertNotContains(r, 'Silla de oficina en buen estado')

    def test_muestra_el_error_de_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = ApiError(500, {'detalle': 'Falla'})
        r = self.client.get('/articulos/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Falla')

    def test_solo_el_administrador_ve_registrar(self):
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo()])
        self.entrar('ADMIN')
        self.assertContains(self.client.get('/articulos/'), 'Registrar artículo')
        self.entrar('CONSULTA')
        self.assertNotContains(self.client.get('/articulos/'), 'Registrar artículo')

    def test_sesion_vencida_redirige_al_login(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/')] = SesionVencida(401)
        r = self.client.get('/articulos/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('login', r['Location'])


class FichaTests(BaseEquipos):
    def preparar(self, **cambios):
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(**cambios)
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])

    def test_inexistente_da_404(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/')] = ApiError(404, {'detail': 'No encontrado'})
        self.assertEqual(self.client.get('/articulos/detalle/7/').status_code, 404)

    def test_campos_vacios_dicen_sin_especificar_y_no_hay_folio_ic(self):
        self.entrar()
        self.preparar(marca=None, modelo=None, num_serie=None, costo_adquisicion=None)
        r = self.client.get('/articulos/detalle/7/')
        self.assertContains(r, 'Sin especificar')
        self.assertNotContains(r, 'IC-')

    def test_el_titulo_sin_marca_ni_modelo_es_el_tipo_no_la_descripcion(self):
        self.entrar()
        self.preparar(marca=None, modelo=None, descripcion='Texto libre largo de la descripción')
        r = self.client.get('/articulos/detalle/7/')
        self.assertContains(r, '<h2 class="equipo-header__title">Laptop</h2>')
        # la descripción sigue apareciendo, pero en su propia tarjeta
        self.assertContains(r, 'Texto libre largo de la descripción')

    def test_admin_ve_acciones_y_consulta_no(self):
        self.preparar()
        self.entrar('ADMIN')
        r = self.client.get('/articulos/detalle/7/')
        for texto in ('Mover artículo', 'Corregir datos', 'Marcar como Obsoleto'):
            self.assertContains(r, texto)
        self.entrar('CONSULTA')
        r = self.client.get('/articulos/detalle/7/')
        for texto in ('Mover artículo', 'Corregir datos', 'Marcar como Obsoleto'):
            self.assertNotContains(r, texto)

    def test_no_localizado_no_ofrece_obsoleto(self):
        self.entrar()
        self.preparar(estado_operativo=NOLOC, ubicacion={'codigo': 'UBI-NOLOC', 'nombre': 'Sin ubicar'})
        self.assertNotContains(self.client.get('/articulos/detalle/7/'), 'Marcar como Obsoleto')


class CambiarEstadoTests(BaseEquipos):
    def test_manda_obsoleto_con_motivo(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo(estado_operativo=OBS)
        r = self.client.post('/articulos/detalle/7/estado/', {'motivo': 'Ya no enciende'})
        self.assertRedirects(r, '/articulos/detalle/7/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [
            ('PATCH', 'articulos/7/', {'estado_operativo': 'OBS', 'motivo': 'Ya no enciende'})])

    def test_regresar_a_util(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo()
        self.client.post('/articulos/detalle/7/estado/', {'activar': '1', 'motivo': 'Se reparó'})
        self.assertEqual(self.api.escrituras()[0][2]['estado_operativo'], 'UTIL')

    def test_sin_motivo_no_llama_a_la_api(self):
        self.entrar()
        self.client.post('/articulos/detalle/7/estado/', {'motivo': '  '})
        self.assertEqual(self.api.escrituras(), [])

    def test_consulta_no_escribe(self):
        self.entrar('CONSULTA')
        self.client.post('/articulos/detalle/7/estado/', {'motivo': 'x'})
        self.assertEqual(self.api.escrituras(), [])

    def test_error_de_la_api_se_muestra_en_la_ficha(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = ApiError(400, {'estado_operativo': 'Un artículo No localizado no puede pasar a Obsoleto.'})
        self.api.respuestas[('GET', 'articulos/7/')] = articulo()
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])
        r = self.client.post('/articulos/detalle/7/estado/', {'motivo': 'x'}, follow=True)
        self.assertContains(r, 'No localizado no puede pasar a Obsoleto')


VALIDO = {'origen': 'ACT', 'marbete_oficial': 'M-200', 'tipo_articulo': 'TIP-001',
          'color': 'Gris', 'descripcion': 'Laptop nueva', 'ubicacion': 'UBI-LAB1',
          'resguardante': '3', 'estado_operativo': 'UTIL'}


class AltaTests(BaseEquipos):
    def test_formulario_sin_folio_ic_ni_campo_de_folio(self):
        self.entrar()
        r = self.client.get('/articulos/registrar/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'IC-')
        self.assertNotContains(r, 'name="folio"')
        self.assertContains(r, 'name="marbete_oficial"')

    def test_alta_valida_manda_el_cuerpo_y_marca_modelo_quedan_nulos(self):
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = articulo(num=9, identificador='M-200')
        r = self.client.post('/articulos/registrar/', VALIDO)
        self.assertRedirects(r, '/articulos/detalle/9/', fetch_redirect_response=False)
        cuerpo = self.api.escrituras()[0][2]
        self.assertEqual(cuerpo['marbete_oficial'], 'M-200')
        self.assertEqual(cuerpo['resguardante'], 3)
        self.assertIsNone(cuerpo['marca'])
        self.assertIsNone(cuerpo['modelo'])
        self.assertIsNone(cuerpo['num_serie'])
        self.assertIsNone(cuerpo['fecha_adquisicion'])
        self.assertIsNone(cuerpo['costo_adquisicion'])
        self.assertFalse(cuerpo['donado'])

    def test_color_y_descripcion_son_obligatorios(self):
        self.entrar()
        r = self.client.post('/articulos/registrar/', dict(VALIDO, color='', descripcion=''))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Escribe el color.')
        self.assertContains(r, 'Escribe la descripción.')

    def test_activo_exige_marbete(self):
        self.entrar()
        r = self.client.post('/articulos/registrar/', dict(VALIDO, marbete_oficial=''))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Los activos llevan marbete oficial.')

    def test_comodato_no_manda_marbete_ni_folio(self):
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = articulo(num=9, identificador='021432611-001')
        self.client.post('/articulos/registrar/', dict(VALIDO, origen='COM', marbete_oficial='X'))
        cuerpo = self.api.escrituras()[0][2]
        self.assertNotIn('marbete_oficial', cuerpo)
        self.assertNotIn('folio_interno', cuerpo)

    def test_donado_con_costo_guarda_el_costo(self):
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = articulo(num=9)
        self.client.post('/articulos/registrar/', dict(VALIDO, donado='on', costo_adquisicion='1,500.50'))
        cuerpo = self.api.escrituras()[0][2]
        self.assertTrue(cuerpo['donado'])
        self.assertEqual(cuerpo['costo_adquisicion'], '1500.50')

    def test_el_formulario_no_bloquea_el_costo_en_donados(self):
        self.entrar()
        r = self.client.get('/articulos/registrar/')
        self.assertNotContains(r, 'costo.disabled')
        self.assertNotContains(r, 'readOnly')

    def test_noloc_y_ubicacion_sin_ubicar_van_juntos(self):
        self.entrar()
        r = self.client.post('/articulos/registrar/', dict(VALIDO, ubicacion='UBI-NOLOC'))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'estado No localizado')
        r = self.client.post('/articulos/registrar/', dict(VALIDO, estado_operativo='NOLOC'))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Sin ubicar')

    def test_sin_ubicar_con_noloc_se_acepta(self):
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = articulo(num=9)
        self.client.post('/articulos/registrar/',
                         dict(VALIDO, ubicacion='UBI-NOLOC', estado_operativo='NOLOC'))
        cuerpo = self.api.escrituras()[0][2]
        self.assertEqual((cuerpo['ubicacion'], cuerpo['estado_operativo']), ('UBI-NOLOC', 'NOLOC'))

    def test_error_de_la_api_junto_al_campo(self):
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = ApiError(
            400, {'marbete_oficial': 'Ya existe un artículo con ese marbete.'})
        r = self.client.post('/articulos/registrar/', VALIDO)
        self.assertContains(r, 'Ya existe un artículo con ese marbete.')
        self.assertContains(r, 'value="M-200"')            # conserva lo capturado

    def test_estado_pendiente_se_avisa(self):
        self.entrar()
        self.api.respuestas[('POST', 'articulos/')] = articulo(
            num=9, estado_registro={'codigo': 'PEND', 'nombre': 'Pendiente'},
            faltantes=['el costo de adquisición'])
        self.api.respuestas[('GET', 'articulos/9/')] = articulo(num=9)
        self.api.respuestas[('GET', 'articulos/9/movimientos/')] = pagina([])
        r = self.client.post('/articulos/registrar/', VALIDO, follow=True)
        self.assertContains(r, 'Pendiente')
        self.assertContains(r, 'el costo de adquisición')

    def test_consulta_no_puede_registrar(self):
        self.entrar('CONSULTA')
        r = self.client.post('/articulos/registrar/', VALIDO)
        self.assertEqual(self.api.escrituras(), [])
        self.assertEqual(r.status_code, 302)


class CorregirTests(BaseEquipos):
    def setUp(self):
        super().setUp()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo()
        self.api.respuestas[('GET', 'articulos/7/movimientos/')] = pagina([])

    def datos(self, **cambios):
        d = {'marbete_oficial': 'M-100', 'marca': 'Dell', 'modelo': 'Latitude',
             'num_serie': 'SN1', 'color': 'Negro', 'fecha_adquisicion': '2026-01-10',
             'costo_adquisicion': '12000.00', 'descripcion': 'Laptop de laboratorio', 'motivo': 'Error de captura'}
        d.update(cambios)
        return d

    def test_solo_manda_lo_que_cambio_y_el_motivo(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo(color='Gris')
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(color='Gris'))
        self.assertRedirects(r, '/articulos/detalle/7/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [
            ('PATCH', 'articulos/7/', {'color': 'Gris', 'motivo': 'Error de captura'})])

    def test_el_formulario_ofrece_el_costo_tambien_en_donados(self):
        self.entrar()
        r = self.client.get('/articulos/detalle/7/corregir/')
        self.assertContains(r, 'name="costo_adquisicion"')
        self.assertContains(r, 'value="12000"')            # sin ceros de más
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            estado_registro={'codigo': 'DON', 'nombre': 'Donado', 'tono': 'violeta'},
            costo_adquisicion=None)
        r = self.client.get('/articulos/detalle/7/corregir/')
        self.assertContains(r, 'name="costo_adquisicion"')
        self.assertNotContains(r, 'disabled')

    def test_corregir_costo_lo_manda_con_motivo(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo()
        self.client.post('/articulos/detalle/7/corregir/', self.datos(costo_adquisicion='1,500.50'))
        self.assertEqual(self.api.escrituras(), [
            ('PATCH', 'articulos/7/', {'costo_adquisicion': '1500.5', 'motivo': 'Error de captura'})])

    def test_vaciar_el_costo_manda_null_no_cero(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo()
        self.client.post('/articulos/detalle/7/corregir/', self.datos(costo_adquisicion=''))
        self.assertEqual(self.api.escrituras()[0][2], {'costo_adquisicion': None, 'motivo': 'Error de captura'})

    def test_mismo_costo_con_otro_formato_no_es_un_cambio(self):
        self.entrar()
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(costo_adquisicion='12000'))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'No hiciste ningún cambio')

    def test_costo_en_donado_sin_costo_se_puede_capturar(self):
        self.entrar()
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            estado_registro={'codigo': 'DON', 'nombre': 'Donado', 'tono': 'violeta'},
            costo_adquisicion=None)
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo()
        self.client.post('/articulos/detalle/7/corregir/', self.datos(costo_adquisicion='800'))
        self.assertEqual(self.api.escrituras()[0][2], {'costo_adquisicion': '800', 'motivo': 'Error de captura'})

    def test_costo_invalido_o_negativo_no_llega_a_la_api(self):
        self.entrar()
        for malo in ('abc', '-5'):
            r = self.client.post('/articulos/detalle/7/corregir/', self.datos(costo_adquisicion=malo))
            self.assertContains(r, 'El costo debe ser un número')
        self.assertEqual(self.api.escrituras(), [])

    def test_si_la_api_rechaza_el_costo_se_muestra_junto_al_campo(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = ApiError(
            400, {'costo_adquisicion': 'En un bien Donado el costo no se modifica.'})
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(costo_adquisicion='900'))
        self.assertContains(r, 'En un bien Donado el costo no se modifica.')

    def test_vaciar_marca_manda_null(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = articulo()
        self.client.post('/articulos/detalle/7/corregir/', self.datos(marca=''))
        self.assertEqual(self.api.escrituras()[0][2], {'marca': None, 'motivo': 'Error de captura'})

    def test_sin_cambios_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos())
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'No hiciste ningún cambio')

    def test_sin_motivo_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(color='Gris', motivo=''))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Indica el motivo del cambio.')

    def test_color_y_descripcion_no_pueden_quedar_vacios(self):
        self.entrar()
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(color='', descripcion=''))
        self.assertEqual(self.api.escrituras(), [])
        self.assertContains(r, 'Este campo es obligatorio.')

    def test_marbete_solo_se_corrige_en_activos(self):
        self.entrar()
        self.assertContains(self.client.get('/articulos/detalle/7/corregir/'), 'name="marbete_oficial"')
        self.api.respuestas[('GET', 'articulos/7/')] = articulo(
            origen={'codigo': 'COM', 'nombre': 'Comodato'}, marbete_oficial=None,
            folio_interno='021432611-001', identificador='021432611-001')
        self.assertNotContains(self.client.get('/articulos/detalle/7/corregir/'), 'name="marbete_oficial"')

    def test_no_se_ofrece_corregir_ubicacion_ni_resguardante_ni_estado(self):
        self.entrar()
        r = self.client.get('/articulos/detalle/7/corregir/')
        for nombre in ('name="ubicacion"', 'name="resguardante"', 'name="estado_operativo"'):
            self.assertNotContains(r, nombre)

    def test_error_de_la_api_junto_al_campo(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'articulos/7/')] = ApiError(
            400, {'marbete_oficial': 'Ya existe un artículo con ese marbete.'})
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(marbete_oficial='M-999'))
        self.assertContains(r, 'Ya existe un artículo con ese marbete.')

    def test_consulta_no_puede_corregir(self):
        self.entrar('CONSULTA')
        r = self.client.post('/articulos/detalle/7/corregir/', self.datos(color='Gris'))
        self.assertEqual(self.api.escrituras(), [])
        self.assertEqual(r.status_code, 302)
