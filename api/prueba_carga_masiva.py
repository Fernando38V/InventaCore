"""Prueba manual de la carga masiva contra la API en marcha (no es parte de las pruebas automáticas).

Uso (con el venv activo y la API encendida en el 8000), desde la carpeta api:

    python prueba_carga_masiva.py              # prepara datos, baja la plantilla, la llena y muestra la VISTA PREVIA
    python prueba_carga_masiva.py --confirmar  # además confirma: guarda las filas válidas

Qué hace:
  1. Inicia sesión (admin / admin por defecto).
  2. Si faltan, crea datos de apoyo de PRUEBA: dos categorías con sus tipos, dos ubicaciones y dos empleados.
  3. Baja la plantilla oficial (GET /carga-masiva/plantilla/): un libro con las hojas Activos, Comodatos
     y Enseres, y verifica sus listas desplegables (Categoría y Tipo de artículo van en columnas separadas).
  4. La llena con filas en las tres hojas: unas válidas y otras con errores a propósito.
  5. La sube a /carga-masiva/validar/ y muestra qué filas pasan y cuáles no, con su motivo.
  6. Con --confirmar, la sube a /carga-masiva/confirmar/ y muestra los artículos que quedaron.

Deja el archivo llenado en prueba_inventario.xlsx para abrirlo en Excel.
"""
import argparse
import json
import sys
import uuid
from io import BytesIO
from urllib import error, parse, request

from openpyxl import load_workbook

ENCABEZADOS = ['{id}', 'Categoría', 'Tipo de artículo', 'Marca', 'Modelo', 'Número de serie',
               'Color', 'Descripción', 'Ubicación', 'Resguardante', 'Estado operativo',
               'Fecha de adquisición', 'Costo de adquisición', '¿Donado?']
HOJAS = {'Activos': 'Marbete', 'Comodatos': 'Folio', 'Enseres': 'Folio'}


