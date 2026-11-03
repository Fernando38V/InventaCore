from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from articulos.models import Articulo
from articulos.serializers import (
    ArticuloCorregirSerializer, ArticuloCrearSerializer, ArticuloSerializer)
from articulos.servicios import alta_articulo, corregir_articulo
from movimientos.models import Movimiento
from movimientos.serializers import MovimientoSerializer


def _con_relaciones(consulta):
    return consulta.select_related(
        'tipo_articulo__categoria', 'origen', 'ubicacion', 'resguardante',
        'estado_operativo', 'estado_registro')


class ArticuloViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                      mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /articulos/ (filtros: q, categoria, tipo_articulo, ubicacion,
    estado_operativo, estado_registro, origen, resguardante) · GET /articulos/<num>/
    · POST /articulos/ · PATCH /articulos/<num>/ (corrección con motivo)
    · GET /articulos/<num>/movimientos/."""

    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    lookup_field = 'num'
    lookup_value_regex = r'\d+'
    serializer_class = ArticuloSerializer

    def get_queryset(self):
        consulta = _con_relaciones(Articulo.objects.all())
        p = self.request.query_params
        for parametro, campo in (
                ('categoria', 'tipo_articulo__categoria_id'), ('tipo_articulo', 'tipo_articulo_id'),
                ('ubicacion', 'ubicacion_id'), ('estado_operativo', 'estado_operativo_id'),
                ('estado_registro', 'estado_registro_id'), ('origen', 'origen_id'),
                ('resguardante', 'resguardante_id')):
            if p.get(parametro):
                consulta = consulta.filter(**{campo: p[parametro]})
        # Cada palabra de la búsqueda debe aparecer en algún campo.
        for palabra in (p.get('q') or '').split():
            consulta = consulta.filter(
                Q(marbete_oficial__icontains=palabra) | Q(folio_interno__icontains=palabra)
                | Q(marca__icontains=palabra) | Q(modelo__icontains=palabra)
                | Q(num_serie__icontains=palabra) | Q(descripcion__icontains=palabra)
                | Q(color__icontains=palabra)
                | Q(tipo_articulo__nombre__icontains=palabra)
                | Q(tipo_articulo__categoria__nombre__icontains=palabra)
                | Q(ubicacion__nombre__icontains=palabra)
                | Q(resguardante__nombre_pila__icontains=palabra)
                | Q(resguardante__primer_apellido__icontains=palabra)
                | Q(resguardante__segundo_apellido__icontains=palabra)
                | Q(resguardante__numero_empleado__icontains=palabra))
        return consulta

    def create(self, request, *args, **kwargs):
        entrada = ArticuloCrearSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        articulo = alta_articulo(entrada.validated_data, request.user)
        articulo = _con_relaciones(Articulo.objects.filter(pk=articulo.pk)).get()
        return Response(ArticuloSerializer(articulo).data, status=201)

    def partial_update(self, request, *args, **kwargs):
        """Corrección desde la ficha: marbete, marca, modelo, serie, color,
        descripción, fecha de adquisición y estado Útil/Obsoleto, con motivo."""
        articulo = self.get_object()
        entrada = ArticuloCorregirSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = dict(entrada.validated_data)
        if not any(campo in datos for campo in (
                'marbete_oficial', 'marca', 'modelo', 'num_serie', 'color', 'descripcion',
                'fecha_adquisicion', 'estado_operativo')):
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'detalle': 'No hay cambios que guardar.'})
        corregir_articulo(articulo, datos, request.user)
        articulo = _con_relaciones(Articulo.objects.filter(pk=articulo.pk)).get()
        return Response(ArticuloSerializer(articulo).data)

    @action(detail=True, methods=['get'])
    def movimientos(self, request, num=None):
        articulo = self.get_object()
        consulta = Movimiento.objects.filter(articulo=articulo)
        consulta = MovimientoSerializer.optimizar(consulta)
        pagina = self.paginate_queryset(consulta)
        return self.get_paginated_response(MovimientoSerializer(pagina, many=True).data)
