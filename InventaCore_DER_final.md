# DER Y MODELO RELACIONAL — VERSIÓN CORREGIDA Y CERRADA
## Sistema de Control y Gestión de Inventario para Equipo Electrónico — CONALEP Tijuana II

**Revisión:** 16/10/2026
**Verificación:** entidad por entidad, atributo por atributo y relación por relación contra el PDF real `RF y RNF Proyecto Conalep (2).pdf` (23 RF + 11 RNF). Los conteos de ocurrencias citados abajo se obtuvieron por búsqueda textual en el PDF, no de memoria.

**Cifras finales: 14 entidades · 19 relaciones · 0 relaciones M:M · 0 atributos en relaciones.**

> Corrección de conteo: el "18 entidades" que circulaba en versiones previas era un arrastre de una versión anterior. No cuadra con la tabla real. **Son 14.**

---

# 1. UBICACION vs DEPARTAMENTO — la distinción que sostiene el modelo

| | UBICACION | DEPARTAMENTO |
|---|---|---|
| Qué representa | Espacio físico donde puede estar un equipo | Unidad organizativa que agrupa personal |
| Renglones en el alcance | 3 (oficina de Informática + 2 laboratorios) | Muchos (todo el plantel) |
| A qué entidad agrupa | EQUIPO | PERSONAL |
| RF que lo exige | RF-11 | RF-14 |

**Texto de RF-11 (literal):** "registrar las ubicaciones relevantes al Departamento de Informática: la oficina del departamento y sus dos laboratorios".

**Texto de RF-14 (literal):** "registrar al personal **del plantel** que puede fungir como resguardante de equipo".

**Por qué no son lo mismo y no se colapsan:** las 3 ubicaciones pertenecen a Informática, pero el personal resguardante puede ser de cualquier departamento del plantel. Por eso DEPARTAMENTO tiene muchos renglones y UBICACION solo 3.

**Por qué NO se agrega `departamento` a UBICACION:**
1. Sería una columna con el mismo valor ("Informática") en los 3 renglones; no aporta información.
2. `departamento` aparece **0 veces** asociado a ubicaciones en el RF/RNF.
3. La pregunta "¿a qué departamento pertenece el Laboratorio 1?" tiene respuesta sin FK: a Informática, por definición de RF-11.
4. Si el proyecto se extendiera a todo el plantel (continuidad futura), ahí sí tendría sentido. Es trabajo futuro, no alcance declarado.

**Consecuencia en wireframes:** W7 pierde la columna DEPARTAMENTO. W12 cambia el gráfico "Equipos por departamento" por **"Equipos por ubicación"** (sustento directo: RF-13 + las 3 áreas).

**Nota sobre W3:** el campo "Departamento (automático)" **no está en ningún RF**. RF-05 lista origen, categoría, marca, modelo, número de serie, ubicación inicial y resguardante inicial — departamento no aparece. Si se conserva, debe leerse como "departamento del resguardante" (derivado de PERSONAL.departamento) y no como dato del equipo.

---

# 2. Entidades (14) — con nulabilidad explícita

## Catálogos (PK = `codigo`, excepto ROL que usa `clave`)

| Entidad | PK | Atributos | Nulabilidad / reglas |
|---|---|---|---|
| ROL | clave | nombre, descripcion | Excepción de nomenclatura heredada de Mermax. Anotarla. |
| CATEGORIA | codigo | nombre (UNIQUE), descripcion, activo | `activo` derivado de RNF-06 + precedente RF-03 |
| UBICACION | codigo | nombre (UNIQUE), descripcion, **responsable** → PERSONAL.numero, activo | `responsable` **NULL** (RF-12). `activo` derivado |
| ORIGEN | codigo | nombre, descripcion | **No es catálogo abierto**: 3 valores fijos del Excel patrimonial (Activo/Comodato/Enser) |
| ESTADO_OPERATIVO | codigo | nombre | Precarga: útil, en reparación, de baja, inactivo (RF-07 + RF-10) |
| ESTADO_REGISTRO | codigo | nombre | Precarga: Pendiente, Registrado, Donado (RF-07) |
| TIPO_MOVIMIENTO | codigo | nombre, genera_resguardo | Precarga: Alta de equipo (TRUE), Cambio de resguardante (TRUE), Cambio de ubicación (FALSE) |
| DEPARTAMENTO | codigo | nombre, descripcion | Muchos renglones: todo el plantel |

