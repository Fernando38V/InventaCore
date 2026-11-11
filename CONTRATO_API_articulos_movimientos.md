# Contrato de la API — Artículos, Movimientos, Resguardos, Dashboard, Reportes y Carga masiva y Bitácora (v14)

Backend: `http://127.0.0.1:8000/api/`. Todas las peticiones (menos el login) llevan
`Authorization: Token <token>`. El rol CONSULTA solo puede hacer GET; ADMIN puede todo.
Los ejemplos son respuestas reales del backend. Refleja DECISIONES.md al 03/11/2026 (DEC-013, DEC-016, DEC-018, DEC-020).

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/articulos/` | Lista paginada (10 por página, `?page=2`) |
| GET | `/articulos/<num>/` | Detalle |
| POST | `/articulos/` | Alta (crea también el movimiento ALTA) |
| PATCH | `/articulos/<num>/` | Corregir la ficha, con motivo (DEC-013) |
| GET | `/articulos/<num>/movimientos/` | Historial de ese artículo |
| GET | `/movimientos/` | Lista paginada |
| GET | `/movimientos/<folio>/` | Detalle, por ejemplo `/movimientos/MOV-0001/` |
| POST | `/movimientos/` | Nuevo movimiento (REUB, REPA, RETE) |
| GET | `/articulos/todos/` | Todo el inventario filtrado, **sin paginar** (mismos filtros que la lista) |
| GET | `/articulos/exportar/` | Excel (.xlsx) del inventario filtrado (DEC-018). Admin y Consulta |
| GET | `/resguardos/` | Lista paginada (filtros: `q`, `resguardante`, `articulo`) |
| GET | `/resguardos/<folio>/` | Detalle, por ejemplo `/resguardos/RES-0001/` |
| POST | `/resguardos/` | Emitir un resguardo (solo Administrador) |
| GET | `/resguardos/<folio>/pdf/` | El PDF emitido, sin cambios (reimpresión) |
| GET | `/resguardos/pendientes/?resguardante=<num>` | Asignaciones que requieren resguardo y aún no tienen |
| GET | `/carga-masiva/plantilla/` | Plantilla .xlsx con listas desplegables (solo Administrador) |
| POST | `/carga-masiva/validar/` | Sube el Excel y devuelve la vista previa; no guarda nada (solo Administrador) |
| POST | `/carga-masiva/confirmar/` | Guarda solo las filas válidas (solo Administrador) |
| GET | `/bitacora/` | Bitácora de auditoría, paginada, más reciente primero (solo Administrador) |
| GET | `/bitacora/<num>/` | Un registro de la bitácora (solo Administrador) |
| GET | `/dashboard/` | Totales para el tablero (DEC-020) |
| GET | `/reportes/inventario/` | Inventario filtrable sin paginar; `?formato=xlsx` lo descarga |
| GET | `/reportes/resguardante/<num>/` | Artículos que tiene hoy un resguardante; `?formato=xlsx` |
| GET | `/reportes/historial/<num>/` | Artículo, todos sus movimientos y sus resguardos |

No hay DELETE (RNF-06) ni PUT. Apoyo para los formularios: `/categorias/`,
`/tipos-articulo/?categoria=CAT-001`, `/ubicaciones/`, `/origenes/`, `/estados-operativos/`,
`/estados-registro/`, `/tipos-movimiento/`, `/personal/?activo=true`.

Paginación: `{"count": 12, "next": "<url|null>", "previous": "<url|null>", "results": [...]}`.

Filtros de `/articulos/`: `q`, `categoria`, `tipo_articulo`, `ubicacion`, `estado_operativo`,
`estado_registro`, `origen`, `resguardante` (num). `q` busca por palabras sueltas en identificador,
marca, modelo, serie, descripción, color, tipo, categoría, ubicación y resguardante.
Filtros de `/movimientos/`: `q`, `tipo`, `ubicacion` (origen o destino), `articulo` (num).

## Artículo (GET, y respuesta del POST y del PATCH)

```json
{
  "num": 1,
  "marbete_oficial": "02-520-00003",
  "folio_interno": null,
  "identificador": "02-520-00003",
  "marca": "Dell",
  "modelo": "OptiPlex 3080",
  "num_serie": "5CD1234ABC",
  "color": "Negro",
  "descripcion": "Computadora de escritorio del laboratorio",
  "costo_adquisicion": "12500.00",
  "fecha_adquisicion": "2021-03-15",
  "fecha_alta": "2026-11-03",
  "tipo_articulo": {
    "codigo": "TIP-001",
    "nombre": "Computadora de escritorio"
  },
  "categoria": {
    "codigo": "CAT-001",
    "nombre": "EQUIPO DE CÓMPUTO"
  },
  "origen": {
    "codigo": "ACT",
    "nombre": "Activo"
  },
  "ubicacion": {
    "codigo": "UBI-OFI",
    "nombre": "Oficina de Informática"
  },
  "resguardante": {
    "num": 2,
    "numero_empleado": "1043",
    "nombre": "María Elena Ruiz Soto"
  },
  "estado_operativo": {
    "codigo": "OBS",
    "nombre": "Obsoleto",
    "tono": "gris"
  },
  "estado_registro": {
    "codigo": "REG",
    "nombre": "Registrado",
    "tono": "verde"
  },
  "faltantes": []
}
```

## Alta — `POST /articulos/`

```json
{
  "origen": "ACT",
  "tipo_articulo": "TIP-001",
  "ubicacion": "UBI-LAB2",
  "resguardante": 1,
  "marbete_oficial": "02-520-00003",
  "marca": "Dell",
  "modelo": "OptiPlex 3080",
  "num_serie": "5CD1234ABC",
  "color": "Negro",
  "descripcion": "Computadora de escritorio del laboratorio",
  "fecha_adquisicion": "2021-03-15",
  "costo_adquisicion": "12500.00"
}
```

Obligatorios: `origen`, `tipo_articulo`, `ubicacion`, `resguardante` (num), `color`, `descripcion` y,
si el origen es `ACT`, `marbete_oficial`. Marca, modelo, serie, fecha y costo son opcionales
(vacío = `null`). Opcionales especiales: `donado: true` y `estado_operativo` (`UTIL` por omisión;
un artículo puede darse de alta ya como `OBS`).

Lo pone el sistema: el folio interno de Comodato y Enser (`02143MMYY-NNN`, que nunca repite un
identificador existente), el estado de registro (Donado; Registrado con fecha y costo; Pendiente
si falta alguno), el movimiento ALTA y, si la ubicación es "Sin ubicar", el estado No localizado.
Un artículo Pendiente trae en `faltantes` lo que le falta.

## Corregir la ficha — `PATCH /articulos/<num>/`

Solo cambia lo que se manda. `motivo` es obligatorio y queda en la bitácora.

```json
{"marca": "Lenovo", "fecha_adquisicion": "2024-05-01", "motivo": "Datos del bien repuesto"}
```

Se pueden corregir: `marbete_oficial` (solo Activos), `marca`, `modelo`, `num_serie`, `color`,
`descripcion`, `fecha_adquisicion`, `costo_adquisicion` y `estado_operativo`. Si cambia la fecha o el costo,
el estado de registro se recalcula (DEC-008). En un bien Donado el costo también se puede capturar o corregir (DEC-021) y el estado se queda Donado. La ubicación y el resguardante no cambian aquí: solo por movimiento.

`estado_operativo` acepta `UTIL` u `OBS` (Obsoleto se marca desde la ficha, sin movimiento; la ubicación y
el resguardante se conservan). Un artículo No localizado no pasa a Obsoleto: se recupera con una
reubicación.

## Movimiento (GET, y respuesta del POST)

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "num": 2,
      "folio": "MOV-0002",
      "fecha": "2026-11-03 01:32",
      "fecha_dia": "2026-11-03",
      "fecha_hora": "01:32",
      "tipo": {
        "codigo": "ALTA",
        "nombre": "Alta de artículo"
      },
      "requiere_resguardo": true,
      "articulo": {
        "num": 2,
        "identificador": "021431126-001",
        "descripcion": "Lenovo"
      },
      "ubicacion_origen": null,
      "ubicacion_llegada": {
        "codigo": "UBI-OFI",
        "nombre": "Oficina de Informática"
      },
      "personal_asigna": {
        "num": 2,
        "numero_empleado": "1043",
        "nombre": "María Elena Ruiz Soto"
      },
      "personal_entrega": null,
      "nota": "Alta del artículo en el sistema",
      "usuario": {
        "num": 1,
        "username": "admin"
      }
    },
    {
      "num": 1,
      "folio": "MOV-0001",
      "fecha": "2026-11-03 01:32",
      "fecha_dia": "2026-11-03",
      "fecha_hora": "01:32",
      "tipo": {
        "codigo": "ALTA",
        "nombre": "Alta de artículo"
      },
      "requiere_resguardo": true,
      "articulo": {
        "num": 1,
        "identificador": "02-520-00003",
        "descripcion": "Dell OptiPlex 3080"
      },
      "ubicacion_origen": null,
      "ubicacion_llegada": {
        "codigo": "UBI-LAB2",
        "nombre": "Laboratorio de Informática 2"
      },
      "personal_asigna": {
        "num": 1,
        "numero_empleado": "1012",
        "nombre": "Juan Pérez Vázquez"
      },
      "personal_entrega": null,
      "nota": "Alta del artículo en el sistema",
      "usuario": {
        "num": 1,
        "username": "admin"
      }
    }
  ]
}
```

