from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from movimientos.models import Movimiento
from movimientos.serializers import MovimientoCrearSerializer, MovimientoSerializer
from movimientos.servicios import registrar_movimiento


class MovimientoViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                        mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /movimientos/ (filtros: q, tipo, ubicacion, equipo) ·
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
        if p.get('equipo', '').isdigit():
            consulta = consulta.filter(articulo_id=int(p['equipo']))
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
