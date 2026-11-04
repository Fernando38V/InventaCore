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

    def test_no_hay_borrado(self):
        n = self.a1['num']
        self.assertEqual(self.c.delete('/api/articulos/%d/' % n).status_code, 405)
        self.assertEqual(self.c.delete('/api/movimientos/MOV-0001/').status_code, 405)


class MovimientosTests(Base):
    def setUp(self):
        super().setUp()
        self.n = self.alta()['num']

    def articulo(self):
        return self.c.get('/api/articulos/%d/' % self.n).data

    def test_reubicacion(self):
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1', motivo='Remodelación')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['folio'], 'MOV-0002')
        self.assertEqual(r.data['tipo']['codigo'], 'REUB')
        self.assertFalse(r.data['requiere_resguardo'])
        self.assertEqual(r.data['ubicacion_origen']['codigo'], 'UBI-OFI')
        self.assertEqual(r.data['ubicacion_llegada']['codigo'], 'UBI-LAB1')
        self.assertIsNone(r.data['personal_entrega'])
        self.assertEqual(r.data['articulo']['descripcion'], 'Dell Latitude')
        self.assertEqual(r.data['nota'], 'Remodelación')
        self.assertEqual(self.articulo()['ubicacion']['codigo'], 'UBI-LAB1')

    def test_cambio_de_resguardante_genera_resguardo(self):
        r = self.mov(tipo='REUB', articulo=self.n, resguardante=self.beto.num, motivo='Reasignación')
        self.assertTrue(r.data['requiere_resguardo'])
        self.assertEqual(r.data['personal_asigna']['nombre'], 'Beto Ruiz Soto')
        self.assertEqual(r.data['personal_entrega']['nombre'], self.ana.nombre_completo)
        self.assertEqual(r.data['ubicacion_llegada']['codigo'], 'UBI-OFI')
        self.assertEqual(self.articulo()['resguardante']['num'], self.beto.num)

    def test_sin_cambio_efectivo_se_rechaza(self):
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-OFI', motivo='x')
        self.assertEqual(r.status_code, 400)
        self.assertIn('ubicacion', r.data)
        self.assertEqual(self.mov(tipo='REUB', articulo=self.n, motivo='x').status_code, 400)

    def test_motivo_y_fecha(self):
        self.assertEqual(self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1').data,
                         {'motivo': 'El motivo es obligatorio.'})
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1', motivo='x', fecha=manana)
        self.assertEqual(r.data, {'fecha': 'La fecha no puede ser futura.'})

    def test_fecha_pasada_se_acepta(self):
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1', motivo='x', fecha='2026-09-01')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['fecha_dia'], '2026-09-01')

    def test_alta_no_se_pide_a_mano(self):
        r = self.mov(tipo='ALTA', articulo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'tipo': 'Selecciona el tipo de movimiento.'})

    def test_articulo_inexistente(self):
        r = self.mov(tipo='REUB', articulo=999, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'articulo': 'Selecciona el artículo.'})

    def test_perdida_y_recuperacion_con_reub(self):
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-NOLOC', motivo='No aparece')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'NOLOC')
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB2', motivo='Apareció',
                     estado_operativo='OBS')
        self.assertEqual(r.status_code, 201, r.data)
        a = self.articulo()
        self.assertEqual((a['ubicacion']['codigo'], a['estado_operativo']['codigo']), ('UBI-LAB2', 'OBS'))

    def test_recuperar_sin_indicar_estado_queda_util(self):
        self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB2', motivo='y')
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'UTIL')

    def test_estado_solo_se_indica_al_recuperar(self):
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1', motivo='x', estado_operativo='OBS')
        self.assertIn('estado_operativo', r.data)

    def test_reparacion_y_retorno(self):
        self.assertEqual(self.mov(tipo='REPA', articulo=self.n, motivo='No enciende').status_code, 201)
        self.assertEqual(self.articulo()['estado_operativo']['codigo'], 'UTIL')
        r = self.mov(tipo='REPA', articulo=self.n, motivo='otra vez')
        self.assertEqual(r.data, {'articulo': 'El artículo ya está en reparación.'})
        r = self.mov(tipo='RETE', articulo=self.n, motivo='Reparado')
        self.assertEqual(r.data, {'ubicacion': 'Indica dónde se reintegra el artículo.'})
        r = self.mov(tipo='RETE', articulo=self.n, ubicacion='UBI-LAB1', motivo='Reparado')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertFalse(r.data['requiere_resguardo'])
        self.assertEqual(self.articulo()['ubicacion']['codigo'], 'UBI-LAB1')

    def test_retorno_sin_reparacion(self):
        r = self.mov(tipo='RETE', articulo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.data, {'articulo': 'El artículo no está en reparación.'})

    def test_reparacion_no_cambia_resguardante_ni_manda_a_no_localizado(self):
        r = self.mov(tipo='REPA', articulo=self.n, resguardante=self.beto.num, motivo='x')
        self.assertIn('resguardante', r.data)
        r = self.mov(tipo='REPA', articulo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        self.assertIn('ubicacion', r.data)

    def test_baja_ya_no_existe(self):
        r = self.mov(tipo='BAJA', articulo=self.n, motivo='Dañado')
        self.assertEqual(r.data, {'tipo': 'Selecciona el tipo de movimiento.'})

    def test_no_localizado_no_admite_reparacion(self):
        self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        r = self.mov(tipo='REPA', articulo=self.n, motivo='x')
        self.assertIn('articulo', r.data)

    def test_al_recuperar_solo_util_u_obsoleto(self):
        self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-NOLOC', motivo='x')
        r = self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB2', motivo='y',
                     estado_operativo='AUTB')
        self.assertIn('estado_operativo', r.data)

    def test_bitacora_del_movimiento(self):
        self.mov(tipo='REUB', articulo=self.n, resguardante=self.beto.num, motivo='Reasignación')
        b = Bitacora.objects.get(tabla_afectada='articulo', accion='UPDATE')
        self.assertEqual(b.motivo, 'Reasignación')
        self.assertEqual(json.loads(b.valor_nuevo), {'resguardante': self.beto.num})
        self.assertTrue(Bitacora.objects.filter(
            tabla_afectada='movimiento', registro_id='MOV-0002', accion='INSERT').exists())

    def test_fallo_no_deja_nada_a_medias(self):
        self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-OFI', motivo='x')
        self.assertEqual(Movimiento.objects.count(), 1)
        self.assertEqual(self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1',
                                  motivo='ok').data['folio'], 'MOV-0002')

    def test_lista_filtros_y_detalle(self):
        self.mov(tipo='REUB', articulo=self.n, ubicacion='UBI-LAB1', motivo='Remodelación')
        r = self.c.get('/api/movimientos/')
        self.assertEqual(r.data['count'], 2)
        self.assertEqual(r.data['results'][0]['folio'], 'MOV-0002')
        self.assertEqual(self.c.get('/api/movimientos/?tipo=ALTA').data['count'], 1)
        self.assertEqual(self.c.get('/api/movimientos/?ubicacion=UBI-LAB1').data['count'], 1)
        self.assertEqual(self.c.get('/api/movimientos/?ubicacion=UBI-OFI').data['count'], 2)
        self.assertEqual(self.c.get('/api/movimientos/?q=remodelación').data['count'], 1)
        self.assertEqual(self.c.get('/api/movimientos/?articulo=%d' % self.n).data['count'], 2)
        self.assertEqual(self.c.get('/api/movimientos/MOV-0001/').data['tipo']['codigo'], 'ALTA')
        self.assertEqual(self.c.get('/api/movimientos/MOV-0099/').status_code, 404)

    def test_equipo_como_sinonimo_de_articulo(self):
        r = self.mov(tipo='REUB', equipo=self.n, ubicacion='UBI-LAB1', motivo='x')
        self.assertEqual(r.status_code, 201)

    def test_se_acepta_formulario_html(self):
        r = self.c.post('/api/movimientos/', {
            'tipo': 'REUB', 'articulo': str(self.n), 'ubicacion': 'UBI-LAB1',
            'resguardante': '', 'motivo': 'x', 'fecha': timezone.localdate().isoformat()})
        self.assertEqual(r.status_code, 201, r.data)


