from django.http import HttpResponse
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from articulos.excel import libro_inventario, nombre_archivo
from articulos.filtros import con_relaciones, inventario
from articulos.models import Articulo
from articulos.serializers import (
    ArticuloCorregirSerializer, ArticuloCrearSerializer, ArticuloSerializer)
from articulos.servicios import alta_articulo, corregir_articulo
from movimientos.models import Movimiento
from movimientos.serializers import MovimientoSerializer


class ArticuloViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /articulos/ (filtros: q, categoria, tipo_articulo, ubicacion,
    estado_operativo, estado_registro, origen, resguardante) · GET /articulos/<num>/
    · POST /articulos/ · PATCH /articulos/<num>/ (corrección con motivo)
    · GET /articulos/<num>/movimientos/ · GET /articulos/todos/ (sin paginar)
    · GET /articulos/exportar/ (.xlsx)."""

    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    lookup_field = 'num'
    lookup_value_regex = r'\d+'
    serializer_class = ArticuloSerializer

    def get_queryset(self):
        return inventario(self.request.query_params)

    def create(self, request, *args, **kwargs):
        entrada = ArticuloCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        articulo = alta_articulo(entrada.validated_data, request.user)
        articulo = con_relaciones(Articulo.objects.filter(pk=articulo.pk)).get()
        return Response(ArticuloSerializer(articulo).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        """Corrección desde la ficha: marbete, marca, modelo, serie, color,
        descripción, fecha y costo de adquisición y estado Útil/Obsoleto, con motivo."""
        articulo = self.get_object()
        entrada = ArticuloCorregirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        if not any(campo in datos for campo in (
                'marbete_oficial', 'marca', 'modelo', 'num_serie', 'color', 'descripcion',
                'fecha_adquisicion', 'costo_adquisicion', 'estado_operativo')):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detalle': 'No hay cambios que guardar.'})
        corregir_articulo(articulo, datos, request.user)
        articulo = con_relaciones(Articulo.objects.filter(pk=articulo.pk)).get()
        return Response(ArticuloSerializer(articulo).data)

    @action(detail=False, methods=['get'])
    def todos(self, request):
        """Todo el inventario filtrado, sin paginar (mismos filtros que la lista)."""
        return Response(ArticuloSerializer(self.get_queryset(), many=True).data)

    @action(detail=False, methods=['get'])
    def exportar(self, request):
        """Excel del inventario filtrado, completo (RF-26). Admin y Consulta."""
        respuesta = HttpResponse(
            libro_inventario(self.get_queryset()),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        respuesta['Content-Disposition'] = 'attachment; filename="%s"' % nombre_archivo()
        return respuesta

    @action(detail=True, methods=['get'])
    def movimientos(self, request, num=None):
        articulo = self.get_object()
        consulta = Movimiento.objects.filter(articulo=articulo)
        consulta = MovimientoSerializer.optimizar(consulta)
        pagina = self.paginate_queryset(consulta)
        return self.get_paginated_response(MovimientoSerializer(pagina, many=True).data)
