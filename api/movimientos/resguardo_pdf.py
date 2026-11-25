"""PDF del resguardo (RF-18, DEC-007, DEC-024).

Replica el formato "Resguardo de Bienes" que usaba la Contadora, adaptado al sistema:
encabezado con el logo de CONALEP Baja California, NOMBRE, ÁREA y FECHA (en blanco,
se llena al firmar), la leyenda del formato, tabla de artículos (número de inventario,
descripción = tipo de artículo, marca, modelo, número de serie y costo) con encabezado
en verde institucional, número de bienes y dos firmas: la de la Contadora (responsable
de seguimiento) y la del resguardante. Sin "Monto revalúo" ni número de empleado.
Se genera con reportlab.
"""
from io import BytesIO
from pathlib import Path

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

ENCABEZADO = ('COLEGIO DE EDUCACIÓN PROFESIONAL TÉCNICA DEL ESTADO', 'BAJA CALIFORNIA')
LOGO = Path(__file__).resolve().parent / 'recursos' / 'logo_conalep_bc.png'
VERDE = colors.HexColor('#00704A')        # verde institucional (encabezado de la tabla)
VERDE_CLARO = colors.HexColor('#EAF4EE')  # renglones alternos

DECLARACION = (
    'Para el desempeño de las actividades oficiales que tengo a mi cargo en esta Entidad, '
    'he recibido los artículos que se describen a continuación, comprometiéndome a '
    'mantenerlos en óptimas condiciones.')
LEYENDA = (
    'Cualquier cambio de ubicación o de resguardante, así como la pérdida, el daño o el '
    'envío a reparación de un bien, deberá reportarse al área responsable del inventario '
    'para su registro.')