`personal_asigna` es quien queda como resguardante; `personal_entrega` es de quién lo recibe (solo
cuando cambió la persona, si no `null`); `nota` es el motivo; `requiere_resguardo` indica si el
movimiento debe documentarse con resguardo (DEC-016).

## Nuevo movimiento — `POST /movimientos/`

```json
{
  "tipo": "REUB",
  "articulo": 1,
  "ubicacion": "UBI-OFI",
  "resguardante": 2,
  "motivo": "Cambio de resguardante por reasignación de área",
  "fecha": "2026-10-20"
}
```

`tipo` es `REUB`, `REPA` o `RETE`. ALTA no se manda: se crea sola. `articulo` es el `num`
(`equipo` se acepta como sinónimo). `fecha` es opcional (hoy por omisión); puede ser pasada, no futura.
Lo que no cambia se omite o se manda vacío.

| Tipo | Reglas |
|---|---|
| REUB | Debe cambiar ubicación, resguardante o ambos. Si cambia la persona, `requiere_resguardo` es `true`. Ir a `UBI-NOLOC` deja el artículo No localizado. Salir de `UBI-NOLOC` reconfirma el estado: se manda `estado_operativo` (`UTIL` u `OBS`), por omisión `UTIL`. |
| REPA | Sin ubicación ni resguardante nuevos. No cambia el estado. No aplica a un artículo No localizado. |
| RETE | Exige `ubicacion`. Solo si el artículo está en reparación. |

