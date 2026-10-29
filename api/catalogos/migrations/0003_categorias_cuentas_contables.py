from django.db import migrations, models

# Cambio de alcance: el inventario es de todo el plantel y `categoria` guarda
# el "Nombre de la cuenta" contable. Catálogo extensible: se pueden agregar más
# desde el sistema; estas son solo las cuentas conocidas al arrancar.
CUENTAS = [
    ('CAT-001', 'VEHÍCULOS Y EQUIPOS DE TRANSPORTE'),
    ('CAT-002', 'MUEBLES DE OFICINA Y ESTANTERÍA'),
    ('CAT-003', 'EQUIPOS Y APARATOS AUDIOVISUALES'),
    ('CAT-004', 'EQUIPO MÉDICO Y DE LABORATORIO'),
    ('CAT-005', 'OTROS EQUIPOS'),
    ('CAT-006', 'OTROS MOBILIARIOS Y EQUIPOS DE ADMINISTRACIÓN'),
    ('CAT-007', 'MAQUINARIA Y EQUIPO INDUSTRIAL'),
]

# Las 7 categorías de equipo electrónico del alcance anterior.
CATEGORIAS_ANTERIORES = [
    'CAT-MON', 'CAT-PCE', 'CAT-LAP', 'CAT-TIP', 'CAT-SWT', 'CAT-ALT', 'CAT-SRV']


def cargar(apps, schema_editor):
    Categoria = apps.get_model('catalogos', 'Categoria')
    # Aún no existen artículos, así que no hay nada que las use.
    Categoria.objects.filter(codigo__in=CATEGORIAS_ANTERIORES).delete()
    for codigo, nombre in CUENTAS:
        Categoria.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0002_catalogos_iniciales'),
    ]

    operations = [
        migrations.AlterField(
            model_name='categoria',
            name='nombre',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
