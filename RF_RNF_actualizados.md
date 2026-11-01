# RF y RNF — InventaCore (actualización al 01/11/2026)

Base: "RF y RNF Proyecto Conalep.pdf". Fuentes de los cambios: DECISIONES.md (DEC-001 a DEC-018) y PENDIENTES.md del repositorio Fernando38V/InventaCore.
Solo se incluyen los requerimientos que cambian y los nuevos. Los demás (RF-03, RNF-01, 03, 04, 05, 07, 08) quedan igual. Se conservan el título del documento y el alcance de la tesina (DEC-009). Los RF-24 a RF-26 son ampliación del alcance.

Convención: "artículo" sustituye a "equipo" (DEC-002). Lo que no está en las decisiones no se agregó; los puntos abiertos están al final.

---

## Requerimientos funcionales modificados

### RF-01 — Autenticación por usuarios
Descripción: El sistema deberá permitir el acceso mediante nombre de usuario y contraseña. Una vez autenticado, el usuario será redirigido a la vista correspondiente a su rol: Administrador o Consulta.
RNF: RNF-01, RNF-02. Prioridad: Alta/Esencial.

### RF-02 — Alta de cuentas de usuario
Características: Registro de cuenta vinculada a un empleado, con asignación de rol en el mismo registro.
Descripción: El sistema permitirá al Administrador registrar una nueva cuenta de usuario vinculada a un empleado, asignando en el mismo registro el rol correspondiente: Administrador (control total: altas, modificaciones, movimientos, bitácora y administración de usuarios; lo usan la Contadora y los jefes) o Consulta (dashboard, consultas, historial, resguardos y reportes PDF; no modifica información ni ve la bitácora).
RNF: RNF-01, RNF-02, RNF-07. Prioridad: Alta/Esencial.

### RF-04 — Gestión del catálogo de categorías y tipos de artículo
Características: Catálogo en dos niveles (categoría → tipo de artículo), vacío al inicio y ampliable desde el sistema.
Descripción: El sistema manejará la clasificación del inventario en dos niveles, categoría y tipo de artículo (cada categoría agrupa varios tipos), como catálogos administrables en base de datos, no como valores fijos en el código. Ambos catálogos inician vacíos y los usuarios autorizados dan de alta nuevas categorías y tipos desde el sistema, sin modificar el código; el sistema genera el código de cada registro. La clasificación es independiente del origen del artículo.
RNF: RNF-03. Prioridad: Media/Deseado.

### RF-05 — Registro de artículo
Características: Alta de artículo, origen, tipo de artículo, ubicación y resguardante obligatorios, identificador según origen.
Descripción: El sistema permitirá al Administrador registrar un nuevo artículo, indicando: origen (Activo / Comodato / Enser), tipo de artículo (la categoría se obtiene del tipo), color, descripción, estado operativo, ubicación y resguardante. Estos campos son obligatorios desde el alta. Marca, modelo, número de serie, fecha de adquisición y costo son opcionales y la interfaz muestra "Sin especificar" cuando faltan. El identificador depende del origen (RF-06). Al crear el artículo, el sistema registra automáticamente el movimiento ALTA. Se permite dar de alta un artículo ya como Obsoleto o, como alta histórica, como No localizado conservando su último resguardante conocido.
RNF: RNF-03, RNF-06, RNF-11. Prioridad: Alta/Esencial.

### RF-06 — Asignación de identificador según origen del artículo
Características: Marbete oficial para Activos; folio generado por el sistema para Comodatos y Enseres.
Descripción: Si el artículo tiene origen 'Activo', el sistema exigirá el MARBETE oficial como identificador, sin folio interno; no se puede registrar un Activo sin marbete. El marbete es un dato oficial del gobierno del estado que el sistema no genera; solo puede corregirse mediante una operación autorizada y auditada, sin cambiar la identidad del registro ni su QR. Si el origen es 'Comodato' o 'Enser', el sistema generará un folio interno no editable con formato 02143MMYY-NNN (MMYY: mes y año de registro; NNN: consecutivo mensual desde 001, compartido por Comodatos y Enseres). El sistema validará el límite de 999 por mes y mostrará un mensaje claro si se alcanza, y nunca repetirá un identificador existente. En la carga masiva (RF-25) se respeta el marbete o folio que el bien ya tiene, aunque tenga otro formato. El número de serie es opcional.
RNF: RNF-06, RNF-11. Prioridad: Alta/Esencial.