Ya no existe el tipo BAJA ni el estado "Autorizado para baja" (DEC-006, DEC-012): Obsoleto es un estado.
La regla de que REPA y RETE van en pareja es mía, no está escrita en DECISIONES.md.

## Resguardos (RF-18, DEC-007, DEC-016)

Un resguardo reúne una o varias asignaciones (movimientos con `requiere_resguardo: true`) **del mismo
resguardante**; el resguardante firma un solo documento. Una asignación se documenta una sola vez.

`GET /resguardos/pendientes/?resguardante=1` sirve para armar la lista que se puede elegir:

```json
{"count": 2, "results": [{
  "folio": "MOV-0001", "tipo": {"codigo": "ALTA", "nombre": "Alta de artículo"},
  "requiere_resguardo": true, "resguardo": null,
  "articulo": {"num": 1, "identificador": "02-520-00001", "descripcion": "Dell Latitude 5420"},
  "personal_asigna": {"num": 1, "numero_empleado": "E-001", "nombre": "Ana López Ruiz"}}]}
```

`POST /resguardos/` (solo Administrador):

```json
{"resguardante": 1, "movimientos": ["MOV-0001", "MOV-0002"]}
```

Respuesta `201`:

```json
{"folio": "RES-0001", "fecha_emision": "2026-11-04 10:22",
 "resguardante": {"num": 1, "numero_empleado": "E-001", "nombre": "Ana López Ruiz"},
 "usuario_emisor": {"num": 1, "username": "admin"},
 "numero_bienes": 2,
 "hash_pdf": "7ba4f844e7b91f880073924dc9fc71219b7bf118ed80211ee0b18f7d665b8923",
 "pdf": "/api/resguardos/RES-0001/pdf/",
 "articulos": [
   {"num": 1, "identificador": "02-520-00001", "descripcion": "Dell Latitude 5420", "movimiento": "MOV-0001"},
   {"num": 2, "identificador": "02-520-00002", "descripcion": "Dell Latitude 5420", "movimiento": "MOV-0002"}]}
```

