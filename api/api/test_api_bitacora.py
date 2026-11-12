"""Lectura de la bitácora (RF-21, PEND-024): solo Administrador, solo lectura."""
from datetime import datetime

from django.utils import timezone

from api.test_api import BaseAPI
from api.test_api_articulos_movimientos import Base
from auditoria.models import Bitacora


def hora(dia, h=12):
    return timezone.make_aware(datetime(2026, 11, dia, h, 0))


class BitacoraBase(BaseAPI):
    def setUp(self):
        super().setUp()
        self.c = self.cliente(self.admin)

    def registro(self, usuario=None, **datos):
        base = dict(usuario=usuario or self.admin, modulo='articulos', accion='INSERT',
                    tabla_afectada='articulo', registro_id='1', motivo=None,
                    valor_anterior=None, valor_nuevo='{"marca": "Dell"}', fecha_hora=hora(5))
        base.update(datos)
        return Bitacora.objects.create(**base)


class PermisosTests(BitacoraBase):
    def test_el_administrador_la_consulta(self):
        self.registro()
        r = self.c.get('/api/bitacora/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 1)

    def test_consulta_no_puede_verla(self):
        self.registro()
        c = self.cliente(self.obs)
        self.assertEqual(c.get('/api/bitacora/').status_code, 403)
        self.assertEqual(c.get('/api/bitacora/1/').status_code, 403)

    def test_sin_sesion_no_entra(self):
        from rest_framework.test import APIClient
        self.assertEqual(APIClient().get('/api/bitacora/').status_code, 401)

    def test_es_solo_lectura(self):
        b = self.registro()
        for metodo in ('post', 'put', 'patch', 'delete'):
            r = getattr(self.c, metodo)('/api/bitacora/%s/' % b.num if metodo != 'post' else '/api/bitacora/',
                                        {'motivo': 'x'}, format='json')
            self.assertEqual(r.status_code, 405, metodo)
        self.assertEqual(Bitacora.objects.count(), 1)


class FormaTests(BitacoraBase):
    def test_forma_de_cada_fila(self):
        self.registro(accion='UPDATE', motivo='Corrección de marca',
                      valor_anterior='{"marca": "Dell"}', valor_nuevo='{"marca": "HP"}')
        fila = self.c.get('/api/bitacora/').data['results'][0]
        self.assertEqual(set(fila), {
            'num', 'fecha_hora', 'usuario', 'modulo', 'accion', 'accion_nombre',
            'tabla_afectada', 'registro_id', 'motivo', 'valor_anterior', 'valor_nuevo'})
        self.assertEqual(fila['usuario']['username'], 'admin')
        self.assertEqual(fila['usuario']['num'], self.admin.pk)
        self.assertTrue(fila['usuario']['nombre'])
        self.assertEqual(fila['accion'], 'UPDATE')
        self.assertEqual(fila['accion_nombre'], 'Modificación')
        self.assertEqual(fila['valor_anterior'], {'marca': 'Dell'})
        self.assertEqual(fila['valor_nuevo'], {'marca': 'HP'})
        self.assertEqual(fila['motivo'], 'Corrección de marca')

    def test_valores_vacios_o_que_no_son_json(self):
        self.registro(valor_anterior=None, valor_nuevo='texto suelto')
        fila = self.c.get('/api/bitacora/').data['results'][0]
        self.assertIsNone(fila['valor_anterior'])
        self.assertEqual(fila['valor_nuevo'], 'texto suelto')

    def test_la_mas_reciente_primero(self):
        self.registro(registro_id='1', fecha_hora=hora(3))
        self.registro(registro_id='2', fecha_hora=hora(7))
        self.registro(registro_id='3', fecha_hora=hora(5))
        ids = [f['registro_id'] for f in self.c.get('/api/bitacora/').data['results']]
        self.assertEqual(ids, ['2', '3', '1'])

    def test_esta_paginada(self):
        for i in range(12):
            self.registro(registro_id=str(i))
        r = self.c.get('/api/bitacora/')
        self.assertEqual((r.data['count'], len(r.data['results'])), (12, 10))
        self.assertIsNotNone(r.data['next'])
        self.assertEqual(len(self.c.get('/api/bitacora/?page=2').data['results']), 2)

    def test_detalle_de_un_registro(self):
        b = self.registro(valor_nuevo='{"a": 1}')
        r = self.c.get('/api/bitacora/%s/' % b.num)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['valor_nuevo'], {'a': 1})
        self.assertEqual(self.c.get('/api/bitacora/9999/').status_code, 404)


