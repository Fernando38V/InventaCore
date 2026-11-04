"""PEND-001 / DEC-016: el resguardo deja de ser 1:1 con el movimiento.

RESGUARDO (folio, fecha de emisión, resguardante, usuario emisor, ruta del PDF
única, hash) y RESGUARDO_DETALLE (movimiento único). Ningún código creaba
filas en la tabla anterior; si alguien las cargó a mano, la migración se
detiene para no perderlas.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def verificar_tabla_vacia(apps, schema_editor):
    if apps.get_model('movimientos', 'Resguardo').objects.exists():
        raise RuntimeError(
            'La tabla resguardo tiene filas del diseño anterior (1:1 con movimiento). '
            'Revísalas antes de migrar: este cambio recrea la tabla.')


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0001_initial'),
        ('movimientos', '0003_sin_baja'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(verificar_tabla_vacia, migrations.RunPython.noop),
        migrations.DeleteModel(name='Resguardo'),
        migrations.CreateModel(
            name='Resguardo',
            fields=[
                ('folio', models.CharField(max_length=20, primary_key=True, serialize=False)),
                ('fecha_emision', models.DateTimeField(
                    default=django.utils.timezone.now, editable=False)),
                ('ruta_pdf', models.CharField(max_length=255, unique=True)),
                ('hash_pdf', models.CharField(max_length=64)),
                ('resguardante', models.ForeignKey(
                    db_column='resguardante', on_delete=django.db.models.deletion.PROTECT,
                    related_name='resguardos', to='personal.personal')),
                ('usuario_emisor', models.ForeignKey(
                    db_column='usuario_emisor', on_delete=django.db.models.deletion.PROTECT,
                    related_name='resguardos_emitidos', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'resguardo',
                'verbose_name_plural': 'resguardos',
                'db_table': 'resguardo',
                'ordering': ['-fecha_emision', '-folio'],
            },
        ),
        migrations.CreateModel(
            name='ResguardoDetalle',
            fields=[
                ('num', models.AutoField(primary_key=True, serialize=False)),
                ('movimiento', models.OneToOneField(
                    db_column='movimiento', on_delete=django.db.models.deletion.PROTECT,
                    related_name='detalle_resguardo', to='movimientos.movimiento')),
                ('resguardo', models.ForeignKey(
                    db_column='resguardo', on_delete=django.db.models.deletion.PROTECT,
                    related_name='detalles', to='movimientos.resguardo')),
            ],
            options={
                'verbose_name': 'detalle de resguardo',
                'verbose_name_plural': 'detalles de resguardo',
                'db_table': 'resguardo_detalle',
                'ordering': ['num'],
            },
        ),
    ]
