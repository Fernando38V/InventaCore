"""Filtros del inventario, compartidos por la lista, la exportación y los reportes."""
from django.db.models import Q

from articulos.models import Articulo


def con_relaciones(consulta):
    return consulta.select_related(
        'tipo_articulo__categoria', 'origen', 'ubicacion', 'resguardante',
        'estado_operativo', 'estado_registro')


def filtrar_articulos(consulta, p):
    """`p` son los parámetros de la URL: categoria, tipo_articulo, ubicacion,
    estado_operativo, estado_registro, origen, resguardante y q (cada palabra
    debe aparecer en algún campo)."""
    for parametro, campo in (
            ('categoria', 'tipo_articulo__categoria_id'), ('tipo_articulo', 'tipo_articulo_id'),
            ('ubicacion', 'ubicacion_id'), ('estado_operativo', 'estado_operativo_id'),
            ('estado_registro', 'estado_registro_id'), ('origen', 'origen_id'),
            ('resguardante', 'resguardante_id')):
        if p.get(parametro):
            consulta = consulta.filter(**{campo: p[parametro]})
    for palabra in (p.get('q') or '').split():
        consulta = consulta.filter(
            Q(marbete_oficial__icontains=palabra) | Q(folio_interno__icontains=palabra)
            | Q(marca__icontains=palabra) | Q(modelo__icontains=palabra)
            | Q(num_serie__icontains=palabra) | Q(descripcion__icontains=palabra)
            | Q(color__icontains=palabra)
            | Q(tipo_articulo__nombre__icontains=palabra)
            | Q(tipo_articulo__categoria__nombre__icontains=palabra)
            | Q(ubicacion__nombre__icontains=palabra)
            | Q(resguardante__nombre_pila__icontains=palabra)
            | Q(resguardante__primer_apellido__icontains=palabra)
            | Q(resguardante__segundo_apellido__icontains=palabra)
            | Q(resguardante__numero_empleado__icontains=palabra))
    return consulta


def inventario(params):
    return filtrar_articulos(con_relaciones(Articulo.objects.all()), params)
