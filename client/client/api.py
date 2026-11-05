import json
import uuid
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
    url, cabeceras = _url_y_cabeceras(request, ruta, 'application/json')
    cuerpo = json.dumps(datos).encode('utf-8') if datos is not None else None
    if cuerpo is not None:
        cabeceras['Content-Type'] = 'application/json'
    peticion = urlrequest.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    texto = _ejecutar(peticion, timeout=10).decode('utf-8')
    return json.loads(texto) if texto else None


def _url_y_cabeceras(request, ruta, accept):
    url = settings.API_URL.rstrip('/') + '/' + ruta.lstrip('/')
    cabeceras = {'Accept': accept}
    token = request.session.get('api_token') if request is not None else None
    if token:
        cabeceras['Authorization'] = 'Token ' + token
    return url, cabeceras


def _ejecutar(peticion, timeout):
    """Hace la petición y devuelve el cuerpo en bytes; traduce los errores."""
    try:
        with urlrequest.urlopen(peticion, timeout=timeout) as respuesta:
            return respuesta.read()
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
    except TimeoutError:
        raise ApiError(0, {'detalle': 'El servidor tardó demasiado en responder.'})


def descargar(request, ruta):
    """GET de un archivo (por ejemplo la plantilla .xlsx). Devuelve los bytes."""
    url, cabeceras = _url_y_cabeceras(request, ruta, '*/*')
    return _ejecutar(urlrequest.Request(url, headers=cabeceras, method='GET'), timeout=30)


def enviar_archivo(request, ruta, nombre, contenido, campos=None, timeout=120):
    """POST multipart con un archivo en el campo `archivo` y campos de texto.
    Devuelve el JSON. El tiempo de espera es mayor porque la API procesa todo
    el archivo (la carga masiva admite hasta 2000 filas)."""
    limite = uuid.uuid4().hex
    partes = []
    for clave, valor in (campos or {}).items():
        partes.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                       % (limite, clave, valor)).encode('utf-8'))
    nombre_seguro = nombre.replace('"', '').replace('\r', '').replace('\n', '')
    partes.append(('--%s\r\nContent-Disposition: form-data; name="archivo"; filename="%s"\r\n'
                   'Content-Type: application/octet-stream\r\n\r\n'
                   % (limite, nombre_seguro)).encode('utf-8'))
    partes.append(contenido)
    partes.append(('\r\n--%s--\r\n' % limite).encode('utf-8'))
    url, cabeceras = _url_y_cabeceras(request, ruta, 'application/json')
    cabeceras['Content-Type'] = 'multipart/form-data; boundary=%s' % limite
    peticion = urlrequest.Request(url, data=b''.join(partes), headers=cabeceras, method='POST')
    texto = _ejecutar(peticion, timeout=timeout).decode('utf-8')
    return json.loads(texto) if texto else None