class Api:
    def __init__(self, base):
        self.base = base.rstrip('/')
        self.token = None

    def llamar(self, metodo, ruta, datos=None, archivo=None, campos=None, binario=False):
        url = self.base + '/' + ruta.lstrip('/')
        cabeceras = {'Accept': 'application/json'}
        if self.token:
            cabeceras['Authorization'] = 'Token ' + self.token
        cuerpo = None
        if archivo is not None:
            limite = uuid.uuid4().hex
            partes = []
            for nombre, valor in (campos or {}).items():
                partes.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                               % (limite, nombre, valor)).encode('utf-8'))
            partes.append(('--%s\r\nContent-Disposition: form-data; name="archivo"; filename="%s"\r\n'
                           'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                           '\r\n\r\n' % (limite, archivo[0])).encode('utf-8'))
            partes.append(archivo[1])
            partes.append(('\r\n--%s--\r\n' % limite).encode('utf-8'))
            cuerpo = b''.join(partes)
            cabeceras['Content-Type'] = 'multipart/form-data; boundary=' + limite
        elif datos is not None:
            cuerpo = json.dumps(datos).encode('utf-8')
            cabeceras['Content-Type'] = 'application/json'
        peticion = request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
        try:
            with request.urlopen(peticion, timeout=120) as r:
                crudo = r.read()
                return crudo if binario else (json.loads(crudo.decode('utf-8')) if crudo else None)
        except error.HTTPError as e:
            detalle = e.read().decode('utf-8', 'replace')
            raise SystemExit('Error %s en %s %s: %s' % (e.code, metodo, ruta, detalle))
        except error.URLError as e:
            raise SystemExit('No se pudo conectar con la API (%s). ¿Está encendida en el 8000?' % e.reason)

    def todos(self, ruta, **filtros):
        resultados, pagina = [], 1
        while True:
            consulta = parse.urlencode(dict(filtros, page=pagina))
            r = self.llamar('GET', '%s?%s' % (ruta, consulta))
            resultados += r['results']
            if not r['next']:
                return resultados
            pagina += 1


def preparar_apoyo(api):
    """Crea, solo si faltan, los catálogos mínimos para la prueba. Devuelve la lista
    de etiquetas que se van a usar en la plantilla."""
    categorias = {c['nombre']: c for c in api.todos('categorias/')}
    for nombre in ('Equipo de cómputo (prueba)', 'Mobiliario (prueba)'):
        if nombre not in categorias:
            categorias[nombre] = api.llamar('POST', 'categorias/', {'nombre': nombre})
            print('  + categoría "%s"' % nombre)
    tipos = {(t['categoria_nombre'], t['nombre']) for t in api.todos('tipos-articulo/')}
    for categoria, nombre in (('Equipo de cómputo (prueba)', 'Laptop (prueba)'),
                              ('Equipo de cómputo (prueba)', 'Monitor (prueba)'),
                              ('Mobiliario (prueba)', 'Silla (prueba)')):
        if (categoria, nombre) not in tipos:
            api.llamar('POST', 'tipos-articulo/', {'nombre': nombre, 'categoria': categorias[categoria]['codigo']})
            print('  + tipo "%s" en "%s"' % (nombre, categoria))
    ubicaciones = [u for u in api.todos('ubicaciones/') if u['codigo'] != 'UBI-NOLOC']
    if len(ubicaciones) < 2:
        for nombre in ('Oficina de Informática (prueba)', 'Laboratorio 1 (prueba)')[len(ubicaciones):]:
            api.llamar('POST', 'ubicaciones/', {'nombre': nombre})
            print('  + ubicación "%s"' % nombre)
    personal = [p for p in api.todos('personal/') if p['activo']]
    if len(personal) < 2:
        departamentos = api.todos('departamentos/')
        if not departamentos:
            api.llamar('POST', 'departamentos/', {'nombre': 'Informática (prueba)'})
            departamentos = api.todos('departamentos/')
        for numero, nombre in (('PRB-001', 'Ana'), ('PRB-002', 'Beto')):
            if numero not in [p['numero_empleado'] for p in personal]:
                api.llamar('POST', 'personal/', {
                    'numero_empleado': numero, 'nombre_pila': nombre, 'primer_apellido': 'Prueba',
                    'puesto': 'Docente', 'departamento': departamentos[0]['codigo']})
                print('  + empleado %s %s Prueba' % (numero, nombre))


def listas_de(contenido):
    libro = load_workbook(BytesIO(contenido))
    listas = {c[0].value: [x.value for x in c[1:] if x.value] for c in libro['Listas'].iter_cols()}
    tipos = {c[0].value: [x.value for x in c[1:] if x.value] for c in libro['Tipos'].iter_cols()}
    return libro, listas, tipos


def llenar(libro, listas, tipos):
    comp = next(c for c in tipos if c.startswith('Equipo de cómputo (prueba)'))
    mob = next(c for c in tipos if c.startswith('Mobiliario (prueba)'))
    lap, mon = [t for t in tipos[comp] if 'prueba' in t][:2]
    silla = [t for t in tipos[mob] if 'prueba' in t][0]
    ubi1, ubi2 = (listas['Ubicación'] * 2)[:2]
    ubi_no = [u for u in listas['Ubicación'] if u.startswith('UBI-NOLOC')]
    per1, per2 = (listas['Resguardante'] * 2)[:2]
    # columnas: id, categoría, tipo, marca, modelo, serie, color, descripción, ubicación,
    #           resguardante, estado, fecha, costo, donado
    filas = {
        'Activos': [
            # ----- válidas -----
            ['PRB-ACT-001', comp, lap, 'Dell', 'Latitude 5420', 'PRB-SN-001', 'Negro',
             'Laptop de oficina', ubi1, per1, 'Útil', '15/01/2024', 12500, 'No'],
            ['PRB-ACT-002', comp, mon, 'LG', '24MK', 'PRB-SN-002', 'Negro',
             'Monitor 24 pulgadas', ubi2, per2, None, '02/03/2023', 3200.5, 'No'],
            ['PRB-ACT-003', comp, lap, None, None, None, 'Plata',
             'Laptop donada (sin costo)', ubi1, per1, None, None, None, 'Sí'],
            # ----- con error a propósito -----
            [None, comp, lap, 'Acer', None, 'PRB-SN-006', 'Azul',
             'ERROR: activo sin marbete', ubi1, per1, None, None, None, 'No'],
            ['PRB-ACT-007', comp, lap, 'Lenovo', None, 'PRB-SN-007', 'Rojo',
             'ERROR: ubicación que no existe', 'Cuarto fantasma', per1, None, None, None, 'No'],
            ['PRB-ACT-001', comp, mon, 'Dell', None, 'PRB-SN-008', 'Negro',
             'ERROR: marbete repetido en el archivo', ubi1, per1, None, '01/01/2021', 900, 'No'],
            ['PRB-ACT-010', mob, lap, None, None, None, 'Negro',
             'ERROR: el tipo Laptop no es de la categoría Mobiliario', ubi1, per1, None, None, None, 'No'],
        ],
        'Comodatos': [
            ['COM-HIST-77', comp, lap, 'HP', None, None, 'Gris',
             'Laptop en comodato con folio propio', ubi1, per2, None, None, None, 'No'],
            [None, mob, silla, None, None, None, 'Negro',
             'Silla en comodato: el sistema le asigna folio', ubi2, per1, None, None, None, 'No'],
        ],
        'Enseres': [
            [None, comp, mon, None, None, None, 'Blanco',
             'Monitor enser: el sistema le asigna folio', ubi2, per1, None, '10/10/2022', 1500, 'No'],
        ],
    }
    if ubi_no:
        filas['Activos'].append(['PRB-ACT-009', comp, lap, 'Toshiba', None, None, 'Negro',
                                 'Equipo no localizado en revisión', ubi_no[0], per1, None, None, None, 'No'])
    for nombre, lista in filas.items():
        hoja = libro[nombre]
        for i, fila in enumerate(lista, start=2):
            for j, valor in enumerate(fila, start=1):
                hoja.cell(row=i, column=j, value=valor)
    return sum(len(v) for v in filas.values())


def mostrar_vista_previa(r):
    print('\nVISTA PREVIA: %d filas, %d válidas, %d con error' % (r['total'], r['validas'], r['con_error']))
    for h in r['hojas']:
        print('  hoja %-10s %d filas · %d válidas · %d con error' % (
            h['hoja'], h['filas'], h['validas'], h['con_error']))
    if r.get('hojas_ignoradas'):
        print('  (hojas ignoradas: %s)' % ', '.join(r['hojas_ignoradas']))
    for f in r['filas']:
        d = f['datos']
        etiqueta = '%-6s' % ('OK' if f['estado'] == 'valida' else 'ERROR')
        print('  %-9s fila %-3d %s %-12s %s' % (f['hoja'], f['fila'], etiqueta,
                                                d['identificador'] or '(sin folio)', d['descripcion']))
        for campo, motivo in f['errores'].items():
            print('             -> %s: %s' % (r['columnas'].get(campo, campo), motivo))


def main():
    pa = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    pa.add_argument('--url', default='http://127.0.0.1:8000/api')
    pa.add_argument('--usuario', default='admin')
    pa.add_argument('--clave', default='admin')
    pa.add_argument('--confirmar', action='store_true', help='guarda las filas válidas')
    args = pa.parse_args()

    api = Api(args.url)
    print('1. Iniciando sesión como %s...' % args.usuario)
    api.token = api.llamar('POST', 'auth/login/', {'username': args.usuario, 'password': args.clave})['token']

    print('2. Datos de apoyo (solo se crean los que faltan):')
    preparar_apoyo(api)

    print('3. Bajando la plantilla...')
    plantilla = api.llamar('GET', 'carga-masiva/plantilla/', binario=True)
    libro, listas, tipos = listas_de(plantilla)
    print('   Hojas: ' + ', '.join(libro.sheetnames))
    print('   Listas desplegables: ' + ', '.join('%s (%d)' % (k, len(v)) for k, v in listas.items() if k))
    print('   Tipos por categoría: ' + '; '.join('%s: %d' % (k, len(v)) for k, v in tipos.items()))
    for nombre, marca in HOJAS.items():
        esperado = [e.replace('{id}', marca) for e in ENCABEZADOS]
        assert [c.value for c in libro[nombre][1]] == esperado, 'La hoja %s cambió de columnas' % nombre

    print('4. Llenando la plantilla con filas de prueba...')
    n = llenar(libro, listas, tipos)
    salida = BytesIO()
    libro.save(salida)
    contenido = salida.getvalue()
    archivo = 'prueba_inventario.xlsx'
    for intento in range(2, 12):
        try:
            with open(archivo, 'wb') as f:
                f.write(contenido)
            break
        except PermissionError:  # el archivo está abierto en Excel: se guarda con otro nombre
            archivo = 'prueba_inventario_%d.xlsx' % intento
    print('   %d filas escritas en %s' % (n, archivo))

    print('5. Subiendo para la vista previa (no guarda nada)...')
    previa = api.llamar('POST', 'carga-masiva/validar/', archivo=(archivo, contenido))
    mostrar_vista_previa(previa)
    if previa.get('ya_cargado'):
        print('\nOJO: este mismo archivo ya se cargó el %(fecha)s (usuario %(usuario)s).' % previa['ya_cargado'])
    antes = api.llamar('GET', 'articulos/')['count']
    print('\nArtículos en el sistema (no cambió): %d' % antes)

    if not args.confirmar:
        print('\nPara guardar las filas válidas: python prueba_carga_masiva.py --confirmar')
        return
    print('\n6. Confirmando la carga...')
    r = api.llamar('POST', 'carga-masiva/confirmar/', archivo=(archivo, contenido),
                   campos={'hash': previa['hash']})
    print('   Cargados: %d · Rechazados: %d' % (r['cargados'], r['rechazados']))
    for a in r['articulos']:
        print('   %s fila %d -> artículo %d, identificador %s' % (a['hoja'], a['fila'], a['num'], a['identificador']))
    print('\nArtículos en el sistema ahora: %d' % api.llamar('GET', 'articulos/')['count'])
    movs = api.llamar('GET', 'movimientos/')['results'][:3]
    for m in movs:
        print('   %s %s · motivo: %s · requiere_resguardo: %s' % (
            m['folio'], m['tipo']['codigo'], m['nota'], m['requiere_resguardo']))
    print('\nSi vuelves a correr con --confirmar, el sistema avisará que ese mismo archivo ya se cargó.')


if __name__ == '__main__':
    sys.exit(main())
