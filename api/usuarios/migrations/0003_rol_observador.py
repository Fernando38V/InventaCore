from django.db import migrations

# La contadora pasa a ser Administradora: el rol CONT desaparece y se agrega
# OBS (Observador), que solo consulta (inventario, movimientos, bitácora...).


def cambiar(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Usuario = apps.get_model('usuarios', 'Usuario')
    Rol.objects.get_or_create(clave='OBS', defaults={
        'nombre': 'Observador',
        'descripcion': 'Solo consulta: inventario, movimientos, bitácora y reportes. No edita ni cambia nada'})
    admin = Rol.objects.get(clave='ADMIN')
    Usuario.objects.filter(rol_id='CONT').update(rol=admin)
    Rol.objects.filter(clave='CONT').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_roles_iniciales'),
    ]

    operations = [
        migrations.RunPython(cambiar, migrations.RunPython.noop),
    ]
