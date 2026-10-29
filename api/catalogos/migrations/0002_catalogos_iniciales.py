from django.db import migrations

# RF-04: las 7 categorías confirmadas.
CATEGORIAS = [
    ('CAT-MON', 'Monitor', 'Monitor de cualquier tipo'),
    ('CAT-PCE', 'Computadora de escritorio', 'Equipo de cómputo fijo'),
    ('CAT-LAP', 'Laptop', 'Equipo de cómputo portátil'),
    ('CAT-TIP', 'Teléfono IP', 'Teléfono de voz sobre IP'),
    ('CAT-SWT', 'Switch', 'Conmutador de red'),
    ('CAT-ALT', 'Altavoz de entrada', 'Bocina o altavoz de acceso'),
    ('CAT-SRV', 'Servidor físico', 'Servidor de gabinete o torre'),
]

# Catálogo fijo (RF-06): los códigos ACT, COM y ENS no deben cambiar.
ORIGENES = [
    ('ACT', 'Activo', 'Bien patrimonial del gobierno del estado, identificado por marbete SAACG.NET'),
    ('COM', 'Comodato', 'Bien recibido en comodato, identificado por folio interno del plantel'),
    ('ENS', 'Enser', 'Bien menor del plantel, identificado por folio interno'),
]

# Los estados del frontend. NOLOC va siempre junto con la ubicación UBI-NOLOC.
# AUTB (Autorizado para baja) es el estado de baja de RF-10.
ESTADOS_OPERATIVOS = [
    ('UTIL', 'Útil'),
    ('OBS', 'Obsoleto'),
    ('AUTB', 'Autorizado para baja'),
    ('NOLOC', 'No localizado'),
]

ESTADOS_REGISTRO = [
    ('PEND', 'Pendiente'),
    ('REG', 'Registrado'),
    ('DON', 'Donado'),
]

TIPOS_MOVIMIENTO = [
    ('ALTA', 'Alta de equipo'),
    ('REUB', 'Reubicación y/o cambio de resguardante'),
    ('REPA', 'Envío a reparación'),
    ('RETE', 'Retorno de reparación'),
]

# RF-11: oficina y dos laboratorios, más la ubicación de equipo no localizado.
# El responsable queda vacío hasta confirmar el nombre del jefe de Informática.
UBICACIONES = [
    ('UBI-OFI', 'Oficina de Informática',
     'Oficina del Departamento de Informática'),
    ('UBI-LAB1', 'Laboratorio de Informática 1', 'Laboratorio de cómputo 1'),
    ('UBI-LAB2', 'Laboratorio de Informática 2', 'Laboratorio de cómputo 2'),
    ('UBI-NOLOC', 'Sin ubicar / No localizado',
     'Equipo no localizado en una revisión. Se llega con un movimiento REUB con motivo; el estado pasa a No localizado'),
]


def cargar(apps, schema_editor):
    Categoria = apps.get_model('catalogos', 'Categoria')
    Origen = apps.get_model('catalogos', 'Origen')
    EstadoOperativo = apps.get_model('catalogos', 'EstadoOperativo')
    EstadoRegistro = apps.get_model('catalogos', 'EstadoRegistro')
    TipoMovimiento = apps.get_model('catalogos', 'TipoMovimiento')
    Ubicacion = apps.get_model('catalogos', 'Ubicacion')

    for codigo, nombre, descripcion in CATEGORIAS:
        Categoria.objects.get_or_create(
            codigo=codigo, defaults={'nombre': nombre, 'descripcion': descripcion})
    for codigo, nombre, descripcion in ORIGENES:
        Origen.objects.get_or_create(
            codigo=codigo, defaults={'nombre': nombre, 'descripcion': descripcion})
    for codigo, nombre in ESTADOS_OPERATIVOS:
        EstadoOperativo.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre in ESTADOS_REGISTRO:
        EstadoRegistro.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre in TIPOS_MOVIMIENTO:
        TipoMovimiento.objects.get_or_create(codigo=codigo, defaults={'nombre': nombre})
    for codigo, nombre, descripcion in UBICACIONES:
        Ubicacion.objects.get_or_create(
            codigo=codigo, defaults={'nombre': nombre, 'descripcion': descripcion})


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(cargar, migrations.RunPython.noop),
    ]
