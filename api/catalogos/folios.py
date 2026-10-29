"""Generación de folios.

Folio interno (Comodato y Enser): 02143 + mes (2) + año (2) + "-" + consecutivo
de 3 dígitos. Ejemplo: 021431026-001 es el primer artículo de octubre de 2026.
El consecutivo se reinicia cada mes y va de 001 a 999. Los Activos no llevan
folio: se identifican por marbete.

Movimiento: MOV-0001, MOV-0002... Resguardo: RES-0001...

Llamar SIEMPRE dentro del mismo `transaction.atomic()` que guarda el registro:
si el guardado falla, el número no se consume y no quedan huecos.
"""
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from catalogos.models import ContadorFolio

PREFIJO_FOLIO_INTERNO = '02143'
MAXIMO_POR_MES = 999


class FolioAgotado(Exception):
    """Se alcanzó el máximo de folios internos del mes."""


def _siguiente(clave):
    with transaction.atomic():
        ContadorFolio.objects.get_or_create(clave=clave)
        contador = ContadorFolio.objects.select_for_update().get(clave=clave)
        contador.ultimo = F('ultimo') + 1
        contador.save(update_fields=['ultimo'])
        contador.refresh_from_db()
        return contador.ultimo


def siguiente_folio_interno(ahora=None):
    """Folio del mes y año locales en que se hace el registro (zona horaria
    del proyecto), no de la fecha de adquisición."""
    ahora = timezone.localtime(ahora or timezone.now())
    periodo = ahora.strftime('%m%y')
    prefijo = getattr(settings, 'FOLIO_PREFIJO', PREFIJO_FOLIO_INTERNO)
    with transaction.atomic():
        numero = _siguiente('FI-%s' % periodo)
        if numero > MAXIMO_POR_MES:
            raise FolioAgotado(
                'Se alcanzó el máximo de %d folios internos para este mes.' % MAXIMO_POR_MES)
    return '%s%s-%03d' % (prefijo, periodo, numero)


def siguiente_folio_movimiento():
    return 'MOV-%04d' % _siguiente('MOV')


def siguiente_folio_resguardo():
    return 'RES-%04d' % _siguiente('RES')
