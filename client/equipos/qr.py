"""Contenido del código QR de un artículo (DEC-005, RF-19).

El QR lleva solo un identificador técnico, sin URL ni dominio: si alguien lo
lee con la cámara del celular ve un texto corto y no llega a ningún sitio.
Solo el escáner de InventaCore, con sesión iniciada, lo convierte en la ficha.

Formato: `IC:<num>`, donde <num> es la clave del artículo. Las etiquetas
impresas quedan fijas en papel: cambiar este formato las invalidaría.
"""
import re

PREFIJO = 'IC:'
_FORMATO = re.compile(r'^IC:(\d{1,9})$')


def contenido(num):
    return '%s%d' % (PREFIJO, num)


def leer(texto):
    """Devuelve el num del artículo, o None si el texto no es un QR de InventaCore."""
    coincide = _FORMATO.match((texto or '').strip())
    return int(coincide.group(1)) if coincide else None
