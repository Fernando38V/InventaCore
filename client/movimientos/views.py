from datetime import date, datetime

from django.core.paginator import Paginator
from django.shortcuts import render, redirect, reverse

from equipos.views import _equipos_prueba, UBICACIONES, _UBI, _PERSONAL


TIPOS_MOVIMIENTO = [
    {'codigo': 'ALTA', 'nombre': 'Alta de equipo'},
    {'codigo': 'REUB', 'nombre': 'Reubicación y/o cambio de resguardante'},
    {'codigo': 'REPA', 'nombre': 'Envío a reparación'},
    {'codigo': 'RETE', 'nombre': 'Retorno de reparación'},
    {'codigo': 'BAJA', 'nombre': 'Baja de equipo'},
]

_TIPO = {t['codigo']: t for t in TIPOS_MOVIMIENTO}


def _equipo_por_num(num):
    for e in _equipos_prueba():
        if e['num'] == num:
            return e
    return None


def _mov(num, tipo, equipo, fecha, llegada=None, origen=None,
         asigna=None, entrega=None, nota='', genera_resguardo=False):
    t = _TIPO[tipo]
    eq = _equipo_por_num(equipo)
    return {
        'num': num,
        'folio': 'MOV-{:04d}'.format(num),
        'fecha': fecha,
        'fecha_dia': fecha.split(' ')[0],
        'fecha_hora': fecha.split(' ')[1],
        'tipo': {'codigo': t['codigo'], 'nombre': t['nombre']},
        'genera_resguardo': genera_resguardo,
        'equipo': {
            'num': eq['num'],
            'identificador': eq['identificador'],
            'descripcion': '{} {}'.format(eq['marca'], eq['modelo']),
        },
        'ubicacion_origen': ({'codigo': origen, 'nombre': _UBI[origen]}
                             if origen else None),
        'ubicacion_llegada': ({'codigo': llegada, 'nombre': _UBI[llegada]}
                              if llegada else None),
        'personal_asigna': {'nombre': asigna} if asigna else None,
        'personal_entrega': {'nombre': entrega} if entrega else None,
        'nota': nota,
    }


def _movimientos_prueba():
    return [
        _mov(1, 'ALTA', 1, '2026-09-22 10:14', llegada='UBI-LAB2',
             asigna='María Elena Ruiz Soto', genera_resguardo=True),
        _mov(2, 'ALTA', 2, '2026-09-22 10:31', llegada='UBI-LAB1',
             asigna='María Elena Ruiz Soto', genera_resguardo=True),
        _mov(3, 'ALTA', 3, '2026-09-23 09:05', llegada='UBI-OFI',
             asigna='Juan Pérez Vázquez', genera_resguardo=True),
        _mov(4, 'ALTA', 8, '2026-09-23 09:48', llegada='UBI-OFI',
             asigna='Juan Pérez Vázquez', genera_resguardo=True),
        _mov(5, 'ALTA', 6, '2026-09-24 11:20', llegada='UBI-LAB1',
             asigna='María Elena Ruiz Soto', genera_resguardo=True),
        _mov(6, 'ALTA', 13, '2026-09-24 12:02', llegada='UBI-OFI',
             asigna='Juan Pérez Vázquez', genera_resguardo=True),
        _mov(7, 'REUB', 6, '2026-09-25 08:40', origen='UBI-LAB1',
             llegada='UBI-LAB2', asigna='Juan Pérez Vázquez',
             nota='Se reubica por remodelación del laboratorio'),
        _mov(8, 'REUB', 1, '2026-09-26 16:15', origen='UBI-LAB2',
             llegada='UBI-LAB2', asigna='Juan Pérez Vázquez',
             entrega='María Elena Ruiz Soto', genera_resguardo=True,
             nota='Cambio de resguardante por reasignación de área'),
        _mov(9, 'BAJA', 11, '2026-09-27 13:22', origen='UBI-OFI',
             asigna='Carlos Alberto Méndez Ríos',
             nota='Audífono dañado sin reparación posible'),
        _mov(10, 'REPA', 9, '2026-09-30 10:00', origen='UBI-LAB2',
             llegada='UBI-NOLOC', asigna='Diana Laura Espinoza Núñez',
             nota='Puertos sin respuesta'),
        _mov(11, 'ALTA', 12, '2026-10-01 09:10', llegada='UBI-NOLOC',
             asigna='Ana Karen Villalobos Pérez', genera_resguardo=True),
        _mov(12, 'BAJA', 14, '2026-10-02 15:45', origen='UBI-NOLOC',
             asigna='Carlos Alberto Méndez Ríos',
             nota='Equipo descontinuado, sin reparación disponible'),
    ]