## Entidades maestras (PK = `num` / `numero`)

| Entidad | PK | Atributos | FK / reglas |
|---|---|---|---|
| PERSONAL | numero | nombrePila, primerApell, segundoApell, puesto (NULL), activo | departamento → DEPARTAMENTO.codigo (NOT NULL). **`nombre` NO es columna** — se calcula como propiedad |
| USUARIO | num | username (UNIQUE), correo (UNIQUE), contrasena (hash), activo, ultimo_acceso (NULL) | personal → PERSONAL.numero (**UNIQUE, NOT NULL**) · rol → ROL.clave (NOT NULL) |
| EQUIPO | num | marbete_oficial (NULL, UNIQUE), folio_interno (NULL, UNIQUE), marca, modelo, num_serie, color (NULL), descripcion, fecha_adquisicion (NULL), costo_adquisicion (NULL), fecha_alta | categoria, ubicacion, origen, estado_operativo, estado_registro → NOT NULL · **resguardante → PERSONAL.numero (NULL)** |

## Entidades con rastro documental (PK = `folio`)

| Entidad | PK | Atributos | FK / reglas |
|---|---|---|---|
| MOVIMIENTO | folio | fecha_movimiento, motivo | equipo (NOT NULL) · tipo_movimiento (NOT NULL) · ubicacion_origen (**NULL**) · ubicacion_destino (NOT NULL) · resguardante_anterior (**NULL**) · resguardante_nuevo (NOT NULL) · usuario (NOT NULL) |
| RESGUARDO | folio | fecha_generacion, ruta_pdf | movimiento → MOVIMIENTO.folio (**UNIQUE, NOT NULL**) |

## Bitácora

| Entidad | PK | Atributos | FK |
|---|---|---|---|
| BITACORA | num | fecha_hora, modulo, accion, valor_anterior (NULL), valor_nuevo (NULL), motivo (NULL), tabla_afectada (VARCHAR), registro_id (VARCHAR) | usuario → USUARIO.num (NOT NULL) |

---

# 3. Relaciones (19) — lectura correcta en notación Chen

El rombo se lee como oración en UNA sola dirección.

| # | Relación | Cardinalidad | Participaciones | Nota |
|---|---|---|---|---|
| 1 | USUARIO ejerce ROL | M:1 | USUARIO (1,1) / ROL (0,M) | Corregida (antes al revés) |
| 2 | USUARIO posee PERSONAL | 1:1 | USUARIO (1,1) / PERSONAL (0,1) | Lleva leyenda |
| 3 | USUARIO genera BITACORA | 1:M | | |
| 4 | USUARIO realiza MOVIMIENTO | 1:M | | |
| 5 | PERSONAL resguarda EQUIPO | 1:M | PERSONAL (0,M) / EQUIPO (0,1) | |
| 6 | PERSONAL entrega MOVIMIENTO | 1:M | | = resguardante_anterior |
| 7 | PERSONAL recibe MOVIMIENTO | 1:M | | = resguardante_nuevo (antes "asigna") |
| 8 | **PERSONAL es responsable de UBICACION** | **1:M** | PERSONAL (0,M) / UBICACION (0,1) | **NUEVA — RF-12** |
| 9 | PERSONAL pertenece a DEPARTAMENTO | M:1 | | Corregida (antes al revés) |
| 10 | UBICACION ubica EQUIPO | 1:M | | |
| 11 | UBICACION origen de MOVIMIENTO | 1:M | | |
| 12 | UBICACION destino de MOVIMIENTO | 1:M | | Antes "llega a" — estandarizado |
| 13 | EQUIPO registra MOVIMIENTO | 1:M | | |
| 14 | MOVIMIENTO genera RESGUARDO | 1:1 | MOVIMIENTO (0,1) / RESGUARDO (1,1) | Lleva leyenda |
| 15 | EQUIPO clasifica CATEGORIA | M:1 | | |
| 16 | EQUIPO clasifica ORIGEN | M:1 | | |
| 17 | EQUIPO indica ESTADO_OPERATIVO | M:1 | | Corregida (antes al revés) |
| 18 | EQUIPO indica ESTADO_REGISTRO | M:1 | | |
| 19 | MOVIMIENTO tiene TIPO_MOVIMIENTO | M:1 | | NUEVA respecto a tu lista de 17 |

