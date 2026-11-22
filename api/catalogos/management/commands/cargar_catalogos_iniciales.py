"""Carga los catálogos base del CONALEP Tijuana II (categorías, tipos y
ubicaciones) desde los CSV de catalogos/datos/. Es idempotente: lo que ya
existe (mismo nombre) se omite, y nunca modifica ni desactiva registros.
Los códigos los genera el sistema (DEC-015).

Uso:  python manage.py cargar_catalogos_iniciales [--simular]
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalogos.codigos import siguiente_codigo
from catalogos.models import Categoria, TipoArticulo, Ubicacion

DATOS = Path(__file__).resolve().parents[2] / 'datos'


def _leer(nombre):
    ruta = DATOS / nombre
    if not ruta.exists():
        raise CommandError('Falta el archivo %s' % ruta)
    with open(ruta, newline='', encoding='utf-8-sig') as f:
        return [{k: (v or '').strip() for k, v in fila.items()} for fila in csv.DictReader(f)]


class Command(BaseCommand):
    help = 'Carga categorías, tipos de artículo y ubicaciones iniciales (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true',
                            help='Muestra qué se crearía y deshace todo al final.')

    def handle(self, *args, **opciones):
        resumen = {}
        with transaction.atomic():
            creadas = existentes = 0
            categorias = {}
            for f in _leer('categorias.csv'):
                obj = Categoria.objects.filter(nombre__iexact=f['nombre']).first()
                if obj:
                    existentes += 1
                else:
                    obj = Categoria.objects.create(
                        codigo=siguiente_codigo(Categoria, 'CAT'), nombre=f['nombre'])
                    creadas += 1
                categorias[f['nombre']] = obj
            resumen['Categorías'] = (creadas, existentes)

            creadas = existentes = 0
            for f in _leer('tipos_articulo.csv'):
                cat = categorias.get(f['categoria']) or \
                    Categoria.objects.filter(nombre__iexact=f['categoria']).first()
                if not cat:
                    raise CommandError('Categoría inexistente: %s' % f['categoria'])
                if TipoArticulo.objects.filter(categoria=cat, nombre__iexact=f['nombre']).exists():
                    existentes += 1
                else:
                    TipoArticulo.objects.create(
                        codigo=siguiente_codigo(TipoArticulo, 'TIP'),
                        nombre=f['nombre'], categoria=cat)
                    creadas += 1
            resumen['Tipos de artículo'] = (creadas, existentes)

            creadas = existentes = 0
            for f in _leer('ubicaciones.csv'):
                if Ubicacion.objects.filter(nombre__iexact=f['nombre']).exists():
                    existentes += 1
                else:
                    Ubicacion.objects.create(
                        codigo=siguiente_codigo(Ubicacion, 'UBI'), nombre=f['nombre'])
                    creadas += 1
            resumen['Ubicaciones'] = (creadas, existentes)

            if opciones['simular']:
                transaction.set_rollback(True)

        for nombre, (c, e) in resumen.items():
            self.stdout.write('%s: %d creadas, %d ya existían' % (nombre, c, e))
        if opciones['simular']:
            self.stdout.write(self.style.WARNING('Simulación: no se guardó nada.'))
