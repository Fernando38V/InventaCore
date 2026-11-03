"""Endpoints de artículos y movimientos."""
import json
from datetime import timedelta

from django.utils import timezone

from api.test_api import BaseAPI
from auditoria.models import Bitacora
from catalogos.models import Categoria, TipoArticulo
from movimientos.models import Movimiento
from personal.models import Personal


class Base(BaseAPI):
    def setUp(self):
        super().setUp()
        self.c = self.cliente(self.admin)
        Categoria.objects.create(codigo='CAT-001', nombre='EQUIPO DE CÓMPUTO')
        TipoArticulo.objects.create(codigo='TIP-001', nombre='Laptop', categoria_id='CAT-001')
        self.ana = self.admin.personal
        self.beto = Personal.objects.create(
            numero_empleado='E900', nombre_pila='Beto', primer_apellido='Ruiz',
            segundo_apellido='Soto', puesto='Docente', departamento_id='DEP-INF')

    def datos(self, **cambios):
        d = {'origen': 'ACT', 'tipo_articulo': 'TIP-001', 'ubicacion': 'UBI-OFI',
             'resguardante': self.ana.num, 'marbete_oficial': '02-520-00003',
             'marca': 'Dell', 'modelo': 'Latitude', 'num_serie': 'SN1', 'color': 'Negro',
             'descripcion': 'Laptop de oficina', 'fecha_adquisicion': '2024-01-15',
             'costo_adquisicion': '12500.00'}
        d.update(cambios)
        return d

    def alta(self, **cambios):
        r = self.c.post('/api/articulos/', self.datos(**cambios), format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def mov(self, **datos):
        return self.c.post('/api/movimientos/', datos, format='json')


class AltaArticuloTests(Base):
    def test_alta_activo_registrado_forma_del_json(self):
        a = self.alta()
        self.assertEqual(a['identificador'], '02-520-00003')
        self.assertIsNone(a['folio_interno'])
        self.assertEqual(a['costo_adquisicion'], '12500.00')
        self.assertEqual(a['categoria'], {'codigo': 'CAT-001', 'nombre': 'EQUIPO DE CÓMPUTO'})
        self.assertEqual(a['tipo_articulo']['codigo'], 'TIP-001')
        self.assertEqual(a['resguardante']['num'], self.ana.num)
        self.assertEqual(a['estado_registro'], {'codigo': 'REG', 'nombre': 'Registrado', 'tono': 'verde'})
        self.assertEqual(a['estado_operativo']['codigo'], 'UTIL')
        self.assertEqual(a['faltantes'], [])

    def test_alta_crea_movimiento_alta_y_bitacora(self):
        a = self.alta()
        m = Movimiento.objects.get(articulo_id=a['num'])
        self.assertEqual((m.folio, m.tipo_movimiento_id, m.requiere_resguardo), ('MOV-0001', 'ALTA', True))
        tablas = set(Bitacora.objects.values_list('tabla_afectada', flat=True))
        self.assertEqual(tablas, {'articulo', 'movimiento'})

    def test_comodato_recibe_folio_interno_del_sistema(self):
        a = self.alta(origen='COM', marbete_oficial=None, num_serie='S2')
        mes = timezone.localtime().strftime('%m%y')
        self.assertEqual(a['folio_interno'], '02143%s-001' % mes)
        self.assertEqual(self.alta(origen='ENS', marbete_oficial=None, num_serie='S3')['folio_interno'],
                         '02143%s-002' % mes)

    def test_comodato_con_marbete_se_rechaza(self):
        r = self.c.post('/api/articulos/', self.datos(origen='COM'), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('marbete_oficial', r.data)

    def test_activo_sin_marbete_se_rechaza(self):
        r = self.c.post('/api/articulos/', self.datos(marbete_oficial=None), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, {'marbete_oficial': 'Los activos llevan marbete oficial.'})

    def test_sin_costo_es_pendiente_y_avisa_que_falta(self):
        a = self.alta(costo_adquisicion=None)
        self.assertEqual(a['estado_registro']['codigo'], 'PEND')
        self.assertEqual(a['faltantes'], ['el costo de adquisición'])
        a = self.alta(marbete_oficial='M2', num_serie='S2', costo_adquisicion=None,
                      fecha_adquisicion=None)
        self.assertEqual(len(a['faltantes']), 2)

    def test_donado_tiene_prioridad(self):
        a = self.alta(donado=True, costo_adquisicion=None, fecha_adquisicion=None)
        self.assertEqual(a['estado_registro']['codigo'], 'DON')

    def test_marca_modelo_y_serie_son_opcionales(self):
        a = self.alta(marca='', modelo=None, num_serie='')
        self.assertEqual((a['marca'], a['modelo'], a['num_serie']), (None, None, None))
        b = self.alta(marbete_oficial='M2', marca='', modelo=None, num_serie='')
        self.assertIsNone(b['num_serie'])

    def test_color_y_descripcion_obligatorios(self):
        r = self.c.post('/api/articulos/', self.datos(color='', descripcion=''), format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(set(r.data), {'color', 'descripcion'})

    def test_marbete_y_serie_repetidos(self):
        self.alta()
        r = self.c.post('/api/articulos/', self.datos(num_serie='OTRA'), format='json')
        self.assertEqual(r.data, {'marbete_oficial': 'Ese marbete ya está registrado.'})
        r = self.c.post('/api/articulos/', self.datos(marbete_oficial='M9'), format='json')
        self.assertEqual(r.data, {'num_serie': 'Ese número de serie ya está registrado.'})

    def test_fecha_futura_y_costo_negativo(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = self.c.post('/api/articulos/', self.datos(fecha_adquisicion=manana,
                                                      costo_adquisicion='-5'), format='json')
        self.assertEqual(set(r.data), {'fecha_adquisicion', 'costo_adquisicion'})

    def test_ubicacion_sin_ubicar_fuerza_estado_no_localizado(self):
        a = self.alta(ubicacion='UBI-NOLOC')
        self.assertEqual(a['estado_operativo']['codigo'], 'NOLOC')
        self.assertFalse(Movimiento.objects.get(articulo_id=a['num']).requiere_resguardo)

    def test_estado_no_localizado_sin_la_ubicacion_se_rechaza(self):
        r = self.c.post('/api/articulos/', self.datos(estado_operativo='NOLOC'), format='json')
        self.assertIn('estado_operativo', r.data)
        r = self.c.post('/api/articulos/', self.datos(ubicacion='UBI-NOLOC',
                                                      estado_operativo='UTIL'), format='json')
        self.assertIn('estado_operativo', r.data)

    def test_resguardante_de_baja_y_tipo_inexistente(self):
        self.beto.activo = False
        self.beto.save()
        r = self.c.post('/api/articulos/', self.datos(resguardante=self.beto.num,
                                                      tipo_articulo='TIP-999'), format='json')
        self.assertEqual(set(r.data), {'resguardante', 'tipo_articulo'})

    def test_si_algo_falla_no_se_consume_folio_ni_queda_nada(self):
        self.alta(origen='COM', marbete_oficial=None, num_serie='S2')
        r = self.c.post('/api/articulos/', self.datos(origen='COM', marbete_oficial=None,
                                                      num_serie='S2'), format='json')
        self.assertEqual(r.status_code, 400)
        mes = timezone.localtime().strftime('%m%y')
        self.assertEqual(self.alta(origen='COM', marbete_oficial=None, num_serie='S9')['folio_interno'],
                         '02143%s-002' % mes)


class ConsultaArticulosTests(Base):
    def setUp(self):
        super().setUp()
        self.a1 = self.alta()
        self.a2 = self.alta(origen='COM', marbete_oficial=None, num_serie='S2', marca='HP',
                            ubicacion='UBI-LAB1', resguardante=self.beto.num, costo_adquisicion=None)

    def test_lista_paginada(self):
        r = self.c.get('/api/articulos/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['count'], len(r.data['results'])), (2, 2))
        self.assertIn('next', r.data)

    def test_detalle(self):
        r = self.c.get('/api/articulos/%d/' % self.a1['num'])
        self.assertEqual(r.data, self.a1)
        self.assertEqual(self.c.get('/api/articulos/999/').status_code, 404)

    def test_filtros(self):
        def cuantos(q):
            return self.c.get('/api/articulos/?' + q).data['count']
        self.assertEqual(cuantos('origen=COM'), 1)
        self.assertEqual(cuantos('ubicacion=UBI-LAB1'), 1)
        self.assertEqual(cuantos('estado_registro=PEND'), 1)
        self.assertEqual(cuantos('estado_operativo=UTIL'), 2)
        self.assertEqual(cuantos('categoria=CAT-001'), 2)
        self.assertEqual(cuantos('categoria=CAT-002'), 0)
        self.assertEqual(cuantos('origen=COM&ubicacion=UBI-OFI'), 0)

    def test_busqueda_por_palabras(self):
        def cuantos(q):
            return self.c.get('/api/articulos/', {'q': q}).data['count']
        self.assertEqual(cuantos('dell'), 1)
        self.assertEqual(cuantos('beto ruiz'), 1)
        self.assertEqual(cuantos('portátil'), 0)
        self.assertEqual(cuantos('laptop cómputo'), 2)

    def test_movimientos_del_articulo(self):
        r = self.c.get('/api/articulos/%d/movimientos/' % self.a1['num'])
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['tipo']['codigo'], 'ALTA')

    def test_consulta_lee_pero_no_crea(self):
        c = self.cliente(self.obs)
        self.assertEqual(c.get('/api/articulos/').status_code, 200)
        self.assertEqual(c.post('/api/articulos/', self.datos(), format='json').status_code, 403)
        self.assertEqual(c.post('/api/movimientos/', {}, format='json').status_code, 403)

    def test_sin_sesion(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get('/api/articulos/').status_code, 401)
        self.assertEqual(APIClient().get('/api/movimientos/').status_code, 401)

    def test_no_hay_borrado_ni_edicion(self):
        n = self.a1['num']
        self.assertEqual(self.c.delete('/api/articulos/%d/' % n).status_code, 405)
        self.assertEqual(self.c.patch('/api/articulos/%d/' % n, {}, format='json').status_code, 405)


class MovimientosTests(Base):
    def setUp(self):
        super().setUp()
        self.n = self.alta()['num']

    def articulo(self):
        return self.c.get('/api/articulos/%d/' % self.n).data

    def test_reubicacion(self):
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='Remodelación')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['folio'], 'MOV-0002')
        self.assertEqual(r.data['tipo']['codigo'], 'REUB')
        self.assertFalse(r.data['genera_resguardo'])
        self.assertEqual(r.data['ubicacion_origen']['codigo'], 'UBI-OFI')
        self.assertEqual(r.data['ubicacion_llegada']['codigo'], 'UBI-LAB1')
        self.assertIsNone(r.data['personal_entrega'])
        self.assertEqual(r.data['equipo']['descripcion'], 'Dell Latitude')
        self.assertEqual(r.data['nota'], 'Remodelación')
        self.assertEqual(self.articulo()['ubicacion']['codigo'], 'UBI-LAB1')

    def test_cambio_de_resguardante_genera_resguardo(self):
        r = self.mov(tipo='REUB', equipo=self.n, resguardante=self.beto.num, motivo='Reasignación')
        self.assertTrue(r.data['genera_resguardo'])
        self.assertEqual(r.data['personal_asigna']['nombre'], 'Beto Ruiz Soto')
        self.assertEqual(r.data['personal_entrega']['nombre'], self.ana.nombre_completo)
        self.assertEqual(r.data['ubicacion_llegada']['codigo'], 'UBI-OFI')
        self.assertEqual(self.articulo()['resguardante']['num'], self.beto.num)

    def test_sin_cambio_efectivo_se_rechaza(self):
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-OFI', motivo='x')
        self.assertEqual(r.status_code, 400)
        self.assertIn('ubicacion', r.data)
        self.assertEqual(self.mov(tipo='REUB', equipo=self.n, motivo='x').status_code, 400)

    def test_motivo_y_fecha(self):
        self.assertEqual(self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1').data,
                         {'motivo': 'El motivo es obligatorio.'})
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='x', fecha=manana)
        self.assertEqual(r.data, {'fecha': 'La fecha no puede ser futura.'})

    def test_fecha_pasada_se_acepta(self):
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='x', fecha='2026-09-01')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['fecha_dia'], '2026-09-01')

    def test_alta_no_se_pide_a_mano(self):
        r = self.mov(tipo='ALTA', equipo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'tipo': 'Selecciona el tipo de movimiento.'})

    def test_equipo_inexistente(self):
        r = self.mov(tipo='REUB', equipo=999, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'equipo': 'Selecciona el equipo.'})

    def test_perdida_y_recuperacion_con_reub(self):
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-NOLOC', motivo='No aparece')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'NOLOC')
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB2', motivo='Apareció',
                     estado_operativo='OBS')
        self.assertEqual(r.status_code, 201, r.data)
        a = self.articulo()
        self.assertEqual((a['ubicacion']['codigo'], a['estado_operativo']['codigo']), ('UBI-LAB2', 'OBS'))

    def test_recuperar_sin_indicar_estado_queda_util(self):
        self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB2', motivo='y')
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'UTIL')

    def test_estado_solo_se_indica_al_recuperar(self):
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='x', estado_operativo='OBS')
        self.assertIn('estado_operativo', r.data)

    def test_reparacion_y_retorno(self):
        self.assertEqual(self.mov(tipo='REPA', equipo=self.n, motivo='No enciende').status_code, 201)
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'UTIL')
        r = self.mov(tipo='REPA', equipo=self.n, motivo='otra vez')
        self.assertEqual(r.data, {'equipo': 'El equipo ya está en reparación.'})
        r = self.mov(tipo='RETE', equipo=self.n, motivo='Reparado')
        self.assertEqual(r.data, {'ubicacion': 'Indica dónde se reintegra el equipo.'})
        r = self.mov(tipo='RETE', equipo=self.n, ubicacion='UBI-LAB1', motivo='Reparado')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['genera_resguardo'])
        self.assertEqual(self.articulo()['ubicacion']['codigo'], 'UBI-LAB1')

    def test_retorno_sin_reparacion(self):
        r = self.mov(tipo='RETE', equipo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'equipo': 'El equipo no está en reparación.'})

    def test_reparacion_no_cambia_resguardante_ni_manda_a_no_localizado(self):
        r = self.mov(tipo='REPA', equipo=self.n, resguardante=self.beto.num, motivo='x')
        self.assertIn('resguardante', r.data)
        r = self.mov(tipo='REPA', equipo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        self.assertIn('ubicacion', r.data)

    def test_baja(self):
        r = self.mov(tipo='BAJA', equipo=self.n, motivo='Dañado sin reparación')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['genera_resguardo'])
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'AUTB')
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'equipo': 'El equipo ya fue dado de baja.'})

    def test_baja_de_no_localizado_se_bloquea(self):
        self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        r = self.mov(tipo='BAJA', equipo=self.n, motivo='x')
        self.assertIn('equipo', r.data)

    def test_bitacora_del_movimiento(self):
        self.mov(tipo='REUB', equipo=self.n, resguardante=self.beto.num, motivo='Reasignación')
        b = Bitacora.objects.get(tabla_afectada='articulo', accion='UPDATE')
        self.assertEqual(b.motivo, 'Reasignación')
        self.assertEqual(json.loads(b.valor_nuevo), {'resguardante': self.beto.num})
        self.assertTrue(Bitacora.objects.filter(
            tabla_afectada='movimiento', registro_id='MOV-0002', accion='INSERT').exists())

    def test_fallo_no_deja_nada_a_medias(self):
        self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-OFI', motivo='x')
        self.assertEqual(Movimiento.objects.count(), 1)
        self.assertEqual(self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1',
                                  motivo='ok').data['folio'], 'MOV-0002')

    def test_lista_filtros_y_detalle(self):
        self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='Remodelación')
        r = self.c.get('/api/movimientos/')
        self.assertEqual(r.data['count'], 2)
        self.assertEqual(r.data['results'][0]['folio'], 'MOV-0002')
        self.assertEqual(self.c.get('/api/movimientos/?tipo=ALTA').data['count'], 1)
        self.assertEqual(self.c.get('/api/movimientos/?ubicacion=UBI-LAB1').data['count'], 1)
        self.assertEqual(self.c.get('/api/movimientos/?ubicacion=UBI-OFI').data['count'], 2)
        self.assertEqual(self.c.get('/api/movimientos/?q=remodelación').data['count'], 1)
        self.assertEqual(self.c.get('/api/movimientos/?equipo=%d' % self.n).data['count'], 2)
        self.assertEqual(self.c.get('/api/movimientos/MOV-0001/').data['tipo']['codigo'], 'ALTA')
        self.assertEqual(self.c.get('/api/movimientos/MOV-0099/').status_code, 404)

    def test_articulo_como_sinonimo_de_equipo(self):
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.status_code, 201)

    def test_se_acepta_formulario_html(self):
        r = self.c.post('/api/movimientos/', {
            'tipo': 'REUB', 'equipo': str(self.n), 'ubicacion': 'UBI-LAB1',
            'resguardante': '', 'motivo': 'x', 'fecha': timezone.localdate().isoformat()})
        self.assertEqual(r.status_code, 201, r.data)
