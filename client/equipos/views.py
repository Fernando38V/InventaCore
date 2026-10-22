from django.shortcuts import render
from django.core.paginator import Paginator
from django.shortcuts import redirect, reverse
from datetime import date, datetime


# ============================================================
# Catálogos — mismos códigos que InventaCore_db.sql
# ============================================================

CATEGORIAS = [
    {'codigo': 'CAT-MON', 'nombre': 'Monitor'},
    {'codigo': 'CAT-PCE', 'nombre': 'Computadora de escritorio'},
    {'codigo': 'CAT-LAP', 'nombre': 'Laptop'},
    {'codigo': 'CAT-TIP', 'nombre': 'Teléfono IP'},
    {'codigo': 'CAT-SWT', 'nombre': 'Switch'},
    {'codigo': 'CAT-ALT', 'nombre': 'Altavoz de entrada'},
    {'codigo': 'CAT-SRV', 'nombre': 'Servidor físico'},
]

UBICACIONES = [
    {'codigo': 'UBI-OFI', 'nombre': 'Oficina de Informática'},
    {'codigo': 'UBI-LAB1', 'nombre': 'Laboratorio 1'},
    {'codigo': 'UBI-LAB2', 'nombre': 'Laboratorio 2'},
    {'codigo': 'UBI-NOLOC', 'nombre': 'Sin ubicar / No localizado'},
]

ORIGENES = [
    {'codigo': 'ACT', 'nombre': 'Activo'},
    {'codigo': 'COM', 'nombre': 'Comodato'},
    {'codigo': 'ENS', 'nombre': 'Enser'},
]

ESTADOS_OPERATIVOS = [
    {'codigo': 'UTIL', 'nombre': 'Útil'},
    {'codigo': 'OBS', 'nombre': 'Obsoleto'},
    {'codigo': 'AUTB', 'nombre': 'Autorizado para baja'},
    {'codigo': 'NOLOC', 'nombre': 'No localizado'},
]

ESTADOS_REGISTRO = [
    {'codigo': 'REG', 'nombre': 'Registrado'},
    {'codigo': 'PEND', 'nombre': 'Pendiente'},
    {'codigo': 'DON', 'nombre': 'Donado'},
]

_CAT = {c['codigo']: c['nombre'] for c in CATEGORIAS}
_UBI = {u['codigo']: u['nombre'] for u in UBICACIONES}
_ORI = {o['codigo']: o['nombre'] for o in ORIGENES}

_PERSONAL = {
    'Juan Pérez Vázquez': 1012,
    'María Elena Ruiz Soto': 1043,
    'Carlos Alberto Méndez Ríos': 1057,
    'Ana Karen Villalobos Pérez': 1068,
    'Diana Laura Espinoza Núñez': 1074,
}

_NOMBRE_OPERATIVO = {'UTIL': 'Útil', 'OBS': 'Obsoleto',
                     'AUTB': 'Autorizado para baja', 'NOLOC': 'No localizado'}
_TONO_OPERATIVO = {'UTIL': 'azul', 'OBS': 'gris', 'AUTB': 'rojo', 'NOLOC': 'ambar'}
_NOMBRE_REGISTRO = {'REG': 'Registrado', 'PEND': 'Pendiente', 'DON': 'Donado'}
_TONO_REGISTRO = {'REG': 'verde', 'PEND': 'ambar', 'DON': 'azul'}


def _operativo(codigo):
    return {'codigo': codigo, 'nombre': _NOMBRE_OPERATIVO[codigo],
            'tono': _TONO_OPERATIVO[codigo]}


def _registro(codigo):
    return {'codigo': codigo, 'nombre': _NOMBRE_REGISTRO[codigo],
            'tono': _TONO_REGISTRO[codigo]}


def _equipo(num, marca, modelo, serie, categoria, origen, ubicacion,
            resguardante, operativo, registro,
            marbete=None, folio=None, color='Negro', costo=None,
            fecha_adquisicion='', fecha_alta=''):
    """Arma un equipo con la MISMA forma que tendrá el JSON de la API."""
    return {
        'num': num,
        'marbete_oficial': marbete,
        'folio_interno': folio,
        'identificador': marbete or folio,
        'marca': marca,
        'modelo': modelo,
        'num_serie': serie,
        'color': color,
        'costo_adquisicion': costo,
        'fecha_adquisicion': fecha_adquisicion,
        'fecha_alta': fecha_alta,
        'categoria': {'codigo': categoria, 'nombre': _CAT[categoria]},
        'origen': {'codigo': origen, 'nombre': _ORI[origen]},
        'ubicacion': {'codigo': ubicacion, 'nombre': _UBI[ubicacion]},
        'resguardante': {'num': _PERSONAL[resguardante], 'nombre': resguardante},
        'estado_operativo': _operativo(operativo),
        'estado_registro': _registro(registro),
    }