**Ninguna entidad queda huérfana.** Todas tienen al menos una relación.

---

# 4. Reglas de integridad que se validan en aplicación (Django `clean()`)

1. **XOR de identificadores:** exactamente uno de `marbete_oficial` / `folio_interno` debe tener valor, según el origen. Nunca ambos, nunca ninguno.
   - Origen Activo → `marbete_oficial` obligatorio, `folio_interno` NULL.
   - Origen Comodato o Enser → `folio_interno` obligatorio, `marbete_oficial` NULL.
2. **1:1 de USUARIO–PERSONAL:** un empleado no puede tener dos cuentas (UNIQUE).
3. **1:1 de MOVIMIENTO–RESGUARDO:** un movimiento no puede tener dos resguardos (UNIQUE).
4. **Coherencia temporal:** `ubicacion_destino` y `resguardante_nuevo` deben coincidir con el estado posterior; si el movimiento es "Alta de equipo", `ubicacion_origen` y `resguardante_anterior` son NULL.
5. **No eliminación:** `EQUIPO`, `MOVIMIENTO`, `RESGUARDO` y `BITACORA` no admiten DELETE. Bajas = cambio de estado. (RNF-06)

---

# 5. Transacciones que el modelo obliga a escribir juntas

**Alta de equipo (RF-05 + RF-18 + RF-19):** una sola transacción escribe
`EQUIPO` + `MOVIMIENTO` (tipo "Alta de equipo") + `RESGUARDO` (PDF generado).
El QR no se guarda: se genera al vuelo a partir del identificador.

**Cambio de resguardante:** `MOVIMIENTO` (tipo "Cambio de resguardante") + `RESGUARDO` + actualización de `EQUIPO.resguardante` y `EQUIPO.ubicacion`.

**Cambio de ubicación:** `MOVIMIENTO` (tipo "Cambio de ubicación") + actualización de `EQUIPO.ubicacion`. **No genera resguardo.**

**Baja de equipo (RF-10):** cambia `EQUIPO.estado_operativo` a "De baja" o "Inactivo" y registra en `BITACORA`. **No genera MOVIMIENTO.** Es la respuesta correcta a "¿dónde queda la baja en el historial?": en la bitácora (RNF-06/RNF-07).

---

# 6. Auditoría: qué se consideró y por qué se rechazó

Útil para la defensa. Cada renglón es una pregunta que te pueden hacer.

| Candidata | Por qué NO va |
|---|---|
| EDIFICIO / NIVEL / PISO | **0 ocurrencias** en el RF/RNF. Invención del wireframe. |
| DEPARTAMENTO en UBICACION | Las 3 áreas son de Informática por RF-11; columna con valor constante. |
| MANTENIMIENTO | Fuera de alcance explícito del proyecto. |
| GARANTÍA / PROVEEDOR | 0 RF. No hay requisito. |
| HISTORIAL_ESTADO_OPERATIVO | Redundante: RNF-06 exige valor anterior/nuevo → BITACORA ya lo resuelve. |
| RESGUARDO_ESTADO ("vigente") | Derivado: "vigente" = resguardo del MOVIMIENTO más reciente de ese equipo. |
| QR (tabla o campo) | Derivado del identificador, se genera al vuelo (RF-19). |
| SESIÓN / LOGIN | RNF-01 no lo pide. |
| REPORTE | Se genera, no se almacena (RF-22). |
| EQUIPO.activo (booleano) | **No debe existir.** `estado_operativo` ya cubre "De baja"/"Inactivo" (RF-10). Dos fuentes de verdad = contradicción. |
| PERSONAL.nombre (columna) | Redundante con nombrePila + primerApell + segundoApell. Va como propiedad calculada. |

