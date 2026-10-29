from django.db import migrations

# RF-01, RF-02: los dos roles del sistema. Las claves ADMIN y CONT son fijas.
ROLES = [
    ('ADMIN', 'Administrador',
     'Control total: altas, bajas y movimientos. Único rol que crea cuentas y consulta la bitácora'),
    ('CONT', 'Contadora',
     'Consulta el inventario y edita datos puntuales. No da de alta equipo ni ejecuta bajas'),
]


def cargar(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    for clave, nombre, descripcion in ROLES:
        Rol.objects.get_or_create(
            clave=clave,
            defaults={'nombre': nombre, 'descripcion': descripcion},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
