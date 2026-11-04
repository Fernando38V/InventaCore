"""Endpoints de la carga masiva (RF-24, RF-25). Solo el Administrador."""
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permisos import SoloAdministrador
from articulos import carga_masiva

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _archivo(request):
    archivo = request.FILES.get('archivo')
    if archivo is None:
        raise ValidationError({'archivo': 'Adjunte el archivo de Excel (campo "archivo").'})
    if archivo.size > carga_masiva.MAX_BYTES:
        raise ValidationError({'archivo': 'El archivo pesa más de %d MB.' % (
            carga_masiva.MAX_BYTES // (1024 * 1024))})
    return archivo.name, archivo.read()


class PlantillaView(APIView):
    """GET /carga-masiva/plantilla/ → plantilla .xlsx con listas desplegables."""

    permission_classes = [SoloAdministrador]

    def get(self, request):
        respuesta = HttpResponse(carga_masiva.generar_plantilla(), content_type=XLSX)
        respuesta['Content-Disposition'] = 'attachment; filename="plantilla_carga_masiva.xlsx"'
        return respuesta


class ValidarView(APIView):
    """POST /carga-masiva/validar/ (multipart, campo `archivo`) → vista previa.
    No guarda nada."""

    permission_classes = [SoloAdministrador]
    parser_classes = [MultiPartParser]

    def post(self, request):
        nombre, contenido = _archivo(request)
        try:
            resultado = carga_masiva.validar_archivo(contenido)
        except carga_masiva.ArchivoInvalido as error:
            raise ValidationError({'archivo': str(error)})
        resultado['archivo'] = nombre
        resultado['filas'] = carga_masiva.publicas(resultado['filas'])
        return Response(resultado)


class ConfirmarView(APIView):
    """POST /carga-masiva/confirmar/ (multipart: `archivo` y `hash` de la vista
    previa) → guarda solo las filas válidas, en una sola transacción."""

    permission_classes = [SoloAdministrador]
    parser_classes = [MultiPartParser]

    def post(self, request):
        nombre, contenido = _archivo(request)
        try:
            resultado = carga_masiva.cargar_archivo(
                contenido, nombre, request.user, request.data.get('hash'))
        except carga_masiva.ArchivoInvalido as error:
            raise ValidationError({'archivo': str(error)})
        return Response(resultado, status=201)
