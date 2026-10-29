from django.db import migrations

# DEC-006: el movimiento BAJA existe. Las categorías arrancan vacías (27/10/2026):
# se quitan las 7 que sembró la migración 0003 si nada las usa.
CATEGORIAS_SEMBRADAS = ['CAT-%03d' % n for n in range(1, 8)]


def aplicar(apps, schema_editor):
    TipoMovimiento = apps.get_model('catalogos', 'TipoMovimiento')
    Categoria = apps.get_model('catalogos', 'Categoria')
    TipoMovimiento.objects.get_or_create(codigo='BAJA', defaults={'nombre': 'Baja'})
    TipoMovimiento.objects.filter(codigo='ALTA').update(nombre='Alta de artículo')
    Categoria.objects.filter(
        codigo__in=CATEGORIAS_SEMBRADAS, tipos__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0005_contadorfolio'),
    ]

    operations = [
        migrations.RunPython(aplicar, migrations.RunPython.noop),
    ]
