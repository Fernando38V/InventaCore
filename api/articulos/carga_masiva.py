"""Carga masiva de artículos desde una plantilla de Excel (RF-24, RF-25, DEC-017).

El libro trae una hoja por origen, como la Contadora ya trabaja: Activos,
Comodatos y Enseres. El origen sale del nombre de la hoja (no hay columna
"Origen"). Categoría y tipo de artículo van en columnas separadas; el
desplegable del tipo depende de la categoría elegida.

Flujo:
  1. `generar_plantilla()` arma el .xlsx con listas desplegables tomadas de los
     catálogos del sistema.
  2. `validar_archivo()` lee el archivo que subió el Administrador y valida cada
     fila con el MISMO serializador del alta manual (no hay dos reglas
     distintas), además de buscar duplicados dentro del archivo y contra la
     base. No guarda nada: devuelve la vista previa.
  3. `cargar_archivo()` vuelve a validar y guarda solo las filas válidas, todas
     en una transacción. Cada artículo genera su ALTA con motivo "Carga masiva",
     sin resguardo pendiente (DEC-007, DEC-017). El estado de registro lo calcula
     el sistema (DEC-008): la plantilla solo trae "¿Donado?".

Diseño técnico de PEND-013 (propuesta): resguardante por número de empleado;
coincidencia sin distinguir mayúsculas, acentos ni espacios extra; una
transacción por archivo con las filas válidas; duplicados dentro del archivo y
contra la base; bitácora del lote.
"""
import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from rest_framework.exceptions import ValidationError

from articulos.models import Articulo
from articulos.serializers import ArticuloCrearSerializer
from articulos.servicios import alta_articulo
from auditoria.models import Bitacora
from catalogos.folios import MAXIMO_POR_MES
from catalogos.models import (Categoria, ContadorFolio, EstadoOperativo, Origen, TipoArticulo,
                              Ubicacion)
from personal.models import Personal

MAX_FILAS = 2000
MAX_BYTES = 5 * 1024 * 1024
SEPARADOR = ' · '

# Una hoja por origen. El primer dato de cada hoja es el identificador del bien:
# marbete en Activos; folio (el que ya tiene, o vacío para que lo asigne el
# sistema) en Comodatos y Enseres.
HOJAS = [
    ('Activos', 'ACT', 'Marbete'),
    ('Comodatos', 'COM', 'Folio'),
    ('Enseres', 'ENS', 'Folio'),
]

# (clave, encabezado, ancho, obligatoria). El encabezado de `identificador`
# depende de la hoja (Marbete o Folio).
COLUMNAS = [
    ('identificador', 'Marbete o folio', 22, False),
    ('categoria', 'Categoría', 28, True),
    ('tipo_articulo', 'Tipo de artículo', 30, True),
    ('marca', 'Marca', 16, False),
    ('modelo', 'Modelo', 18, False),
    ('num_serie', 'Número de serie', 20, False),
    ('color', 'Color', 14, True),
    ('descripcion', 'Descripción', 42, True),
    ('ubicacion', 'Ubicación', 34, True),
    ('resguardante', 'Resguardante', 38, True),
    ('estado_operativo', 'Estado operativo', 18, False),
    ('fecha_adquisicion', 'Fecha de adquisición', 20, False),
    ('costo_adquisicion', 'Costo de adquisición', 20, False),
    ('donado', '¿Donado?', 12, False),
]
ENCABEZADOS = {clave: encabezado for clave, encabezado, _, _ in COLUMNAS}
ALIAS_IDENTIFICADOR = {'marbete', 'folio', 'marbete o folio', 'folio interno', 'folio (si ya tiene)'}
CAMPO_DEL_SERIALIZADOR = {'marbete_oficial': 'identificador'}


def encabezado_de(clave, hoja_nombre):
    if clave == 'identificador':
        return {h: e for h, _, e in HOJAS}[hoja_nombre]
    return ENCABEZADOS[clave]


class ArchivoInvalido(Exception):
    """El archivo no se puede leer como plantilla."""


# ------------------------------------------------------------------ utilidades

