from rest_framework import viewsets

from auditoria.mixins import BitacoraMixin
from catalogos import serializers as s
from catalogos.models import (
    Categoria, EstadoOperativo, EstadoRegistro, Origen, TipoArticulo, TipoMovimiento,
    Ubicacion)


def _filtro_activo(consulta, params):
    if params.get('activo') in ('true', 'false'):
        consulta = consulta.filter(activo=params['activo'] == 'true')
    return consulta


class CategoriaViewSet(BitacoraMixin, viewsets.ModelViewSet):
    modulo = 'categorias'
    serializer_class = s.CategoriaSerializer

    def get_queryset(self):
        return _filtro_activo(Categoria.objects.all(), self.request.query_params)


class TipoArticuloViewSet(BitacoraMixin, viewsets.ModelViewSet):
    modulo = 'tipos_articulo'
    serializer_class = s.TipoArticuloSerializer

    def get_queryset(self):
        consulta = TipoArticulo.objects.select_related('categoria')
        if self.request.query_params.get('categoria'):
            consulta = consulta.filter(categoria_id=self.request.query_params['categoria'])
        return _filtro_activo(consulta, self.request.query_params)


class UbicacionViewSet(BitacoraMixin, viewsets.ModelViewSet):
    modulo = 'ubicaciones'
    serializer_class = s.UbicacionSerializer

    def get_queryset(self):
        return _filtro_activo(
            Ubicacion.objects.select_related('responsable'), self.request.query_params)


class _SoloLectura(viewsets.ReadOnlyModelViewSet):
    pagination_class = None


class OrigenViewSet(_SoloLectura):
    queryset = Origen.objects.all()
    serializer_class = s.OrigenSerializer


class EstadoOperativoViewSet(_SoloLectura):
    queryset = EstadoOperativo.objects.all()
    serializer_class = s.EstadoOperativoSerializer


class EstadoRegistroViewSet(_SoloLectura):
    queryset = EstadoRegistro.objects.all()
    serializer_class = s.EstadoRegistroSerializer


class TipoMovimientoViewSet(_SoloLectura):
    queryset = TipoMovimiento.objects.all()
    serializer_class = s.TipoMovimientoSerializer
