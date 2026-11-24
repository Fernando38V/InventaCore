"""Marbete imprimible del artículo: réplica de la etiqueta física del CONALEP
más el código QR (variante A).

Medidas PROVISIONALES, tomadas de los PDF de marbetes que usa la institución
("Marbetes BUTACAS" y "Marbetes LOCKERs Sala docentes"): hoja carta con
10 etiquetas de 4 x 2 pulgadas (2 columnas x 5 filas), el acomodo de las hojas
de etiquetas tipo Avery 5163. Cuando se mida una etiqueta física, se ajustan
aquí y nada más.
"""

# Etiqueta (mm)
ANCHO_MM = 101.6          # 4 in
ALTO_MM = 50.8            # 2 in

# Hoja carta con etiquetas (mm)
HOJA_ANCHO_MM = 215.9
HOJA_ALTO_MM = 279.4
MARGEN_SUPERIOR_MM = 12.7     # 0.5 in
MARGEN_IZQUIERDO_MM = 4.0     # ~0.156 in
SEPARACION_COLUMNAS_MM = 4.8  # ~0.19 in
SEPARACION_FILAS_MM = 0.0
COLUMNAS = 2
FILAS = 5

ENCABEZADO = ('Colegio de Educación Profesional', 'Técnica del Estado de Baja', 'California')

# Logos opcionales (archivos de la institución). Si no existen en static/, el
# marbete sale sin ellos y con el espacio en blanco.
LOGO_IZQUIERDO = 'img/marbete/logo_izquierdo.png'
LOGO_DERECHO = 'img/marbete/logo_derecho.png'

# Renglón del nombre del bien: es el tipo de artículo (Monitor, Laptop, Escalera…), igual que la
# etiqueta física. Hasta NOMBRE_CORTO caracteres va en letra normal; más largo baja a letra chica.
# La descripción del artículo (notas) no se imprime.
NOMBRE_CORTO = 30

# Tope de etiquetas por impresión por lote (una consulta a la API por artículo): 5 hojas.
MAX_LOTE = 50


def posiciones():
    return range(1, COLUMNAS * FILAS + 1)


def leer_posicion(valor):
    """Posición en la hoja (1 = arriba a la izquierda, se avanza por renglón).
    Un valor inválido regresa 1."""
    try:
        posicion = int(valor)
    except (TypeError, ValueError):
        return 1
    return posicion if posicion in posiciones() else 1


def coordenadas(posicion):
    """(arriba, izquierda) en mm de la etiqueta número `posicion` en la hoja."""
    fila, columna = divmod(posicion - 1, COLUMNAS)
    arriba = MARGEN_SUPERIOR_MM + fila * (ALTO_MM + SEPARACION_FILAS_MM)
    izquierda = MARGEN_IZQUIERDO_MM + columna * (ANCHO_MM + SEPARACION_COLUMNAS_MM)
    return round(arriba, 2), round(izquierda, 2)


def repartir(etiquetas, inicio=1):
    """Acomoda las etiquetas en hojas: la primera hoja empieza en el lugar `inicio`
    y las demás en el 1. Regresa una lista de hojas; cada hoja es una lista de
    dicts {'posicion', 'arriba', 'izquierda', 'etiqueta'}."""
    hojas, hoja, posicion = [], [], leer_posicion(inicio)
    for etiqueta in etiquetas:
        if posicion > COLUMNAS * FILAS:
            hojas.append(hoja)
            hoja, posicion = [], 1
        arriba, izquierda = coordenadas(posicion)
        hoja.append({'posicion': posicion, 'arriba': arriba, 'izquierda': izquierda,
                     'etiqueta': etiqueta})
        posicion += 1
    if hoja:
        hojas.append(hoja)
    return hojas