- `GET <pdf>` devuelve el archivo emitido (`application/pdf`, `inline`) tal cual se guardó. Reimprimir **no**
  crea folio ni movimiento. Si el archivo ya no coincide con su hash o no está en el servidor: `409`.
- El PDF trae el encabezado, los datos del resguardante, la tabla (no. de inventario, descripción, marca,
  modelo, serie y costo), el número de bienes, la leyenda y las dos firmas: la Contadora (responsable de
  seguimiento) y el resguardante. Sin "Monto revalúo". Generarlo no significa que esté firmado.
- El nombre de la Contadora sale de `CONTADORA_NOMBRE` en `settings.py`. Si falta, la API responde `400`
  con un mensaje que lo dice.
- Errores `400` (en `movimientos`): el folio no existe, no requiere resguardo, es de otra persona, ya está
  documentado en otro resguardo, o el artículo ya no está a cargo de ese resguardante.
- Cada movimiento trae ahora `"resguardo": "RES-0001"` (o `null` si todavía no está documentado).
- Las altas de la carga masiva (DEC-017) no generan resguardo (`requiere_resguardo: false`).

## Dashboard — `GET /dashboard/` (DEC-020)

Admin y Consulta. Siempre trae un renglón por estado, aunque valga 0, y en este orden:

```json
{"total_articulos": 2,
 "por_estado_operativo": [{"codigo": "UTIL", "nombre": "Útil", "tono": "azul", "total": 2},
                          {"codigo": "OBS", "nombre": "Obsoleto", "tono": "gris", "total": 0},
                          {"codigo": "NOLOC", "nombre": "No localizado", "tono": "ambar", "total": 0}],
 "por_estado_registro": [{"codigo": "REG", "nombre": "Registrado", "tono": "verde", "total": 2},
                         {"codigo": "PEND", "nombre": "Pendiente", "tono": "ambar", "total": 0},
                         {"codigo": "DON", "nombre": "Donado", "tono": "azul", "total": 0}],
 "por_ubicacion": [{"codigo": "UBI-OFI", "nombre": "Oficina de Informática", "total": 2}],
 "pendientes_de_datos": {"total": 0, "articulos": []},
 "ultimos_movimientos": [{"folio": "MOV-0002", "...": "mismo formato que GET /movimientos/"}],
 "resguardos_por_emitir": 0}
```

`por_ubicacion` son las ubicaciones activas, de más a menos artículos. `pendientes_de_datos.articulos` trae
los 10 primeros con su ficha completa (incluye `faltantes`). `ultimos_movimientos` son 10.

## Reportes y Excel (DEC-018, DEC-020)

Todos sin paginar y abiertos a Admin y Consulta.

- `GET /reportes/inventario/?ubicacion=&resguardante=&estado_operativo=` (y los demás filtros de
  `/articulos/`) → `{"total": 2, "resultados": [<artículos>]}`.
- `GET /reportes/resguardante/<num>/` → `{"resguardante": {...}, "total": 2, "resultados": [<artículos>]}`.
- `GET /reportes/historial/<num>/` → `{"articulo": {...}, "movimientos": [<todos>], "resguardos": [{"folio",
  "fecha_emision", "resguardante", "pdf"}]}`.
- Excel: `GET /articulos/exportar/` o cualquier reporte con `?formato=xlsx`. Columnas de DEC-018, en este
  orden: Identificador, Categoría, Tipo de artículo, Marca, Modelo, Serie, Color, Descripción, Origen,
  Ubicación, Resguardante, Estado operativo, Fecha de adquisición, Costo de adquisición, Estado de registro.
  Sin cuenta contable. Los textos que empiezan con `=`, `+`, `-` o `@` llevan un apóstrofo para que Excel no
  los tome como fórmula. El archivo se llama `inventario_AAAAMMDD.xlsx`.

## Carga masiva desde Excel (RF-24, RF-25, DEC-017)

Solo Administrador. Antes de la primera carga deben existir categorías, tipos, ubicaciones y personal.

