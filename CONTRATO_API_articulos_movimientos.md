# Contrato de la API — Artículos, Movimientos, Resguardos, Dashboard y Reportes (v10)

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
el estado de registro se recalcula (DEC-008). En un bien Donado el costo no se modifica (responde `400`
mientras PEND-004 siga abierto) y el estado se queda Donado. La ubicación y el resguardante no cambian aquí: solo por movimiento.

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
- Las altas de la carga masiva (DEC-017) no generan resguardo: el servicio de alta acepta
  `requiere_resguardo=False` para eso. La carga masiva en sí todavía no está construida.

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