class CorreccionFichaTests(Base):
    def setUp(self):
        super().setUp()
        self.a = self.alta()
        self.url = '/api/articulos/%d/' % self.a['num']

    def corregir(self, **datos):
        return self.c.patch(self.url, datos, format='json')

    def test_corrige_datos_con_motivo_y_bitacora(self):
        r = self.corregir(marca='HP', modelo='ProBook', color='Gris', motivo='Datos del bien repuesto')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['marca'], r.data['modelo'], r.data['color']), ('HP', 'ProBook', 'Gris'))
        b = Bitacora.objects.filter(tabla_afectada='articulo', accion='UPDATE').get()
        self.assertEqual(b.motivo, 'Datos del bien repuesto')
        self.assertEqual(json.loads(b.valor_anterior), {'marca': 'Dell', 'modelo': 'Latitude', 'color': 'Negro'})
        self.assertEqual(json.loads(b.valor_nuevo), {'marca': 'HP', 'modelo': 'ProBook', 'color': 'Gris'})

    def test_exige_motivo(self):
        r = self.corregir(marca='HP')
        self.assertEqual(r.data, {'motivo': 'Indique el motivo del cambio.'})

    def test_sin_cambios(self):
        self.assertEqual(self.corregir(motivo='x').data, {'detalle': 'No hay cambios que guardar.'})
        self.assertEqual(self.corregir(marca='Dell', motivo='x').data,
                         {'detalle': 'No hay cambios que guardar.'})

    def test_color_y_descripcion_no_quedan_vacios(self):
        r = self.corregir(color='', descripcion='  ', motivo='x')
        self.assertEqual(set(r.data), {'color', 'descripcion'})

    def test_marca_modelo_y_serie_se_pueden_borrar(self):
        r = self.corregir(marca='', modelo='', num_serie='', motivo='No aplica')
        self.assertEqual((r.data['marca'], r.data['modelo'], r.data['num_serie']), (None, None, None))

    def test_serie_y_marbete_repetidos(self):
        b = self.alta(marbete_oficial='M2', num_serie='S2')
        r = self.c.patch('/api/articulos/%d/' % b['num'],
                         {'num_serie': 'SN1', 'marbete_oficial': '02-520-00003', 'motivo': 'x'}, format='json')
        self.assertEqual(set(r.data), {'num_serie', 'marbete_oficial'})

    def test_corregir_el_marbete_de_un_activo(self):
        r = self.corregir(marbete_oficial='02-520-99999', motivo='Marbete mal capturado')
        self.assertEqual((r.status_code, r.data['identificador']), (200, '02-520-99999'))

    def test_comodato_no_lleva_marbete(self):
        b = self.alta(origen='COM', marbete_oficial=None, num_serie='S9')
        r = self.c.patch('/api/articulos/%d/' % b['num'], {'marbete_oficial': 'X', 'motivo': 'x'}, format='json')
        self.assertIn('marbete_oficial', r.data)

    def test_la_fecha_recalcula_el_estado_de_registro(self):
        p = self.alta(marbete_oficial='M2', num_serie='S2', fecha_adquisicion=None)
        self.assertEqual(p['estado_registro']['codigo'], 'PEND')
        r = self.c.patch('/api/articulos/%d/' % p['num'],
                         {'fecha_adquisicion': '2024-05-01', 'motivo': 'Se encontró la factura'}, format='json')
        self.assertEqual(r.data['estado_registro']['codigo'], 'REG')
        self.assertEqual(r.data['faltantes'], [])
        r = self.c.patch('/api/articulos/%d/' % p['num'],
                         {'fecha_adquisicion': None, 'motivo': 'Fecha equivocada'}, format='json')
        self.assertEqual(r.data['estado_registro']['codigo'], 'PEND')

    def test_donado_sigue_donado(self):
        d = self.alta(marbete_oficial='M2', num_serie='S2', donado=True, costo_adquisicion=None,
                      fecha_adquisicion=None)
        r = self.c.patch('/api/articulos/%d/' % d['num'],
                         {'fecha_adquisicion': '2024-05-01', 'motivo': 'x'}, format='json')
        self.assertEqual(r.data['estado_registro']['codigo'], 'DON')

    def test_el_costo_se_corrige_y_pasa_a_registrado(self):
        p = self.alta(marbete_oficial='M2', num_serie='S2', costo_adquisicion=None)
        self.assertEqual(p['estado_registro']['codigo'], 'PEND')
        self.assertEqual(p['faltantes'], ['el costo de adquisición'])
        r = self.c.patch('/api/articulos/%d/' % p['num'],
                         {'costo_adquisicion': '8500.50', 'motivo': 'Llegó la factura'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['costo_adquisicion'], '8500.50')
        self.assertEqual(r.data['estado_registro']['codigo'], 'REG')
        b = Bitacora.objects.filter(tabla_afectada='articulo', accion='UPDATE').last()
        self.assertEqual(b.motivo, 'Llegó la factura')
        self.assertIn('costo_adquisicion', json.loads(b.valor_nuevo))
        r = self.c.patch('/api/articulos/%d/' % p['num'],
                         {'costo_adquisicion': None, 'motivo': 'Costo equivocado'}, format='json')
        self.assertEqual(r.data['estado_registro']['codigo'], 'PEND')

    def test_costo_invalido_o_sin_motivo(self):
        self.assertIn('costo_adquisicion', self.corregir(costo_adquisicion='-5', motivo='x').data)
        self.assertEqual(self.corregir(costo_adquisicion='100').data,
                         {'motivo': 'Indique el motivo del cambio.'})

    def test_en_un_donado_el_costo_no_se_modifica(self):
        d = self.alta(marbete_oficial='M3', num_serie='S3', donado=True, costo_adquisicion=None,
                      fecha_adquisicion=None)
        r = self.c.patch('/api/articulos/%d/' % d['num'],
                         {'costo_adquisicion': '100', 'motivo': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data, {'costo_adquisicion': 'En un bien Donado el costo no se modifica.'})

    def test_la_carga_masiva_puede_dar_el_alta_sin_requerir_resguardo(self):
        from articulos.servicios import alta_articulo
        from articulos.serializers import ArticuloCrearSerializer
        entrada = ArticuloCrearSerializer(data=self.datos(marbete_oficial='M9', num_serie='S9'))
        entrada.is_valid(raise_exception=True)
        a = alta_articulo(entrada.validated_data, self.admin, requiere_resguardo=False)
        self.assertFalse(Movimiento.objects.get(articulo=a).requiere_resguardo)

    def test_fecha_futura(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertIn('fecha_adquisicion', self.corregir(fecha_adquisicion=manana, motivo='x').data)

    def test_obsoleto_desde_la_ficha_conserva_ubicacion_y_resguardante(self):
        r = self.corregir(estado_operativo='OBS', motivo='Ya no sirve')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['estado_operativo']['codigo'], 'OBS')
        self.assertEqual(r.data['ubicacion']['codigo'], 'UBI-OFI')
        self.assertEqual(r.data['resguardante']['num'], self.ana.num)
        self.assertEqual(Movimiento.objects.count(), 1)  # sin movimiento: solo el ALTA
        r = self.corregir(estado_operativo='UTIL', motivo='Corrección auditada')
        self.assertEqual(r.data['estado_operativo']['codigo'], 'UTIL')

    def test_no_localizado_no_pasa_a_obsoleto(self):
        self.c.post('/api/movimientos/', {'tipo': 'REUB', 'articulo': self.a['num'],
                                          'ubicacion': 'UBI-NOLOC', 'motivo': 'x'}, format='json')
        r = self.corregir(estado_operativo='OBS', motivo='x')
        self.assertIn('estado_operativo', r.data)

    def test_no_se_puede_poner_no_localizado_a_mano(self):
        self.assertIn('estado_operativo', self.corregir(estado_operativo='NOLOC', motivo='x').data)
        self.assertIn('estado_operativo', self.corregir(estado_operativo='AUTB', motivo='x').data)

    def test_ubicacion_y_resguardante_no_se_cambian_por_la_ficha(self):
        r = self.corregir(ubicacion='UBI-LAB1', resguardante=self.beto.num, marca='HP', motivo='x')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data['ubicacion']['codigo'], r.data['resguardante']['num']),
                         ('UBI-OFI', self.ana.num))

    def test_consulta_no_corrige(self):
        c = self.cliente(self.obs)
        self.assertEqual(c.patch(self.url, {'marca': 'HP', 'motivo': 'x'}, format='json').status_code, 403)

    def test_put_y_delete_no_existen(self):
        self.assertEqual(self.c.put(self.url, {}, format='json').status_code, 405)
        self.assertEqual(self.c.delete(self.url).status_code, 405)


