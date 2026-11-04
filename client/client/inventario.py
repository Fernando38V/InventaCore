"""Ayudas compartidas por las pantallas de equipos (artículos) y movimientos."""
from client.utils import listar_todo

UBICACION_NOLOC = 'UBI-NOLOC'     # DEC-012: ubicación y estado No localizado van juntos
ESTADO_NOLOC = 'NOLOC'
SIN_ESPECIFICAR = 'Sin especificar'


def opciones_catalogo(request, ruta, actual='', solo_activos=False):
    """[{'codigo', 'nombre'}] de un catálogo de la API.

    Para filtros se devuelven todos. En formularios (`solo_activos`) solo los
    activos, más el valor actual aunque ya esté inactivo. Los catálogos fijos
    (orígenes, estados) no traen `activo`: cuentan como activos.
    """
    opciones = []
    for fila in listar_todo(request, ruta):
        activo = fila.get('activo', True)
        if solo_activos and not activo and fila['codigo'] != actual:
            continue
        nombre = fila['nombre'] if activo else fila['nombre'] + ' (inactivo)'
        opciones.append({'codigo': fila['codigo'], 'nombre': nombre})
    return opciones


def opciones_personal(request, actual=''):
    """Personal activo para elegir resguardante: [{'valor', 'texto'}]."""
    opciones = []
    for p in listar_todo(request, 'personal'):
        valor = str(p['num'])
        if not p['activo'] and valor != str(actual):
            continue
        texto = '%s — %s' % (p['numero_empleado'], p['nombre_completo'])
        opciones.append({'valor': valor,
                         'texto': texto if p['activo'] else texto + ' (inactivo)'})
    return sorted(opciones, key=lambda o: o['texto'].lower())


def opciones_tipos(request, actual=''):
    """Tipos de artículo activos de categorías activas, con su categoría.

    Devuelve (categorias, tipos) para el select en cascada del alta: primero
    se elige la categoría y luego uno de sus tipos.
    """
    categorias = [c for c in listar_todo(request, 'categorias', activo='true')]
    codigos = {c['codigo'] for c in categorias}
    tipos = []
    for t in listar_todo(request, 'tipos-articulo', activo='true'):
        if t['categoria'] in codigos or t['codigo'] == actual:
            tipos.append({'codigo': t['codigo'], 'nombre': t['nombre'],
                          'categoria': t['categoria']})
    return ([{'codigo': c['codigo'], 'nombre': c['nombre']} for c in categorias],
            sorted(tipos, key=lambda t: t['nombre'].lower()))


def nombre_articulo(articulo):
    """Marca y modelo si existen; si no, la descripción (siempre obligatoria)."""
    texto = ' '.join(p for p in (articulo.get('marca'), articulo.get('modelo')) if p)
    return texto or articulo.get('descripcion') or SIN_ESPECIFICAR


def resumen_movimiento(m):
    """Frase corta de lo que cambió en un movimiento (para la ficha)."""
    partes = []
    origen, llegada = m.get('ubicacion_origen'), m.get('ubicacion_llegada')
    asigna, entrega = m.get('personal_asigna'), m.get('personal_entrega')
    if llegada and origen is None:
        partes.append('Ubicación: %s' % llegada['nombre'])
    elif llegada and origen['codigo'] != llegada['codigo']:
        partes.append('%s → %s' % (origen['nombre'], llegada['nombre']))
    if entrega and asigna:
        partes.append('Resguardante: %s → %s' % (entrega['nombre'], asigna['nombre']))
    elif origen is None and asigna:
        partes.append('Resguardante: %s' % asigna['nombre'])
    return ' · '.join(partes)
