"""Pequeñas ayudas para que el mismo código funcione en Django 4.2 y 5.x."""
from django.db import models


def restriccion_check(condicion, nombre):
    """CheckConstraint: Django 4.2 usa `check=`; desde 5.1 se llama `condition=`
    (y en 6.0 `check=` desaparece)."""
    try:
        return models.CheckConstraint(condition=condicion, name=nombre)
    except TypeError:
        return models.CheckConstraint(check=condicion, name=nombre)