---

# 7. Cobertura: los 23 RF contra las 14 entidades

| RF | Entidad(es) que lo sostienen |
|---|---|
| RF-01 Autenticación | USUARIO |
| RF-02 Alta de cuentas | USUARIO + ROL + PERSONAL |
| RF-03 Baja lógica de cuenta | USUARIO.activo |
| RF-04 Catálogo de categorías | CATEGORIA |
| RF-05 Registro de equipo | EQUIPO + MOVIMIENTO (alta) |
| RF-06 Identificador según origen | EQUIPO.marbete_oficial / folio_interno |
| RF-07 Costo y estado de registro | EQUIPO.costo_adquisicion + ESTADO_REGISTRO |
| RF-08 Modificación de datos | EQUIPO + BITACORA |
| RF-09 Consulta de equipo | EQUIPO (todos sus FK son filtros) |
| RF-10 Baja lógica de equipo | EQUIPO.estado_operativo + BITACORA |
| RF-11 Registro de ubicaciones | UBICACION |
| RF-12 Modificación de ubicaciones | UBICACION + PERSONAL (responsable) |
| RF-13 Consulta de ubicaciones | UBICACION + EQUIPO.ubicacion |
| RF-14 Registro de empleados | PERSONAL + DEPARTAMENTO |
| RF-15 Consulta de empleados | PERSONAL + EQUIPO.resguardante |
| RF-16 Registro de movimiento | MOVIMIENTO + TIPO_MOVIMIENTO |
| RF-17 Historial de movimientos | MOVIMIENTO |
| RF-18 Resguardo PDF | RESGUARDO + TIPO_MOVIMIENTO.genera_resguardo |
| RF-19 Generación de QR | Derivado del identificador de EQUIPO |
| RF-20 Lectura de QR | Derivado (sin entidad) |
| RF-21 Bitácora de auditoría | BITACORA |
| RF-22 Reportes exportables | Consultas sobre EQUIPO/MOVIMIENTO |
| RF-23 Búsqueda rápida | EQUIPO + PERSONAL (por resguardante) |

**Los 23 RF quedan cubiertos. No falta ninguna entidad.**

---

# 8. Correcciones al MR de Adad (ordenadas por gravedad)

## 8.1 Bloqueantes

| # | Tabla | Corrección | Fuente |
|---|---|---|---|
| 1 | EQUIPO | Falta `resguardante` → PERSONAL.numero (NULL) | RF-05 |
| 2 | USUARIO | Falta `contrasena` (hash, nunca texto plano) | RNF-01 |
| 3 | USUARIO | Falta `username` | RF-01 |
| 4 | USUARIO | `correo` debe ser UNIQUE | RF-02 |
| 5 | USUARIO | `personal` debe ser **UNIQUE** (1:1) | DER rel. 2 |
| 6 | UBICACION | Falta `responsable` → PERSONAL.numero (NULL) | RF-12 |
| 7 | RESGUARDO | `movimiento` debe ser **UNIQUE** (1:1) | DER rel. 14 |
| 8 | EQUIPO | `folio_interno` **no** puede ser NOT NULL | RF-06 + regla XOR |

## 8.2 Nulabilidad y estructura

| # | Tabla | Corrección |
|---|---|---|
| 9 | MOVIMIENTO | `ubicacion_origen` debe ser NULL (el alta no tiene origen) |
| 10 | PERSONAL | Quitar `nombre` como columna; calcularlo como propiedad |
| 11 | PERSONAL | Confirmar que `Num` **es** el número de empleado (RF-14/RF-15 buscan por ahí) |

## 8.3 Nomenclatura (no cambia estructura)