### RF-07 — Registro y control del costo de adquisición
Características: Estado de registro (Registrado / Pendiente / Donado) calculado por el sistema, independiente del estado operativo.
Descripción: El sistema deberá capturar el costo y la fecha de adquisición del artículo, ambos opcionales y que pueden capturarse o corregirse después desde la ficha. El estado de registro lo calcula siempre el sistema, también en la carga masiva: Donado tiene prioridad (el Administrador indica si el bien es donado); si no es donado, es 'Registrado' cuando la fecha y el costo de adquisición están completos y 'Pendiente' cuando falta alguno. Al completar o corregir los datos, el estado se recalcula. Si un Administrador corrige un artículo marcado como Donado por error, la corrección queda en bitácora y el estado se recalcula. El estado de registro es independiente del estado operativo (Útil, Obsoleto, No localizado) y no debe confundirse con él.
RNF: RNF-06, RNF-09. Prioridad: Alta/Esencial.

### RF-08 — Modificación de datos del artículo
Características: Corrección de la ficha con motivo y bitácora; ubicación y resguardante solo por movimiento.
Descripción: El sistema permitirá al Administrador corregir desde la ficha la marca, modelo, número de serie, color, descripción y fecha de adquisición, indicando siempre el motivo y con registro en la bitácora, sin afectar el historial de movimientos. La ubicación y el resguardante solo cambian mediante un movimiento (RF-16). El cambio a Obsoleto se realiza desde la ficha conforme a RF-10. El rol Consulta no puede modificar información.
RNF: RNF-03, RNF-06. Prioridad: Alta/Esencial.

### RF-09 — Consulta de artículos
Descripción: El sistema desplegará un listado del inventario registrado, con buscador por número de serie o identificador, y filtros por origen (Activo/Comodato/Enser), categoría, tipo de artículo, ubicación actual, resguardante, estado operativo y estado de registro.
RNF: RNF-03, RNF-04. Prioridad: Alta/Esencial.

### RF-10 — Baja lógica de artículo (estado Obsoleto)
Características: Cambio a estado 'Obsoleto' desde la ficha, conservación de historial.
Descripción: El sistema permitirá al Administrador marcar un artículo como 'Obsoleto' (lo que la institución llama baja: artículos que ya no sirven ni se usan) desde su ficha, con motivo obligatorio y registro en bitácora, sin generar un movimiento; la ubicación y el resguardante se conservan. El artículo no se elimina de la base de datos y conserva su historial completo. Un artículo 'No localizado' no puede pasar a Obsoleto. Regresar de Obsoleto a Útil es excepcional y solo mediante corrección auditada. El proceso de baja ante la dirección estatal lo realiza la institución fuera del sistema.
RNF: RNF-06, RNF-07. Prioridad: Alta/Esencial.

### RF-11 — Registro de ubicaciones
Características: Alta de ubicaciones (espacio físico), catálogo ampliable desde el sistema.
Descripción: El sistema deberá permitir al Administrador registrar las ubicaciones (espacios físicos) donde se resguardan los artículos. El catálogo es ampliable por usuarios autorizados desde el sistema, sin modificar el código, y el sistema genera el código de cada ubicación. Incluye la ubicación protegida 'No localizado', que se mantiene sincronizada con el estado operativo del mismo nombre. La ubicación del artículo y el departamento del resguardante son datos independientes.
RNF: RNF-03. Prioridad: Alta/Esencial.

### RF-12 — Modificación de ubicaciones
Descripción: El sistema permitirá al Administrador actualizar los datos de una ubicación existente, excepto los valores protegidos (No localizado).
RNF: RNF-03. Prioridad: Media/Deseado.

### RF-13 y RF-15 — Consulta de ubicaciones / Consulta de empleados
Solo terminología: "equipo(s)" pasa a "artículo(s)".

### RF-14 — Registro de empleados
Descripción: El sistema permitirá al Administrador registrar al personal del plantel que puede fungir como resguardante de artículos. El personal puede dejar de estar activo sin eliminarse: solo el personal activo puede recibir nuevas asignaciones y su historial se conserva.
RNF: RNF-03. Prioridad: Alta/Esencial.

### RF-16 — Registro de movimiento de artículo
Características: Reubicación y/o cambio de resguardante, reparación, motivo obligatorio, sellado de auditoría.
Descripción: El sistema permitirá al Administrador registrar movimientos de un artículo (cualquier origen) con tres opciones: reubicación y/o cambio de resguardante, envío a reparación y retorno de reparación. En la reubicación se puede cambiar solo la ubicación, solo el resguardante o ambos; lo que no cambia se conserva y no se permiten movimientos sin cambio efectivo. El motivo y la fecha son obligatorios. El movimiento ALTA lo registra automáticamente el sistema al crear un artículo (alta manual o carga masiva); no es opción manual. La pérdida y la recuperación de un bien se registran como reubicación hacia y desde la ubicación 'No localizado'; al recuperarlo se elige la ubicación real y se reconfirma el estado. En la reposición por el resguardante se conserva el mismo registro: se registra la reubicación con motivo "Reposición" y los datos del bien nuevo se corrigen desde la ficha (RF-08). El registro queda sellado con el usuario que lo realizó y no puede eliminarse.
RNF: RNF-03, RNF-06, RNF-07. Prioridad: Alta/Esencial.

