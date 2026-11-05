"""Carga masiva desde Excel (RF-24, RF-25, DEC-017)."""
import json
import time
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook, load_workbook

from api.test_api_articulos_movimientos import Base
from articulos import carga_masiva
from articulos.models import Articulo
from auditoria.models import Bitacora
from catalogos.models import Categoria, TipoArticulo
from movimientos.models import Movimiento

COLS = [c for c, *_ in carga_masiva.COLUMNAS]


def enc(hoja='Activos'):
    return [carga_masiva.encabezado_de(c, hoja) for c in COLS]


def libro(filas, encabezados=None, hoja=None):
    """Arma un .xlsx con una hoja por origen. Cada fila es un dict {clave: valor}
    con la clave opcional 'hoja' (Activos por omisión). Con `hoja=` todas las
    filas van a una sola hoja con ese nombre."""
    wb = Workbook()
    wb.remove(wb.active)
    grupos = {}
    for f in filas:
        grupos.setdefault(hoja or f.get('hoja', 'Activos'), []).append(f)
    nombres = [hoja] if hoja else [h for h in ('Activos', 'Comodatos', 'Enseres') if h in grupos]
    for nombre in nombres or ['Activos']:
        ws = wb.create_sheet(nombre)
        ws.append(encabezados or enc(nombre if nombre in ('Activos', 'Comodatos', 'Enseres') else 'Activos'))
        for f in grupos.get(nombre, []):
            ws.append([f.get(c) for c in COLS])
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


def fila(**datos):
    base = {'identificador': 'M-001', 'categoria': 'CAT-001', 'tipo_articulo': 'TIP-001',
            'marca': 'Dell', 'modelo': 'Latitude', 'num_serie': 'SN-001', 'color': 'Negro',
            'descripcion': 'Laptop de oficina', 'ubicacion': 'UBI-OFI', 'resguardante': 'E001',
            'fecha_adquisicion': '15/01/2024', 'costo_adquisicion': 12500}
    base.update(datos)
    return base


class CargaBase(Base):
    def subir(self, contenido, ruta='validar', nombre='inventario_2026.xlsx', **extra):
        datos = {'archivo': SimpleUploadedFile(nombre, contenido)}
        datos.update(extra)
        return self.c.post('/api/carga-masiva/%s/' % ruta, datos, format='multipart')

    def validar(self, filas, **kw):
        return self.subir(libro(filas), **kw)

    def confirmar(self, contenido, hash_=None, **kw):
        if hash_ is None:
            hash_ = self.subir(contenido).data['hash']
        return self.subir(contenido, 'confirmar', hash=hash_, **kw)


