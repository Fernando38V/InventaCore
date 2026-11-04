"""Dashboard y reportes (DEC-020). Solo lectura: Administrador y Consulta.

Dashboard: totales por estado operativo, estado de registro y ubicación;
artículos Pendientes de datos; últimos movimientos.
Reportes: inventario filtrable, artículos de un resguardante, historial de un
artículo y la exportación a Excel (DEC-018). Todos sin paginar.
"""
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from articulos.excel import libro_inventario, nombre_archivo
from articulos.filtros import con_relaciones, inventario
from articulos.models import Articulo
from articulos.serializers import (
    TONO_OPERATIVO, TONO_REGISTRO, ArticuloSerializer, par, persona)
from catalogos.models import EstadoOperativo, EstadoRegistro, Ubicacion
from movimientos.models import Movimiento, Resguardo
from movimientos.serializers import MovimientoSerializer

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _excel(articulos, nombre=None):
    respuesta = HttpResponse(libro_inventario(articulos), content_type=XLSX)
    respuesta['Content-Disposition'] = 'attachment; filename="%s"' % (nombre or nombre_archivo())
    return respuesta


def _conteos(modelo, campo, tonos):
    """Un renglón por estado (aunque sea 0), en el orden de `tonos`."""
    total = dict(Articulo.objects.values_list(campo).annotate(n=Count('pk')))
    orden = list(tonos)
    estados = sorted(modelo.objects.all(), key=lambda e: (
        orden.index(e.pk) if e.pk in orden else len(orden), e.pk))
    return [{'codigo': e.pk, 'nombre': e.nombre, 'tono': tonos.get(e.pk, 'gris'),
             'total': total.get(e.pk, 0)} for e in estados]


class DashboardView(APIView):
    def get(self, request):
        por_ubicacion = dict(Articulo.objects.values_list('ubicacion').annotate(n=Count('pk')))
        ubicaciones = [dict(par(u), total=por_ubicacion.get(u.pk, 0))
                       for u in Ubicacion.objects.filter(activo=True)]
        ubicaciones.sort(key=lambda u: (-u['total'], u['nombre']))
        pendientes = con_relaciones(Articulo.objects.filter(estado_registro_id='PEND')).order_by('num')
        ultimos = MovimientoSerializer.optimizar(Movimiento.objects.all())[:10]
        return Response({
            'total_articulos': Articulo.objects.count(),
            'por_estado_operativo': _conteos(EstadoOperativo, 'estado_operativo', TONO_OPERATIVO),
            'por_estado_registro': _conteos(EstadoRegistro, 'estado_registro', TONO_REGISTRO),
            'por_ubicacion': ubicaciones,
            'pendientes_de_datos': {
                'total': pendientes.count(),
                'articulos': ArticuloSerializer(pendientes[:10], many=True).data,
            },
            'ultimos_movimientos': MovimientoSerializer(ultimos, many=True).data,
            'resguardos_por_emitir': Movimiento.objects.filter(
                requiere_resguardo=True, detalle_resguardo__isnull=True).count(),
        })


class InventarioView(APIView):
    """Inventario filtrable por ubicación, resguardante y estado (y los demás
    filtros de /articulos/). `?formato=xlsx` lo descarga en Excel."""

    def get(self, request):
        consulta = inventario(request.query_params)
        if request.query_params.get('formato') == 'xlsx':
            return _excel(consulta)
        datos = ArticuloSerializer(consulta, many=True).data
        return Response({'total': len(datos), 'resultados': datos})


class ArticulosDeResguardanteView(APIView):
    """Artículos que tiene hoy un resguardante. `?formato=xlsx` en Excel."""

    def get(self, request, num):
        from personal.models import Personal
        personal = get_object_or_404(Personal, pk=num)
        consulta = con_relaciones(Articulo.objects.filter(resguardante=personal))
        if request.query_params.get('formato') == 'xlsx':
            return _excel(consulta, 'articulos_%s.xlsx' % personal.numero_empleado)
        datos = ArticuloSerializer(consulta, many=True).data
        return Response({'resguardante': persona(personal), 'total': len(datos),
                         'resultados': datos})


class HistorialDeArticuloView(APIView):
    """Todos los movimientos de un artículo y los resguardos que lo documentan."""

    def get(self, request, num):
        articulo = get_object_or_404(con_relaciones(Articulo.objects.all()), pk=num)
        movimientos = MovimientoSerializer.optimizar(
            Movimiento.objects.filter(articulo=articulo))
        resguardos = Resguardo.objects.filter(
            detalles__movimiento__articulo=articulo).select_related('resguardante').distinct()
        return Response({
            'articulo': ArticuloSerializer(articulo).data,
            'movimientos': MovimientoSerializer(movimientos, many=True).data,
            'resguardos': [{'folio': r.folio, 'fecha_emision': timezone.localtime(r.fecha_emision).strftime('%Y-%m-%d %H:%M'),
                            'resguardante': persona(r.resguardante),
                            'pdf': '/api/resguardos/%s/pdf/' % r.folio} for r in resguardos],
        })