### RF-17 — Consulta de historial de movimientos
Solo terminología: "equipo" pasa a "artículo".

### RF-18 — Generación de documento de resguardo
Características: PDF bajo demanda, consolidado por resguardante, dos firmas.
Descripción: El sistema permitirá generar bajo demanda un documento de resguardo en PDF para uno o varios artículos de un mismo resguardante, de modo que firme un solo documento con todos los artículos listados (incluyendo su identificador según origen), el resguardante nuevo y, en su caso, el resguardante anterior, la fecha y espacios para dos firmas: la de la Contadora (responsable de seguimiento) y la del resguardante o nuevo resguardante, para los tres orígenes. El documento no incluye "Monto revalúo" y su diseño es propio del sistema. El PDF emitido se conserva sin cambios y puede reimprimirse sin generar folio ni movimiento nuevos. Generar el PDF no equivale a que esté firmado; no hay firma digital. El cambio de resguardante, incluso cuando alguien deja la institución, se documenta con este mismo resguardo. No se genera comprobante en altas históricas de bienes no localizados ni en la carga masiva.
RNF: RNF-04, RNF-08. Prioridad: Alta/Esencial.

### RF-19 — Generación de código QR por artículo
Características: Identificador técnico permanente basado en la clave del artículo.
Descripción: El sistema asignará un código QR a todo artículo, sea por alta manual o por carga masiva. El QR codifica un identificador técnico permanente basado en la clave primaria del artículo; no contiene URL ni dominio ni el marbete o folio, por lo que no cambia si el marbete se corrige. El sistema no guarda la imagen del QR: la genera para descargarse o imprimirse. Imprimir y adherir las etiquetas corresponde a la institución.
RNF: RNF-03. Prioridad: Alta/Esencial.

### RF-20 — Lectura de código QR desde el navegador
Características: Escáner dentro de InventaCore con cámara del celular, solo usuarios autenticados.
Descripción: El sistema permitirá escanear el código QR de un artículo con la cámara del celular desde el navegador web, mediante un escáner integrado en InventaCore disponible para usuarios autenticados, redirigiendo directamente a la ficha del artículo.
RNF: RNF-04, RNF-08. Prioridad: Alta/Esencial.

### RF-21 — Bitácora de auditoría del sistema
Características: Registro automático e inalterable de acciones críticas, visible solo para el Administrador.
Descripción: El sistema deberá registrar automáticamente toda acción crítica (alta, cambio a Obsoleto, modificación, movimiento), almacenando usuario, acción, motivo, valores anteriores y nuevos, y fecha/hora. Cada operación crítica actualiza el artículo, crea el movimiento y escribe la bitácora en una sola transacción. La bitácora es de solo consulta, solo la ve el rol Administrador y no puede modificarse ni eliminarse.
RNF: RNF-06, RNF-07. Prioridad: Alta/Esencial.

### RF-22 — Generación de reportes exportables
Descripción: El sistema permitirá generar reportes filtrados por origen (Activo/Comodato/Enser), categoría, tipo de artículo, ubicación, estado operativo, estado de registro y rango de fechas, con exportación a PDF. El rol Consulta puede generar reportes PDF.
RNF: RNF-04. Prioridad: Alta/Esencial.

### RF-23 — Búsqueda rápida de artículo
Descripción: El sistema ofrecerá un buscador único en el panel principal para localizar un artículo por su identificador (marbete o folio), mediante el escáner QR integrado o por nombre del resguardante actual.
RNF: RNF-03, RNF-04. Prioridad: Alta/Esencial.

---

## Requerimientos funcionales nuevos (ampliación del alcance, no alcance de la tesina)

### RF-24 — Generación de plantilla de Excel para carga masiva
Características: Plantilla con listas desplegables generadas desde los catálogos.
Descripción: El sistema generará una plantilla de Excel para que la institución capture en ella su inventario existente. Las columnas de catálogo (tipo, origen, ubicación, resguardante, estado operativo y ¿Donado?) traerán listas desplegables generadas desde los catálogos del sistema para evitar variantes de escritura. La plantilla solo incluye la columna ¿Donado? (Sí/No); nunca el estado de registro. Antes de la primera carga deben existir en el sistema las categorías, los tipos, las ubicaciones y el personal.
RNF (propuesta): RNF-04. Prioridad: por definir.

