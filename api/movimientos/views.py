from django.db.models import Q
from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from movimientos.models import Movimiento, Resguardo
from movimientos.resguardos import (
    ArchivoDeResguardoAlterado, contenido_original, emitir_resguardo, pendientes)
from movimientos.serializers import (
    MovimientoCrearSerializer, MovimientoSerializer, ResguardoCrearSerializer,
    ResguardoSerializer)
from movimientos.servicios import registrar_movimiento


class MovimientoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                        mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /movimientos/ (filtros: q, tipo, ubicacion, articulo) ·
    GET /movimientos/<folio>/ · POST /movimientos/."""

    lookup_field = 'folio'
    lookup_value_regex = r'MOV-\d+'
    serializer_class = MovimientoSerializer

    def get_queryset(self):
        consulta = MovimientoSerializer.optimizar(Movimiento.objects.all())
        p = self.request.query_params
        if p.get('tipo'):
            consulta = consulta.filter(tipo_movimiento_id=p['tipo'])
        if p.get('ubicacion'):
            consulta = consulta.filter(
                Q(ubicacion_origen_id=p['ubicacion']) | Q(ubicacion_destino_id=p['ubicacion']))
        filtro_articulo = p.get('articulo') or p.get('equipo') or ''
        if filtro_articulo.isdigit():
            consulta = consulta.filter(articulo_id=int(filtro_articulo))
        for palabra in (p.get('q') or '').split():
            consulta = consulta.filter(
                Q(folio__icontains=palabra) | Q(motivo__icontains=palabra)
                | Q(articulo__marbete_oficial__icontains=palabra)
                | Q(articulo__folio_interno__icontains=palabra)
                | Q(articulo__marca__icontains=palabra) | Q(articulo__modelo__icontains=palabra)
                | Q(articulo__descripcion__icontains=palabra)
                | Q(tipo_movimiento__nombre__icontains=palabra)
                | Q(resguardante_nuevo__nombre_pila__icontains=palabra)
                | Q(resguardante_nuevo__primer_apellido__icontains=palabra)
                | Q(resguardante_nuevo__segundo_apellido__icontains=palabra)
                | Q(resguardante_anterior__nombre_pila__icontains=palabra)
                | Q(resguardante_anterior__primer_apellido__icontains=palabra)
                | Q(resguardante_anterior__segundo_apellido__icontains=palabra))
        return consulta

    def create(self, request, *args, **kwargs):
        entrada = MovimientoCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        movimiento = registrar_movimiento(entrada.validated_data, request.user)
        movimiento = MovimientoSerializer.optimizar(
            Movimiento.objects.filter(pk=movimiento.pk)).get()
        return Response(MovimientoSerializer(movimiento).data, status=201)


class ResguardoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                       mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /resguardos/ (filtros: q, resguardante, articulo) · GET /resguardos/<folio>/
    · POST /resguardos/ {resguardante, movimientos: [folios]} (solo Administrador)
    · GET /resguardos/<folio>/pdf/ (el archivo emitido, sin cambios)
    · GET /resguardos/pendientes/?resguardante= (asignaciones sin documentar)."""

    lookup_field = 'folio'
    lookup_value_regex = r'RES-\d+'
    serializer_class = ResguardoSerializer

    def get_queryset(self):
        consulta = ResguardoSerializer.optimizar(Resguardo.objects.all())
        p = self.request.query_params
        if p.get('resguardante', '').isdigit():
            consulta = consulta.filter(resguardante_id=int(p['resguardante']))
        if p.get('articulo', '').isdigit():
            consulta = consulta.filter(detalles__movimiento__articulo_id=int(p['articulo']))
        for palabra in (p.get('q') or '').split():
            consulta = consulta.filter(
                Q(folio__icontains=palabra) | Q(resguardante__nombre_pila__icontains=palabra)
                | Q(resguardante__primer_apellido__icontains=palabra)
                | Q(resguardante__segundo_apellido__icontains=palabra)
                | Q(resguardante__numero_empleado__icontains=palabra))
        return consulta.distinct()

    def create(self, request, *args, **kwargs):
        entrada = ResguardoCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        resguardo = emitir_resguardo(
            entrada.validated_data['resguardante'], entrada.validated_data['movimientos'],
            request.user)
        resguardo = self.get_queryset().get(pk=resguardo.pk)
        return Response(ResguardoSerializer(resguardo).data, status=201)

    @action(detail=True, methods=['get'])
    def pdf(self, request, folio=None):
        resguardo = self.get_object()
        try:
            datos = contenido_original(resguardo)
        except ArchivoDeResguardoAlterado as error:
            return Response({'detalle': str(error)}, status=409)
        respuesta = HttpResponse(datos, content_type='application/pdf')
        respuesta['Content-Disposition'] = 'inline; filename="%s.pdf"' % resguardo.folio
        return respuesta

    @action(detail=False, methods=['get'])
    def pendientes(self, request):
        """Asignaciones que requieren resguardo y todavía no tienen uno."""
        r = request.query_params.get('resguardante', '')
        consulta = MovimientoSerializer.optimizar(
            pendientes(int(r) if r.isdigit() else None))
        pagina = self.paginate_queryset(consulta)
        return self.get_paginated_response(MovimientoSerializer(pagina, many=True).data)