def listado_movimientos(request):
    movimientos = _movimientos_prueba()

    q = request.GET.get('q', '').strip()
    f_tipo = request.GET.get('tipo', '').strip()
    f_ubicacion = request.GET.get('ubicacion', '').strip()

    if q:
        aguja = q.lower()

        def coincide(m):
            campos = (
                m['folio'],
                m['equipo']['identificador'],
                m['equipo']['descripcion'],
                m['tipo']['nombre'],
                m['personal_asigna']['nombre'] if m['personal_asigna'] else '',
                m['personal_entrega']['nombre'] if m['personal_entrega'] else '',
            )
            return aguja in ' '.join(campos).lower()

        movimientos = [m for m in movimientos if coincide(m)]

    if f_tipo:
        movimientos = [m for m in movimientos
                       if m['tipo']['codigo'] == f_tipo]

    if f_ubicacion:
        def en_ubicacion(m):
            origen = m['ubicacion_origen'] or {}
            llegada = m['ubicacion_llegada'] or {}
            return (origen.get('codigo') == f_ubicacion
                    or llegada.get('codigo') == f_ubicacion)

        movimientos = [m for m in movimientos if en_ubicacion(m)]

    movimientos.sort(key=lambda m: m['fecha'], reverse=True)

    total = len(movimientos)

    paginator = Paginator(movimientos, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    params = request.GET.copy()
    params.pop('page', None)
    filtros_qs = params.urlencode()
    qs_prefijo = '?{}&'.format(filtros_qs) if filtros_qs else '?'

    hay_filtros = any([q, f_tipo, f_ubicacion])

    contexto = {
        'page_obj': page_obj,
        'movimientos': page_obj.object_list,
        'total': total,
        'hay_filtros': hay_filtros,
        'qs_prefijo': qs_prefijo,
        'rango_paginas': list(paginator.get_elided_page_range(
            page_obj.number, on_each_side=1, on_ends=1)),
        'pagina_elipsis': paginator.ELLIPSIS,
        'tipos': TIPOS_MOVIMIENTO,
        'ubicaciones': UBICACIONES,
        'registrado': request.GET.get('registrado', ''),
        'f': {'q': q, 'tipo': f_tipo, 'ubicacion': f_ubicacion},
    }
    return render(request, 'movimientos/listado.html', contexto)


def _validar_movimiento(datos):
    errores = {}
    limpio = {}

    def txt(k):
        return (datos.get(k) or '').strip()

    tipo = txt('tipo')
    if tipo not in _TIPO or tipo == 'ALTA':
        errores['tipo'] = 'Selecciona el tipo de movimiento.'
    limpio['tipo'] = tipo

    equipo_num = txt('equipo')
    equipo = _equipo_por_num(int(equipo_num)) if equipo_num.isdigit() else None
    if not equipo:
        errores['equipo'] = 'Selecciona el equipo.'
    limpio['equipo_num'] = equipo_num
    limpio['equipo'] = equipo

    ubicacion = txt('ubicacion')
    resguardante = txt('resguardante')
    limpio['ubicacion'] = ubicacion
    limpio['resguardante'] = resguardante

    if tipo == 'REUB' and not ubicacion and not resguardante:
        errores['ubicacion'] = 'Especifica una nueva ubicación, un nuevo resguardante, o ambos.'
    elif tipo == 'RETE' and not ubicacion:
        errores['ubicacion'] = 'Indica dónde se reintegra el equipo.'

    motivo = txt('motivo')
    if not motivo:
        errores['motivo'] = 'El motivo es obligatorio.'
    limpio['motivo'] = motivo

    fecha = txt('fecha')
    limpio['fecha'] = ''
    if not fecha:
        errores['fecha'] = 'Falta la fecha.'
    else:
        try:
            f = datetime.strptime(fecha, '%Y-%m-%d').date()
            if f > date.today():
                errores['fecha'] = 'La fecha no puede ser futura.'
            else:
                limpio['fecha'] = fecha
        except ValueError:
            errores['fecha'] = 'La fecha no es válida.'

    return errores, limpio


def _siguiente_folio_movimiento():
    """Folio simulado, igual que el de equipos. Cuando exista la tabla
    real de movimientos, lo asigna la base de datos."""
    return 'MOV-{:04d}'.format(len(_movimientos_prueba()) + 1)


def nuevo_movimiento(request):
    if request.method == 'POST':
        bloqueado = request.POST.get('bloqueado') == '1'
        errores, limpio = _validar_movimiento(request.POST)
        if not errores:
            return redirect(
                '{}?registrado={}'.format(
                    reverse('movimientos:listado'), _siguiente_folio_movimiento()))
    else:
        bloqueado = bool(request.GET.get('equipo'))
        errores = {}
        limpio = {
            'tipo': '',
            'equipo_num': request.GET.get('equipo', ''),
            'ubicacion': '',
            'resguardante': '',
            'motivo': '',
            'fecha': date.today().isoformat(),
        }

    equipo_fijo = None
    if bloqueado and limpio.get('equipo_num', '').isdigit():
        equipo_fijo = _equipo_por_num(int(limpio['equipo_num']))

    contexto = {
        'errores': errores,
        'v': limpio,
        'bloqueado': bloqueado,
        'equipo_fijo': equipo_fijo,
        'equipos': sorted(_equipos_prueba(), key=lambda e: e['identificador'] or ''),
        'tipos': [t for t in TIPOS_MOVIMIENTO if t['codigo'] != 'ALTA'],
        'ubicaciones': UBICACIONES,
        'personal': sorted(_PERSONAL.keys()),
        'hoy': date.today().isoformat(),
    }
    return render(request, 'movimientos/nuevo.html', contexto)