class PlantillaTests(CargaBase):
    def test_la_plantilla_trae_tres_hojas_y_listas_desplegables_de_los_catalogos(self):
        r = self.c.get('/api/carga-masiva/plantilla/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        wb = load_workbook(BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ['Instrucciones', 'Activos', 'Comodatos', 'Enseres', 'Listas', 'Tipos'])
        for nombre in ('Activos', 'Comodatos', 'Enseres'):
            self.assertEqual([c.value for c in wb[nombre][1]], enc(nombre))
            self.assertEqual(len(wb[nombre].data_validations.dataValidation), 6)
        self.assertEqual(wb['Activos']['A1'].value, 'Marbete')
        self.assertEqual(wb['Comodatos']['A1'].value, 'Folio')
        self.assertNotIn('Origen', enc())
        self.assertEqual(wb['Activos']['B1'].value, 'Categoría')
        self.assertEqual(wb['Activos']['C1'].value, 'Tipo de artículo')
        listas = {col[0].value: [c.value for c in col[1:] if c.value] for col in wb['Listas'].iter_cols()}
        self.assertEqual(listas['Categoría'], ['EQUIPO DE CÓMPUTO'])
        self.assertEqual(listas['Estado operativo'], ['Obsoleto', 'Útil'])
        self.assertEqual(listas['¿Donado?'], ['Sí', 'No'])
        self.assertIn('UBI-OFI · Oficina de Informática', listas['Ubicación'])
        self.assertIn('E001 · Admin Prueba', listas['Resguardante'])
        self.assertEqual(listas['Categoría (tipos)'], ['EQUIPO DE CÓMPUTO'])
        self.assertEqual(listas['Nombre del rango'], ['tip_1'])
        self.assertNotIn('estado de registro', ' '.join(enc()).lower())

    def test_el_desplegable_del_tipo_depende_de_la_categoria(self):
        Categoria.objects.create(codigo='CAT-002', nombre='MUEBLES')
        TipoArticulo.objects.create(codigo='TIP-002', nombre='Silla', categoria_id='CAT-002')
        TipoArticulo.objects.create(codigo='TIP-003', nombre='Oculto', categoria_id='CAT-002', activo=False)
        wb = load_workbook(BytesIO(self.c.get('/api/carga-masiva/plantilla/').content))
        tipos = {col[0].value: [c.value for c in col[1:] if c.value] for col in wb['Tipos'].iter_cols()}
        self.assertEqual(tipos, {'EQUIPO DE CÓMPUTO': ['Laptop'], 'MUEBLES': ['Silla']})
        formulas = {str(v.sqref)[0]: v.formula1 for v in wb['Activos'].data_validations.dataValidation}
        self.assertEqual(formulas['C'], '=INDIRECT(VLOOKUP($B2,Listas!$G$2:$H$3,2,FALSE))')
        self.assertEqual(set(wb.defined_names), {'tip_1', 'tip_2'})
        self.assertEqual(wb.defined_names['tip_2'].attr_text, 'Tipos!$B$2:$B$2')

    def test_la_plantilla_no_ofrece_catalogos_desactivados(self):
        TipoArticulo.objects.create(codigo='TIP-002', nombre='Oculto', categoria_id='CAT-001', activo=False)
        wb = load_workbook(BytesIO(self.c.get('/api/carga-masiva/plantilla/').content))
        self.assertEqual([c.value for c in wb['Tipos']['A'][1:] if c.value], ['Laptop'])

    def test_la_plantilla_oculta_las_hojas_auxiliares_y_va_vacia(self):
        wb = load_workbook(BytesIO(self.c.get('/api/carga-masiva/plantilla/').content))
        estados = {h.title: h.sheet_state for h in wb.worksheets}
        self.assertEqual(estados, {'Instrucciones': 'visible', 'Activos': 'visible', 'Comodatos': 'visible',
                                   'Enseres': 'visible', 'Listas': 'hidden', 'Tipos': 'hidden'})
        for nombre in ('Activos', 'Comodatos', 'Enseres'):
            self.assertIsNone(wb[nombre]['B2'].value)  # ni filas de ejemplo que se puedan cargar
        texto = ' '.join(str(c.value) for c in wb['Instrucciones']['A'] if c.value)
        self.assertIn('Pegado especial', texto)
        self.assertIn('EJEMPLO', texto)
        self.assertIn('S/S', texto)
        self.assertIn('5. SUBA EL ARCHIVO', texto)

    def test_la_plantilla_llenada_se_puede_cargar(self):
        wb = load_workbook(BytesIO(self.c.get('/api/carga-masiva/plantilla/').content))
        for hoja, valores in (('Activos', ['M-1', 'EQUIPO DE CÓMPUTO', 'Laptop', None, None, None, 'Negro',
                                           'Laptop', 'UBI-OFI · Oficina de Informática', 'E001 · Admin Prueba']),
                              ('Enseres', [None, 'EQUIPO DE CÓMPUTO', 'Laptop', None, None, None, 'Gris',
                                           'Otra', 'UBI-OFI · Oficina de Informática', 'E001 · Admin Prueba'])):
            for columna, valor in enumerate(valores, start=1):
                wb[hoja].cell(row=2, column=columna, value=valor)
        salida = BytesIO()
        wb.save(salida)
        r = self.subir(salida.getvalue())
        self.assertEqual((r.data['validas'], r.data['con_error']), (2, 0), r.data)

    def test_solo_el_administrador(self):
        c = self.cliente(self.obs)
        self.assertEqual(c.get('/api/carga-masiva/plantilla/').status_code, 403)
        r = c.post('/api/carga-masiva/validar/', {'archivo': SimpleUploadedFile('a.xlsx', libro([fila()]))},
                   format='multipart')
        self.assertEqual(r.status_code, 403)


class ValidarTests(CargaBase):
    def test_vista_previa_con_filas_validas_y_con_error_sin_guardar(self):
        r = self.validar([
            fila(),
            fila(identificador='M-002', num_serie='SN-002', ubicacion='UBI-NO-EXISTE'),
            fila(identificador=None, num_serie='SN-003'),                  # Activo sin marbete
            fila(identificador='M-004', num_serie='SN-004', color=None),   # falta color
        ])
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data['total'], r.data['validas'], r.data['con_error']), (4, 1, 3))
        self.assertEqual([f['estado'] for f in r.data['filas']], ['valida', 'error', 'error', 'error'])
        self.assertEqual([f['fila'] for f in r.data['filas']], [2, 3, 4, 5])
        self.assertIn('No se reconoce la ubicación', r.data['filas'][1]['errores']['ubicacion'])
        self.assertEqual(r.data['filas'][2]['errores'], {'identificador': 'Los activos llevan marbete oficial.'})
        self.assertEqual(r.data['filas'][3]['errores'], {'color': 'Este dato es obligatorio.'})
        self.assertEqual(r.data['columnas']['donado'], '¿Donado?')
        self.assertEqual(r.data['columnas']['identificador'], 'Marbete o folio')
        self.assertEqual(len(r.data['hash']), 64)
        self.assertEqual(Articulo.objects.count(), 0)  # validar no guarda nada
        self.assertNotIn('_alta', r.data['filas'][0])

    def test_catalogos_sin_distinguir_mayusculas_acentos_ni_espacios(self):
        r = self.validar([fila(categoria=' equipo de COMPUTO ', tipo_articulo='LAPTOP', ubicacion=' ubi-ofi',
                               resguardante='e001', estado_operativo='util')])
        self.assertEqual(r.data['validas'], 1, r.data['filas'])

    def test_acepta_las_etiquetas_de_la_lista_desplegable(self):
        r = self.validar([fila(tipo_articulo='Laptop',
                               ubicacion='UBI-OFI · Oficina de Informática',
                               resguardante='E001 · Admin Prueba')])
        self.assertEqual(r.data['validas'], 1, r.data['filas'])

    def test_categoria_y_tipo_son_columnas_separadas(self):
        r = self.validar([fila(categoria='EQUIPO DE CÓMPUTO', tipo_articulo='Laptop'),
                          fila(identificador='M-2', num_serie='S2', tipo_articulo='TIP-001')])
        self.assertEqual(r.data['validas'], 2, r.data['filas'])
        self.assertEqual(r.data['filas'][0]['datos']['categoria'], 'EQUIPO DE CÓMPUTO')
        self.assertEqual(r.data['filas'][0]['datos']['tipo_articulo'], 'Laptop')
        self.assertEqual(r.data['filas'][0]['datos']['origen'], 'Activo')
        self.assertEqual(Articulo.objects.count(), 0)

    def test_el_tipo_debe_pertenecer_a_la_categoria(self):
        Categoria.objects.create(codigo='CAT-002', nombre='MUEBLES')
        TipoArticulo.objects.create(codigo='TIP-002', nombre='Silla', categoria_id='CAT-002')
        r = self.validar([
            fila(categoria='MUEBLES', tipo_articulo='Laptop'),                       # existe, en otra categoría
            fila(identificador='M-2', num_serie='S2', categoria='MUEBLES', tipo_articulo='Silla'),
            fila(identificador='M-3', num_serie='S3', tipo_articulo='Inventado'),    # no existe
            fila(identificador='M-4', num_serie='S4', categoria='NO EXISTE'),
            fila(identificador='M-5', num_serie='S5', categoria=None, tipo_articulo=None),
        ])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['error', 'valida', 'error', 'error', 'error'])
        self.assertEqual(r.data['filas'][0]['errores'],
                         {'tipo_articulo': 'El tipo "Laptop" no pertenece a la categoría "MUEBLES".'})
        self.assertIn('No se reconoce el tipo de artículo "Inventado"', r.data['filas'][2]['errores']['tipo_articulo'])
        self.assertIn('No se reconoce la categoría', r.data['filas'][3]['errores']['categoria'])
        self.assertEqual(set(r.data['filas'][4]['errores']), {'categoria', 'tipo_articulo'})

    def test_el_mismo_nombre_de_tipo_en_dos_categorias(self):
        Categoria.objects.create(codigo='CAT-002', nombre='MUEBLES')
        TipoArticulo.objects.create(codigo='TIP-002', nombre='Laptop', categoria_id='CAT-002')
        r = self.validar([fila(tipo_articulo='Laptop'),
                          fila(identificador='M-2', num_serie='S2', categoria='MUEBLES', tipo_articulo='Laptop')])
        self.assertEqual(r.data['validas'], 2, r.data['filas'])

    def test_el_origen_sale_de_la_hoja(self):
        r = self.validar([fila(), fila(hoja='Comodatos', identificador='IC-1', num_serie='S2'),
                          fila(hoja='Enseres', identificador=None, num_serie='S3')])
        self.assertEqual([f['datos']['origen'] for f in r.data['filas']], ['Activo', 'Comodato', 'Enser'])
        self.assertEqual([f['hoja'] for f in r.data['filas']], ['Activos', 'Comodatos', 'Enseres'])
        self.assertEqual([f['fila'] for f in r.data['filas']], [2, 2, 2])
        self.assertEqual(r.data['hojas'], [
            {'hoja': 'Activos', 'origen': 'Activo', 'filas': 1, 'validas': 1, 'con_error': 0},
            {'hoja': 'Comodatos', 'origen': 'Comodato', 'filas': 1, 'validas': 1, 'con_error': 0},
            {'hoja': 'Enseres', 'origen': 'Enser', 'filas': 1, 'validas': 1, 'con_error': 0}])

    def test_activo_sin_marbete_pero_comodato_y_enser_sin_folio_si(self):
        r = self.validar([fila(identificador=None), fila(hoja='Comodatos', identificador=None, num_serie='S2')])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['error', 'valida'])

    def test_se_aceptan_hojas_en_singular_y_se_ignoran_las_demas(self):
        wb = Workbook()
        wb.remove(wb.active)
        for nombre in ('Licencias', 'Activo', 'Enser'):
            ws = wb.create_sheet(nombre)
            ws.append(enc('Activos' if nombre == 'Activo' else 'Enseres'))
        wb['Activo'].append([fila().get(c) for c in COLS])
        wb['Enser'].append([fila(identificador=None, num_serie='S9').get(c) for c in COLS])
        wb['Licencias'].append(['lo que sea'])
        salida = BytesIO()
        wb.save(salida)
        r = self.subir(salida.getvalue())
        self.assertEqual(r.data['validas'], 2, r.data)
        self.assertEqual(r.data['hojas_ignoradas'], ['Licencias'])

    def test_falta_una_columna_en_una_hoja_dice_cual(self):
        wb = Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet('Comodatos')
        ws.append(enc('Comodatos')[:-1])
        salida = BytesIO()
        wb.save(salida)
        r = self.subir(salida.getvalue())
        self.assertIn('hoja "Comodatos"', r.data['archivo'])
        self.assertIn('¿Donado?', r.data['archivo'])

    def test_resguardante_por_numero_de_empleado_no_por_nombre(self):
        r = self.validar([fila(resguardante='Admin Prueba')])
        self.assertIn('No se reconoce al resguardante', r.data['filas'][0]['errores']['resguardante'])

    def test_fechas_y_costos_en_varios_formatos(self):
        r = self.validar([
            fila(fecha_adquisicion='2024-03-01', costo_adquisicion='$12,500.50'),
            fila(identificador='M-002', num_serie='S2', fecha_adquisicion='31/12/2023', costo_adquisicion='9800'),
            fila(identificador='M-003', num_serie='S3', fecha_adquisicion='no es fecha', costo_adquisicion='mucho'),
        ])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['valida', 'valida', 'error'])
        self.assertEqual(set(r.data['filas'][2]['errores']), {'fecha_adquisicion', 'costo_adquisicion'})

    def test_fecha_futura_y_costo_negativo_con_las_reglas_del_alta(self):
        r = self.validar([fila(fecha_adquisicion='01/01/2099', identificador='M-002', num_serie='S2'),
                          fila(costo_adquisicion=-5, identificador='M-003', num_serie='S3')])
        self.assertIn('fecha_adquisicion', r.data['filas'][0]['errores'])
        self.assertIn('costo_adquisicion', r.data['filas'][1]['errores'])

    def test_duplicados_dentro_del_archivo(self):
        r = self.validar([fila(), fila(num_serie='OTRA'), fila(identificador='M-009')])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['valida', 'error', 'error'])
        self.assertEqual(r.data['filas'][1]['errores']['identificador'], 'Repetido: ya aparece en la fila 2 de la hoja Activos.')
        self.assertEqual(r.data['filas'][2]['errores']['num_serie'], 'Repetido: ya aparece en la fila 2 de la hoja Activos.')

    def test_duplicados_contra_la_base(self):
        self.alta(marbete_oficial='M-001', num_serie='SN-001')
        r = self.validar([fila(), fila(identificador='M-002', num_serie='SN-001'),
                          fila(identificador='m-001', num_serie='SN-777')])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['error'] * 3)
        self.assertIn('Duplicado', r.data['filas'][0]['errores']['identificador'])
        self.assertIn('Duplicado', r.data['filas'][1]['errores']['num_serie'])
        self.assertIn('Duplicado', r.data['filas'][2]['errores']['identificador'])  # sin distinguir mayúsculas

    def test_comodato_respeta_su_folio_y_sin_folio_el_sistema_lo_asigna(self):
        r = self.validar([
            fila(hoja='Comodatos', identificador='IC-2019-044', num_serie='S1'),
            fila(hoja='Enseres', identificador=None, num_serie='S2'),
        ])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['valida', 'valida'], r.data['filas'])

    def test_s_s_na_y_guion_se_toman_como_vacio_con_aviso_sin_bloquear(self):
        r = self.validar([fila(marca='S/S', modelo='n/a', num_serie='-')])
        f = r.data['filas'][0]
        self.assertEqual(f['estado'], 'valida', f)
        self.assertEqual(set(f['avisos']), {'marca', 'modelo', 'num_serie'})
        self.assertEqual(f['avisos']['marca'], '"S/S" se tomó como vacío y no se guardó.')
        self.assertEqual((f['datos']['marca'], f['datos']['modelo'], f['datos']['num_serie']), (None,) * 3)
        self.assertEqual(r.data['con_aviso'], 1)
        # no es un número de serie: dos filas con "S/S" no chocan entre sí
        r = self.validar([fila(num_serie='S/S'), fila(identificador='M-2', num_serie='S/S')])
        self.assertEqual(r.data['validas'], 2, r.data['filas'])
        self.confirmar(libro([fila(marca='S/M', num_serie='s/s')]))
        a = Articulo.objects.get()
        self.assertEqual((a.marca, a.modelo or None, a.num_serie), (None, 'Latitude', None))

    def test_la_vista_previa_cuenta_los_folios_nuevos(self):
        r = self.validar([fila(), fila(hoja='Comodatos', identificador=None, num_serie='S2'),
                          fila(hoja='Enseres', identificador=None, num_serie='S3'),
                          fila(hoja='Enseres', identificador='ENS-9', num_serie='S4'),
                          fila(hoja='Enseres', identificador=None, num_serie='S5', color=None)])  # con error
        self.assertEqual(r.data['folios_nuevos'], 2)
        self.assertEqual([f['folio_nuevo'] for f in r.data['filas']], [False, True, True, False, False])

    def test_el_resultado_lista_los_folios_asignados(self):
        r = self.confirmar(libro([fila(), fila(hoja='Comodatos', identificador=None, num_serie='S2'),
                                  fila(hoja='Enseres', identificador='IC-77', num_serie='S3')]))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['folios_nuevos'], 1)
        self.assertEqual([a['folio_nuevo'] for a in r.data['articulos']], [False, True, False])
        nuevo = r.data['articulos'][1]['identificador']
        self.assertRegex(nuevo, r'^02143\d{4}-\d{3}$')
        self.assertEqual(json.loads(Bitacora.objects.get(modulo='carga_masiva').valor_nuevo)['folios_asignados'], 1)

    def test_aviso_de_posible_duplicado_sin_folio_ni_serie(self):
        sin = dict(hoja='Enseres', identificador=None, num_serie=None, descripcion='Silla de oficina',
                   marca='Nova', modelo='X1', color='Negro')
        c = self.confirmar(libro([fila(**sin)]))
        self.assertEqual(c.status_code, 201, c.data)
        r = self.validar([
            fila(**sin),                                      # igual a uno que ya está en el sistema
            fila(**dict(sin, color='Rojo')),                 # distinto color: sin aviso
            fila(**dict(sin, descripcion='Mesa', hoja='Comodatos')),
            fila(**dict(sin, descripcion='Mesa', hoja='Comodatos')),   # igual a la fila anterior del archivo
            fila(identificador='M-9', num_serie='SN-9'),     # con marbete y serie: no se revisa
        ])
        # las filas salen en el orden de las hojas: Activos, Comodatos, Enseres
        filas = r.data['filas']
        self.assertEqual([f['estado'] for f in filas], ['valida'] * 5)
        self.assertEqual(filas[0]['avisos'], {})                                  # con marbete y serie
        self.assertEqual(filas[1]['avisos'], {})                                  # primera Mesa
        self.assertIn('fila 2 de la hoja Comodatos', filas[2]['avisos']['posible_duplicado'])
        self.assertIn('se parece al artículo', filas[3]['avisos']['posible_duplicado'])  # ya en el sistema
        self.assertEqual(filas[4]['avisos'], {})                                  # otro color
        # es un aviso: no bloquea la carga
        r = self.confirmar(libro([fila(**dict(sin, marca='NOVA'))]))   # otro archivo, mismo parecido
        self.assertEqual((r.status_code, r.data['cargados']), (201, 1))

    def test_donado_y_sin_ubicar(self):
        r = self.validar([
            fila(donado='Sí', costo_adquisicion=None, fecha_adquisicion=None),
            fila(identificador='M-002', num_serie='S2', ubicacion='UBI-NOLOC'),
        ])
        self.assertEqual(r.data['validas'], 2, r.data['filas'])

    def test_donado_con_costo_o_sin_costo_se_acepta_y_sigue_donado(self):
        """DEC-021: el costo de un Donado es opcional; vacío queda NULL."""
        self.confirmar(libro([fila(donado='Sí', costo_adquisicion=3000),
                              fila(identificador='M-2', num_serie='S2', donado='Sí', costo_adquisicion=None)]))
        a, b = Articulo.objects.order_by('num')
        self.assertEqual((str(a.costo_adquisicion), a.estado_registro_id), ('3000.00', 'DON'))
        self.assertEqual((b.costo_adquisicion, b.estado_registro_id), (None, 'DON'))

    def test_estado_no_localizado_a_mano_con_otra_ubicacion_es_error(self):
        r = self.validar([fila(estado_operativo='No localizado')])
        self.assertIn('estado_operativo', r.data['filas'][0]['errores'])

    def test_si_no_invalido(self):
        r = self.validar([fila(donado='quizá')])
        self.assertEqual(r.data['filas'][0]['errores']['donado'], 'Escriba Sí o No.')

    def test_filas_vacias_se_ignoran(self):
        r = self.validar([fila(), {}, {'marca': '   '}])
        self.assertEqual(r.data['total'], 1)

    def test_el_hash_cambia_si_cambia_el_archivo(self):
        a = self.validar([fila()]).data['hash']
        b = self.validar([fila(marca='HP')]).data['hash']
        self.assertNotEqual(a, b)

    def test_archivos_invalidos(self):
        self.assertIn('no es un Excel', self.subir(b'hola esto no es excel').data['archivo'])
        self.assertIn('Adjunte el archivo', self.c.post('/api/carga-masiva/validar/', {}, format='multipart').data['archivo'])
        faltan = self.subir(libro([fila()], encabezados=enc()[:-3]))
        self.assertIn('Faltan columnas', faltan.data['archivo'])
        self.assertIn('Costo de adquisición', faltan.data['archivo'])
        sin_hoja = self.subir(libro([fila()], hoja='Otra'))
        self.assertIn('ninguna de las hojas "Activos", "Comodatos" o "Enseres"', sin_hoja.data['archivo'])
        self.assertIn('no tiene filas', self.subir(libro([])).data['archivo'])

    def test_limite_de_filas(self):
        antes = carga_masiva.MAX_FILAS
        carga_masiva.MAX_FILAS = 3
        try:
            r = self.validar([fila(identificador='M%d' % i, num_serie='S%d' % i) for i in range(4)])
        finally:
            carga_masiva.MAX_FILAS = antes
        self.assertIn('más de 3 filas', r.data['archivo'])

    def test_encabezados_en_otro_orden_o_con_asterisco(self):
        inverso = list(reversed(carga_masiva.COLUMNAS))
        wb = Workbook()
        ws = wb.active
        ws.title = 'Activos'
        ws.append([carga_masiva.encabezado_de(c, 'Activos') + (' *' if o else '') for c, _, _, o in inverso])
        f = fila()
        ws.append([f.get(c) for c, *_ in inverso])
        salida = BytesIO()
        wb.save(salida)
        r = self.subir(salida.getvalue())
        self.assertEqual(r.data['validas'], 1, r.data)

    def test_mismo_marbete_o_folio_en_dos_hojas_se_detecta(self):
        r = self.validar([fila(identificador='X-1'), fila(hoja='Comodatos', identificador='x-1', num_serie='S2')])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['valida', 'error'])
        self.assertEqual(r.data['filas'][1]['errores']['identificador'],
                         'Repetido: ya aparece en la fila 2 de la hoja Activos.')

    def test_maximo_de_folios_del_mes(self):
        from django.utils import timezone
        from catalogos.models import ContadorFolio
        periodo = timezone.localtime(timezone.now()).strftime('%m%y')
        ContadorFolio.objects.create(clave='FI-%s' % periodo, ultimo=998)
        r = self.validar([fila(hoja='Comodatos', identificador=None, num_serie='S%d' % i) for i in range(3)])
        self.assertEqual([f['estado'] for f in r.data['filas']], ['valida', 'error', 'error'])  # solo caben 1
        self.assertIn('máximo de 999 folios', r.data['filas'][1]['errores']['identificador'])
        # con folio propio sí entra aunque el mes esté lleno
        r = self.validar([fila(hoja='Comodatos', identificador='IC-1', num_serie='S1')])
        self.assertEqual(r.data['validas'], 1)


