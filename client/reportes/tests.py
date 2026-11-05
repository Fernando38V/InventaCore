"""Pruebas del dashboard y los reportes (DEC-020, DEC-018)."""
from unittest.mock import MagicMock, patch

from catalogos.tests import BaseCliente, pagina
from client.api import ApiError
from equipos.tests import articulo


def tablero(**cambios):
    d = {
        'total_articulos': 12,
        'por_estado_operativo': [
            {'codigo': 'UTIL', 'nombre': 'Útil', 'tono': 'azul', 'total': 9},
            {'codigo': 'OBS', 'nombre': 'Obsoleto', 'tono': 'gris', 'total': 0},
            {'codigo': 'NOLOC', 'nombre': 'No localizado', 'tono': 'ambar', 'total': 3}],
        'por_estado_registro': [
            {'codigo': 'REG', 'nombre': 'Registrado', 'tono': 'verde', 'total': 6},
            {'codigo': 'PEND', 'nombre': 'Pendiente', 'tono': 'ambar', 'total': 4},
            {'codigo': 'DON', 'nombre': 'Donado', 'tono': 'azul', 'total': 2}],
        'por_ubicacion': [{'codigo': 'UBI-%02d' % i, 'nombre': 'Ubicación %d' % i, 'total': 10 - i}
                          for i in range(10)],
        'pendientes_de_datos': {'total': 4, 'articulos': [articulo(
            num=8, marca=None, modelo=None,
            estado_registro={'codigo': 'PEND', 'nombre': 'Pendiente', 'tono': 'ambar'},
            faltantes=['el costo de adquisición', 'la fecha de adquisición'])]},
        'ultimos_movimientos': [{
            'folio': 'MOV-0009', 'fecha_dia': '2026-11-05', 'fecha_hora': '09:00',
            'tipo': {'codigo': 'REUB', 'nombre': 'Reubicación'},
            'articulo': {'num': 7, 'identificador': 'M-100', 'descripcion': 'Laptop'},
            'ubicacion_llegada': {'codigo': 'UBI-OFI', 'nombre': 'Oficina'},
            'personal_asigna': {'num': 1, 'nombre': 'Ana López'}}],
        'resguardos_por_emitir': 2,
    }
    d.update(cambios)
    return d


class BaseReportes(BaseCliente):
    def setUp(self):
        super().setUp()
        self.descargar = MagicMock(return_value=b'PK excel')
        for destino, falso in (('reportes.views.llamar', self.api),
                               ('reportes.views.descargar', self.descargar)):
            parche = patch(destino, falso)
            parche.start()
            self.addCleanup(parche.stop)
        r = self.api.respuestas
        r[('GET', 'ubicaciones/')] = pagina([{'codigo': 'UBI-LAB1', 'nombre': 'Laboratorio 1', 'activo': True}])
        r[('GET', 'estados-operativos/')] = [{'codigo': 'UTIL', 'nombre': 'Útil'}, {'codigo': 'NOLOC', 'nombre': 'No localizado'}]
        r[('GET', 'estados-registro/')] = [{'codigo': 'PEND', 'nombre': 'Pendiente'}]
        r[('GET', 'personal/')] = pagina([
            {'num': 3, 'numero_empleado': 'E003', 'nombre_completo': 'Juan Pérez', 'activo': True},
            {'num': 4, 'numero_empleado': 'E004', 'nombre_completo': 'Rosa Ruiz', 'activo': False}])


class DashboardTests(BaseReportes):
    def test_muestra_totales_reparto_y_listas(self):
        self.entrar('CONSULTA')
        self.api.respuestas[('GET', 'dashboard/')] = tablero()
        r = self.client.get('/reportes/dashboard/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '<span class="kpi__valor">12</span>', html=False)
        self.assertEqual(r.context['nolocalizados'], 3)
        # La barra más grande va al 100 % y las demás en proporción; el 0 no se dibuja.
        anchos = [e['ancho'] for e in r.context['estado_operativo']]
        self.assertEqual(anchos, [100, 0, 33])
        self.assertContains(r, 'reparto__barra--cero')
        # Solo 8 ubicaciones; el resto se resume.
        self.assertEqual(len(r.context['ubicaciones']), 8)
        self.assertContains(r, 'Y 2 ubicaciones más con 3 artículos.')
        # Pendiente sin marca ni modelo: se nombra por su tipo, nunca por la descripción.
        self.assertContains(r, 'Laptop · Laboratorio 1')
        self.assertContains(r, 'El costo de adquisición y la fecha de adquisición')
        self.assertContains(r, 'Ver los 4')
        self.assertContains(r, 'MOV-0009')
        self.assertContains(r, '/movimientos/resguardos/?vista=pendientes')

    def test_enlaces_a_los_listados_filtrados(self):
        self.entrar()
        self.api.respuestas[('GET', 'dashboard/')] = tablero()
        r = self.client.get('/reportes/dashboard/')
        self.assertContains(r, '/articulos/?estado_registro=PEND')
        self.assertContains(r, '/articulos/?estado_operativo=NOLOC')
        self.assertContains(r, '/articulos/?ubicacion=UBI-00')

    def test_inventario_vacio(self):
        self.entrar()
        self.api.respuestas[('GET', 'dashboard/')] = tablero(
            total_articulos=0, por_ubicacion=[], ultimos_movimientos=[],
            pendientes_de_datos={'total': 0, 'articulos': []}, resguardos_por_emitir=0,
            por_estado_operativo=[{'codigo': 'UTIL', 'nombre': 'Útil', 'tono': 'azul', 'total': 0}],
            por_estado_registro=[])
        r = self.client.get('/reportes/dashboard/')
        self.assertContains(r, 'No hay artículos pendientes de datos.')
        self.assertContains(r, 'Todavía no hay movimientos.')
        self.assertEqual(r.context['estado_operativo'][0]['ancho'], 0)

    def test_error_de_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'dashboard/')] = ApiError(0, {'detalle': 'No se pudo conectar con el servidor.'})
        r = self.client.get('/reportes/dashboard/')
        self.assertContains(r, 'No se pudo cargar el tablero. No se pudo conectar con el servidor.')


