"""Registros que nunca se editan ni se borran (RNF-06, RNF-07).

La protección vive en Django: bloquea `save()` sobre un registro existente,
`delete()` y las operaciones masivas `update()` / `delete()` / `bulk_update()`.
No impide que alguien con acceso directo a MySQL modifique las filas; si se
quiere ese nivel, habría que agregar triggers (decisión pendiente del equipo).
"""
from django.db import models


class RegistroInmutable(Exception):
    """Se intentó editar o borrar un registro de historial."""


class InmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RegistroInmutable('Los registros de historial no se pueden editar.')

    def delete(self):
        raise RegistroInmutable('Los registros de historial no se pueden borrar.')


class InmutableModel(models.Model):
    objects = InmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroInmutable('Los registros de historial no se pueden editar.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInmutable('Los registros de historial no se pueden borrar.')
