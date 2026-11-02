"""Pruebas de las pantallas de catálogos y personal.

Usan una API simulada: comprueban lo que el cliente MANDA y cómo reacciona
a las respuestas, sin necesitar la API real ni su base de datos. El recorrido
contra la API real se hace a mano (ver el resumen de la tarea).

    python manage.py test catalogos
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from catalogos.config import PERSONAL
from catalogos.views import _fila
from client.api import ApiError, SesionVencida
from client.utils import listar_todo

CAT = {'codigo': 'CAT-001', 'nombre': 'Cómputo', 'descripcion': None, 'activo': True}
NOLOC = {'codigo': 'UBI-NOLOC', 'nombre': 'No localizado', 'descripcion': None,
         'responsable': None, 'responsable_nombre': None, 'activo': True}


def pagina(items, total=None):
    return {'count': total if total is not None else len(items),
            'next': None, 'previous': None, 'results': items}


class ApiFalsa:
    """Sustituye a client.api.llamar. `respuestas` va por (método, ruta sin
    query string); un valor Exception se lanza en lugar de devolverse."""

    def __init__(self):
        self.respuestas = {}
        self.llamadas = []

    def __call__(self, request, metodo, ruta, datos=None):
        self.llamadas.append((metodo, ruta, datos))
        clave = (metodo, ruta.split('?')[0])
        respuesta = self.respuestas.get(clave, pagina([]) if metodo == 'GET' else {})
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta

    def escrituras(self):
        return [ll for ll in self.llamadas if ll[0] != 'GET']


class BaseCliente(TestCase):
    def setUp(self):
        self.api = ApiFalsa()
        for destino in ('catalogos.views.llamar', 'client.utils.llamar'):
            parche = patch(destino, self.api)
            parche.start()
            self.addCleanup(parche.stop)

    def entrar(self, rol='ADMIN'):
        sesion = self.client.session
        sesion['api_token'] = 'token'
        sesion['usuario'] = {'num': 1, 'username': 'u', 'empleado': 'Prueba Uno',
                             'rol': rol, 'rol_nombre': rol.title()}
        sesion.save()


class ListadoTests(BaseCliente):
    def test_pide_a_la_api_la_pagina_y_los_filtros(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/')] = pagina([CAT])
        r = self.client.get('/catalogos/categorias/?activo=true&page=2')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.api.llamadas[0],
                         ('GET', 'categorias/?activo=true&page=2', None))

    def test_filtro_activo_invalido_no_llega_a_la_api(self):
        self.entrar()
        self.client.get('/catalogos/categorias/?activo=zzz')
        self.assertEqual(self.api.llamadas[0][1], 'categorias/?page=1')

    def test_admin_ve_botones_y_consulta_no(self):
        self.api.respuestas[('GET', 'categorias/')] = pagina([CAT])
        self.entrar('ADMIN')
        html = self.client.get('/catalogos/categorias/').content.decode()
        self.assertIn('Nueva categoría', html)
        self.assertIn('data-bs-target="#modalEstado"', html)
        self.entrar('CONSULTA')
        html = self.client.get('/catalogos/categorias/').content.decode()
        self.assertIn('Cómputo', html)
        self.assertNotIn('Nueva categoría', html)
        self.assertNotIn('modalEstado', html)

    def test_ubicacion_no_localizado_no_tiene_acciones(self):
        self.entrar()
        self.api.respuestas[('GET', 'ubicaciones/')] = pagina([NOLOC])
        html = self.client.get('/catalogos/ubicaciones/').content.decode()
        self.assertIn('Del sistema', html)
        self.assertNotIn('data-activar', html)

    def test_pagina_que_ya_no_existe_vuelve_a_la_primera(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/')] = ApiError(404, {'detail': 'Página inválida.'})
        r = self.client.get('/catalogos/categorias/?page=9&activo=true')
        self.assertRedirects(r, '/catalogos/categorias/?activo=true',
                             fetch_redirect_response=False)

    def test_api_caida_muestra_aviso_y_no_rompe(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/')] = ApiError(0, {'detalle': 'No se pudo conectar'})
        r = self.client.get('/catalogos/categorias/')
        self.assertContains(r, 'No se pudo conectar')

    def test_sesion_vencida_lleva_al_login(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/')] = SesionVencida(401, {})
        r = self.client.get('/catalogos/categorias/')
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)

    def test_catalogo_desconocido_es_404(self):
        self.entrar()
        self.assertEqual(self.client.get('/catalogos/personal/').status_code, 404)
        self.assertEqual(self.client.get('/catalogos/otro/').status_code, 404)


class AltaYEdicionTests(BaseCliente):
    def test_alta_manda_los_campos_sin_codigo_y_vacio_como_null(self):
        self.entrar()
        self.api.respuestas[('POST', 'categorias/')] = dict(CAT, codigo='CAT-002', nombre='Muebles')
        r = self.client.post('/catalogos/categorias/nuevo/',
                             {'nombre': ' Muebles ', 'descripcion': '', 'codigo': 'CAT-999'})
        self.assertRedirects(r, '/catalogos/categorias/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(),
                         [('POST', 'categorias/', {'nombre': 'Muebles', 'descripcion': None})])

    def test_campo_obligatorio_vacio_no_llama_a_la_api(self):
        self.entrar()
        r = self.client.post('/catalogos/categorias/nuevo/', {'nombre': '', 'descripcion': ''})
        self.assertContains(r, 'Este campo es obligatorio.')
        self.assertEqual(self.api.escrituras(), [])

    def test_error_de_la_api_se_muestra_en_su_campo_y_conserva_lo_escrito(self):
        self.entrar()
        self.api.respuestas[('POST', 'categorias/')] = ApiError(400, {'nombre': 'Ya existe.'})
        r = self.client.post('/catalogos/categorias/nuevo/', {'nombre': 'Cómputo'})
        self.assertContains(r, 'Ya existe.')
        self.assertContains(r, 'value="Cómputo"')

    def test_error_500_de_la_api_no_rompe_el_formulario(self):
        self.entrar()
        self.api.respuestas[('POST', 'categorias/')] = ApiError(500, {'detalle': 'Error 500 en el servidor.'})
        r = self.client.post('/catalogos/categorias/nuevo/', {'nombre': 'X'})
        self.assertContains(r, 'Error 500 en el servidor.')

    def test_edicion_manda_solo_lo_que_cambio_y_el_motivo(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/CAT-001/')] = CAT
        self.api.respuestas[('PATCH', 'categorias/CAT-001/')] = CAT
        r = self.client.post('/catalogos/categorias/CAT-001/editar/', {
            'nombre': 'Cómputo', 'descripcion': 'Equipo de cómputo', 'motivo': 'Aclaración'})
        self.assertRedirects(r, '/catalogos/categorias/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [(
            'PATCH', 'categorias/CAT-001/',
            {'descripcion': 'Equipo de cómputo', 'motivo': 'Aclaración'})])

    def test_edicion_sin_motivo_no_llama_a_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/CAT-001/')] = CAT
        r = self.client.post('/catalogos/categorias/CAT-001/editar/', {
            'nombre': 'Cómputo', 'descripcion': 'Nueva', 'motivo': ''})
        self.assertContains(r, 'Indica el motivo del cambio.')
        self.assertEqual(self.api.escrituras(), [])

    def test_edicion_sin_cambios_no_llama_a_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/CAT-001/')] = CAT
        r = self.client.post('/catalogos/categorias/CAT-001/editar/', {
            'nombre': 'Cómputo', 'descripcion': '', 'motivo': ''})
        self.assertContains(r, 'No hiciste ningún cambio.')
        self.assertEqual(self.api.escrituras(), [])

    def test_responsable_vacio_se_manda_como_null_y_el_numero_como_entero(self):
        self.entrar()
        ubicacion = dict(NOLOC, codigo='UBI-001', nombre='Biblioteca', responsable=5)
        self.api.respuestas[('GET', 'ubicaciones/UBI-001/')] = ubicacion
        self.api.respuestas[('PATCH', 'ubicaciones/UBI-001/')] = ubicacion
        self.client.post('/catalogos/ubicaciones/UBI-001/editar/', {
            'nombre': 'Biblioteca', 'responsable': '', 'descripcion': '', 'motivo': 'Sin responsable'})
        self.assertEqual(self.api.escrituras()[0][2], {'responsable': None, 'motivo': 'Sin responsable'})
        self.api.llamadas.clear()
        self.api.respuestas[('POST', 'ubicaciones/')] = dict(ubicacion, nombre='Aula')
        self.client.post('/catalogos/ubicaciones/nuevo/', {
            'nombre': 'Aula', 'responsable': '7', 'descripcion': ''})
        self.assertEqual(self.api.escrituras()[0][2]['responsable'], 7)

    def test_ubicacion_del_sistema_no_se_edita(self):
        self.entrar()
        self.api.respuestas[('GET', 'ubicaciones/UBI-NOLOC/')] = NOLOC
        r = self.client.get('/catalogos/ubicaciones/UBI-NOLOC/editar/')
        self.assertRedirects(r, '/catalogos/ubicaciones/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras(), [])

    def test_registro_inexistente_es_404(self):
        self.entrar()
        self.api.respuestas[('GET', 'categorias/CAT-9/')] = ApiError(404, {'detail': 'No encontrado.'})
        self.assertEqual(self.client.get('/catalogos/categorias/CAT-9/editar/').status_code, 404)

    def test_personal_manda_segundo_apellido_vacio_como_null(self):
        self.entrar()
        self.api.respuestas[('POST', 'personal/')] = {'num': 3, 'nombre_completo': 'Ana López'}
        r = self.client.post('/personal/nuevo/', {
            'numero_empleado': 'E9', 'departamento': 'DEP-INF', 'nombre_pila': 'Ana',
            'primer_apellido': 'López', 'segundo_apellido': '', 'puesto': 'Docente'})
        self.assertRedirects(r, '/personal/', fetch_redirect_response=False)
        self.assertEqual(self.api.escrituras()[0][2]['segundo_apellido'], None)


class EstadoTests(BaseCliente):
    def test_desactivar_manda_activo_false_y_motivo(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'categorias/CAT-001/')] = CAT
        r = self.client.post('/catalogos/categorias/CAT-001/estado/',
                             {'activar': '0', 'motivo': 'Ya no se usa'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.api.escrituras(), [(
            'PATCH', 'categorias/CAT-001/', {'activo': False, 'motivo': 'Ya no se usa'})])

    def test_activar_manda_activo_true(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'personal/4/')] = {'num': 4, 'nombre_completo': 'Ana López'}
        self.client.post('/personal/4/estado/', {'activar': '1', 'motivo': 'Regresa'})
        self.assertEqual(self.api.escrituras()[0][2], {'activo': True, 'motivo': 'Regresa'})

    def test_sin_motivo_no_llama_a_la_api(self):
        self.entrar()
        self.client.post('/catalogos/categorias/CAT-001/estado/', {'activar': '0', 'motivo': '  '})
        self.assertEqual(self.api.escrituras(), [])

    def test_regresa_a_la_pagina_de_origen_pero_no_a_otro_sitio(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'categorias/CAT-001/')] = CAT
        datos = {'activar': '0', 'motivo': 'x'}
        r = self.client.post('/catalogos/categorias/CAT-001/estado/',
                             dict(datos, volver='/catalogos/categorias/?page=2'))
        self.assertEqual(r['Location'], '/catalogos/categorias/?page=2')
        r = self.client.post('/catalogos/categorias/CAT-001/estado/',
                             dict(datos, volver='https://malo.example.com/'))
        self.assertEqual(r['Location'], '/catalogos/categorias/')

    def test_rechazo_de_la_api_se_muestra_como_aviso(self):
        self.entrar()
        self.api.respuestas[('PATCH', 'ubicaciones/UBI-NOLOC/')] = ApiError(
            400, {'activo': 'La ubicación de no localizados no se puede desactivar.'})
        r = self.client.post('/catalogos/ubicaciones/UBI-NOLOC/estado/',
                             {'activar': '0', 'motivo': 'x'}, follow=True)
        self.assertContains(r, 'no se puede desactivar')

    def test_solo_acepta_post(self):
        self.entrar()
        self.assertEqual(self.client.get('/catalogos/categorias/CAT-001/estado/').status_code, 405)


class ConsultaTests(BaseCliente):
    """El rol Consulta no escribe: el cliente ni lo intenta (y la API lo valida)."""

    def test_no_abre_formularios_ni_cambia_estados(self):
        self.entrar('CONSULTA')
        for url in ('/catalogos/categorias/nuevo/', '/catalogos/categorias/CAT-001/editar/',
                    '/personal/nuevo/'):
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.client.post('/catalogos/categorias/nuevo/', {'nombre': 'X'})
        self.client.post('/catalogos/categorias/CAT-001/estado/', {'activar': '0', 'motivo': 'x'})
        self.assertEqual(self.api.escrituras(), [])
        self.assertEqual([ll for ll in self.api.llamadas if 'CAT-001/' in ll[1]], [])

    def test_sin_sesion_pide_login(self):
        r = self.client.get('/catalogos/categorias/')
        self.assertRedirects(r, '/cuentas/login/', fetch_redirect_response=False)


class UtilidadesTests(SimpleTestCase):
    def test_listar_todo_recorre_todas_las_paginas(self):
        paginas = {
            'x/?activo=true&page=1': {'results': [1, 2], 'next': 'sigue'},
            'x/?activo=true&page=2': {'results': [3], 'next': None},
        }
        with patch('client.utils.llamar',
                   lambda request, metodo, ruta: paginas[ruta]):
            self.assertEqual(listar_todo(None, 'x', activo='true'), [1, 2, 3])

    def test_aviso_de_baja_de_personal_con_articulos_a_cargo(self):
        item = {'num': 7, 'numero_empleado': 'E7', 'nombre_completo': 'Ana López',
                'puesto': 'Docente', 'departamento_nombre': 'Informática',
                'articulos_a_cargo': 3, 'activo': True}
        fila = _fila(PERSONAL, item)
        self.assertIn('3 artículo(s) a su cargo', fila['aviso'])
        self.assertEqual(fila['url_editar'], '/personal/7/editar/')
        self.assertEqual(_fila(PERSONAL, dict(item, articulos_a_cargo=0))['aviso'],
                         PERSONAL['aviso_baja'])
