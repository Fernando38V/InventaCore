"""Foto del artículo (PEND-027). Una foto opcional por artículo.

La imagen se guarda en la base de datos, en la tabla `articulo_foto` (una fila por
artículo, columna LONGBLOB). Va en tabla aparte para que las consultas del
inventario nunca lean los bytes. Un solo respaldo (mysqldump) cubre todo.

Lo que llega se vuelve a codificar siempre: se acepta JPG, PNG o WebP (se revisa el
contenido, no la extensión), se corrige la orientación, se quita todo metadato
(EXIF, ubicación GPS), se reduce a 1200 px por lado y se guarda como JPEG.
"""
import hashlib
import warnings
from io import BytesIO

from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from articulos.models import Articulo, ArticuloFoto
from auditoria.servicios import registrar

MAX_BYTES = 5 * 1024 * 1024        # lo que se acepta subir
MAX_LADO = 1200                    # px del lado mayor al guardar
MAX_PIXELES = 50_000_000           # contra imágenes que se "inflan" al abrirse
FORMATOS = {'JPEG', 'PNG', 'WEBP'}


class FotoNoDisponible(Exception):
    """El artículo no tiene foto, o su archivo ya no está en el servidor."""


def _procesar(archivo):
    """Valida la imagen y devuelve los bytes del JPEG ya reducido y limpio."""
    if archivo.size == 0:
        raise ValidationError({'foto': 'El archivo está vacío.'})
    if archivo.size > MAX_BYTES:
        raise ValidationError({'foto': 'La foto pesa más de %d MB.' % (MAX_BYTES // (1024 * 1024))})
    crudo = archivo.read()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            imagen = Image.open(BytesIO(crudo))
            if imagen.format not in FORMATOS:
                raise ValidationError({'foto': 'Use una imagen JPG, PNG o WebP.'})
            ancho, alto = imagen.size
            if ancho * alto > MAX_PIXELES:
                raise ValidationError({'foto': 'La imagen es demasiado grande en píxeles.'})
            imagen.load()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise ValidationError({'foto': 'El archivo no es una imagen válida (JPG, PNG o WebP).'})

    imagen = ImageOps.exif_transpose(imagen)
    if imagen.mode in ('RGBA', 'LA') or (imagen.mode == 'P' and 'transparency' in imagen.info):
        imagen = imagen.convert('RGBA')
        fondo = Image.new('RGB', imagen.size, (255, 255, 255))
        fondo.paste(imagen, mask=imagen.getchannel('A'))
        imagen = fondo
    else:
        imagen = imagen.convert('RGB')
    imagen.thumbnail((MAX_LADO, MAX_LADO), Image.LANCZOS)
    salida = BytesIO()
    imagen.save(salida, 'JPEG', quality=85, optimize=True)   # sin exif: se descartan los metadatos
    return salida.getvalue()


def leer_foto(articulo):
    try:
        return bytes(ArticuloFoto.objects.only('imagen').get(articulo_id=articulo.pk).imagen)
    except ArticuloFoto.DoesNotExist:
        raise FotoNoDisponible('El artículo no tiene foto.')


def _marca(foto):
    return None if foto is None else foto.hash[:12]


@transaction.atomic
def guardar_foto(articulo, archivo, usuario, motivo=''):
    """Agrega o reemplaza la foto. El motivo es opcional la primera vez y obligatorio
    al reemplazar (DEC-004). Todo cambio queda en la bitácora (sin los bytes: solo
    una huella corta)."""
    articulo = Articulo.objects.select_for_update().get(pk=articulo.pk)
    actual = ArticuloFoto.objects.filter(articulo=articulo).first()
    motivo = (motivo or '').strip()
    if actual and not motivo:
        raise ValidationError({'motivo': 'Indique el motivo para reemplazar la foto.'})
    contenido = _procesar(archivo)
    huella = hashlib.sha256(contenido).hexdigest()
    if actual and actual.hash == huella:
        raise ValidationError({'foto': 'Esa es la misma foto que ya tiene el artículo.'})
    anterior = {'foto': _marca(actual)}
    ArticuloFoto.objects.update_or_create(
        articulo=articulo,
        defaults={'imagen': contenido, 'tipo_mime': 'image/jpeg', 'hash': huella,
                  'fecha': timezone.now()})
    registrar(usuario, 'articulos', 'UPDATE', articulo, anterior=anterior,
              nuevo={'foto': huella[:12]}, motivo=(motivo or 'Foto agregada')[:255])
    return articulo


@transaction.atomic
def quitar_foto(articulo, usuario, motivo=''):
    articulo = Articulo.objects.select_for_update().get(pk=articulo.pk)
    actual = ArticuloFoto.objects.filter(articulo=articulo).first()
    if actual is None:
        raise ValidationError({'detalle': 'El artículo no tiene foto.'})
    motivo = (motivo or '').strip()
    if not motivo:
        raise ValidationError({'motivo': 'Indique el motivo para quitar la foto.'})
    anterior = {'foto': _marca(actual)}
    actual.delete()
    registrar(usuario, 'articulos', 'UPDATE', articulo, anterior=anterior,
              nuevo={'foto': None}, motivo=motivo[:255])
    return articulo
