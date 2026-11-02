"""Definición de cada catálogo del cliente.

Los nombres de campo son los de los serializers de la API
(api/catalogos/serializers.py y api/personal/serializers.py). Las vistas
genéricas de catalogos/views.py se configuran con estos diccionarios.

Claves de uso general:
  ns, slug, api   - espacio de URLs del cliente, ruta del cliente y ruta de la API
  pk              - campo que identifica el registro en la URL de la API
  a               - terminación de género para los mensajes ('a' o 'o')
  columnas        - (etiqueta, campo) de la tabla del listado
  campos          - campos del formulario (max = longitud máxima del modelo,
                    nulo = se manda null si queda vacío, entero = se manda int,
                    fuente = select cuyas opciones salen de otro listado)
  filtros         - selects del listado (el nombre es también el parámetro de la API)
  protegidos      - registros del sistema que no se editan ni se desactivan
"""

ESTADO = {
    'nombre': 'activo',
    'todos': 'Todos los estados',
    'opciones': [('true', 'Activos'), ('false', 'Inactivos')],
}

AVISO_ALTA = 'El registro volverá a estar activo.'
AVISO_BAJA = 'El registro no se borra: queda inactivo y se conserva en el historial.'

CATALOGOS = {
    'categorias': {
        'ns': 'catalogos', 'slug': 'categorias', 'api': 'categorias', 'pk': 'codigo',
        'genera_codigo': True, 'a': 'a',
        'singular': 'categoría', 'plural': 'categorías',
        'titulo': 'Categorías',
        'subtitulo': 'Agrupan los tipos de artículo del inventario',
        'nuevo': 'Nueva categoría', 'editar': 'Editar categoría',
        'de': 'la categoría',
        'campo_nombre': 'nombre',
        'columnas': [('Código', 'codigo'), ('Nombre', 'nombre'),
                     ('Descripción', 'descripcion')],
        'campos': [
            {'nombre': 'nombre', 'etiqueta': 'Nombre', 'requerido': True,
             'max': 100, 'completo': True},
            {'nombre': 'descripcion', 'etiqueta': 'Descripción', 'tipo': 'textarea',
             'nulo': True, 'max': 150, 'completo': True},
        ],
        'filtros': [ESTADO],
        'protegidos': (),
        'aviso_baja': ('No se podrán crear tipos nuevos en una categoría '
                       'desactivada. El registro no se borra.'),
        'aviso_alta': AVISO_ALTA,
    },

    'tipos-articulo': {
        'ns': 'catalogos', 'slug': 'tipos-articulo', 'api': 'tipos-articulo',
        'pk': 'codigo', 'genera_codigo': True, 'a': 'o',
        'singular': 'tipo de artículo', 'plural': 'tipos de artículo',
        'titulo': 'Tipos de artículo',
        'subtitulo': 'Clasifican cada artículo dentro de su categoría',
        'nuevo': 'Nuevo tipo de artículo', 'editar': 'Editar tipo de artículo',
        'de': 'del tipo de artículo',
        'campo_nombre': 'nombre',
        'columnas': [('Código', 'codigo'), ('Nombre', 'nombre'),
                     ('Categoría', 'categoria_nombre'),
                     ('Descripción', 'descripcion')],
        'campos': [
            {'nombre': 'categoria', 'etiqueta': 'Categoría', 'tipo': 'select',
             'requerido': True, 'fuente': 'categorias',
             'ayuda_editar': ('No se puede cambiar de categoría si ya hay '
                              'artículos de este tipo.')},
            {'nombre': 'nombre', 'etiqueta': 'Nombre', 'requerido': True, 'max': 100},
            {'nombre': 'descripcion', 'etiqueta': 'Descripción', 'tipo': 'textarea',
             'nulo': True, 'max': 150, 'completo': True},
        ],
        'filtros': [
            {'nombre': 'categoria', 'todos': 'Todas las categorías',
             'fuente': 'categorias'},
            ESTADO,
        ],
        'protegidos': (),
        'aviso_baja': AVISO_BAJA,
        'aviso_alta': AVISO_ALTA,
    },

    'ubicaciones': {
        'ns': 'catalogos', 'slug': 'ubicaciones', 'api': 'ubicaciones',
        'pk': 'codigo', 'genera_codigo': True, 'a': 'a',
        'singular': 'ubicación', 'plural': 'ubicaciones',
        'titulo': 'Ubicaciones',
        'subtitulo': 'Espacios físicos donde se resguardan los artículos',
        'nuevo': 'Nueva ubicación', 'editar': 'Editar ubicación',
        'de': 'la ubicación',
        'campo_nombre': 'nombre',
        'columnas': [('Código', 'codigo'), ('Nombre', 'nombre'),
                     ('Responsable', 'responsable_nombre'),
                     ('Descripción', 'descripcion')],
        'campos': [
            {'nombre': 'nombre', 'etiqueta': 'Nombre', 'requerido': True, 'max': 100},
            {'nombre': 'responsable', 'etiqueta': 'Responsable', 'tipo': 'select',
             'fuente': 'personal', 'nulo': True, 'entero': True,
             'ayuda': 'Opcional. Solo se ofrece personal activo.'},
            {'nombre': 'descripcion', 'etiqueta': 'Descripción', 'tipo': 'textarea',
             'nulo': True, 'max': 150, 'completo': True},
        ],
        'filtros': [ESTADO],
        # UBI-NOLOC es del sistema (DEC-012): la API no la renombra ni desactiva.
        'protegidos': ('UBI-NOLOC',),
        'aviso_baja': AVISO_BAJA,
        'aviso_alta': AVISO_ALTA,
    },

    'departamentos': {
        'ns': 'catalogos', 'slug': 'departamentos', 'api': 'departamentos',
        'pk': 'codigo', 'genera_codigo': True, 'a': 'o',
        'singular': 'departamento', 'plural': 'departamentos',
        'titulo': 'Departamentos',
        'subtitulo': 'Unidades organizativas a las que pertenece el personal',
        'nuevo': 'Nuevo departamento', 'editar': 'Editar departamento',
        'de': 'del departamento',
        'campo_nombre': 'nombre',
        'columnas': [('Código', 'codigo'), ('Nombre', 'nombre'),
                     ('Descripción', 'descripcion')],
        'campos': [
            {'nombre': 'nombre', 'etiqueta': 'Nombre', 'requerido': True,
             'max': 100, 'completo': True},
            # En el modelo Departamento la descripción es obligatoria.
            {'nombre': 'descripcion', 'etiqueta': 'Descripción', 'tipo': 'textarea',
             'requerido': True, 'max': 150, 'completo': True},
        ],
        # La API no filtra departamentos por `activo`: no hay filtros.
        'filtros': [],
        'protegidos': (),
        'aviso_baja': ('No se podrá asignar a personal nuevo. '
                       'El registro no se borra.'),
        'aviso_alta': AVISO_ALTA,
    },
}

