"""Códigos de catálogo generados por el sistema (DEC-015).

El usuario nunca escribe un código: se arma PREFIJO-NNN con el siguiente
número libre (DEP-002, CAT-001, TIP-001, UBI-004). Los códigos que ya existen
con otra forma (DEP-INF, UBI-OFI...) no estorban: solo cuentan los numéricos.
"""
import re

from django.db import transaction

from catalogos.models import ContadorFolio


def siguiente_codigo(modelo, prefijo):
    """Llamar dentro de la misma transacción que guarda el registro."""
    patron = re.compile(r'^%s-(\d+)$' % re.escape(prefijo))
    with transaction.atomic():
        contador, creado = ContadorFolio.objects.select_for_update().get_or_create(
            clave='COD-%s' % prefijo)
        if creado:
            numeros = [int(m.group(1)) for m in
                       (patron.match(c) for c in modelo.objects.values_list('codigo', flat=True))
                       if m]
            contador.ultimo = max(numeros, default=0)
        contador.ultimo += 1
        contador.save(update_fields=['ultimo'])
        return '%s-%03d' % (prefijo, contador.ultimo)


class CodigoAutomatico:
    """Mixin de ModelSerializer: `codigo` es solo lectura y se genera al crear.
    Cada serializador define `prefijo_codigo`."""

    prefijo_codigo = None

    def get_extra_kwargs(self):
        extra = super().get_extra_kwargs()
        extra.setdefault('codigo', {})['read_only'] = True
        return extra

    def create(self, datos):
        datos['codigo'] = siguiente_codigo(self.Meta.model, self.prefijo_codigo)
        # Un formulario HTML que omite el checkbox llega como False; al crear,
        # lo no indicado es "activo".
        if 'activo' in self.fields and 'activo' not in self.initial_data:
            datos['activo'] = True
        return super().create(datos)
