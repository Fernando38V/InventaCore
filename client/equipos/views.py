from django.shortcuts import render


def detalle_equipo(request, num):
    """M2 — Detalle de Equipo (mockup).

    Campos alineados al esquema real de Adad (bloque EQUIPO del script SQL).
    Se reemplaza por datos reales cuando exista:
    GET /api/equipos/<num>/
    """
    equipo = {
        'num': num,
        'marbete_oficial': '02-520-00003',
        'folio_interno': 'E-02-520-0178',
        'marca': 'Dell',
        'modelo': 'OptiPlex 3080',
        'num_serie': 'MXL2301A9K',
        'color': 'Negro',
        'descripcion': 'Equipo asignado al área de desarrollo de software. '
                        'Sin incidencias reportadas desde su alta.',
        'fecha_adquisicion': '03/02/2024',
        'costo_adquisicion': '13,450.00',
        'fecha_alta': '03/02/2024',
        'categoria': 'Computadora de escritorio',
        'ubicacion': 'Laboratorio 2 — Informática',
        'resguardante': 'Ing. Carlos Pérez Ramírez',
        'origen': 'Compra directa',
        'estado_operativo': 'Operando',
        'estado_registro': 'Activo',
    }

    movimientos = [
        {'tipo': 'Alta', 'fecha': '03/02/2024', 'detalle': 'Registro inicial en el sistema.', 'usuario': 'Admin'},
        {'tipo': 'Asignación', 'fecha': '10/02/2024', 'detalle': 'Asignado a Laboratorio 1 — Ing. Marco Díaz.', 'usuario': 'Admin'},
        {'tipo': 'Transferencia', 'fecha': '14/08/2025', 'detalle': 'Transferido a Laboratorio 2 — Ing. Carlos Pérez.', 'usuario': 'Admin'},
    ]

    return render(request, 'equipos/detalle.html', {
        'equipo': equipo,
        'movimientos': movimientos,
    })


def listado_equipos(request):
    """Listado de equipos (versión mínima para navegar).

    Placeholder funcional: permite llegar a los detalles de prueba.
    El listado real con filtros y paginación se construye en M6.
    """
    equipos = [
        {'num': 1, 'marca': 'Dell', 'modelo': 'OptiPlex 3080',
         'marbete_oficial': '02-520-00003', 'folio_interno': 'E-02-520-0178',
         'ubicacion': 'Laboratorio 2 — Informática', 'estado_registro': 'Activo'},
        {'num': 2, 'marca': 'HP', 'modelo': 'ProDesk 400 G7',
         'marbete_oficial': '02-520-00004', 'folio_interno': 'E-02-520-0179',
         'ubicacion': 'Laboratorio 1 — Informática', 'estado_registro': 'Activo'},
        {'num': 3, 'marca': 'Lenovo', 'modelo': 'ThinkCentre M70q',
         'marbete_oficial': '02-520-00005', 'folio_interno': 'E-02-520-0180',
         'ubicacion': 'Dirección Académica', 'estado_registro': 'Activo'},
    ]
    return render(request, 'equipos/listado.html', {'equipos': equipos})