class ConfirmarTests(CargaBase):
    def test_solo_entran_las_filas_validas_con_alta_sin_resguardo(self):
        contenido = libro([
            fila(),
            fila(identificador='M-002', num_serie='SN-002', ubicacion='UBI-XX'),
            fila(identificador='M-003', num_serie='SN-003', donado='Sí', costo_adquisicion=None),
            fila(hoja='Comodatos', identificador='IC-2019-044', num_serie='SN-004'),
            fila(hoja='Enseres', identificador=None, num_serie='SN-005', fecha_adquisicion=None),
        ])
        r = self.confirmar(contenido)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual((r.data['total'], r.data['cargados'], r.data['rechazados']), (5, 4, 1))
        self.assertEqual([(a['hoja'], a['fila']) for a in r.data['articulos']],
                         [('Activos', 2), ('Activos', 4), ('Comodatos', 2), ('Enseres', 2)])
        self.assertEqual((r.data['filas_rechazadas'][0]['hoja'], r.data['filas_rechazadas'][0]['fila']),
                         ('Activos', 3))
        self.assertEqual([(h['hoja'], h['validas'], h['con_error']) for h in r.data['hojas']],
                         [('Activos', 2, 1), ('Comodatos', 1, 0), ('Enseres', 1, 0)])
        self.assertEqual(Articulo.objects.count(), 4)
        reg = {a.identificador: a.estado_registro_id for a in Articulo.objects.all()}
        self.assertEqual(reg['M-001'], 'REG')
        self.assertEqual(reg['M-003'], 'DON')
        self.assertEqual(reg['IC-2019-044'], 'REG')
        generado = [i for i in reg if i.startswith('02143')]
        self.assertEqual(len(generado), 1)
        self.assertEqual(reg[generado[0]], 'PEND')  # sin fecha
        for m in Movimiento.objects.all():
            self.assertEqual(m.tipo_movimiento_id, 'ALTA')
            self.assertFalse(m.requiere_resguardo)
            self.assertTrue(m.motivo.startswith('Carga masiva (inventario_2026.xlsx, '), m.motivo)
        self.assertEqual(Movimiento.objects.count(), 4)

    def test_bitacora_de_cada_articulo_y_del_lote(self):
        contenido = libro([fila(), fila(identificador='M-002', num_serie='S2', color=None)])
        r = self.confirmar(contenido)
        lote = Bitacora.objects.get(modulo='carga_masiva')
        self.assertEqual(lote.usuario, self.admin)
        datos = json.loads(lote.valor_nuevo)
        self.assertEqual((datos['cargados'], datos['rechazados'], datos['filas_en_archivo']), (1, 1, 2))
        self.assertEqual(datos['por_hoja'], {'Activos': 1})
        self.assertEqual(datos['archivo'], 'inventario_2026.xlsx')
        self.assertEqual(datos['hash'], r.data['hash'])
        self.assertTrue(Bitacora.objects.filter(tabla_afectada='articulo', accion='INSERT', modulo='articulos').exists())
        self.assertTrue(Bitacora.objects.filter(tabla_afectada='movimiento', accion='INSERT').exists())

    def test_ubicacion_sin_ubicar_queda_no_localizado(self):
        self.confirmar(libro([fila(ubicacion='UBI-NOLOC')]))
        self.assertEqual(Articulo.objects.get().estado_operativo_id, 'NOLOC')

    def test_obsoleto_desde_la_carga(self):
        self.confirmar(libro([fila(estado_operativo='Obsoleto')]))
        self.assertEqual(Articulo.objects.get().estado_operativo_id, 'OBS')

    def test_el_archivo_debe_ser_el_que_se_reviso(self):
        contenido = libro([fila()])
        hash_malo = self.subir(libro([fila(marca='Otra')])).data['hash']
        r = self.confirmar(contenido, hash_=hash_malo)
        self.assertEqual(r.status_code, 400)
        self.assertIn('no es el mismo que se revisó', r.data['archivo'])
        self.assertEqual(r.data['archivo'].count('mismo'), 1)
        self.assertEqual(Articulo.objects.count(), 0)
        self.assertEqual(self.subir(contenido, 'confirmar').status_code, 400)  # sin hash

    def test_confirmar_dos_veces_no_duplica(self):
        contenido = libro([fila()])
        h = self.subir(contenido).data['hash']
        self.assertEqual(self.confirmar(contenido, hash_=h).status_code, 201)
        r = self.confirmar(contenido, hash_=h)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Este mismo archivo ya se cargó el', r.data['archivo'])
        self.assertIn('usuario admin', r.data['archivo'])
        self.assertEqual(Articulo.objects.count(), 1)

    def test_el_mismo_archivo_no_duplica_filas_sin_marbete_folio_ni_serie(self):
        """Un enser sin folio ni serie no se reconoce como duplicado por sus datos:
        lo detiene la huella del archivo."""
        contenido = libro([fila(hoja='Enseres', identificador=None, num_serie=None)])
        self.assertEqual(self.confirmar(contenido).status_code, 201)
        previa = self.subir(contenido)
        self.assertEqual(previa.data['validas'], 1)  # por sus datos, la fila pasaría
        self.assertEqual(previa.data['ya_cargado']['usuario'], 'admin')
        self.assertEqual(self.subir(contenido, 'confirmar', hash=previa.data['hash']).status_code, 400)
        self.assertEqual(Articulo.objects.count(), 1)
        # un archivo distinto sí se puede cargar
        otro = libro([fila(hoja='Enseres', identificador=None, num_serie=None, descripcion='Otra silla')])
        self.assertEqual(self.confirmar(otro).status_code, 201)
        self.assertEqual(Articulo.objects.count(), 2)

    def test_vista_previa_sin_carga_previa(self):
        self.assertIsNone(self.subir(libro([fila()])).data['ya_cargado'])

    def test_sin_filas_validas_no_se_guarda_nada(self):
        r = self.confirmar(libro([fila(color=None)]))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Bitacora.objects.filter(modulo='carga_masiva').count(), 0)

    def test_todo_o_nada_si_falla_una_fila_al_guardar(self):
        from unittest import mock
        from rest_framework.exceptions import ValidationError
        contenido = libro([fila(), fila(identificador='M-002', num_serie='S2'),
                           fila(identificador='M-003', num_serie='S3')])
        h = self.subir(contenido).data['hash']
        real = carga_masiva.alta_articulo
        llamadas = []

        def falla_en_la_tercera(*a, **kw):
            llamadas.append(1)
            if len(llamadas) == 3:
                raise ValidationError({'detalle': 'Falla simulada.'})
            return real(*a, **kw)
        with mock.patch.object(carga_masiva, 'alta_articulo', falla_en_la_tercera):
            r = self.confirmar(contenido, hash_=h)
        self.assertEqual(r.status_code, 400)
        self.assertIn('fila 4 de Activos', r.data['archivo'])
        self.assertIn('No se guardó nada', r.data['archivo'])
        self.assertEqual((Articulo.objects.count(), Movimiento.objects.count()), (0, 0))
        self.assertEqual(Bitacora.objects.count(), 0)

    def test_los_folios_generados_no_chocan_con_los_historicos(self):
        from django.utils import timezone
        periodo = timezone.localtime(timezone.now()).strftime('%m%y')
        historico = '02143%s-001' % periodo
        self.confirmar(libro([
            fila(hoja='Comodatos', identificador=historico, num_serie='S1'),
            fila(hoja='Comodatos', identificador=None, num_serie='S2'),
        ]))
        folios = sorted(Articulo.objects.values_list('folio_interno', flat=True))
        self.assertEqual(folios, [historico, '02143%s-002' % periodo])

    def test_consulta_no_puede_cargar(self):
        c = self.cliente(self.obs)
        r = c.post('/api/carga-masiva/confirmar/', {'archivo': SimpleUploadedFile('a.xlsx', libro([fila()])),
                                                    'hash': 'x'}, format='multipart')
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Articulo.objects.count(), 0)


