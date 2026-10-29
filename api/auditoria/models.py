from django.conf import settings
from django.db import models
from django.utils import timezone

from api.inmutable import InmutableModel


class Bitacora(InmutableModel):
    """Registro inalterable de cada acción relevante (RF-21, RNF-06, RNF-07).

    `valor_anterior` y `valor_nuevo` guardan un JSON con los campos que
    cambiaron. `tabla_afectada` y `registro_id` no son llaves foráneas: la
    bitácora apunta a cualquier tabla. `motivo` es obligatorio en la API
    para las correcciones.
    """

    ACCIONES = [('INSERT', 'Alta'), ('UPDATE', 'Modificación'), ('DELETE', 'Baja lógica')]

    num = models.AutoField(primary_key=True)
    fecha_hora = models.DateTimeField(default=timezone.now, editable=False)
    modulo = models.CharField(max_length=50)
    accion = models.CharField(max_length=20, choices=ACCIONES)
    tabla_afectada = models.CharField(max_length=50)
    registro_id = models.CharField(max_length=50)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)
    motivo = models.CharField(max_length=255, null=True, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        db_column='usuario', related_name='bitacora')

    class Meta:
        db_table = 'bitacora'
        ordering = ['-fecha_hora', '-num']
        verbose_name = 'registro de bitácora'
        verbose_name_plural = 'bitácora'
        indexes = [
            models.Index(fields=['tabla_afectada', 'registro_id'],
                         name='ix_bitacora_registro'),
            models.Index(fields=['fecha_hora'], name='ix_bitacora_fecha'),
        ]

    def __str__(self):
        return '%s %s %s' % (self.accion, self.tabla_afectada, self.registro_id)