class FiltrosTests(BitacoraBase):
    def setUp(self):
        super().setUp()
        self.registro(modulo='articulos', accion='INSERT', registro_id='10', fecha_hora=hora(2),
                      valor_nuevo='{"descripcion": "Laptop de oficina"}')
        self.registro(modulo='movimientos', accion='INSERT', tabla_afectada='movimiento',
                      registro_id='MOV-0001', fecha_hora=hora(4))
        self.registro(modulo='articulos', accion='UPDATE', registro_id='10', fecha_hora=hora(6),
                      motivo='Se corrigió el número de serie')
        self.registro(usuario=self.obs, modulo='usuarios', accion='DELETE',
                      tabla_afectada='usuario', registro_id='7', fecha_hora=hora(8))

    def ids(self, consulta):
        r = self.c.get('/api/bitacora/?' + consulta)
        self.assertEqual(r.status_code, 200, r.data)
        return sorted(f['registro_id'] for f in r.data['results'])

    def test_por_modulo(self):
        self.assertEqual(self.ids('modulo=articulos'), ['10', '10'])
        self.assertEqual(self.ids('modulo=MOVIMIENTOS'), ['MOV-0001'])

    def test_por_accion(self):
        self.assertEqual(self.ids('accion=update'), ['10'])
        self.assertEqual(self.ids('accion=DELETE'), ['7'])

    def test_por_usuario_numero_o_nombre(self):
        self.assertEqual(self.ids('usuario=%s' % self.obs.pk), ['7'])
        self.assertEqual(self.ids('usuario=OBS'), ['7'])
        self.assertEqual(len(self.ids('usuario=admin')), 3)

    def test_historial_de_un_registro(self):
        self.assertEqual(self.ids('tabla_afectada=articulo&registro_id=10'), ['10', '10'])
        self.assertEqual(self.ids('tabla_afectada=movimiento&registro_id=MOV-0001'), ['MOV-0001'])
        self.assertEqual(self.ids('tabla_afectada=articulo&registro_id=99'), [])

    def test_por_fechas_incluye_los_dos_dias(self):
        self.assertEqual(self.ids('fecha_desde=2026-11-04&fecha_hasta=2026-11-06'), ['10', 'MOV-0001'])
        self.assertEqual(self.ids('fecha_desde=2026-11-06'), ['10', '7'])
        self.assertEqual(self.ids('fecha_hasta=2026-11-02'), ['10'])

    def test_busqueda_libre(self):
        self.assertEqual(self.ids('q=serie'), ['10'])
        self.assertEqual(self.ids('q=laptop'), ['10'])
        self.assertEqual(self.ids('q=MOV-0001'), ['MOV-0001'])
        self.assertEqual(self.ids('q=obs'), ['7'])
        self.assertEqual(self.ids('q=serie+inexistente'), [])

    def test_filtros_combinados(self):
        self.assertEqual(self.ids('modulo=articulos&accion=UPDATE&usuario=admin'), ['10'])

    def test_filtros_invalidos(self):
        for consulta, campo in (('fecha_desde=ayer', 'fecha_desde'),
                                ('fecha_hasta=2026-13-01', 'fecha_hasta'),
                                ('accion=BORRAR', 'accion'),
                                ('fecha_desde=2026-11-09&fecha_hasta=2026-11-01', 'fecha_hasta')):
            r = self.c.get('/api/bitacora/?' + consulta)
            self.assertEqual(r.status_code, 400, consulta)
            self.assertIn(campo, r.data)


class IntegracionTests(Base):
    """Lo que el sistema escribe al operar es lo que la bitácora devuelve."""

    def test_un_alta_y_una_correccion_aparecen_en_la_bitacora(self):
        a = self.alta()
        r = self.c.patch('/api/articulos/%s/' % a['num'],
                         {'marca': 'HP', 'motivo': 'Marca mal capturada'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.c.get('/api/bitacora/?tabla_afectada=articulo&registro_id=%s' % a['num'])
        self.assertEqual([f['accion'] for f in r.data['results']], ['UPDATE', 'INSERT'])
        cambio = r.data['results'][0]
        self.assertEqual(cambio['motivo'], 'Marca mal capturada')
        self.assertEqual(cambio['valor_anterior'], {'marca': 'Dell'})
        self.assertEqual(cambio['valor_nuevo'], {'marca': 'HP'})
        self.assertEqual(cambio['usuario']['username'], 'admin')