class VolumenTests(CargaBase):
    def test_carga_de_500_filas(self):
        for i in range(2):
            Categoria.objects.get_or_create(codigo='CAT-00%d' % (i + 5), nombre='Otra %d' % i)
        filas = []
        for i in range(500):
            if i % 3 == 0:
                filas.append(fila(identificador='M-%04d' % i, num_serie='SN-%04d' % i))
            elif i % 3 == 1:
                filas.append(fila(hoja='Comodatos', identificador=None, num_serie='SN-%04d' % i))
            else:
                filas.append(fila(hoja='Enseres', identificador='ENS-%04d' % i, num_serie=None, costo_adquisicion=None))
        contenido = libro(filas)
        t0 = time.time()
        previa = self.subir(contenido)
        t_validar = time.time() - t0
        self.assertEqual((previa.data['validas'], previa.data['con_error']), (500, 0))
        t0 = time.time()
        r = self.subir(contenido, 'confirmar', hash=previa.data['hash'])
        t_cargar = time.time() - t0
        self.assertEqual((r.status_code, r.data['cargados']), (201, 500))
        self.assertEqual(Articulo.objects.count(), 500)
        self.assertEqual(Movimiento.objects.count(), 500)
        folios = list(Articulo.objects.exclude(folio_interno=None).values_list('folio_interno', flat=True))
        self.assertEqual(len(folios), len(set(folios)))
        print('\n[volumen] 500 filas: vista previa %.1fs, carga %.1fs' % (t_validar, t_cargar))