1. **Plantilla:** `GET /carga-masiva/plantilla/` baja `plantilla_carga_masiva.xlsx`: un libro con una hoja por
   origen, como lo trabaja la Contadora: *Activos*, *Comodatos* y *Enseres* (más *Instrucciones* y las hojas
   auxiliares *Listas* y *Tipos*, que alimentan los desplegables). **El origen sale de la hoja**; no hay columna
   "Origen". Columnas de cada hoja: Marbete (en Activos) o Folio (en Comodatos y Enseres), **Categoría**,
   **Tipo de artículo** (columnas separadas; el desplegable del tipo muestra solo los de la categoría elegida),
   Marca, Modelo, Número de serie, Color, Descripción, Ubicación, Resguardante, Estado operativo, Fecha de
   adquisición, Costo de adquisición, ¿Donado? (Sí/No). **No** trae el estado de registro: lo calcula el sistema.
2. **Vista previa:** `POST /carga-masiva/validar/`, `multipart/form-data`, campo `archivo`. No guarda nada.
3. **Confirmar:** `POST /carga-masiva/confirmar/`, `multipart/form-data`, campos `archivo` (el mismo) y `hash`
   (el de la vista previa). Vuelve a validar y guarda solo las filas válidas, todas en una transacción
   (si algo falla, no se guarda nada). Si el archivo cambió respecto a la vista previa: `400`.

Cambios de la v13 (DEC-017 y DEC-021, 05/11/2026):
- Cada fila trae `avisos` (`{}` si no hay): avisos que **no bloquean** la fila. Claves: `marca`, `modelo` o
  `num_serie` cuando el valor era `S/S`, `S/M`, `S/N`, `N/A`, `NA` o un guion (se toma como vacío y no se guarda),
  y `posible_duplicado` en una fila sin marbete, folio ni serie que coincide en tipo, descripción, marca, modelo,
  color, ubicación y resguardante con un artículo del sistema o con otra fila del archivo.
- La vista previa trae `folios_nuevos` (cuántos folios asignará el sistema: filas válidas de Comodatos y Enseres
  sin folio) y `con_aviso`; cada fila trae `folio_nuevo` (true/false). El cliente puede exigir su casilla de
  confirmación con ese número; la API no la exige.
- Confirmar trae `folios_nuevos` y cada artículo cargado `folio_nuevo`; el `identificador` es el folio asignado.
- La plantilla oculta las hojas *Listas* y *Tipos* (los desplegables siguen funcionando), trae las instrucciones
  en 5 pasos con un ejemplo en la hoja *Instrucciones*, y sus hojas de datos van vacías.
- Costo en un bien Donado (DEC-021): opcional y editable. `PATCH /articulos/{num}/` con `costo_adquisicion`
  funciona también en un Donado (con `motivo` y bitácora; el estado de registro sigue siendo Donado). `null` lo
  deja vacío; nunca se guarda 0 por omisión. Antes respondía `400` "En un bien Donado el costo no se modifica."

Hojas: se aceptan también en singular (`Activo`, `Comodato`, `Enser`) y sin importar mayúsculas o acentos. Puede
faltar alguna (o venir vacía) mientras haya al menos una con filas. Cualquier otra hoja (por ejemplo *Licencias*)
se ignora y se informa en `hojas_ignoradas`. Se procesan en el orden Activos, Comodatos, Enseres.

La vista previa trae `ya_cargado` (`null`, o `{"fecha": "2026-11-04 11:20", "usuario": "admin"}` si **ese mismo
archivo** ya se cargó). Confirmar un archivo ya cargado responde `400`: así subirlo dos veces no duplica las filas
que no tienen marbete, folio ni serie (por ejemplo un enser sin folio), que el sistema no puede reconocer como
repetidas por sus datos. Un archivo con cualquier cambio sí se puede cargar.

Respuesta de la vista previa (los `datos` de cada fila traen todas las columnas, aquí se recortan):

