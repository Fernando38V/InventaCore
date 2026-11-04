"""Exportación del inventario a Excel (RF-26, DEC-018).

Columnas de DEC-018, en ese orden. Sin cuenta contable. El estado de registro
es calculado y solo de salida.
"""
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

COLUMNAS = [
    ('Identificador', 22), ('Categoría', 24), ('Tipo de artículo', 24), ('Marca', 16),
    ('Modelo', 18), ('Serie', 20), ('Color', 12), ('Descripción', 40), ('Origen', 12),
    ('Ubicación', 28), ('Resguardante', 30), ('Estado operativo', 16),
    ('Fecha de adquisición', 18), ('Costo de adquisición', 18), ('Estado de registro', 18),
]


def _texto(valor):
    """Evita que una celda de texto se interprete como fórmula al abrirla en Excel."""
    if isinstance(valor, str) and valor[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + valor
    return valor


def fila(a):
    resguardante = a.resguardante
    return [
        _texto(a.identificador), _texto(a.tipo_articulo.categoria.nombre),
        _texto(a.tipo_articulo.nombre), _texto(a.marca), _texto(a.modelo), _texto(a.num_serie),
        _texto(a.color), _texto(a.descripcion), _texto(a.origen.nombre), _texto(a.ubicacion.nombre),
        _texto(resguardante.nombre_completo if resguardante else None),
        _texto(a.estado_operativo.nombre), a.fecha_adquisicion,
        None if a.costo_adquisicion is None else float(a.costo_adquisicion),
        _texto(a.estado_registro.nombre),
    ]


def libro_inventario(articulos):
    """Devuelve los bytes de un .xlsx con todos los artículos recibidos."""
    libro = Workbook()
    hoja = libro.active
    hoja.title = 'Inventario'
    hoja.append([nombre for nombre, _ in COLUMNAS])
    for celda in hoja[1]:
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = PatternFill('solid', fgColor='1F4E78')
        celda.alignment = Alignment(vertical='center', wrap_text=True)
    for i, (_, ancho) in enumerate(COLUMNAS, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    for articulo in articulos.iterator(chunk_size=500):
        hoja.append(fila(articulo))
    for fila_datos in hoja.iter_rows(min_row=2):
        fila_datos[12].number_format = 'DD/MM/YYYY'
        fila_datos[13].number_format = '#,##0.00'
    hoja.freeze_panes = 'A2'
    hoja.auto_filter.ref = hoja.dimensions
    salida = BytesIO()
    libro.save(salida)
    return salida.getvalue()


def nombre_archivo():
    return 'inventario_%s.xlsx' % timezone.localdate().strftime('%Y%m%d')