### RF-25 — Carga masiva de artículos desde Excel
Características: Validación, vista previa y confirmación; solo entran las filas válidas.
Descripción: El sistema permitirá al Administrador subir la plantilla llena. Al subirla, el sistema volverá a validar todos los datos y mostrará una vista previa con las filas válidas y las filas con error, indicando el motivo. Al confirmar, solo entrarán las filas válidas. Un identificador (marbete o folio) que ya existe en el sistema se rechaza como duplicado. Cada artículo cargado cumple las mismas reglas que el alta manual (ubicación y resguardante obligatorios, marbete obligatorio para Activos), recibe su QR, tiene su estado de registro calculado por el sistema y genera su ALTA automática con motivo "Carga masiva" (archivo y fecha), sin resguardo pendiente. Los inventarios por año se cargan del más reciente (2026) al más antiguo; los anteriores solo agregan los bienes que no aparecen en los más recientes. La institución llena y carga la información; el equipo del proyecto no carga el inventario.
RNF (propuesta): RNF-06, RNF-07, RNF-09. Prioridad: por definir.

### RF-26 — Exportación del inventario a Excel
Características: Archivo de Excel del inventario para la dirección estatal.
Descripción: El sistema exportará el inventario a Excel para que la Contadora lo envíe a la dirección estatal. Columnas: identificador (marbete o folio), categoría, tipo, marca, modelo, serie, color, descripción, origen, ubicación, resguardante, estado operativo, fecha y costo de adquisición, y estado de registro (calculado, solo de salida). No incluye cuenta contable.
RNF (propuesta): RNF-04, RNF-11. Prioridad: por definir.

---

## Requerimientos no funcionales modificados

### RNF-02 — Control de acceso por rol
Descripción: Cada módulo estará restringido según el rol del usuario. El rol Administrador tiene acceso completo, incluida la bitácora y la administración de usuarios. El rol Consulta puede ver el dashboard, consultas, historial, resguardos y reportes PDF, sin modificar información ni ver la bitácora. Los permisos se validan en el backend.

### RNF-06 — Integridad de registros
Descripción: Los registros de artículos y movimientos no podrán eliminarse. El paso a Obsoleto (la baja institucional) se realiza mediante cambio de estado operativo, y toda modificación exige motivo; las correcciones quedan registradas con valor anterior, nuevo, motivo, usuario y fecha.

### RNF-09 — Retroalimentación de operaciones al usuario
Descripción: El sistema deberá informar de forma clara e inmediata el resultado de toda operación crítica, incluyendo advertencias cuando un registro quede en estado 'Pendiente' por falta de fecha o costo de adquisición, un mensaje claro cuando se alcance el límite de 999 folios del mes y, en la carga masiva, el motivo de cada fila con error.

### RNF-10 — Confirmación de acciones irreversibles
Descripción: Antes de ejecutar el cambio de un artículo a Obsoleto o un cambio de resguardante, el sistema deberá solicitar confirmación explícita del usuario.

### RNF-11 — Independencia de sistemas externos
Descripción: El sistema deberá operar de forma 100% interna al CONALEP Tijuana II, sin conexión, integración ni exportación automática hacia el sistema de contabilidad gubernamental SAACG.NET del estado. El MARBETE SAACG.NET se conserva como dato oficial de referencia para el artículo de origen 'Activo', corregible solo mediante una operación autorizada y auditada. La exportación a Excel (RF-26) es un archivo que el usuario envía manualmente, no una integración.

---

## Puntos abiertos (no se resolvieron; requieren tu confirmación)

1. Terminología: se usó "artículo". El título del documento y el encabezado de sección "Gestión de equipo electrónico (catálogo)" no se tocaron (DEC-009). ¿Los renombro?
2. RF-04: las 7 categorías ya no se precargan (DEC-002). Siguen en el alcance de la tesina; hay que cuidar que los documentos no se contradigan.
3. RF-08: DEC-013 no menciona si el tipo de artículo o el origen se pueden corregir desde la ficha. Se omitió.
4. RF-18: DEC-007 no dice si el resguardo consolidado conserva al "resguardante anterior". Se dejó el texto original.
5. RF-07: el costo en bienes donados sigue abierto (PEND-004); por eso se quitó "Donado, sin costo" y no se afirma si el costo se bloquea.
6. RF-24 a RF-26: las decisiones no fijan prioridad ni qué rol exporta a Excel (DEC-001 no lista Excel entre lo que ve Consulta). La vinculación a RNF es propuesta mía.
7. RF-03: DEC-001 lo lista como impactado, pero su texto sigue válido; sin cambio.
8. RNF-03: no hay criterio de rendimiento para la carga masiva; depende de la prueba de carga (PEND-013).
9. No incluidas por ser propuesta o pendiente: PEND-001 (diseño de resguardos), PEND-005, PEND-007, PEND-013 (diseño técnico y bitácora de la carga), PEND-014 y PEND-017.