```json
{"archivo": "inventario_2026.xlsx", "hash": "9b0615db…", "total": 4, "validas": 2, "con_error": 2,
 "ya_cargado": null, "hojas_ignoradas": ["Licencias"], "folios_nuevos": 1, "con_aviso": 0,
 "hojas": [{"hoja": "Activos", "origen": "Activo", "filas": 2, "validas": 1, "con_error": 1},
           {"hoja": "Enseres", "origen": "Enser", "filas": 2, "validas": 1, "con_error": 1}],
 "columnas": {"identificador": "Marbete o folio", "categoria": "Categoría", "tipo_articulo": "Tipo de artículo",
              "…": "…", "donado": "¿Donado?"},
 "filas": [
   {"hoja": "Activos", "fila": 2, "estado": "valida", "errores": {}, "avisos": {}, "folio_nuevo": false,
    "datos": {"origen": "Activo", "identificador": "02-520-00001", "categoria": "EQUIPO DE CÓMPUTO", "tipo_articulo": "Laptop", "…": "…"}},
   {"hoja": "Activos", "fila": 4, "estado": "error", "errores": {"identificador": "Los activos llevan marbete oficial."},
    "datos": {"origen": "Activo", "identificador": null, "…": "…"}},
   {"hoja": "Enseres", "fila": 5, "estado": "error",
    "errores": {"tipo_articulo": "El tipo \"Laptop\" no pertenece a la categoría \"MUEBLES\"."},
    "datos": {"origen": "Enser", "identificador": "IC-2019-044", "…": "…"}}]}
```

`hoja` + `fila` identifican la fila del Excel (la fila se numera desde 2 en cada hoja). `errores` va por clave de
columna (las de `columnas`). Respuesta `201` de confirmar:

```json
{"archivo": "inventario_2026.xlsx", "hash": "9b0615db…", "total": 4, "cargados": 2, "rechazados": 2,
 "hojas": [{"hoja": "Activos", "origen": "Activo", "filas": 3, "validas": 2, "con_error": 1}],
 "articulos": [{"hoja": "Activos", "fila": 2, "num": 1, "identificador": "02-520-00001"},
               {"hoja": "Enseres", "fila": 2, "num": 2, "identificador": "021431126-001"}],
 "filas_rechazadas": [{"hoja": "Activos", "fila": 4, "estado": "error", "errores": {"…": "…"}, "datos": {"…": "…"}}]}
```

Reglas:
- Cada fila se valida con las mismas reglas del alta manual. Los catálogos se reconocen sin distinguir
  mayúsculas, acentos ni espacios extra; Categoría y Tipo aceptan el nombre o el código. El **tipo se busca
  dentro de la categoría de la fila**: si el tipo existe pero en otra categoría el error dice que no pertenece
  a ella. El mismo nombre de tipo puede existir en dos categorías. Ubicación y Resguardante aceptan la
  etiqueta de la lista (`E001 · Nombre`) o solo el código. El resguardante se identifica por su **número de
  empleado**, no por el nombre.
- **Marbete o folio:** en Activos es el marbete (obligatorio). En Comodatos y Enseres es el folio que el bien ya
  tiene (se respeta aunque tenga otro formato); si va vacío, el sistema asigna uno (`02143MMYY-NNN`).
- Se rechaza como duplicado un marbete, folio o serie que ya existe en el sistema, y los repetidos dentro del
  mismo archivo, también entre hojas (la segunda aparición; el mensaje dice la hoja y fila de la primera).
- Fecha `DD/MM/AAAA` (también `AAAA-MM-DD`); costo numérico (acepta `$` y comas); ¿Donado? `Sí`/`No`
  (vacío = No); estado operativo `Útil`/`Obsoleto` (vacío = Útil). Un bien en "Sin ubicar" queda No localizado.
- Cada artículo cargado genera su ALTA con motivo `Carga masiva (archivo.xlsx, DD/MM/AAAA)` y
  `requiere_resguardo: false` (no genera resguardo pendiente). En la bitácora queda una fila por artículo y
  otra del lote (`modulo: carga_masiva`: archivo, huella, filas cargadas por hoja y rechazadas).
- Límites: 2000 filas (entre las tres hojas) y 5 MB por archivo. Errores de archivo (no es .xlsx, ninguna de las
  tres hojas, faltan columnas en una hoja —el mensaje nombra la hoja—, sin filas, demasiadas filas) llegan como
  `400` con `{"archivo": "mensaje"}`.
- Si faltan folios del mes (máximo 999), las filas de Comodatos/Enseres sin folio que ya no caben se marcan con
  error; con folio propio sí entran.
- Los inventarios por año se cargan del más reciente (2026) al más antiguo: los anteriores solo agregan lo
  que no aparece en los más recientes (lo garantiza el rechazo de duplicados).
- Los desplegables (incluido el del tipo dependiente de la categoría) se probaron en LibreOffice; falta
  probarlos en Excel real.