PERSONAL = {
    'ns': 'personal', 'slug': 'personal', 'api': 'personal', 'pk': 'num',
    'genera_codigo': False, 'a': 'o',
    'singular': 'empleado', 'plural': 'empleados',
    'titulo': 'Personal',
    'subtitulo': 'Personal del plantel que puede ser resguardante de artículos',
    'nuevo': 'Nuevo empleado', 'editar': 'Editar empleado',
    'de': 'del empleado',
    'campo_nombre': 'nombre_completo',
    'busqueda': 'Número de empleado o nombre',
    'columnas': [('Núm. empleado', 'numero_empleado'),
                 ('Nombre', 'nombre_completo'), ('Puesto', 'puesto'),
                 ('Departamento', 'departamento_nombre'),
                 ('Artículos a cargo', 'articulos_a_cargo')],
    'campos': [
        {'nombre': 'numero_empleado', 'etiqueta': 'Número de empleado',
         'requerido': True, 'max': 20},
        {'nombre': 'departamento', 'etiqueta': 'Departamento', 'tipo': 'select',
         'requerido': True, 'fuente': 'departamentos'},
        {'nombre': 'nombre_pila', 'etiqueta': 'Nombre(s)', 'requerido': True,
         'max': 50},
        {'nombre': 'primer_apellido', 'etiqueta': 'Primer apellido',
         'requerido': True, 'max': 50},
        {'nombre': 'segundo_apellido', 'etiqueta': 'Segundo apellido',
         'nulo': True, 'max': 50},
        {'nombre': 'puesto', 'etiqueta': 'Puesto', 'requerido': True, 'max': 50},
    ],
    'filtros': [
        {'nombre': 'departamento', 'todos': 'Todos los departamentos',
         'fuente': 'departamentos'},
        ESTADO,
    ],
    'protegidos': (),
    # DEC-003: solo el personal activo recibe asignaciones nuevas; el historial se conserva.
    'aviso_baja': ('Ya no podrá recibir artículos a su resguardo. '
                   'El registro y su historial se conservan.'),
    'aviso_alta': 'Volverá a poder recibir artículos a su resguardo.',
}
