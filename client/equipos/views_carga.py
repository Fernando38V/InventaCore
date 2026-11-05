"""Carga masiva de artículos desde Excel (RF-24, RF-25, DEC-017). Solo Administrador.

Pasos: descargar la plantilla, subir el archivo lleno (la API lo valida y
devuelve la vista previa sin guardar nada) y confirmar (la API vuelve a
validar y guarda solo las filas válidas).

La API pide el mismo archivo otra vez al confirmar, junto con la huella
(`hash`) de la vista previa. Para no obligar a subirlo dos veces, el cliente
guarda una copia temporal en disco y en la sesión solo la ruta, el nombre y
la huella. La copia se borra al confirmar o al subir otro archivo.
"""
import os
import tempfile
import time
import uuid

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from client.api import ApiError, SesionVencida, descargar, enviar_archivo
from client.utils import errores_api, es_admin

SESION = 'carga_masiva'
MAX_BYTES = 5 * 1024 * 1024          # mismo límite que la API (carga_masiva.MAX_BYTES)
CADUCIDAD = 24 * 60 * 60              # copias temporales olvidadas se borran al día
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

# Nombre de cada columna para los mensajes. La vista previa trae `columnas`
# de la API; la respuesta de confirmar no, y se usan estos.
ETIQUETAS = {
    'identificador': 'Marbete o folio', 'categoria': 'Categoría',
    'tipo_articulo': 'Tipo de artículo', 'marca': 'Marca', 'modelo': 'Modelo',
    'num_serie': 'Número de serie', 'color': 'Color', 'descripcion': 'Descripción',
    'ubicacion': 'Ubicación', 'resguardante': 'Resguardante',
    'estado_operativo': 'Estado operativo', 'fecha_adquisicion': 'Fecha de adquisición',
    'costo_adquisicion': 'Costo de adquisición', 'donado': '¿Donado?',
}

# Columnas que se muestran en la tabla y las claves de la API que cubren:
# una celda se marca en rojo si alguna de sus claves trae error.
COLUMNAS_TABLA = [
    ('identificador', ('identificador',)),
    ('articulo', ('categoria', 'tipo_articulo', 'marca', 'modelo')),
    ('num_serie', ('num_serie',)),
    ('ubicacion', ('ubicacion', 'estado_operativo')),
    ('resguardante', ('resguardante',)),
    ('adquisicion', ('fecha_adquisicion', 'costo_adquisicion', 'donado')),
]


# --- copia temporal del archivo ------------------------------------------

def _carpeta():
    carpeta = getattr(settings, 'CARGA_MASIVA_DIR', None) or os.path.join(
        tempfile.gettempdir(), 'inventacore_carga')
    os.makedirs(carpeta, exist_ok=True)
    return carpeta


def _limpiar_viejos(carpeta):
    limite = time.time() - CADUCIDAD
    for nombre in os.listdir(carpeta):
        ruta = os.path.join(carpeta, nombre)
        try:
            if os.path.getmtime(ruta) < limite:
                os.remove(ruta)
        except OSError:
            pass


def _olvidar(request):
    datos = request.session.pop(SESION, None)
    if datos:
        try:
            os.remove(datos['ruta'])
        except OSError:
            pass


def _guardar(request, nombre, contenido, huella):
    _olvidar(request)
    carpeta = _carpeta()
    _limpiar_viejos(carpeta)
    ruta = os.path.join(carpeta, uuid.uuid4().hex + '.xlsx')
    with open(ruta, 'wb') as f:
        f.write(contenido)
    request.session[SESION] = {'ruta': ruta, 'nombre': nombre, 'hash': huella}


def _recuperar(request):
    """(nombre, contenido, hash) del archivo revisado, o None."""
    datos = request.session.get(SESION)
    if not datos:
        return None
    try:
        with open(datos['ruta'], 'rb') as f:
            return datos['nombre'], f.read(), datos['hash']
    except OSError:
        request.session.pop(SESION, None)
        return None


# --- auxiliares ----------------------------------------------------------

def _mensaje(error):
    """Los errores del archivo llegan como {'archivo': mensaje}."""
    datos = error.datos if isinstance(error.datos, dict) else {}
    if datos.get('archivo'):
        valor = datos['archivo']
        return ' '.join(valor) if isinstance(valor, list) else str(valor)
    return errores_api(error)[1]


def _sin_permiso(request):
    messages.error(request, 'Solo el Administrador puede hacer la carga masiva.')
    return redirect('equipos:listado')


