from io import BytesIO

from openpyxl import load_workbook

from api.test_api_articulos_movimientos import Base


class DashboardYReportesTests(Base):
    def setUp(self):
        super().setUp()
        self.a1 = self.alta(marbete_oficial='M1', num_serie='S1')
        self.a2 = self.alta(marbete_oficial='M2', num_serie='S2', costo_adquisicion=None)
        self.a3 = self.alta(origen='COM', marbete_oficial=None, num_serie='S3', donado=True,
                            costo_adquisicion=None, fecha_adquisicion=None)
        self.mov(tipo='REUB', articulo=self.a1['num'], ubicacion='UBI-LAB1',
                 resguardante=str(self.beto.num), motivo='Cambio')
        self.mov(tipo='REUB', articulo=self.a2['num'], ubicacion='UBI-NOLOC', motivo='No está')
        self.c_consulta = self.cliente(self.obs)

    def test_dashboard(self):
        r = self.c.get('/api/dashboard/')
        self.assertEqual(r.status_code, 200)
        d = r.data
        self.assertEqual(d['total_articulos'], 3)
        self.assertEqual([x['codigo'] for x in d['por_estado_operativo']], ['UTIL', 'OBS', 'NOLOC'])
        self.assertEqual([x['codigo'] for x in d['por_estado_registro']], ['REG', 'PEND', 'DON'])
        op = {x['codigo']: x['total'] for x in d['por_estado_operativo']}
        self.assertEqual(op, {'UTIL': 2, 'OBS': 0, 'NOLOC': 1})
        reg = {x['codigo']: x['total'] for x in d['por_estado_registro']}
        self.assertEqual(reg, {'REG': 1, 'PEND': 1, 'DON': 1})
        ubi = {x['codigo']: x['total'] for x in d['por_ubicacion']}
        self.assertEqual((ubi['UBI-LAB1'], ubi['UBI-OFI']), (1, 1))
        self.assertEqual(d['pendientes_de_datos']['total'], 1)
        self.assertEqual(d['pendientes_de_datos']['articulos'][0]['identificador'], 'M2')
        self.assertEqual(d['pendientes_de_datos']['articulos'][0]['faltantes'],
                         ['el costo de adquisición'])
        self.assertEqual(len(d['ultimos_movimientos']), 5)  # 3 altas + 2 reubicaciones
        self.assertEqual(d['ultimos_movimientos'][0]['folio'], 'MOV-0005')
        self.assertEqual(d['resguardos_por_emitir'], 4)  # 3 altas + 1 cambio de persona

    def test_el_dashboard_solo_pide_sesion(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get('/api/dashboard/').status_code, 401)

    def test_inventario_filtrable_y_sin_paginar(self):
        r = self.c.get('/api/reportes/inventario/')
        self.assertEqual((r.data['total'], len(r.data['resultados'])), (3, 3))
        r = self.c.get('/api/reportes/inventario/?ubicacion=UBI-LAB1')
        self.assertEqual([a['identificador'] for a in r.data['resultados']], ['M1'])
        r = self.c.get('/api/reportes/inventario/?resguardante=%d' % self.beto.num)
        self.assertEqual(r.data['total'], 1)
        r = self.c.get('/api/reportes/inventario/?estado_operativo=NOLOC')
        self.assertEqual(r.data['total'], 1)
        r = self.c.get('/api/reportes/inventario/?estado_registro=DON')
        self.assertEqual(r.data['total'], 1)

    def test_inventario_en_excel(self):
        r = self.c_consulta.get('/api/reportes/inventario/?formato=xlsx&estado_registro=REG')
        self.assertEqual(r.status_code, 200)
        filas = list(load_workbook(BytesIO(r.content)).active.values)
        self.assertEqual(len(filas), 2)

    def test_articulos_de_un_resguardante(self):
        r = self.c.get('/api/reportes/resguardante/%d/' % self.ana.num)
        self.assertEqual(r.data['total'], 2)  # a2 (en NOLOC, sigue a su nombre) y a3
        self.assertEqual(r.data['resguardante']['num'], self.ana.num)
        self.assertEqual(self.c.get('/api/reportes/resguardante/99999/').status_code, 404)
        x = self.c.get('/api/reportes/resguardante/%d/?formato=xlsx' % self.beto.num)
        self.assertEqual(len(list(load_workbook(BytesIO(x.content)).active.values)), 2)

    def test_historial_de_un_articulo(self):
        r = self.c.get('/api/reportes/historial/%d/' % self.a1['num'])
        self.assertEqual(r.data['articulo']['identificador'], 'M1')
        self.assertEqual([m['tipo']['codigo'] for m in r.data['movimientos']], ['REUB', 'ALTA'])
        self.assertEqual(r.data['resguardos'], [])
        self.assertEqual(self.c.get('/api/reportes/historial/99999/').status_code, 404)


class DashboardVacioTests(Base):
    def test_sin_articulos_todo_en_cero(self):
        d = self.cliente(self.obs).get('/api/dashboard/').data
        self.assertEqual(d['total_articulos'], 0)
        self.assertEqual({x['total'] for x in d['por_estado_operativo']}, {0})
        self.assertEqual(d['pendientes_de_datos'], {'total': 0, 'articulos': []})
        self.assertEqual(d['ultimos_movimientos'], [])
        self.assertEqual(d['resguardos_por_emitir'], 0)
        r = self.c.get('/api/reportes/inventario/')
        self.assertEqual((r.data['total'], r.data['resultados']), (0, []))
