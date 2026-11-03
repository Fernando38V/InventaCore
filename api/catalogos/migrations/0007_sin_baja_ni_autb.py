from django.db import migrations

# DEC-006 y DEC-012 (01/11/2026): ya no existe el movimiento BAJA ni el estado
# "Autorizado para baja". Obsoleto equivale a lo que la institución llama baja.
DESCRIPCION_NOLOC = (
    'Ubicación temporal para artículo no localizado en una revisión. '
    'Se llega con una reubicación (REUB) con motivo documentado')


def aplicar(apps, schema_editor):
    Articulo = apps.get_model('articulos', 'Articulo')
    Movimiento = apps.get_model('movimientos', 'Movimiento')
    TipoMovimiento = apps.get_model('catalogos', 'TipoMovimiento')
    EstadoOperativo = apps.get_model('catalogos', 'EstadoOperativo')
    Ubicacion = apps.get_model('catalogos', 'Ubicacion')

    if Movimiento.objects.filter(tipo_movimiento='BAJA').exists():
        raise RuntimeError(
            'Hay movimientos BAJA registrados y el historial no se borra. '
            'Revise esos movimientos antes de aplicar esta migración.')
    TipoMovimiento.objects.filter(codigo='BAJA').delete()

    Articulo.objects.filter(estado_operativo='AUTB').update(estado_operativo='OBS')
    EstadoOperativo.objects.filter(codigo='AUTB').delete()

    Ubicacion.objects.filter(codigo='UBI-NOLOC').update(descripcion=DESCRIPCION_NOLOC)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0006_baja_y_categorias_vacias'),
        ('articulos', '0003_alinear_con_decisiones'),
        ('movimientos', '0002_requiere_resguardo_y_baja'),
    ]

    operations = [
        migrations.RunPython(aplicar, migrations.RunPython.noop),
    ]