| # | Dónde | Como está | Debe quedar |
|---|---|---|---|
| 12 | MOVIMIENTO | PK `Num` | PK `Folio` |
| 13 | MOVIMIENTO | `Personal_Asigna` / `Personal_Entrega` | `Resguardante_Anterior` / `Resguardante_Nuevo` |
| 14 | MOVIMIENTO | `Ubicacion_Llegada` | `Ubicacion_Destino` |
| 15 | Todo el MR | Mezcla CamelCase y snake_case | snake_case parejo |
| 16 | DER (imagen) | Óvalo `codigo` suelto | Eliminar |
| 17 | DER (imagen) | 3 relaciones al revés (rel. 1, 9, 17) | Corregir lecturas |

---

# 9. Lo que está BIEN y no debe tocarse

- **BITACORA.tabla_afectada y registro_id como VARCHAR, no FK.** Correcto: la bitácora es polimórfica. Si fueran FK, MySQL obligaría a elegir una sola tabla y la bitácora dejaría de servir.
- **La separación PERSONAL / USUARIO.** Correcta y a propósito: el resguardante típico es un maestro que nunca tendrá cuenta.
- **EQUIPO guarda estado actual; MOVIMIENTO guarda historial.** Patrón evento→estado.
- **Las participaciones (0,1) y (1,1) con leyenda.** Ambas correctas, no son contradicción.
- **El QR sin entidad propia.** Se genera al vuelo.
- **ORIGEN como entidad de 3 valores fijos.** Es entidad por integridad, pero no es catálogo administrable por el usuario.

---

# 10. Pendientes

1. Confirmar con Adad que `PERSONAL.Num` es el número de empleado.
2. Verificar precarga exacta de ESTADO_OPERATIVO (útil, en reparación, de baja, inactivo) y ESTADO_REGISTRO (Pendiente, Registrado, Donado).
3. Decidir `USUARIO.ultimo_acceso`: se agrega al modelo o se quita de W9.
4. Preguntar a Rogelio: ¿el folio de MOVIMIENTO es autogenerado o capturado? (el RF no lo resuelve).
5. Preguntar a Rogelio: ¿el resguardo lleva tercera firma "V°B°"? (RF-18 solo dice "un espacio para firma").
6. Definir si `UBICACION.activo` se implementa con acción de desactivar en W7 o se omite.

---

# 11. Qué SÍ y qué NO es requisito (para la defensa)

## Obligatorio — texto del RF

EQUIPO: marbete_oficial, folio_interno, ubicacion, resguardante, categoria, marca, modelo, num_serie, origen (RF-05/RF-06) · descripcion (RF-08) · costo_adquisicion, estado_registro (RF-07) · estado_operativo (RF-08/RF-10).
USUARIO: username, correo (RF-01) · contrasena (RNF-01) · rol, personal (RF-02) · activo (RF-03).
PERSONAL: numero, departamento (RF-14) · nombrePila, primerApell, segundoApell (RF-15).
UBICACION: responsable (RF-12, Características).
MOVIMIENTO: fecha, motivo, usuario, equipo, ubicacion_origen, ubicacion_destino, resguardante_anterior, resguardante_nuevo (RF-16 + RF-18).
RESGUARDO: ruta_pdf, movimiento (RF-18).
BITACORA: usuario, accion, valor_anterior, valor_nuevo, fecha_hora (RF-21).

## Decisión de diseño — razonable, pero NO es requisito

EQUIPO.color · EQUIPO.fecha_adquisicion · EQUIPO.fecha_alta · PERSONAL.puesto · PERSONAL.activo · USUARIO.ultimo_acceso · BITACORA.tabla_afectada · BITACORA.registro_id · BITACORA.modulo · BITACORA.motivo · CATEGORIA.activo · UBICACION.activo.

**ESTADO_OPERATIVO "No localizado":** 0 ocurrencias en el RF. Es decisión de diseño con buena justificación — tu hallazgo con pandas tiene un equipo real de TJII en estatus NO LOCALIZADO, y RF-07 escribe "(útil, en reparación, de baja, **etc.**)". Si se agrega, se justifica con el Excel, **no** con el RF.

**CATEGORIA.activo / UBICACION.activo:** redactar como "derivado de la política de baja lógica del RNF-06", no como "RNF-06 lo exige" — su Descripción acota a "registros de equipo y movimientos".
