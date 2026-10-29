from rest_framework import viewsets

from auditoria.mixins import BitacoraMixin
from personal.models import Departamento, Personal
from personal.serializers import DepartamentoSerializer, PersonalSerializer


class DepartamentoViewSet(BitacoraMixin, viewsets.ModelViewSet):
    modulo = 'departamentos'
    queryset = Departamento.objects.all()
    serializer_class = DepartamentoSerializer


class PersonalViewSet(BitacoraMixin, viewsets.ModelViewSet):
    modulo = 'personal'
    serializer_class = PersonalSerializer

    def get_queryset(self):
        consulta = Personal.objects.select_related('departamento')
        p = self.request.query_params
        if p.get('departamento'):
            consulta = consulta.filter(departamento_id=p['departamento'])
        if p.get('activo') in ('true', 'false'):
            consulta = consulta.filter(activo=p['activo'] == 'true')
        if p.get('q'):
            q = p['q']
            from django.db.models import Q
            consulta = consulta.filter(
                Q(nombre_pila__icontains=q) | Q(primer_apellido__icontains=q)
                | Q(segundo_apellido__icontains=q) | Q(numero_empleado__icontains=q))
        return consulta
