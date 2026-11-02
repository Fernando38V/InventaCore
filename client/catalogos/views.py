"""Pantallas de catálogos y de personal conectadas a la API.

Una sola implementación sirve a los cinco catálogos; lo que cambia de uno a
otro está en catalogos/config.py. Las vistas de personal (personal/urls.py)
reutilizan estas mismas funciones con catalogo='personal'.

La API es la que decide los permisos: aquí solo se ocultan los botones y se
evita mostrar formularios al rol Consulta.
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from catalogos.config import CATALOGOS, PERSONAL
from client.api import ApiError, SesionVencida, llamar
from client.utils import (
    contexto_paginacion, destino_seguro, errores_api, es_admin, listar_todo,
    numero_de_pagina)

CONFIG = dict(CATALOGOS, personal=PERSONAL)

# fuente de un select -> (ruta de la API, campo que se guarda, texto que se ve)
FUENTES = {
    'categorias': ('categorias', 'codigo', lambda f: f['nombre']),
    'departamentos': ('departamentos', 'codigo', lambda f: f['nombre']),
    'personal': ('personal', 'num',
                 lambda f: '%s — %s' % (f['numero_empleado'], f['nombre_completo'])),
}


# --- auxiliares ---------------------------------------------------------

def _config(catalogo):
    cfg = CONFIG.get(catalogo)
    if cfg is None:
        raise Http404
    return cfg


def _url(cfg, accion, *args):
    """URL del cliente. Personal tiene su propio espacio de nombres."""
    if cfg['ns'] == 'personal':
        nombre = 'listado' if accion == 'lista' else accion
        return reverse('personal:' + nombre, args=args)
    return reverse('catalogos:' + accion, args=(cfg['slug'],) + args)


def _url_con_filtros(cfg, params):
    return _url(cfg, 'lista') + ('?' + urlencode(params) if params else '')


def _sin_permiso(request, cfg):
    messages.error(request, 'Solo el Administrador puede hacer esto.')
    return redirect(_url(cfg, 'lista'))


def _opciones(request, fuente, actual='', todos=False):
    """Opciones [{valor, texto}] de un select a partir de un listado de la API.
    En los formularios solo se ofrecen los activos, más el valor actual aunque
    ya esté inactivo (para no perderlo al editar)."""
    ruta, campo_valor, texto = FUENTES[fuente]
    opciones = []
    for f in listar_todo(request, ruta):
        valor = str(f[campo_valor])
        if todos or f['activo'] or valor == str(actual):
            etiqueta = texto(f)
            opciones.append({
                'valor': valor,
                'texto': etiqueta if f['activo'] else etiqueta + ' (inactivo)',
            })
    return opciones


def _leer_filtros(request, cfg):
    """(valores actuales, parámetros para la API) a partir del query string."""
    nombres = [f['nombre'] for f in cfg['filtros']]
    if cfg.get('busqueda'):
        nombres.append('q')
    actuales = {}
    for nombre in nombres:
        valor = request.GET.get(nombre, '').strip()
        if nombre == 'activo' and valor not in ('true', 'false'):
            valor = ''
        actuales[nombre] = valor
    return actuales, {k: v for k, v in actuales.items() if v}


def _fila(cfg, item):
    pk = item[cfg['pk']]
    activo = item['activo']
    celdas = []
    for etiqueta, campo in cfg['columnas']:
        valor = item.get(campo)
        celdas.append((etiqueta, '—' if valor in (None, '') else valor))
    aviso = cfg['aviso_baja'] if activo else cfg['aviso_alta']
    if activo and item.get('articulos_a_cargo'):
        aviso = ('Tiene %d artículo(s) a su cargo y seguirán a su nombre hasta '
                 'que se reasignen con un movimiento. %s'
                 % (item['articulos_a_cargo'], cfg['aviso_baja']))
    return {
        'pk': pk,
        'nombre': item[cfg['campo_nombre']],
        'activo': activo,
        'celdas': celdas,
        'protegido': str(pk) in cfg['protegidos'],
        'aviso': aviso,
        'url_editar': _url(cfg, 'editar', pk),
        'url_estado': _url(cfg, 'estado', pk),
    }


# --- listado ------------------------------------------------------------

def inicio(request):
    return redirect('catalogos:lista', catalogo='categorias')


def lista(request, catalogo):
    cfg = _config(catalogo)
    pagina = numero_de_pagina(request)
    actuales, params = _leer_filtros(request, cfg)

    error = ''
    datos = {'count': 0, 'results': []}
    try:
        datos = llamar(request, 'GET', '%s/?%s' % (
            cfg['api'], urlencode(dict(params, page=pagina))))
    except SesionVencida:
        raise
    except ApiError as e:
        if e.status == 404 and pagina > 1:      # página que ya no existe
            return redirect(_url_con_filtros(cfg, params))
        error = errores_api(e)[1]

    filtros = []
    for f in cfg['filtros']:
        if 'opciones' in f:
            opciones = [{'valor': v, 'texto': t} for v, t in f['opciones']]
        else:
            try:
                opciones = _opciones(request, f['fuente'], todos=True)
            except SesionVencida:
                raise
            except ApiError as e:
                opciones = []
                error = error or errores_api(e)[1]
        filtros.append({'nombre': f['nombre'], 'todos': f['todos'],
                        'opciones': opciones, 'actual': actuales[f['nombre']]})

    pestanas = []
    if cfg['ns'] == 'catalogos':
        pestanas = [{'titulo': c['titulo'], 'url': _url(c, 'lista'),
                     'activa': c is cfg} for c in CATALOGOS.values()]

    contexto = {
        'cfg': cfg,
        'filas': [_fila(cfg, item) for item in datos['results']],
        'filtros': filtros,
        'f': actuales,
        'hay_filtros': any(actuales.values()),
        'url_lista': _url(cfg, 'lista'),
        'url_nuevo': _url(cfg, 'nuevo'),
        'pestanas': pestanas,
        'error_api': error,
    }
    contexto.update(contexto_paginacion(request, datos['count'], pagina))
    return render(request, 'catalogos/listado.html', contexto)


# --- alta y edición -----------------------------------------------------

def _norm(valor):
    return '' if valor is None else str(valor)


def _valor_api(campo, texto):
    """Valor que se manda a la API: null si el campo admite vacío."""
    if texto == '':
        return None if campo.get('nulo') else ''
    if campo.get('entero') and texto.isdigit():
        return int(texto)
    return texto


def _formulario(request, cfg, pk=None):
    if not es_admin(request):
        return _sin_permiso(request, cfg)

    editando = pk is not None
    registro = None
    if editando:
        try:
            registro = llamar(request, 'GET', '%s/%s/' % (cfg['api'], pk))
        except SesionVencida:
            raise
        except ApiError as e:
            if e.status == 404:
                raise Http404
            messages.error(request, errores_api(e)[1])
            return redirect(_url(cfg, 'lista'))
        if str(pk) in cfg['protegidos']:
            messages.error(request, 'Este registro es del sistema y no se puede modificar.')
            return redirect(_url(cfg, 'lista'))

    campos = cfg['campos']
    valores = {c['nombre']: _norm(registro.get(c['nombre'])) if registro else ''
               for c in campos}
    errores, general, motivo = {}, '', ''

    if request.method == 'POST':
        valores = {c['nombre']: request.POST.get(c['nombre'], '').strip()
                   for c in campos}
        motivo = request.POST.get('motivo', '').strip()

        for c in campos:
            if c.get('requerido') and not valores[c['nombre']]:
                errores[c['nombre']] = 'Este campo es obligatorio.'

        cambios = {}
        if editando:
            # Solo se mandan los campos que cambiaron: la bitácora de la API
            # guarda únicamente esos.
            cambios = {c['nombre']: _valor_api(c, valores[c['nombre']])
                       for c in campos
                       if valores[c['nombre']] != _norm(registro.get(c['nombre']))}
            if not errores and not cambios:
                general = 'No hiciste ningún cambio.'
            elif cambios and not motivo:
                errores['motivo'] = 'Indica el motivo del cambio.'

        if not errores and not general:
            try:
                if editando:
                    guardado = llamar(request, 'PATCH', '%s/%s/' % (cfg['api'], pk),
                                      dict(cambios, motivo=motivo))
                else:
                    guardado = llamar(request, 'POST', cfg['api'] + '/', {
                        c['nombre']: _valor_api(c, valores[c['nombre']])
                        for c in campos})
            except SesionVencida:
                raise
            except ApiError as e:
                por_campo, general = errores_api(
                    e, [c['nombre'] for c in campos] + ['motivo'])
                errores.update(por_campo)
            else:
                guardado = guardado or {}
                nombre = guardado.get(cfg['campo_nombre'], '')
                sujeto = cfg['singular'].capitalize()
                if editando:
                    mensaje = '%s «%s» actualizad%s.' % (sujeto, nombre, cfg['a'])
                elif cfg['genera_codigo']:
                    mensaje = '%s «%s» registrad%s con el código %s.' % (
                        sujeto, nombre, cfg['a'], guardado.get('codigo', ''))
                else:
                    mensaje = '%s «%s» registrad%s.' % (sujeto, nombre, cfg['a'])
                messages.success(request, mensaje)
                return redirect(_url(cfg, 'lista'))

    campos_ctx = []
    for c in campos:
        campo = dict(c, tipo=c.get('tipo', 'text'), valor=valores[c['nombre']],
                     error=errores.get(c['nombre']),
                     ayuda=(c.get('ayuda') or '') if not editando
                     else (c.get('ayuda_editar') or c.get('ayuda') or ''))
        if c.get('fuente'):
            try:
                campo['opciones'] = _opciones(request, c['fuente'],
                                              actual=valores[c['nombre']])
            except SesionVencida:
                raise
            except ApiError as e:
                campo['opciones'] = []
                general = general or errores_api(e)[1]
        campos_ctx.append(campo)

    return render(request, 'catalogos/form.html', {
        'cfg': cfg,
        'editando': editando,
        'pk': pk,
        'campos': campos_ctx,
        'general': general,
        'motivo': motivo,
        'error_motivo': errores.get('motivo'),
        'url_lista': _url(cfg, 'lista'),
    })


def nuevo(request, catalogo):
    return _formulario(request, _config(catalogo))


def editar(request, catalogo, codigo):
    return _formulario(request, _config(catalogo), codigo)


# --- activar / desactivar ----------------------------------------------

@require_POST
def cambiar_estado(request, catalogo, codigo):
    """La baja es lógica (`activo`) y, como toda edición, exige motivo."""
    cfg = _config(catalogo)
    if not es_admin(request):
        return _sin_permiso(request, cfg)

    activar = request.POST.get('activar') == '1'
    motivo = request.POST.get('motivo', '').strip()
    volver = destino_seguro(request, request.POST.get('volver'), _url(cfg, 'lista'))

    if not motivo:
        messages.error(request, 'Indica el motivo del cambio.')
        return redirect(volver)
    try:
        guardado = llamar(request, 'PATCH', '%s/%s/' % (cfg['api'], codigo),
                          {'activo': activar, 'motivo': motivo})
    except SesionVencida:
        raise
    except ApiError as e:
        messages.error(request, errores_api(e)[1])
    else:
        messages.success(request, '%s «%s» %s.' % (
            cfg['singular'].capitalize(), (guardado or {}).get(cfg['campo_nombre'], ''),
            ('activad' if activar else 'desactivad') + cfg['a']))
    return redirect(volver)