class ExportacionTests(Base):
    def setUp(self):
        super().setUp()
        for i in range(12):
            self.alta(marbete_oficial='M%02d' % i, num_serie='S%02d' % i)
        self.alta(origen='COM', marbete_oficial=None, num_serie='SC', descripcion='=HYPERLINK("x")',
                  costo_adquisicion=None)

    def test_todos_devuelve_todo_sin_paginar_y_respeta_filtros(self):
        r = self.c.get('/api/articulos/todos/')
        self.assertEqual((r.status_code, len(r.data)), (200, 13))
        self.assertEqual(len(self.c.get('/api/articulos/').data['results']), 10)
        r = self.c.get('/api/articulos/todos/?origen=COM')
        self.assertEqual(len(r.data), 1)

    def test_excel_con_las_columnas_de_dec_018(self):
        from io import BytesIO
        from openpyxl import load_workbook
        r = self.c.get('/api/articulos/exportar/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        self.assertIn('inventario_', r['Content-Disposition'])
        hoja = load_workbook(BytesIO(r.content)).active
        filas = list(hoja.values)
        self.assertEqual(len(filas), 14)  # encabezado + 13 artículos
        self.assertEqual(filas[0][:3], ('Identificador', 'Categoría', 'Tipo de artículo'))
        self.assertEqual(filas[0][-1], 'Estado de registro')
        self.assertNotIn('Cuenta contable', filas[0])
        comodato = [f for f in filas[1:] if f[8] == 'Comodato'][0]
        self.assertTrue(comodato[0].startswith('02143'))
        self.assertEqual(comodato[7], "'=HYPERLINK(\"x\")")  # no se interpreta como fórmula
        self.assertIsNone(comodato[13])
        self.assertEqual(comodato[14], 'Pendiente')

    def test_excel_respeta_filtros(self):
        from io import BytesIO
        from openpyxl import load_workbook
        r = self.c.get('/api/articulos/exportar/?origen=COM')
        self.assertEqual(len(list(load_workbook(BytesIO(r.content)).active.values)), 2)

    def test_consulta_puede_exportar(self):
        c = self.cliente(self.obs)
        self.assertEqual(c.get('/api/articulos/exportar/').status_code, 200)
        self.assertEqual(c.get('/api/articulos/todos/').status_code, 200)


import shutil
import tempfile

from django.test import override_settings

from movimientos.models import Resguardo, ResguardoDetalle


class ResguardosTests(Base):
    def setUp(self):
        super().setUp()
        self.carpeta = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.carpeta, True)
        configuracion = override_settings(
            RESGUARDOS_DIR=self.carpeta, CONTADORA_NOMBRE='Rosa María Gómez Luna')
        configuracion.enable()
        self.addCleanup(configuracion.disable)
        self.a1 = self.alta(marbete_oficial='M1', num_serie='S1')
        self.a2 = self.alta(marbete_oficial='M2', num_serie='S2', marca=None)
        self.m1 = Movimiento.objects.get(articulo_id=self.a1['num']).folio
        self.m2 = Movimiento.objects.get(articulo_id=self.a2['num']).folio

    def emitir(self, movimientos='todos', resguardante=None):
        if movimientos == 'todos':
            movimientos = [self.m1, self.m2]
        return self.c.post('/api/resguardos/', {
            'resguardante': resguardante or self.ana.num,
            'movimientos': movimientos}, format='json')

    def test_un_resguardo_con_varios_articulos(self):
        r = self.emitir()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['folio'], 'RES-0001')
        self.assertEqual(r.data['numero_bienes'], 2)
        self.assertEqual({a['identificador'] for a in r.data['articulos']}, {'M1', 'M2'})
        self.assertEqual(r.data['usuario_emisor']['username'], 'admin')
        self.assertEqual(ResguardoDetalle.objects.count(), 2)
        self.assertTrue(Bitacora.objects.filter(tabla_afectada='resguardo', accion='INSERT').exists())

    def test_el_pdf_se_guarda_y_la_reimpresion_entrega_el_original(self):
        r = self.emitir()
        pdf1 = self.c.get(r.data['pdf'])
        self.assertEqual((pdf1.status_code, pdf1['Content-Type']), (200, 'application/pdf'))
        self.assertTrue(pdf1.content.startswith(b'%PDF'))
        import hashlib
        self.assertEqual(hashlib.sha256(pdf1.content).hexdigest(), r.data['hash_pdf'])
        pdf2 = self.c.get(r.data['pdf'])
        self.assertEqual(pdf1.content, pdf2.content)
        self.assertEqual(Resguardo.objects.count(), 1)  # reimprimir no crea folio nuevo
        self.assertEqual(Movimiento.objects.count(), 2)

    def test_el_pdf_trae_el_nombre_de_la_contadora_y_los_articulos(self):
        r = self.emitir()
        import re
        import zlib
        crudo = self.c.get(r.data['pdf']).content
        texto = b''
        for flujo in re.findall(rb'stream\r?\n(.*?)endstream', crudo, re.S):
            try:
                texto += zlib.decompress(__import__('base64').a85decode(flujo.strip(), adobe=True))
            except Exception:
                continue
        self.assertIn(b'RES-0001', texto)
        # reportlab escribe los acentos como secuencias octales (í = \\355, ó = \\363)
        self.assertIn(b'Rosa Mar\\355a G\\363mez Luna', texto)
        self.assertIn(b'Responsable de seguimiento', texto)
        self.assertIn(b'M1', texto)

    def test_una_asignacion_no_se_documenta_dos_veces(self):
        self.assertEqual(self.emitir([self.m1]).status_code, 201)
        r = self.emitir([self.m1, self.m2])
        self.assertEqual(r.status_code, 400)
        self.assertIn('ya está documentado', r.data['movimientos'])
        self.assertEqual(Resguardo.objects.count(), 1)

    def test_no_mezcla_resguardantes_ni_movimientos_que_no_lo_requieren(self):
        self.mov(tipo='REUB', articulo=self.a1['num'], resguardante=str(self.beto.num),
                 motivo='Cambio de persona')
        m_beto = Movimiento.objects.filter(articulo_id=self.a1['num']).first().folio
        r = self.emitir([m_beto, self.m2])  # m_beto es de Beto
        self.assertEqual(r.status_code, 400)
        self.assertIn('otra persona', r.data['movimientos'])
        self.mov(tipo='REPA', articulo=self.a2['num'], ubicacion='UBI-LAB1', motivo='Falla')
        reparacion = Movimiento.objects.filter(articulo_id=self.a2['num']).first().folio
        r = self.emitir([reparacion])
        self.assertIn('no requiere resguardo', r.data['movimientos'])

    def test_un_articulo_que_ya_no_esta_a_cargo_no_se_documenta(self):
        self.mov(tipo='REUB', articulo=self.a1['num'], resguardante=str(self.beto.num),
                 motivo='Cambio de persona')
        r = self.emitir([self.m1])  # la ALTA de Ana, pero ya lo tiene Beto
        self.assertEqual(r.status_code, 400)
        self.assertIn('ya no está a cargo', r.data['movimientos'])

    def test_pendientes_y_marca_en_el_movimiento(self):
        r = self.c.get('/api/resguardos/pendientes/?resguardante=%d' % self.ana.num)
        self.assertEqual(r.data['count'], 2)
        self.emitir([self.m1])
        r = self.c.get('/api/resguardos/pendientes/?resguardante=%d' % self.ana.num)
        self.assertEqual([m['folio'] for m in r.data['results']], [self.m2])
        m = self.c.get('/api/movimientos/%s/' % self.m1).data
        self.assertEqual(m['resguardo'], 'RES-0001')
        self.assertIsNone(self.c.get('/api/movimientos/%s/' % self.m2).data['resguardo'])

    def test_validaciones_de_entrada(self):
        self.assertEqual(self.emitir([]).status_code, 400)
        self.assertEqual(self.emitir(['XYZ']).status_code, 400)
        self.assertEqual(self.emitir(['MOV-0999']).status_code, 400)
        self.assertEqual(self.emitir([self.m1, self.m1]).status_code, 400)
        self.assertEqual(self.emitir(resguardante=99999).status_code, 400)
        self.assertEqual(Resguardo.objects.count(), 0)

    def test_sin_nombre_de_contadora_no_se_emite(self):
        with override_settings(CONTADORA_NOMBRE=''):
            r = self.emitir()
        self.assertEqual(r.status_code, 400)
        self.assertIn('CONTADORA_NOMBRE', r.data['detalle'])
        self.assertEqual(Resguardo.objects.count(), 0)

    def test_si_el_archivo_cambia_la_reimpresion_avisa(self):
        import os
        r = self.emitir()
        with open(os.path.join(self.carpeta, 'RES-0001.pdf'), 'ab') as f:
            f.write(b'alterado')
        self.assertEqual(self.c.get(r.data['pdf']).status_code, 409)

    def test_los_resguardos_no_se_editan_ni_se_borran(self):
        from api.inmutable import RegistroInmutable
        self.emitir()
        res = Resguardo.objects.get()
        with self.assertRaises(RegistroInmutable):
            res.delete()
        res.hash_pdf = 'x'
        with self.assertRaises(RegistroInmutable):
            res.save()

    def test_consulta_lee_pero_no_emite(self):
        r = self.emitir()
        c = self.cliente(self.obs)
        self.assertEqual(c.get('/api/resguardos/').status_code, 200)
        self.assertEqual(c.get(r.data['pdf']).status_code, 200)
        self.assertEqual(c.post('/api/resguardos/', {'resguardante': self.ana.num,
                                                      'movimientos': [self.m2]}, format='json').status_code, 403)

    def test_lista_y_filtros(self):
        self.emitir([self.m1])
        self.assertEqual(self.c.get('/api/resguardos/?resguardante=%d' % self.ana.num).data['count'], 1)
        self.assertEqual(self.c.get('/api/resguardos/?resguardante=%d' % self.beto.num).data['count'], 0)
        self.assertEqual(self.c.get('/api/resguardos/?articulo=%d' % self.a1['num']).data['count'], 1)
        self.assertEqual(self.c.get('/api/resguardos/?q=RES-0001').data['count'], 1)