def _filas(filas, columnas):
    """Prepara las filas de la API para la tabla."""
    columnas = dict(ETIQUETAS, **(columnas or {}))
    resultado = []
    for f in filas:
        d = f.get('datos') or {}
        errores = f.get('errores') or {}
        marcadas = {col for col, claves in COLUMNAS_TABLA if any(c in errores for c in claves)}
        resultado.append({
            'hoja': f['hoja'], 'fila': f['fila'], 'valida': f['estado'] == 'valida',
            'origen': d.get('origen'),
            'identificador': d.get('identificador'),
            'categoria': d.get('categoria'), 'tipo': d.get('tipo_articulo'),
            'marca_modelo': ' '.join(p for p in (d.get('marca'), d.get('modelo')) if p),
            'num_serie': d.get('num_serie'),
            'ubicacion': d.get('ubicacion'), 'estado_operativo': d.get('estado_operativo'),
            'resguardante': d.get('resguardante'),
            'fecha': d.get('fecha_adquisicion'), 'costo': d.get('costo_adquisicion'),
            'donado': (d.get('donado') or '').strip().lower() in ('sí', 'si', 's', 'x'),
            'errores': [(columnas.get(c, c.replace('_', ' ').capitalize()), m)
                        for c, m in errores.items()],
            'marcadas': marcadas,
        })
    return resultado


# --- vistas --------------------------------------------------------------

def carga_masiva(request):
    """GET: paso 1 (plantilla y subir). POST: valida el archivo y muestra la vista previa."""
    if not es_admin(request):
        return _sin_permiso(request)

    error = ''
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if archivo is None:
            error = 'Elige el archivo de Excel con la plantilla llena.'
        elif not archivo.name.lower().endswith('.xlsx'):
            error = 'El archivo debe ser de Excel (.xlsx). Usa la plantilla del sistema.'
        elif archivo.size > MAX_BYTES:
            error = 'El archivo pesa más de 5 MB. Divídelo en archivos más pequeños.'
        else:
            contenido = archivo.read()
            try:
                previa = enviar_archivo(request, 'carga-masiva/validar/', archivo.name, contenido)
            except SesionVencida:
                raise
            except ApiError as e:
                error = _mensaje(e)
            else:
                _guardar(request, archivo.name, contenido, previa['hash'])
                columnas = previa.get('columnas') or {}
                filas = _filas(previa.get('filas') or [], columnas)
                return render(request, 'equipos/carga_masiva.html', {
                    'paso': 'previa', 'previa': previa, 'filas': filas,
                    'puede_confirmar': previa['validas'] > 0 and not previa.get('ya_cargado'),
                })

    return render(request, 'equipos/carga_masiva.html', {'paso': 'subir', 'error': error})


def plantilla_carga(request):
    """Descarga la plantilla que arma la API con los catálogos vigentes."""
    if not es_admin(request):
        return _sin_permiso(request)
    try:
        contenido = descargar(request, 'carga-masiva/plantilla/')
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, 'No se pudo descargar la plantilla: ' + _mensaje(e))
        return redirect('equipos:carga_masiva')
    respuesta = HttpResponse(contenido, content_type=XLSX)
    respuesta['Content-Disposition'] = 'attachment; filename="plantilla_carga_masiva.xlsx"'
    return respuesta


@require_POST
def confirmar_carga(request):
    """Manda el archivo revisado y su huella; la API guarda solo las filas válidas."""
    if not es_admin(request):
        return _sin_permiso(request)
    guardado = _recuperar(request)
    if guardado is None:
        messages.warning(request, 'La vista previa ya no está disponible. Sube el archivo de nuevo.')
        return redirect('equipos:carga_masiva')
    nombre, contenido, huella = guardado
    try:
        resultado = enviar_archivo(request, 'carga-masiva/confirmar/', nombre, contenido,
                                   {'hash': huella})
    except SesionVencida:
        raise
    except ApiError as e:
        _olvidar(request)
        if e.status == 0:
            messages.error(request, _mensaje(e) + ' Revisa en el listado si los artículos se '
                           'cargaron antes de intentarlo otra vez.')
        else:
            messages.error(request, _mensaje(e))
        return redirect('equipos:carga_masiva')
    _olvidar(request)
    rechazadas = _filas(resultado.get('filas_rechazadas') or [], {})
    return render(request, 'equipos/carga_masiva.html', {
        'paso': 'resultado', 'resultado': resultado, 'rechazadas': rechazadas,
    })
