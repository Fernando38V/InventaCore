"""Lectura de la bitácora de auditoría (RF-21, PEND-024). Solo el Administrador.

GET /bitacora/          lista paginada, la más reciente primero. Filtros:
    q                   busca en usuario, módulo, acción, tabla, registro, motivo y valores
    usuario             número o nombre de usuario (exacto)
    modulo              exacto, por ejemplo articulos, movimientos, carga_masiva
    accion              INSERT, UPDATE o DELETE
    fecha_desde, fecha_hasta   AAAA-MM-DD, ambos días incluidos
    tabla_afectada, registro_id  historial de un registro concreto
GET /bitacora/<num>/    un registro.
La bitácora no se puede modificar ni borrar: no hay POST, PATCH ni DELETE.
"""
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets

from api.permisos import SoloAdministrador
from auditoria.models import Bitacora
from auditoria.serializers import BitacoraSerializer


def _fecha(valor, campo):
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise serializers.ValidationError({campo: 'Use el formato AAAA-MM-DD.'})


class BitacoraViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    permission_classes = [SoloAdministrador]
    serializer_class = BitacoraSerializer
    lookup_field = 'num'
    lookup_value_regex = r'\d+'

    def get_queryset(self):
        consulta = BitacoraSerializer.optimizar(Bitacora.objects.all())
        p = self.request.query_params

        usuario = (p.get('usuario') or '').strip()
        if usuario:
            if usuario.isdigit():
                consulta = consulta.filter(usuario_id=int(usuario))
            else:
                consulta = consulta.filter(usuario__username__iexact=usuario)
        if p.get('modulo'):
            consulta = consulta.filter(modulo__iexact=p['modulo'].strip())
        accion = (p.get('accion') or '').strip().upper()
        if accion:
            if accion not in dict(Bitacora.ACCIONES):
                raise serializers.ValidationError(
                    {'accion': 'Use INSERT, UPDATE o DELETE.'})
            consulta = consulta.filter(accion=accion)
        if p.get('tabla_afectada'):
            consulta = consulta.filter(tabla_afectada=p['tabla_afectada'].strip())
        if p.get('registro_id'):
            consulta = consulta.filter(registro_id=p['registro_id'].strip())

        zona = timezone.get_current_timezone()
        desde = (p.get('fecha_desde') or '').strip()
        hasta = (p.get('fecha_hasta') or '').strip()
        f_desde = _fecha(desde, 'fecha_desde') if desde else None
        f_hasta = _fecha(hasta, 'fecha_hasta') if hasta else None
        if f_desde and f_hasta and f_desde > f_hasta:
            raise serializers.ValidationError(
                {'fecha_hasta': 'La fecha final no puede ser anterior a la inicial.'})
        if f_desde:
            consulta = consulta.filter(
                fecha_hora__gte=timezone.make_aware(datetime.combine(f_desde, time.min), zona))
        if f_hasta:
            consulta = consulta.filter(fecha_hora__lt=timezone.make_aware(
                datetime.combine(f_hasta + timedelta(days=1), time.min), zona))

        for palabra in (p.get('q') or '').split():
            consulta = consulta.filter(
                Q(usuario__username__icontains=palabra) | Q(modulo__icontains=palabra)
                | Q(accion__icontains=palabra) | Q(tabla_afectada__icontains=palabra)
                | Q(registro_id__icontains=palabra) | Q(motivo__icontains=palabra)
                | Q(valor_anterior__icontains=palabra) | Q(valor_nuevo__icontains=palabra))
        return consulta
