from django.db import migrations

# DEC-001: el rol se llama CONSULTA (antes OBS, Observador).


def renombrar(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Usuario = apps.get_model('usuarios', 'Usuario')
    consulta, _ = Rol.objects.get_or_create(clave='CONSULTA', defaults={
        'nombre': 'Consulta',
        'descripcion': 'Dashboard, consultas, historial, resguardos y reportes PDF. No modifica nada ni ve la bitácora'})
    Usuario.objects.filter(rol_id='OBS').update(rol=consulta)
    Rol.objects.filter(clave='OBS').delete()
    Rol.objects.filter(clave='ADMIN').update(
        descripcion='Todo, incluida la bitácora y administrar usuarios')


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_rol_observador'),
    ]

    operations = [
        migrations.RunPython(renombrar, migrations.RunPython.noop),
    ]