def _equipos_prueba():
    """Datos de prueba. Se reemplaza por la llamada a la API cuando exista."""
    return [
        _equipo(1, 'Dell', 'OptiPlex 3080', '5CD1234ABC', 'CAT-PCE', 'ACT',
                'UBI-LAB2', 'Juan Pérez Vázquez', 'UTIL', 'REG',
                marbete='02-520-00003', costo='12500.00',
                fecha_adquisicion='2021-03-15', fecha_alta='2026-09-22'),
        _equipo(2, 'HP', 'ProDesk 400 G7', '8CC2345DEF', 'CAT-PCE', 'ACT',
                'UBI-LAB1', 'Juan Pérez Vázquez', 'UTIL', 'REG',
                marbete='02-520-00004', costo='13200.00',
                fecha_adquisicion='2022-01-20', fecha_alta='2026-09-22'),
        _equipo(3, 'Lenovo', 'ThinkCentre M70q', 'PF3A7B21', 'CAT-PCE', 'ACT',
                'UBI-OFI', 'María Elena Ruiz Soto', 'UTIL', 'REG',
                marbete='02-520-00005', costo='14800.00',
                fecha_adquisicion='2022-08-11', fecha_alta='2026-09-23'),
        _equipo(4, 'Dell', 'Latitude 5420', '7XK9P2LM', 'CAT-LAP', 'ACT',
                'UBI-OFI', 'Carlos Alberto Méndez Ríos', 'UTIL', 'PEND',
                marbete='02-520-00011',
                fecha_adquisicion='2023-02-06', fecha_alta='2026-09-25'),
        _equipo(5, 'HP', 'EliteBook 840 G8', '5CG3456GHI', 'CAT-LAP', 'COM',
                'UBI-OFI', 'Ana Karen Villalobos Pérez', 'UTIL', 'REG',
                folio='E-02-520-0181', costo='18900.00',
                fecha_adquisicion='2023-05-18', fecha_alta='2026-09-26'),
        _equipo(6, 'LG', '24MK430', 'LG24A9X31', 'CAT-MON', 'ACT',
                'UBI-LAB1', 'Juan Pérez Vázquez', 'UTIL', 'REG',
                marbete='02-520-00021', costo='3150.00',
                fecha_adquisicion='2021-09-02', fecha_alta='2026-09-24'),
        _equipo(7, 'Samsung', 'S24R350', 'SM24K77B2', 'CAT-MON', 'COM',
                'UBI-LAB2', 'Diana Laura Espinoza Núñez', 'UTIL', 'PEND',
                folio='E-02-520-0182', fecha_adquisicion='2024-01-30',
                fecha_alta='2026-09-29'),
        _equipo(8, 'Cisco', 'SG350-28', 'CSCO8812AB', 'CAT-SWT', 'ACT',
                'UBI-OFI', 'Carlos Alberto Méndez Ríos', 'UTIL', 'REG',
                marbete='02-520-00031', costo='9740.00',
                fecha_adquisicion='2020-11-04', fecha_alta='2026-09-23'),
        _equipo(9, 'TP-Link', 'TL-SG1024', 'TPL4419KK', 'CAT-SWT', 'ENS',
                'UBI-NOLOC', 'Diana Laura Espinoza Núñez', 'UTIL', 'REG',
                folio='0214300046-001',
                fecha_adquisicion='2019-06-12', fecha_alta='2026-09-30'),
        _equipo(10, 'Grandstream', 'GXP1625', 'GS16P2201', 'CAT-TIP', 'ACT',
                'UBI-OFI', 'María Elena Ruiz Soto', 'UTIL', 'REG',
                marbete='02-520-00041', costo='1290.00',
                fecha_adquisicion='2022-04-15', fecha_alta='2026-09-27'),
        _equipo(11, 'Grandstream', 'GXP1625', 'GS16P2202', 'CAT-TIP', 'ACT',
                'UBI-OFI', 'María Elena Ruiz Soto', 'AUTB', 'REG',
                marbete='02-520-00042', costo='1290.00',
                fecha_adquisicion='2022-04-15', fecha_alta='2026-09-27'),
        _equipo(12, 'JBL', 'Amplificada 60W', 'JBLA2023X7', 'CAT-ALT', 'ENS',
                'UBI-NOLOC', 'Ana Karen Villalobos Pérez', 'UTIL', 'PEND',
                folio='E-02-520-0190',
                fecha_adquisicion='2018-10-08', fecha_alta='2026-10-01'),
        _equipo(13, 'Dell', 'PowerEdge R740', 'SVR740X92', 'CAT-SRV', 'ACT',
                'UBI-OFI', 'Carlos Alberto Méndez Ríos', 'UTIL', 'REG',
                marbete='02-520-00051', costo='86400.00',
                fecha_adquisicion='2022-07-19', fecha_alta='2026-09-24'),
        _equipo(14, 'Lenovo', 'ThinkCentre M720', 'PF2B8C44', 'CAT-PCE', 'COM',
                'UBI-NOLOC', 'Diana Laura Espinoza Núñez', 'AUTB', 'REG',
                folio='E-02-520-0183',
                fecha_adquisicion='2020-02-27', fecha_alta='2026-10-02'),
    ]

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
    """Listado de equipos con búsqueda, filtros y paginación.

    Los datos se filtran aquí en memoria porque el backend aún no expone
    el endpoint. Cuando exista, se cambia solo el origen de `equipos`:
    los filtros se mandan igual como query params y el template no cambia.
    """
    equipos = _equipos_prueba()

    q = request.GET.get('q', '').strip()
    f_categoria = request.GET.get('categoria', '').strip()
    f_ubicacion = request.GET.get('ubicacion', '').strip()
    f_operativo = request.GET.get('estado_operativo', '').strip()
    f_registro = request.GET.get('estado_registro', '').strip()
    f_origen = request.GET.get('origen', '').strip()

    if q:
        aguja = q.lower()

        def coincide(e):
            campos = (
                e['identificador'] or '', e['marca'], e['modelo'],
                e['num_serie'], e['resguardante']['nombre'],
                e['categoria']['nombre'], e['ubicacion']['nombre'],
            )
            return aguja in ' '.join(campos).lower()

        equipos = [e for e in equipos if coincide(e)]

    if f_categoria:
        equipos = [e for e in equipos
                   if e['categoria']['codigo'] == f_categoria]
    if f_ubicacion:
        equipos = [e for e in equipos
                   if e['ubicacion']['codigo'] == f_ubicacion]
    if f_operativo:
        equipos = [e for e in equipos
                   if e['estado_operativo']['codigo'] == f_operativo]
    if f_registro:
        equipos = [e for e in equipos
                   if e['estado_registro']['codigo'] == f_registro]
    if f_origen:
        equipos = [e for e in equipos
                   if e['origen']['codigo'] == f_origen]

    total = len(equipos)

    paginator = Paginator(equipos, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Query string de los filtros, sin la página, para no perderlos al paginar
    params = request.GET.copy()
    params.pop('page', None)
    filtros_qs = params.urlencode()
    qs_prefijo = '?{}&'.format(filtros_qs) if filtros_qs else '?'

    hay_filtros = any([q, f_categoria, f_ubicacion,
                       f_operativo, f_registro, f_origen])

    contexto = {
        'page_obj': page_obj,
        'equipos': page_obj.object_list,
        'total': total,
        'hay_filtros': hay_filtros,
        'qs_prefijo': qs_prefijo,
        'rango_paginas': list(paginator.get_elided_page_range(
            page_obj.number, on_each_side=1, on_ends=1)),
        'pagina_elipsis': paginator.ELLIPSIS,
        'categorias': CATEGORIAS,
        'ubicaciones': UBICACIONES,
        'origenes': ORIGENES,
        'estados_operativos': ESTADOS_OPERATIVOS,
        'estados_registro': ESTADOS_REGISTRO,
        'f': {
            'q': q,
            'categoria': f_categoria,
            'ubicacion': f_ubicacion,
            'estado_operativo': f_operativo,
            'estado_registro': f_registro,
            'origen': f_origen,
        },
    }
    return render(request, 'equipos/listado.html', contexto)


def _siguiente_consecutivo():
    """Siguiente número del consecutivo de folios internos.

    PROVISIONAL: hoy se calcula sobre los datos de prueba. Cuando exista
    la base real, se reemplaza por una consulta a EQUIPO.
    """
    numeros = []
    for e in _equipos_prueba():
        folio = e.get('folio_interno')
        if not folio:
            continue
        cola = folio.rsplit('-', 1)[-1]
        if cola.isdigit():
            numeros.append(int(cola))
    return max(numeros, default=0) + 1


def generar_folio_interno(origen):
    prefijo = {'ACT': 'A', 'COM': 'C', 'ENS': 'E'}.get(origen, 'X')
    return 'IC-{}-{:04d}'.format(prefijo, _siguiente_consecutivo())


def _validar_equipo(datos):
    errores = {}
    limpio = {}

    def txt(k):
        return (datos.get(k) or '').strip()

    origen = txt('origen')
    if origen not in ('ACT', 'COM', 'ENS'):
        errores['origen'] = 'Selecciona el origen del equipo.'
    limpio['origen'] = origen

    for campo, etiqueta in (
        ('categoria', 'la categoría'),
        ('ubicacion', 'la ubicación'),
        ('resguardante', 'el resguardante'),
    ):
        valor = txt(campo)
        if not valor:
            errores[campo] = 'Falta {}.'.format(etiqueta)
        limpio[campo] = valor

    for campo, etiqueta in (
        ('marca', 'la marca'),
        ('modelo', 'el modelo'),
        ('num_serie', 'el número de serie'),
    ):
        valor = txt(campo)
        if not valor:
            errores[campo] = 'Falta {}.'.format(etiqueta)
        limpio[campo] = valor

    marbete = txt('marbete_oficial')
    folio = txt('folio_interno')

    if origen == 'ACT':
        if not marbete:
            errores['marbete_oficial'] = 'Los equipos activos llevan marbete oficial.'
        limpio['marbete_oficial'] = marbete
        limpio['folio_interno'] = generar_folio_interno(origen)
    else:
        if not folio:
            errores['folio_interno'] = 'Falta el folio interno.'
        limpio['marbete_oficial'] = None
        limpio['folio_interno'] = folio

    fecha = txt('fecha_adquisicion')
    limpio['fecha_adquisicion'] = ''
    if fecha:
        try:
            f = datetime.strptime(fecha, '%Y-%m-%d').date()
            if f > date.today():
                errores['fecha_adquisicion'] = 'La fecha no puede ser futura.'
            else:
                limpio['fecha_adquisicion'] = fecha
        except ValueError:
            errores['fecha_adquisicion'] = 'La fecha no es válida.'

    costo = txt('costo_adquisicion').replace(',', '')
    monto = None
    if costo:
        try:
            monto = '{:.2f}'.format(float(costo))
        except ValueError:
            errores['costo_adquisicion'] = 'El costo debe ser un número.'
    limpio['costo_adquisicion'] = monto

    if datos.get('donado') == 'on':
        limpio['estado_registro'] = 'DON'
    elif monto:
        limpio['estado_registro'] = 'REG'
    else:
        limpio['estado_registro'] = 'PEND'

    limpio['estado_operativo'] = txt('estado_operativo') or 'UTIL'
    limpio['color'] = txt('color')
    limpio['descripcion'] = txt('descripcion')

    return errores, limpio



def registrar_equipo(request):
    if request.method == 'POST':
        errores, limpio = _validar_equipo(request.POST)
        if not errores:
            return redirect(
                '{}?creado={}'.format(
                    reverse('equipos:listado'), limpio['folio_interno']))
    else:
        limpio = {'origen': 'ACT', 'estado_operativo': 'UTIL'}
        errores = {}

    origen_actual = limpio.get('origen') or 'ACT'

    contexto = {
        'errores': errores,
        'v': limpio,
        'folio_sugerido': generar_folio_interno(origen_actual),
        'hoy': date.today().isoformat(),
        'categorias': CATEGORIAS,
        'ubicaciones': UBICACIONES,
        'origenes': ORIGENES,
        'estados_operativos': ESTADOS_OPERATIVOS,
        'personal': sorted(_PERSONAL.keys()),
    }
    return render(request, 'equipos/registrar.html', contexto)