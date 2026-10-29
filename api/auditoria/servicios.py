"""Escritura en la bitácora (RF-21)."""
import json

from auditoria.models import Bitacora

EXCLUIDOS = {'password'}


def datos_de(instancia):
    """Valores actuales del registro, listos para guardarse como JSON."""
    resultado = {}
    for campo in instancia._meta.concrete_fields:
        if campo.name in EXCLUIDOS:
            continue
        resultado[campo.name] = getattr(instancia, campo.attname)
    return json.loads(json.dumps(resultado, default=str))


def registrar(usuario, modulo, accion, instancia, anterior=None, nuevo=None, motivo=None):
    """Guarda una fila. En UPDATE solo se guardan los campos que cambiaron."""
    if accion == 'UPDATE' and anterior is not None and nuevo is not None:
        cambios = [c for c in nuevo if anterior.get(c) != nuevo[c]]
        anterior = {c: anterior.get(c) for c in cambios}
        nuevo = {c: nuevo[c] for c in cambios}
    return Bitacora.objects.create(
        usuario=usuario, modulo=modulo, accion=accion,
        tabla_afectada=instancia._meta.db_table, registro_id=str(instancia.pk),
        valor_anterior=None if anterior is None else json.dumps(anterior, ensure_ascii=False),
        valor_nuevo=None if nuevo is None else json.dumps(nuevo, ensure_ascii=False),
        motivo=motivo or None)