def _n(valor):
    """Para comparar: sin acentos, sin mayúsculas y con espacios simples."""
    if valor is None:
        return ''
    texto = unicodedata.normalize('NFKD', str(valor))
    texto = ''.join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', texto).strip().casefold()


def _hoja_conocida(nombre):
    """Nombre canónico de la hoja (Activos, Comodatos, Enseres) o None. Acepta
    singular, mayúsculas y acentos distintos."""
    n = _n(nombre)
    for hoja, _, _ in HOJAS:
        if n in (_n(hoja), _n(hoja)[:-1], _n(hoja)[:-2]):
            return hoja
    return None


def _texto(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    if isinstance(valor, (datetime, date)):
        return valor.strftime('%d/%m/%Y')
    valor = re.sub(r'\s+', ' ', str(valor)).strip()
    return valor or None


def _fecha(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    for formato in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    raise ValueError


def _costo(valor):
    if valor is None or valor == '':
        return None
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = re.sub(r'[\s$,]', '', str(valor))
    try:
        return Decimal(texto)
    except InvalidOperation:
        raise ValueError


def _si_no(valor):
    n = _n(valor)
    if n in ('', 'no', 'n', 'false', '0'):
        return False
    if n in ('si', 's', 'true', '1', 'x'):
        return True
    raise ValueError


# ------------------------------------------------------------------- plantilla


def _etiqueta_ubicacion(u):
    return SEPARADOR.join((u.codigo, u.nombre))


def _etiqueta_personal(p):
    return SEPARADOR.join((p.numero_empleado, p.nombre_completo))


INSTRUCCIONES = [
    'PLANTILLA DE CARGA MASIVA DE ARTÍCULOS — InventaCore',
    '',
    'Antes de cargar: deben existir en el sistema las categorías, los tipos de artículo, '
    'las ubicaciones y el personal. Las listas desplegables salen de esos catálogos.',
    '',
    '1. El libro trae una hoja por origen: "Activos", "Comodatos" y "Enseres". Llene cada bien en la '
    'hoja que le corresponde, una fila por artículo. Puede dejar vacías las hojas que no use. '
    'No cambie ni mueva los encabezados ni los nombres de las hojas.',
    '2. Obligatorios: Categoría, Tipo de artículo, Color, Descripción, Ubicación y Resguardante. '
    'En Activos, también el Marbete.',
    '3. Activos: la primera columna es el MARBETE oficial. Comodatos y Enseres: la primera columna es '
    'el FOLIO que el bien ya tiene (se respeta aunque tenga otro formato); si no tiene, déjelo vacío '
    'y el sistema le asigna uno.',
    '4. Elija primero la Categoría y después el Tipo de artículo: la lista de tipos muestra solo los '
    'de la categoría elegida. Ubicación y Resguardante también se eligen de la lista; el resguardante '
    'se identifica por su número de empleado.',
    '5. Estado operativo: Útil u Obsoleto. Si lo deja vacío será Útil. Un bien en la ubicación '
    '"Sin ubicar" queda No localizado automáticamente.',
    '6. Fecha de adquisición: DD/MM/AAAA. Costo de adquisición: número (por ejemplo 12500.50).',
    '7. ¿Donado?: Sí o No (vacío = No). El estado de registro (Registrado, Pendiente o Donado) '
    'lo calcula el sistema; no se captura.',
    '8. El número de serie es opcional, pero no puede repetirse. Un marbete, folio o serie que ya '
    'existe en el sistema se rechaza como duplicado.',
    '9. Cargue primero el inventario más reciente (2026) y después los años anteriores: estos '
    'solo agregan los bienes que no aparecen en los más recientes.',
    f'10. Máximo {MAX_FILAS} filas por archivo (entre las tres hojas). Al subirlo verá una vista previa '
    'con las filas válidas y las filas con error; al confirmar solo entran las válidas.',
    '11. Las hojas "Listas" y "Tipos" alimentan los desplegables: no las modifique.',
]


def generar_plantilla():
    """Bytes del .xlsx de la plantilla (RF-24)."""
    libro = Workbook()
    ayuda = libro.active
    ayuda.title = 'Instrucciones'
    for i, linea in enumerate(INSTRUCCIONES, start=1):
        celda = ayuda.cell(row=i, column=1, value=linea)
        celda.alignment = Alignment(wrap_text=True, vertical='top')
    ayuda['A1'].font = Font(bold=True, size=13)
    ayuda.column_dimensions['A'].width = 120

    hojas = [libro.create_sheet(nombre) for nombre, _, _ in HOJAS]
    listas = libro.create_sheet('Listas')
    tipos_hoja = libro.create_sheet('Tipos')

    categorias = list(Categoria.objects.filter(activo=True).order_by('nombre'))
    ubicaciones = [_etiqueta_ubicacion(u) for u in Ubicacion.objects.filter(
        activo=True).order_by('nombre')]
    personal = [_etiqueta_personal(p) for p in Personal.objects.filter(
        activo=True).order_by('primer_apellido', 'segundo_apellido', 'nombre_pila')]
    estados = [e.nombre for e in EstadoOperativo.objects.filter(activo=True).exclude(
        pk='NOLOC').order_by('codigo')]
    listas_datos = [('Categoría', [c.nombre for c in categorias]), ('Ubicación', ubicaciones),
                    ('Resguardante', personal), ('Estado operativo', estados),
                    ('¿Donado?', ['Sí', 'No'])]
    rangos = {}
    for columna, (titulo, valores) in enumerate(listas_datos, start=1):
        listas.cell(row=1, column=columna, value=titulo).font = Font(bold=True)
        for fila, valor in enumerate(valores, start=2):
            listas.cell(row=fila, column=columna, value=valor)
        letra = get_column_letter(columna)
        listas.column_dimensions[letra].width = 44
        rangos[titulo] = "=Listas!$%s$2:$%s$%d" % (letra, letra, max(len(valores) + 1, 2))

    # Tipos por categoría: una columna por categoría en "Tipos" y un nombre
    # definido por columna; "Listas" guarda la correspondencia categoría -> nombre
    # para que el desplegable del tipo se arme con INDIRECT.
    columna_mapa = len(listas_datos) + 2
    listas.cell(row=1, column=columna_mapa, value='Categoría (tipos)').font = Font(bold=True)
    listas.cell(row=1, column=columna_mapa + 1, value='Nombre del rango').font = Font(bold=True)
    letra_cat, letra_rango = get_column_letter(columna_mapa), get_column_letter(columna_mapa + 1)
    listas.column_dimensions[letra_cat].width = 44
    listas.column_dimensions[letra_rango].width = 18
    for numero, categoria in enumerate(categorias, start=1):
        nombres = [t.nombre for t in TipoArticulo.objects.filter(
            categoria=categoria, activo=True).order_by('nombre')]
        letra = get_column_letter(numero)
        tipos_hoja.cell(row=1, column=numero, value=categoria.nombre).font = Font(bold=True)
        for fila, nombre in enumerate(nombres, start=2):
            tipos_hoja.cell(row=fila, column=numero, value=nombre)
        tipos_hoja.column_dimensions[letra].width = 34
        rango = 'tip_%d' % numero
        libro.defined_names[rango] = DefinedName(
            rango, attr_text="Tipos!$%s$2:$%s$%d" % (letra, letra, max(len(nombres) + 1, 2)))
        listas.cell(row=numero + 1, column=columna_mapa, value=categoria.nombre)
        listas.cell(row=numero + 1, column=columna_mapa + 1, value=rango)
    ultimo_mapa = max(len(categorias) + 1, 2)
    mapa = "Listas!$%s$2:$%s$%d" % (letra_cat, letra_rango, ultimo_mapa)

    relleno = PatternFill('solid', fgColor='1F4E78')
    relleno_obligatorio = PatternFill('solid', fgColor='9C2F2F')
    ultima = MAX_FILAS + 1
    columna_de = {clave: get_column_letter(i) for i, (clave, *_) in enumerate(COLUMNAS, start=1)}
    for hoja, (nombre, _, _) in zip(hojas, HOJAS):
        for i, (clave, _, ancho, obligatoria) in enumerate(COLUMNAS, start=1):
            celda = hoja.cell(row=1, column=i, value=encabezado_de(clave, nombre))
            celda.font = Font(bold=True, color='FFFFFF')
            celda.fill = relleno_obligatorio if (obligatoria or (
                clave == 'identificador' and nombre == 'Activos')) else relleno
            celda.alignment = Alignment(vertical='center', wrap_text=True)
            hoja.column_dimensions[get_column_letter(i)].width = ancho
        hoja.freeze_panes = 'A2'
        validaciones = [('categoria', rangos['Categoría']), ('ubicacion', rangos['Ubicación']),
                        ('resguardante', rangos['Resguardante']),
                        ('estado_operativo', rangos['Estado operativo']),
                        ('donado', rangos['¿Donado?']),
                        ('tipo_articulo', '=INDIRECT(VLOOKUP($%s2,%s,2,FALSE))' % (
                            columna_de['categoria'], mapa))]
        for clave, formula in validaciones:
            validacion = DataValidation(
                type='list', formula1=formula, allow_blank=True, showErrorMessage=True,
                errorTitle='Valor no válido',
                error='Elija un valor de la lista (primero la categoría y luego el tipo).'
                if clave == 'tipo_articulo' else 'Elija un valor de la lista.')
            hoja.add_data_validation(validacion)
            validacion.add('%s2:%s%d' % (columna_de[clave], columna_de[clave], ultima))
        posicion = {clave: i for i, (clave, *_) in enumerate(COLUMNAS)}
        for fila in hoja.iter_rows(min_row=2, max_row=min(ultima, 300)):
            fila[posicion['fecha_adquisicion']].number_format = 'DD/MM/YYYY'
            fila[posicion['costo_adquisicion']].number_format = '#,##0.00'

    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


# ------------------------------------------------------------------- lectura

def leer_archivo(contenido):
    """Lee las hojas Activos, Comodatos y Enseres.

    Devuelve (filas, hojas_ignoradas) con filas = [(hoja, número_de_fila,
    {clave: valor_de_celda})] en el orden Activos, Comodatos, Enseres."""
    if len(contenido) > MAX_BYTES:
        raise ArchivoInvalido('El archivo pesa más de %d MB.' % (MAX_BYTES // (1024 * 1024)))
    if not contenido.startswith(b'PK'):
        raise ArchivoInvalido('El archivo no es un Excel (.xlsx) válido.')
    try:
        libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)
    except Exception:
        raise ArchivoInvalido('El archivo no es un Excel (.xlsx) válido.')
    try:
        encontradas, ignoradas = {}, []
        for nombre in libro.sheetnames:
            canonica = _hoja_conocida(nombre)
            if canonica and canonica not in encontradas:
                encontradas[canonica] = libro[nombre]
            elif _n(nombre) not in ('instrucciones', 'listas', 'tipos'):
                ignoradas.append(nombre)
        if not encontradas:
            raise ArchivoInvalido(
                'No se encontró ninguna de las hojas "Activos", "Comodatos" o "Enseres". '
                'Use la plantilla del sistema.')
        resultado = []
        for hoja_nombre, _, _ in HOJAS:
            hoja = encontradas.get(hoja_nombre)
            if hoja is None:
                continue
            filas = hoja.iter_rows(values_only=True)
            encabezados = next(filas, None)
            if encabezados is None:
                continue
            columnas = {}
            for posicion, texto in enumerate(encabezados):
                columnas.setdefault(_n(str(texto or '').rstrip('* ').strip()), posicion)
            posiciones, faltan = {}, []
            for clave, _, _, _ in COLUMNAS:
                if clave == 'identificador':
                    candidatos = [columnas[a] for a in ALIAS_IDENTIFICADOR if a in columnas]
                    posicion = min(candidatos) if candidatos else None
                else:
                    posicion = columnas.get(_n(ENCABEZADOS[clave]))
                if posicion is None:
                    faltan.append(encabezado_de(clave, hoja_nombre))
                posiciones[clave] = posicion
            if faltan:
                raise ArchivoInvalido(
                    'Faltan columnas en la hoja "%s": %s. Use la plantilla del sistema.'
                    % (hoja_nombre, ', '.join(faltan)))
            for numero, fila in enumerate(filas, start=2):
                datos = {clave: (fila[pos] if pos < len(fila) else None)
                         for clave, pos in posiciones.items()}
                if all(v is None or str(v).strip() == '' for v in datos.values()):
                    continue
                resultado.append((hoja_nombre, numero, datos))
                if len(resultado) > MAX_FILAS:
                    raise ArchivoInvalido(
                        'El archivo tiene más de %d filas entre las tres hojas. Divídalo en '
                        'archivos más pequeños.' % MAX_FILAS)
        if not resultado:
            raise ArchivoInvalido('El archivo no tiene filas con datos.')
        return resultado, ignoradas
    finally:
        libro.close()


# ---------------------------------------------------------------- validación

class _Catalogos:
    """Catálogos en memoria para no consultar la base por cada fila."""

    def __init__(self):
        def mapa(pares):
            resultado = {}
            for texto, pk in pares:
                resultado.setdefault(_n(texto), pk)
            return resultado

        categorias = list(Categoria.objects.all())
        self.categorias = mapa([(c.codigo, c.pk) for c in categorias]
                               + [(c.nombre, c.pk) for c in categorias])
        self.nombre_categoria = {c.pk: c.nombre for c in categorias}
        self.estados = mapa([(e.codigo, e.pk) for e in EstadoOperativo.objects.all()]
                            + [(e.nombre, e.pk) for e in EstadoOperativo.objects.all()])
        # Tipos de cada categoría (por nombre o código) y, aparte, en qué
        # categorías existe cada nombre, para decir "pertenece a otra categoría".
        self.tipos = {}
        self.tipo_en_categorias = {}
        for t in TipoArticulo.objects.all():
            self.tipos.setdefault(t.categoria_id, {})
            self.tipos[t.categoria_id].setdefault(_n(t.codigo), t.pk)
            self.tipos[t.categoria_id].setdefault(_n(t.nombre), t.pk)
            self.tipo_en_categorias.setdefault(_n(t.nombre), set()).add(t.categoria_id)
            self.tipo_en_categorias.setdefault(_n(t.codigo), set()).add(t.categoria_id)
        ubicaciones = list(Ubicacion.objects.all())
        nombres = {}
        for u in ubicaciones:
            nombres[_n(u.nombre)] = nombres.get(_n(u.nombre), 0) + 1
        pares = [(u.codigo, u.pk) for u in ubicaciones]
        pares += [(_etiqueta_ubicacion(u), u.pk) for u in ubicaciones]
        pares += [(u.nombre, u.pk) for u in ubicaciones if nombres[_n(u.nombre)] == 1]
        self.ubicaciones = mapa(pares)
        personal = list(Personal.objects.all())
        self.personal = mapa([(p.numero_empleado, p.pk) for p in personal]
                             + [(_etiqueta_personal(p), p.pk) for p in personal])

    @staticmethod
    def buscar(mapa, texto):
        n = _n(texto)
        if n in mapa:
            return mapa[n]
        return mapa.get(_n(str(texto).split('·')[0]))


def _primer_mensaje(errores):
    resultado = {}
    for campo, mensajes in errores.items():
        if isinstance(mensajes, (list, tuple)):
            mensajes = [m for m in mensajes if m]
            mensaje = str(mensajes[0]) if mensajes else 'Dato no válido.'
        else:
            mensaje = str(mensajes)
        if mensaje.startswith('Este campo es requerido') or mensaje.startswith(
                'This field is required') or 'no puede estar en blanco' in mensaje:
            mensaje = 'Este dato es obligatorio.'
        resultado[CAMPO_DEL_SERIALIZADOR.get(campo, campo)] = mensaje
    return resultado


def _fila_previa(hoja, numero, crudo, errores, alta=None, folio=None):
    resumen = {clave: _texto(crudo.get(clave)) for clave in ENCABEZADOS}
    resumen['origen'] = ORIGEN_NOMBRE[hoja]
    return {'hoja': hoja, 'fila': numero, 'estado': 'error' if errores else 'valida',
            'errores': errores, 'datos': resumen, '_alta': alta, '_folio': folio}


ORIGEN_DE_HOJA = {hoja: origen for hoja, origen, _ in HOJAS}
ORIGEN_NOMBRE = {'Activos': 'Activo', 'Comodatos': 'Comodato', 'Enseres': 'Enser'}


def _validar_fila(hoja, numero, crudo, cat):
    errores = {}
    origen = ORIGEN_DE_HOJA[hoja]

    def pedir(clave):
        if _texto(crudo.get(clave)) is None:
            errores[clave] = 'Este dato es obligatorio.'
            return None
        return _texto(crudo.get(clave))

    def catalogo(clave, mapa, nombre, obligatorio=True):
        texto = pedir(clave) if obligatorio else _texto(crudo.get(clave))
        if texto is None:
            return None
        pk = cat.buscar(mapa, texto)
        if pk is None:
            errores[clave] = 'No se reconoce %s "%s". Elija un valor de la lista.' % (nombre, texto)
        return pk

    categoria = catalogo('categoria', cat.categorias, 'la categoría')
    tipo = None
    texto_tipo = pedir('tipo_articulo')
    if texto_tipo is not None and categoria is not None:
        tipo = cat.tipos.get(categoria, {}).get(_n(texto_tipo))
        if tipo is None:
            otras = cat.tipo_en_categorias.get(_n(texto_tipo))
            if otras:
                errores['tipo_articulo'] = 'El tipo "%s" no pertenece a la categoría "%s".' % (
                    texto_tipo, cat.nombre_categoria[categoria])
            else:
                errores['tipo_articulo'] = (
                    'No se reconoce el tipo de artículo "%s". Elija un valor de la lista.'
                    % texto_tipo)
    ubicacion = catalogo('ubicacion', cat.ubicaciones, 'la ubicación')
    resguardante = catalogo('resguardante', cat.personal, 'al resguardante')
    estado = catalogo('estado_operativo', cat.estados, 'el estado operativo', obligatorio=False)
    color, descripcion = pedir('color'), pedir('descripcion')

    try:
        donado = _si_no(crudo.get('donado'))
    except ValueError:
        donado = False
        errores['donado'] = 'Escriba Sí o No.'
    try:
        fecha = _fecha(crudo.get('fecha_adquisicion'))
    except ValueError:
        fecha = None
        errores['fecha_adquisicion'] = 'Fecha no válida. Use DD/MM/AAAA.'
    try:
        costo = _costo(crudo.get('costo_adquisicion'))
    except ValueError:
        costo = None
        errores['costo_adquisicion'] = 'El costo debe ser un número.'

    identificador = _texto(crudo.get('identificador'))
    folio = None
    if origen == 'ACT':
        if identificador is None:
            errores['identificador'] = 'Los activos llevan marbete oficial.'
    elif identificador is not None:
        folio, identificador = identificador, None
        if len(folio) > 25:
            errores['identificador'] = 'El folio no puede tener más de 25 caracteres.'

    if errores:
        return _fila_previa(hoja, numero, crudo, errores)

    entrada = {'origen': origen, 'tipo_articulo': tipo, 'ubicacion': ubicacion,
               'resguardante': resguardante, 'color': color, 'descripcion': descripcion,
               'marbete_oficial': identificador, 'marca': _texto(crudo.get('marca')),
               'modelo': _texto(crudo.get('modelo')), 'num_serie': _texto(crudo.get('num_serie')),
               'fecha_adquisicion': fecha.isoformat() if fecha else None,
               'costo_adquisicion': str(costo) if costo is not None else None,
               'donado': donado}
    if estado:
        entrada['estado_operativo'] = estado
    serializador = ArticuloCrearSerializer(data=entrada)
    if not serializador.is_valid():
        return _fila_previa(hoja, numero, crudo, _primer_mensaje(serializador.errors))
    return _fila_previa(hoja, numero, crudo, {}, alta=serializador.validated_data, folio=folio)


def _revisar_duplicados(filas):
    """Marca como error los identificadores y series repetidos en el archivo o
    que ya existen en el sistema."""
    def clave_identificador(fila):
        alta = fila['_alta']
        return fila['_folio'] or alta.get('marbete_oficial')

    candidatos = [f for f in filas if f['estado'] == 'valida']
    marbetes = [f['_alta'].get('marbete_oficial') for f in candidatos if f['_alta'].get('marbete_oficial')]
    folios = [f['_folio'] for f in candidatos if f['_folio']]
    series = [f['_alta'].get('num_serie') for f in candidatos if f['_alta'].get('num_serie')]
    en_base = {
        'marbete': {_n(x) for x in Articulo.objects.filter(
            marbete_oficial__in=marbetes).values_list('marbete_oficial', flat=True)},
        'folio': {_n(x) for x in Articulo.objects.filter(
            folio_interno__in=folios).values_list('folio_interno', flat=True)},
        'serie': {_n(x) for x in Articulo.objects.filter(
            num_serie__in=series).values_list('num_serie', flat=True)},
    }
    vistos_id, vistos_serie = {}, {}

    def donde(f):
        return 'la fila %d de la hoja %s' % (f['fila'], f['hoja'])

    for fila in filas:
        if fila['estado'] != 'valida':
            # Las filas con error también "ocupan" su identificador para avisar
            # de repetidos, pero solo si lo tienen capturado.
            continue
        alta = fila['_alta']
        identificador = clave_identificador(fila)
        serie = alta.get('num_serie')
        errores = {}
        if identificador:
            n = _n(identificador)
            tipo = 'marbete' if alta.get('marbete_oficial') else 'folio'
            if n in en_base[tipo]:
                errores['identificador'] = 'Duplicado: ese %s ya está registrado en el sistema.' % tipo
            elif n in vistos_id:
                errores['identificador'] = 'Repetido: ya aparece en %s.' % donde(vistos_id[n])
            else:
                vistos_id[n] = fila
        if serie:
            n = _n(serie)
            if n in en_base['serie']:
                errores['num_serie'] = 'Duplicado: ese número de serie ya está registrado en el sistema.'
            elif n in vistos_serie:
                errores['num_serie'] = 'Repetido: ya aparece en %s.' % donde(vistos_serie[n])
            else:
                vistos_serie[n] = fila
        if errores:
            fila['estado'], fila['errores'] = 'error', errores


def _revisar_folios_disponibles(filas):
    """Los folios que asigna el sistema (Comodato y Enser sin folio) caben en
    el máximo de 999 del mes (RF-06)."""
    periodo = timezone.localtime(timezone.now()).strftime('%m%y')
    contador = ContadorFolio.objects.filter(clave='FI-%s' % periodo).first()
    libres = MAXIMO_POR_MES - (contador.ultimo if contador else 0)
    for fila in filas:
        if fila['estado'] != 'valida':
            continue
        if fila['_alta']['origen'].pk in ('COM', 'ENS') and not fila['_folio']:
            if libres <= 0:
                fila['estado'] = 'error'
                fila['errores'] = {'identificador': (
                    'Se alcanzó el máximo de %d folios internos de este mes: escriba el '
                    'folio que ya tiene el bien o cargue esta fila el mes siguiente.'
                    % MAXIMO_POR_MES)}
            else:
                libres -= 1


def _lote_previo(huella):
    """El mismo archivo (mismo contenido) ya cargado antes, o None. Evita que
    volver a subirlo duplique las filas que no tienen marbete, folio ni serie."""
    return Bitacora.objects.filter(
        modulo='carga_masiva', registro_id='lote-%s' % huella[:12]).select_related('usuario').first()


def validar_archivo(contenido):
    """Vista previa: no guarda nada. Devuelve el resumen y todas las filas."""
    crudas, ignoradas = leer_archivo(contenido)
    catalogos = _Catalogos()
    filas = [_validar_fila(hoja, numero, crudo, catalogos) for hoja, numero, crudo in crudas]
    _revisar_duplicados(filas)
    _revisar_folios_disponibles(filas)
    validas = sum(1 for f in filas if f['estado'] == 'valida')
    huella = hashlib.sha256(contenido).hexdigest()
    previo = _lote_previo(huella)
    hojas = []
    for hoja, origen, _ in HOJAS:
        de_hoja = [f for f in filas if f['hoja'] == hoja]
        if de_hoja:
            buenas = sum(1 for f in de_hoja if f['estado'] == 'valida')
            hojas.append({'hoja': hoja, 'origen': ORIGEN_NOMBRE[hoja], 'filas': len(de_hoja),
                          'validas': buenas, 'con_error': len(de_hoja) - buenas})
    return {
        'hash': huella,
        'total': len(filas), 'validas': validas, 'con_error': len(filas) - validas,
        # Si este mismo archivo ya se cargó: cuándo y quién (confirmar lo rechaza).
        'ya_cargado': None if previo is None else {
            'fecha': timezone.localtime(previo.fecha_hora).strftime('%Y-%m-%d %H:%M'),
            'usuario': previo.usuario.username},
        'hojas': hojas, 'hojas_ignoradas': ignoradas,
        'columnas': dict(ENCABEZADOS, identificador='Marbete o folio'), 'filas': filas,
    }


def publicas(filas):
    """Quita los datos internos para responder por la API."""
    return [{k: v for k, v in f.items() if not k.startswith('_')} for f in filas]


# ------------------------------------------------------------------- carga

def cargar_archivo(contenido, nombre, usuario, hash_revisado):
    """Vuelve a validar y guarda solo las filas válidas, en una transacción."""
    if hash_revisado != hashlib.sha256(contenido).hexdigest():
        raise ValidationError({'archivo': (
            'El archivo no es el mismo que se revisó. Súbalo de nuevo para ver la vista previa.')})
    resultado = validar_archivo(contenido)
    if resultado['ya_cargado']:
        raise ValidationError({'archivo': (
            'Este mismo archivo ya se cargó el %(fecha)s (usuario %(usuario)s). '
            'Para cargar filas nuevas use un archivo distinto.' % resultado['ya_cargado'])})
    validas = [f for f in resultado['filas'] if f['estado'] == 'valida']
    if not validas:
        raise ValidationError({'archivo': 'No hay filas válidas que cargar.'})

    nombre = (nombre or 'archivo.xlsx')[:120]
    hoy = timezone.localdate().strftime('%d/%m/%Y')
    motivo = 'Carga masiva (%s, %s)' % (nombre, hoy)
    cargados = []
    with transaction.atomic():
        for fila in validas:
            try:
                articulo = alta_articulo(
                    fila['_alta'], usuario, requiere_resguardo=False,
                    folio_interno=fila['_folio'], motivo=motivo)
            except ValidationError as error:
                raise ValidationError({'archivo': 'No se pudo cargar la fila %d de %s (%s). No se guardó nada.' % (
                    fila['fila'], fila['hoja'], '; '.join(str(v) for v in _aplanar(error.detail)))})
            cargados.append({'hoja': fila['hoja'], 'fila': fila['fila'], 'num': articulo.num,
                             'identificador': articulo.identificador})
        Bitacora.objects.create(
            usuario=usuario, modulo='carga_masiva', accion='INSERT', tabla_afectada='articulo',
            registro_id='lote-%s' % resultado['hash'][:12],
            valor_nuevo=json.dumps({
                'archivo': nombre, 'hash': resultado['hash'], 'filas_en_archivo': resultado['total'],
                'cargados': len(cargados), 'rechazados': resultado['con_error'],
                'por_hoja': {h['hoja']: sum(1 for c in cargados if c['hoja'] == h['hoja'])
                             for h in resultado['hojas']}},
                ensure_ascii=False),
            motivo=motivo[:255])
    rechazadas = [f for f in resultado['filas'] if f['estado'] == 'error']
    return {
        'archivo': nombre, 'hash': resultado['hash'], 'total': resultado['total'],
        'cargados': len(cargados), 'rechazados': len(rechazadas),
        'hojas': resultado['hojas'], 'articulos': cargados, 'filas_rechazadas': publicas(rechazadas),
    }


def _aplanar(detalle):
    if isinstance(detalle, dict):
        for valor in detalle.values():
            yield from _aplanar(valor)
    elif isinstance(detalle, (list, tuple)):
        for valor in detalle:
            yield from _aplanar(valor)
    else:
        yield detalle
