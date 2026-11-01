import json
from urllib import error as urlerror
from urllib import request as urlrequest

from django.conf import settings


class ApiError(Exception):
    """La API respondió con error o no se pudo conectar (status 0)."""

    def __init__(self, status, datos=None):
        self.status = status
        self.datos = datos or {}
        super().__init__(str(self.datos))


class SesionVencida(ApiError):
    """Token vencido o inválido (401)."""


def llamar(request, metodo, ruta, datos=None):
    """Llama a la API. `ruta` sin la base y con diagonal final, ej. 'auth/login/'.
    Si hay sesión, manda el token guardado. Devuelve el JSON ya convertido."""
    url = settings.API_URL.rstrip('/') + '/' + ruta.lstrip('/')
    cuerpo = json.dumps(datos).encode('utf-8') if datos is not None else None
    cabeceras = {'Accept': 'application/json'}
    if cuerpo is not None:
        cabeceras['Content-Type'] = 'application/json'
    token = request.session.get('api_token') if request is not None else None
    if token:
        cabeceras['Authorization'] = 'Token ' + token

    peticion = urlrequest.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urlrequest.urlopen(peticion, timeout=10) as respuesta:
            texto = respuesta.read().decode('utf-8')
            return json.loads(texto) if texto else None
    except urlerror.HTTPError as e:
        texto = e.read().decode('utf-8', 'replace')
        try:
            detalle = json.loads(texto)
        except ValueError:
            detalle = {'detalle': 'Error %s en el servidor.' % e.code}
        if e.code == 401:
            raise SesionVencida(401, detalle)
        raise ApiError(e.code, detalle)
    except urlerror.URLError:
        raise ApiError(0, {'detalle': 'No se pudo conectar con el servidor. '
                                      'Verifica que la API esté encendida.'})