## Bitácora de auditoría — `GET /bitacora/` (RF-21, PEND-024)

Solo el Administrador (Consulta recibe 403). Solo lectura: no hay POST, PATCH ni DELETE (405).
Paginada de 10 en 10 (`?page=2`), la más reciente primero.

| Filtro | Qué hace |
|---|---|
| `q` | Busca palabras en usuario, módulo, acción, tabla, registro, motivo y valores |
| `usuario` | Número o nombre de usuario (exacto) |
| `modulo` | Exacto, sin distinguir mayúsculas: `articulos`, `movimientos`, `resguardos`, `carga_masiva`, `usuarios`, etc. |
| `accion` | `INSERT`, `UPDATE` o `DELETE` (baja lógica) |
| `fecha_desde`, `fecha_hasta` | `AAAA-MM-DD`; ambos días se incluyen (hora de Tijuana) |
| `tabla_afectada` + `registro_id` | Historial de un registro concreto, por ejemplo `articulo` y `12` |

Los filtros se pueden combinar. Un filtro inválido responde 400 con `{campo: mensaje}`.

```json
{
  "count": 1, "next": null, "previous": null,
  "results": [{
    "num": 3,
    "fecha_hora": "2026-11-11T10:18:52.530987-08:00",
    "usuario": {"num": 1, "username": "admin", "nombre": "Admin Prueba"},
    "modulo": "articulos",
    "accion": "UPDATE",
    "accion_nombre": "Modificación",
    "tabla_afectada": "articulo",
    "registro_id": "1",
    "motivo": "Marca mal capturada",
    "valor_anterior": {"marca": "Dell"},
    "valor_nuevo": {"marca": "HP"}
  }]
}
```

- `valor_anterior` y `valor_nuevo` llegan ya como JSON (objeto), o `null`. En un UPDATE solo traen los
  campos que cambiaron; en un INSERT, `valor_anterior` es `null`. Si algún registro viejo no fuera JSON
  válido se devuelve el texto tal cual.
- `motivo` puede ser `null` (las altas no lo llevan; las correcciones sí).
- `accion_nombre` es el texto para mostrar: Alta, Modificación o Baja lógica.
- `registro_id` es texto (puede ser `12`, `MOV-0001` o `lote-<huella>` en una carga masiva).
- Nunca se incluyen contraseñas.

## Errores

Validación: `400` con `{campo: mensaje}`, con las claves de los campos del formulario.

```json
{
  "color": "Este campo no puede estar en blanco."
}
```

```json
{
  "motivo": "El motivo es obligatorio."
}
```

```json
{
  "motivo": "Indique el motivo del cambio."
}
```

Sin sesión: `401`. Rol CONSULTA escribiendo: `403`. Inexistente: `404`.

## Lo que Fernando tendrá que ajustar en equipos y movimientos

1. **Tipo en vez de categoría.** El alta manda `tipo_articulo`; la categoría sale del tipo (DEC-002).
2. **Marca y modelo son opcionales** (DEC-011). `color` y `descripcion` son obligatorios.
3. **Folio interno.** Lo genera el sistema (`02143MMYY-NNN`); el formulario no lo pide ni lo sugiere.
4. **Resguardante por `num`**, no por nombre.
5. **Nombres de clave.** En movimientos: `equipo` pasó a `articulo` y `genera_resguardo` a
   `requiere_resguardo`. `fecha_adquisicion` vacía llega como `null`.
6. **Sin BAJA ni AUTB.** El formulario de movimiento ofrece tres opciones (REUB, REPA, RETE).
7. **Obsoleto** se marca desde la ficha con `PATCH` y motivo, no con un movimiento.
8. `ubicacion_llegada` siempre viene (la misma ubicación si no cambió), nunca `null`.
9. **Costo.** Se corrige desde la ficha con `PATCH` (`costo_adquisicion` + `motivo`); un artículo Pendiente por
   falta de costo pasa a Registrado. En un Donado el costo no se modifica.
10. **Listas completas.** Para exportar o armar reportes usar `/articulos/todos/` o `/reportes/...`, no la
    lista paginada de 10.
11. **Resguardos.** El botón de resguardo usa `/resguardos/pendientes/` y `POST /resguardos/`; ver el PDF con
    `GET /resguardos/<folio>/pdf/`.