class InventarioTests(BaseReportes):
    def test_sin_ver_no_pide_el_reporte(self):
        self.entrar('CONSULTA')
        r = self.client.get('/reportes/')
        self.assertContains(r, 'pulsa «Ver reporte»')
        self.assertFalse([ll for ll in self.api.llamadas if ll[1].startswith('reportes/')])

    def test_filtros_van_a_la_api(self):
        self.entrar()
        self.api.respuestas[('GET', 'reportes/inventario/')] = {'total': 1, 'resultados': [articulo()]}
        r = self.client.get('/reportes/?ubicacion=UBI-LAB1&resguardante=3&estado_operativo=UTIL&estado_registro=&ver=1')
        rutas = [ll[1] for ll in self.api.llamadas if ll[1].startswith('reportes/')]
        self.assertEqual(rutas, ['reportes/inventario/?ubicacion=UBI-LAB1&resguardante=3&estado_operativo=UTIL'])
        self.assertContains(r, '1 artículo')
        self.assertContains(r, 'M-100')
        self.assertContains(r, '$12000.00')
        # Personal inactivo también se puede elegir: aún puede tener bienes.
        self.assertContains(r, 'E004 — Rosa Ruiz (inactivo)')

    def test_recorta_en_pantalla_y_avisa(self):
        self.entrar()
        filas = [articulo(num=i, identificador='M-%d' % i) for i in range(205)]
        self.api.respuestas[('GET', 'reportes/inventario/')] = {'total': 205, 'resultados': filas}
        r = self.client.get('/reportes/?ver=1')
        self.assertEqual(len(r.context['articulos']), 200)
        self.assertContains(r, 'se muestran los primeros 200 de 205')

    def test_excel_con_los_mismos_filtros(self):
        self.entrar('CONSULTA')
        r = self.client.get('/reportes/excel/inventario/?ubicacion=UBI-LAB1&estado_operativo=')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'PK excel')
        self.assertIn('attachment; filename="inventario_', r['Content-Disposition'])
        self.assertEqual(self.descargar.call_args[0][1],
                         'reportes/inventario/?ubicacion=UBI-LAB1&formato=xlsx')

    def test_excel_falla_regresa_con_aviso(self):
        self.entrar()
        self.descargar.side_effect = ApiError(0, {'detalle': 'No se pudo conectar con el servidor.'})
        self.api.respuestas[('GET', 'reportes/inventario/')] = {'total': 0, 'resultados': []}
        r = self.client.get('/reportes/excel/inventario/?ubicacion=UBI-LAB1', follow=True)
        self.assertContains(r, 'No se pudo generar el Excel')


class ResguardanteTests(BaseReportes):
    def test_articulos_de_una_persona_y_su_excel(self):
        self.entrar('CONSULTA')
        self.api.respuestas[('GET', 'reportes/resguardante/3/')] = {
            'resguardante': {'num': 3, 'numero_empleado': 'E003', 'nombre': 'Juan Pérez'},
            'total': 1, 'resultados': [articulo()]}
        r = self.client.get('/reportes/?vista=resguardante&persona=3')
        self.assertContains(r, 'a cargo de <strong>Juan Pérez</strong>')
        self.assertContains(r, 'href="/reportes/excel/resguardante/3/"')
        r = self.client.get('/reportes/excel/resguardante/3/')
        self.assertEqual(self.descargar.call_args[0][1], 'reportes/resguardante/3/?formato=xlsx')
        self.assertIn('articulos_resguardante_3.xlsx', r['Content-Disposition'])

    def test_sin_persona_no_llama(self):
        self.entrar()
        r = self.client.get('/reportes/?vista=resguardante')
        self.assertContains(r, 'Elige a una persona')

    def test_persona_que_no_existe(self):
        self.entrar()
        self.api.respuestas[('GET', 'reportes/resguardante/99/')] = ApiError(404, {'detail': 'No encontrado.'})
        r = self.client.get('/reportes/?vista=resguardante&persona=99')
        self.assertContains(r, 'No encontrado.')


class HistorialTests(BaseReportes):
    def test_buscar_y_ver_historial_con_resguardos(self):
        self.entrar('CONSULTA')
        self.api.respuestas[('GET', 'articulos/')] = pagina([articulo()])
        r = self.client.get('/reportes/?vista=historial&q=M-100')
        self.assertContains(r, 'Ver historial')
        self.assertContains(r, 'articulo=7')
        self.api.respuestas[('GET', 'reportes/historial/7/')] = {
            'articulo': articulo(),
            'movimientos': [tablero()['ultimos_movimientos'][0]],
            'resguardos': [{'folio': 'RES-0001', 'fecha_emision': '2026-11-05 09:30',
                            'resguardante': {'num': 1, 'nombre': 'Ana López'},
                            'pdf': '/api/resguardos/RES-0001/pdf/'}]}
        r = self.client.get('/reportes/?vista=historial&articulo=7')
        self.assertContains(r, 'Movimientos (1)')
        self.assertContains(r, 'href="/movimientos/resguardos/RES-0001/pdf/" target="_blank"')

    def test_busqueda_sin_resultados(self):
        self.entrar()
        r = self.client.get('/reportes/?vista=historial&q=nada')
        self.assertContains(r, 'Ningún artículo coincide')
