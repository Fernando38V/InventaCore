"""Errores de validación como {campo: mensaje} (RNF-09)."""
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler


def _aplanar(detalle):
    if isinstance(detalle, dict):
        return {campo: _aplanar(valor) for campo, valor in detalle.items()}
    if isinstance(detalle, (list, tuple)):
        primero = detalle[0] if detalle else ''
        return _aplanar(primero) if isinstance(primero, (dict, list, tuple)) else str(primero)
    return str(detalle)


def manejador_de_errores(exc, contexto):
    respuesta = exception_handler(exc, contexto)
    if respuesta is None:
        return None
    if isinstance(exc, ValidationError):
        datos = _aplanar(exc.detail)
        respuesta.data = datos if isinstance(datos, dict) else {'detalle': datos}
    return respuesta