def _esc(texto, vacio='—'):
    texto = '' if texto is None else str(texto).strip()
    return (texto or vacio).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def generar_pdf(resguardo, resguardante, articulos, contadora, institucion):
    """`articulos` es una lista de objetos Articulo (con tipo cargado). Devuelve bytes."""
    estilos = getSampleStyleSheet()
    normal = ParagraphStyle('n', parent=estilos['Normal'], fontSize=9, leading=11)
    celda = ParagraphStyle('c', parent=normal, fontSize=8, leading=9.5)
    cabeza = ParagraphStyle('h', parent=celda, textColor=colors.white, fontName='Helvetica-Bold')
    institucional = ParagraphStyle('i', parent=normal, fontName='Helvetica-Bold', fontSize=11,
                                   leading=13.5, alignment=TA_CENTER)
    subtitulo = ParagraphStyle('s', parent=institucional, fontSize=11, leading=13)
    derecha = ParagraphStyle('d', parent=normal, fontSize=8, leading=10, alignment=TA_RIGHT)
    centro = ParagraphStyle('ce', parent=normal, alignment=TA_CENTER)
    justificado = ParagraphStyle('j', parent=normal, alignment=TA_JUSTIFY)
    declaracion = ParagraphStyle('de', parent=justificado, fontName='Helvetica-Bold')

    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida, pagesize=letter, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.4 * cm, bottomMargin=1.8 * cm,
        title='Resguardo %s' % resguardo.folio, author=institucion)
    ancho = letter[0] - 3.2 * cm

    emision = timezone.localtime(resguardo.fecha_emision).strftime('%d/%m/%Y %H:%M')
    logo = Image(str(LOGO), width=2.6 * cm, height=1.85 * cm) if LOGO.exists() else ''
    titulo = [Paragraph(_esc(linea), institucional) for linea in ENCABEZADO]
    titulo.append(Paragraph('Resguardo de Bienes', subtitulo))
    encabezado = Table([[logo, titulo, '']], colWidths=[2.8 * cm, ancho - 5.6 * cm, 2.8 * cm])
    encabezado.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                    ('LEFTPADDING', (0, 0), (-1, -1), 0),
                                    ('RIGHTPADDING', (0, 0), (-1, -1), 0)]))

    departamento = getattr(resguardante.departamento, 'nombre', None)
    area = ' - '.join(x for x in (departamento, institucion) if x)
    linea = ('LINEBELOW', (1, 0), (1, 0), 0.6, colors.black)
    datos_persona = Table([
        [Paragraph('<b>NOMBRE:</b>', normal), Paragraph(_esc(resguardante.nombre_completo).upper(), normal),
         Paragraph('<b>FECHA:</b>', normal), ''],
        [Paragraph('<b>ÁREA:</b>', normal), Paragraph(_esc(area).upper(), normal), '', ''],
    ], colWidths=[1.8 * cm, ancho - 6.6 * cm, 1.6 * cm, 3.2 * cm])
    datos_persona.setStyle(TableStyle([
        linea, ('LINEBELOW', (1, 1), (1, 1), 0.6, colors.black),
        ('LINEBELOW', (3, 0), (3, 0), 0.6, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'), ('LEFTPADDING', (0, 0), (-1, -1), 2)]))

    filas = [[Paragraph(t, cabeza) for t in (
        'No.', 'Número de inventario', 'Descripción', 'Marca', 'Modelo', 'Número de serie',
        'Costo')]]
    for i, a in enumerate(articulos, start=1):
        costo = '—' if a.costo_adquisicion is None else '${:,.2f}'.format(a.costo_adquisicion)
        tipo = getattr(a.tipo_articulo, 'nombre', None)
        filas.append([Paragraph('%d.' % i, celda), Paragraph(_esc(a.identificador), celda),
                      Paragraph(_esc(tipo).upper(), celda),
                      Paragraph(_esc(a.marca, 'S/M').upper(), celda),
                      Paragraph(_esc(a.modelo, 'S/M').upper(), celda),
                      Paragraph(_esc(a.num_serie, 'S/S').upper(), celda),
                      Paragraph(costo, celda)])
    tabla = Table(filas, repeatRows=1, colWidths=[
        0.9 * cm, 3.6 * cm, 4.1 * cm, 2.2 * cm, 2.3 * cm, 2.9 * cm, ancho - 16.0 * cm])
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), VERDE),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, colors.HexColor('#9FBFAF')),
        ('BOX', (0, 0), (-1, -1), 0.6, VERDE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]
    estilo += [('BACKGROUND', (0, n), (-1, n), VERDE_CLARO) for n in range(2, len(filas), 2)]
    tabla.setStyle(TableStyle(estilo))

    datos = [encabezado, Paragraph(
                 'Folio <b>%s</b> · Emitido el %s' % (resguardo.folio, emision), derecha),
             Spacer(1, 0.35 * cm), datos_persona, Spacer(1, 0.35 * cm),
             Paragraph(DECLARACION, declaracion), Spacer(1, 0.35 * cm),
             tabla, Spacer(1, 0.4 * cm),
             Paragraph('<b>Número de bienes:</b> %d' % len(articulos), normal),
             Spacer(1, 0.3 * cm), Paragraph(LEYENDA, justificado), Spacer(1, 1.8 * cm)]

    firmas = Table([
        ['_' * 38, '_' * 38],
        [Paragraph('<b>%s</b>' % _esc(contadora), centro),
         Paragraph('<b>%s</b>' % _esc(resguardante.nombre_completo), centro)],
        [Paragraph('Responsable de seguimiento', centro), Paragraph('Resguardante', centro)],
    ], colWidths=[ancho / 2, ancho / 2])
    firmas.setStyle(TableStyle([('ALIGN', (0, 0), (-1, 0), 'CENTER')]))
    datos.append(KeepTogether([firmas]))

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(1.6 * cm, 1.0 * cm, 'Resguardo %s' % resguardo.folio)
        canvas.drawRightString(letter[0] - 1.6 * cm, 1.0 * cm, 'Página %d' % documento.page)
        canvas.restoreState()

    doc.build(datos, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()
