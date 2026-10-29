from django.db import transaction
from rest_framework.exceptions import ValidationError

from auditoria.servicios import datos_de, registrar


class BitacoraMixin:
    """Registra en la bitácora cada alta y cada modificación hecha por la API,
    en la misma transacción. Toda modificación exige `motivo` (RNF-06).
    Sin DELETE: los registros se desactivan con `activo`."""

    modulo = ''
    http_method_names = ['get', 'post', 'patch', 'put', 'head', 'options']

    @transaction.atomic
    def perform_create(self, serializer):
        instancia = serializer.save()
        registrar(self.request.user, self.modulo, 'INSERT', instancia,
                  nuevo=datos_de(instancia))

    @transaction.atomic
    def perform_update(self, serializer):
        motivo = str(self.request.data.get('motivo') or '').strip()
        if not motivo:
            raise ValidationError({'motivo': 'Indique el motivo del cambio.'})
        anterior = datos_de(serializer.instance)
        instancia = serializer.save()
        registrar(self.request.user, self.modulo, 'UPDATE', instancia,
                  anterior=anterior, nuevo=datos_de(instancia), motivo=motivo[:255])
