"""PDF del resguardo (RF-18, DEC-007).

Estructura del formato institucional: encabezado, datos del resguardante,
tabla de artículos (número de inventario, descripción, marca, modelo, serie y
costo), número de bienes, leyenda de responsabilidad y dos firmas: la de la
Contadora (responsable de seguimiento) y la del resguardante. Sin "Monto
revalúo". Se genera con reportlab.
"""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

LEYENDA = (
    'El resguardante declara recibir los bienes que se listan, en buen estado, y se '
    'responsabiliza de su uso, cuidado y custodia. Cualquier cambio de ubicación o de '
    'resguardante, así como la pérdida, el daño o el envío a reparación de un bien, '
    'deberá reportarse al área responsable del inventario para su registro.')


def _esc(texto):
    return (str(texto) if texto is not None else '—').replace('&', '&amp;').replace(
        '<', '&lt;').replace('>', '&gt;')


def generar_pdf(resguardo, resguardante, articulos, contadora, institucion):
    """`articulos` es una lista de objetos Articulo (con tipo cargado). Devuelve bytes."""
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle('n', parent=estilos['Normal'], fontSize=9, leading=11)
    celda = ParagraphStyle('c', parent=normal, fontSize=8, leading=9.5)
    titulo = ParagraphStyle('t', parent=estilos['Title'], fontSize=15, spaceAfter=2)
    centro = ParagraphStyle('ce', parent=normal, alignment=TA_CENTER)
    leyenda = ParagraphStyle('l', parent=normal, alignment=TA_JUSTIFY)

    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida, pagesize=letter, leftMargin=1.8 * cm, rightMargin=1.8 * cm,
        topMargin=1.6 * cm, bottomMargin=1.8 * cm,
        title='Resguardo %s' % resguardo.folio, author=institucion)

    emision = timezone.localtime(resguardo.fecha_emision).strftime('%d/%m/%Y %H:%M')
    datos = [
        Paragraph(_esc(institucion), centro),
        Paragraph('RESGUARDO DE BIENES', titulo),
        Paragraph('Folio %s · Emitido el %s' % (resguardo.folio, emision), centro),
        Spacer(1, 0.5 * cm),
    ]
    departamento = getattr(resguardante.departamento, 'nombre', None)
    ficha = Table([
        [Paragraph('<b>Resguardante:</b> %s' % _esc(resguardante.nombre_completo), normal),
         Paragraph('<b>No. de empleado:</b> %s' % _esc(resguardante.numero_empleado), normal)],
        [Paragraph('<b>Puesto:</b> %s' % _esc(resguardante.puesto), normal),
         Paragraph('<b>Departamento:</b> %s' % _esc(departamento), normal)],
    ], colWidths=[10 * cm, 7.4 * cm])
    ficha.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                               ('TOPPADDING', (0, 0), (-1, -1), 4),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    datos += [ficha, Spacer(1, 0.5 * cm)]

    filas = [[Paragraph('<b>%s</b>' % t, celda) for t in (
        'No.', 'No. de inventario', 'Descripción', 'Marca', 'Modelo', 'Serie', 'Costo')]]
    for i, a in enumerate(articulos, start=1):
        costo = '—' if a.costo_adquisicion is None else '${:,.2f}'.format(a.costo_adquisicion)
        filas.append([Paragraph(str(i), celda), Paragraph(_esc(a.identificador), celda),
                      Paragraph(_esc(a.descripcion), celda), Paragraph(_esc(a.marca), celda),
                      Paragraph(_esc(a.modelo), celda), Paragraph(_esc(a.num_serie), celda),
                      Paragraph(costo, celda)])
    tabla = Table(filas, repeatRows=1, colWidths=[
        0.9 * cm, 3.0 * cm, 4.6 * cm, 2.1 * cm, 2.2 * cm, 2.3 * cm, 2.7 * cm])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8EEF4')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    datos += [tabla, Spacer(1, 0.4 * cm),
              Paragraph('<b>Número de bienes:</b> %d' % len(articulos), normal),
              Spacer(1, 0.4 * cm), Paragraph(LEYENDA, leyenda), Spacer(1, 1.8 * cm)]

    firmas = Table([
        ['_' * 38, '_' * 38],
        [Paragraph('<b>%s</b>' % _esc(contadora), centro),
         Paragraph('<b>%s</b>' % _esc(resguardante.nombre_completo), centro)],
        [Paragraph('Responsable de seguimiento', centro), Paragraph('Resguardante', centro)],
    ], colWidths=[8.7 * cm, 8.7 * cm])
    firmas.setStyle(TableStyle([('ALIGN', (0, 0), (-1, 0), 'CENTER')]))
    datos.append(KeepTogether([firmas]))

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(1.8 * cm, 1.0 * cm, 'Resguardo %s' % resguardo.folio)
        canvas.drawRightString(letter[0] - 1.8 * cm, 1.0 * cm, 'Página %d' % documento.page)
        canvas.restoreState()

    doc.build(datos, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
