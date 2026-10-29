from django.db import migrations

# RF-14: solo Informática viene precargado. Los demás departamentos se
# agregan desde el sistema.
DEPARTAMENTOS = [
    ('DEP-INF', 'Informática', 'Departamento al que pertenecen las ubicaciones del alcance'),
]


def cargar(apps, schema_editor):
    Departamento = apps.get_model('personal', 'Departamento')
    for codigo, nombre, descripcion in DEPARTAMENTOS:
        Departamento.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'descripcion': descripcion},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
