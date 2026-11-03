# DECISIONES — InventaCore

Última actualización: 01/11/2026
Aquí solo van decisiones que Fernando aprobó. Las propuestas y dudas van en PENDIENTES.md.
Fuente de las decisiones DEC-017 a DEC-019 y de los cambios del 01/11/2026: reunión con la Contadora (29/10/2026) y confirmaciones de Fernando (29/10 y 01/11/2026).

## DEC-001 — Roles del sistema

Estado: CONFIRMADA (25/10/2026)
Decisión: Dos roles, ADMINISTRADOR y CONSULTA. La Contadora y los jefes usan rol ADMINISTRADOR (incluye administrar usuarios). No hay rol Contadora ni Gestor.
ADMINISTRADOR: todo, incluida la bitácora. CONSULTA: dashboard, consultas, historial, resguardos y reportes PDF; no modifica nada ni ve la bitácora.
Los permisos se validan en el backend; ?rol= del frontend es solo simulación.
Impacto: RF-01, 02, 03, 08, 21; RNF-02; ROL; USUARIO; API; frontend; pruebas de permisos.
Implementación: backend de Adad (usuarios, login con token, permisos). Frontend: login real, rol real en sesión, menú y bloqueo por rol implementados (01/11/2026, ver DEC-019).

## DEC-002 — Clasificación del inventario y nombre de la entidad

Estado: CONFIRMADA (nombre ARTICULO confirmado 01/11/2026)
Decisión: CATEGORIA 1:M TIPO_ARTICULO 1:M ARTICULO. La entidad que antes se llamaba EQUIPO se llama ARTICULO (tabla `articulo`). ARTICULO tiene FK solo a TIPO_ARTICULO; la categoría se obtiene por esa relación. La clasificación es independiente de ORIGEN. No se guarda número de cuenta contable. Categorías y tipos arrancan vacíos y se dan de alta desde el sistema.
La tesina conserva "equipo electrónico" como alcance aprobado (DEC-009).
Impacto: RF-04, 05, 09, 22; DER; diccionario; alta, filtros, carga masiva.

## DEC-003 — Ubicación y resguardante obligatorios

Estado: CONFIRMADA
Decisión: Todo ARTICULO tiene ubicación y resguardante desde el alta (también en la carga masiva). `articulo.ubicacion` y `articulo.resguardante` son FK NOT NULL. No hay borradores ni personas ficticias "Sin asignar". El resguardante es una persona real de PERSONAL; para nuevas asignaciones debe estar activa. El historial de PERSONAL se conserva aunque la persona deje de estar activa.

## DEC-004 — Bitácora de auditoría

Estado: CONFIRMADA
Decisión: BITACORA la escribe Django desde los servicios del backend, sin triggers ni procedimientos almacenados. Cada operación crítica actualiza ARTICULO, crea MOVIMIENTO y escribe BITACORA en una sola transacción. Toda modificación exige motivo.
Implementación: iniciada por Adad (BitacoraMixin, servicio registrar).

## DEC-005 — QR con identificador permanente

Estado: CONFIRMADA
Decisión: El QR contiene un identificador técnico basado en la PK de ARTICULO, sin URL ni dominio. No hay entidad QR ni se guarda la imagen. Todo artículo tiene QR, sin importar si entró por alta manual o por carga masiva. La lectura se hace con un escáner dentro de InventaCore (usuario autenticado). Imprimir y pegar las etiquetas corresponde a la institución, no al proyecto.
Impacto: RF-19, 20, 23; frontend; API.

## DEC-006 — Movimientos del inventario

Estado: CONFIRMADA (actualizada 01/11/2026: se elimina BAJA)
Decisión: Cuatro tipos internos: ALTA, REUB, REPA, RETE. Ya no existe el tipo BAJA.
ALTA se registra automáticamente al crear un artículo, por alta manual o por carga masiva (no es opción manual). El formulario "Nuevo movimiento" tiene tres opciones: Reubicación y/o cambio de resguardante, Envío a reparación y Retorno de reparación.
REUB cambia solo ubicación, solo resguardante o ambos en una operación. Lo que no cambia se conserva (campo vacío no es NULL). No se permiten movimientos sin cambio efectivo.
El ALTA es incorporación al sistema, no entrega física.
Contexto: la institución hoy no registra salidas, retornos ni reubicaciones; el módulo de movimientos busca corregir eso.

## DEC-007 — Resguardos individuales y consolidados

Estado: CONFIRMADA EN LO FUNCIONAL (actualizada 01/11/2026)
Decisión: Los resguardos se generan bajo demanda para uno o varios artículos del mismo resguardante; el resguardante firma un solo documento con todos los artículos listados. El PDF emitido se conserva sin cambios y se reimprime sin folio ni movimiento nuevos. Generar el PDF no equivale a que esté firmado. Sin firma digital.
Firmas: dos, la de la Contadora (responsable de seguimiento) y la del resguardante o nuevo resguardante, para los tres orígenes (Activo, Comodato y Enser). Se elimina "Monto revalúo". No hay segundo formato: el sistema propone un diseño propio, más limpio que el actual, con el listado de artículos resguardados.
El cambio de resguardante (incluido cuando alguien deja la institución) se hace con REUB y se documenta con este mismo resguardo.
No se genera comprobante en altas históricas de bienes no localizados ni en la carga masiva.
Pendiente técnico: PEND-001.

## DEC-008 — Estados de registro

Estado: CONFIRMADA
Decisión: Registrado, Pendiente y Donado. Donado tiene prioridad. Si no es donado: con fecha y costo de adquisición completos es Registrado; si falta alguno, Pendiente. El sistema siempre lo calcula, también en la carga masiva: la plantilla solo trae la columna "¿Donado?" (Sí/No), nunca el estado de registro. La fecha de adquisición puede capturarse o corregirse después desde la ficha, y el estado se recalcula. Si un Administrador corrige un Donado por error, queda en BITACORA y se recalcula.
Pendiente institucional: costo en bienes donados (PEND-004).

## DEC-009 — Alcance del software y de la tesina

Estado: CONFIRMADA (contexto actualizado 01/11/2026)
Decisión: El software administra inventario general. La tesina conserva título, objetivos y alcance aprobados (equipo electrónico del Departamento de Informática). La ampliación (inventario general, carga masiva y exportación a Excel) se documenta como mejora adicional, separando lo implementado de lo evaluado.
Contexto: la Contadora usará el sistema como alternativa sin dejar Excel. Por acuerdo con el asesor empresarial, el sistema se adapta a la forma en que ella trabaja. El equipo del proyecto no carga el inventario institucional: entrega la plantilla y la institución la llena y la carga.

## DEC-010 — Identificadores por origen y folio

Estado: CONFIRMADA (actualizada 01/11/2026)
Decisión:

- Activos usan marbete oficial, sin folio interno. No se puede registrar un Activo sin marbete oficial (ni manual ni por carga).
- Comodatos y Enseres usan folio interno. En el alta manual lo genera el sistema, no editable: 02143MMYY-NNN (MMYY = mes y año de registro en el sistema, NNN consecutivo mensual desde 001). Comodatos y Enseres comparten el consecutivo mensual.
- El sistema valida el límite de 999 por mes y muestra un mensaje claro si se alcanza.
- En la carga masiva se respeta el folio o marbete que ya tiene el bien, aunque tenga otro formato (por ejemplo 10 dígitos antes del guion). Así las etiquetas físicas no cambian. El consecutivo generado solo se usa en altas manuales nuevas, y nunca puede repetir un identificador existente.
- El marbete de un Activo puede corregirse con operación autorizada y auditada, sin cambiar la identidad del registro ni su QR. Número de serie opcional.

## DEC-011 — Campos obligatorios y opcionales de ARTICULO

Estado: CONFIRMADA (actualizada 27/10/2026, ratificada por la Contadora 29/10/2026)
Decisión: Obligatorios: tipo de artículo, origen, identificador, ubicación, resguardante, estado operativo, color y descripción. Pueden ser NULL: marca, modelo, número de serie, fecha de adquisición y costo. La fecha de adquisición se puede capturar o cambiar después. La interfaz muestra "Sin especificar"; no se guardan textos como S/M o S/S.

## DEC-012 — Estado operativo, No localizado y reposición

Estado: CONFIRMADA (actualizada 01/11/2026)
Decisión: Tres estados: Útil, Obsoleto y No localizado. Se eliminan "Autorizado para baja" (AUTB) y la baja como movimiento.

- Obsoleto equivale a lo que la institución llama baja: artículos que ya no sirven ni se usan. La Contadora los reporta a la dirección estatal, que hace el proceso de baja. El registro nunca se borra. Regresar de Obsoleto a Útil es excepcional y solo con corrección auditada.
- "No localizado" existe como estado y como ubicación (UBI-NOLOC) y se sincronizan en ambos sentidos, validado en frontend y backend. NOLOC y UBI-NOLOC son valores protegidos.
- Un artículo No localizado no puede pasar a Obsoleto.
- La pérdida y la recuperación se registran con REUB. Al recuperar se elige la ubicación real y se reconfirma el estado.
- Reposición: el resguardante es responsable de reponer el bien. El bien que lo repone toma el mismo registro (mismo marbete o folio, mismo QR e historial). Se registra un REUB de UBI-NOLOC a la ubicación real con motivo "Reposición" y se corrigen desde la ficha los datos del bien nuevo (marca, modelo, serie, color, descripción), con registro en BITACORA. La institución levanta un acta de hechos fuera del sistema.
- Se permite el alta histórica de un bien no localizado, conservando su último resguardante conocido.

## DEC-013 — Edición de la ficha

Estado: CONFIRMADA (actualizada 01/11/2026)
Decisión: Ubicación y resguardante solo cambian por MOVIMIENTO. Marca, modelo, serie, color, descripción y fecha de adquisición se corrigen desde la ficha con motivo y registro en BITACORA. El cambio a Obsoleto se hace desde la ficha con motivo obligatorio y BITACORA, sin movimiento (Obsoleto es un estado, no un lugar); la ubicación y el resguardante se conservan. Un artículo puede darse de alta ya como Obsoleto. No localizado y reparación siguen sus propias reglas.

## DEC-014 — DEPARTAMENTO y UBICACION

Estado: CONFIRMADA
Decisión: Son entidades distintas. DEPARTAMENTO es la unidad organizativa de PERSONAL; UBICACION es el espacio físico del bien. No hay entidad EDIFICIO ni relación obligatoria entre ambas. La ubicación del bien y el departamento del resguardante no tienen que coincidir.

## DEC-015 — Catálogos ampliables

Estado: CONFIRMADA
Decisión: Los usuarios autorizados amplían categorías, tipos de artículo y ubicaciones sin tocar código. El sistema genera los códigos de catálogo; el usuario no los escribe.

## DEC-016 — Resguardo: PK y atributo requiere_resguardo

Estado: CONFIRMADA (implementada por Adad en movimiento)
Decisión: RESGUARDO usa folio como PK. MOVIMIENTO.requiere_resguardo (booleano, lo fija el sistema al crear el movimiento) indica qué asignaciones deben documentarse. No existe TIPO_MOVIMIENTO.genera_resguardo.

## DEC-017 — Carga masiva desde plantilla de Excel

Estado: CONFIRMADA EN LO FUNCIONAL (29/10 y 01/11/2026); diseño técnico en PEND-013
Decisión:

- El sistema genera una plantilla de Excel. La Contadora pasa ahí su inventario existente y la sube al sistema. El equipo del proyecto no carga los datos.
- Antes de la primera carga deben existir en el sistema las categorías, los tipos, las ubicaciones y el personal.
- Las columnas de catálogo (tipo, origen, ubicación, resguardante, estado operativo, ¿Donado?) traen listas desplegables generadas desde los catálogos, para evitar variantes de escritura. El sistema vuelve a validar todo al subir el archivo.
- Antes de guardar, el sistema muestra una vista previa con las filas válidas y las filas con error y su motivo. Al confirmar, solo entran las filas válidas.
- Un identificador (marbete o folio) que ya existe en el sistema se rechaza como duplicado.
- Cada artículo cargado genera su ALTA automática con motivo "Carga masiva" (archivo y fecha), sin resguardo pendiente.
- El estado de registro lo calcula el sistema (DEC-008).
- Orden de carga de los inventarios por año (23, 24, 25 y 26): primero el más reciente (2026) y después los anteriores, que solo agregan los bienes que no aparecen en los más recientes.
  Prueba prevista: además del alta manual, probar la carga masiva y el comportamiento del sistema con muchos registros.

## DEC-018 — Exportación a Excel

Estado: CONFIRMADA (01/11/2026)
Decisión: El sistema exporta el inventario a Excel para que la Contadora lo envíe a la dirección estatal. Columnas: identificador (marbete o folio), categoría, tipo, marca, modelo, serie, color, descripción, origen, ubicación, resguardante, estado operativo, fecha y costo de adquisición, y estado de registro (calculado, solo de salida). Sin cuenta contable.

## DEC-019 — Módulos visibles por rol

Estado: CONFIRMADA (01/11/2026)
Decisión: El rol CONSULTA solo accede a Dashboard, Equipos (artículos), Movimientos y Reportes, y a su perfil. Personal, Catálogos, Bitácora y Usuarios y Roles son solo del ADMINISTRADOR: Consulta no los ve en el menú ni los abre escribiendo la URL.

- Precisa DEC-001: la consulta de ubicaciones y empleados (RF-13 y RF-15) es solo para el Administrador.
- Cliente: el menú se arma según el rol y `usuarios/middleware.py` redirige a Consulta al dashboard si intenta entrar a una sección de administración.
- API: la lectura (GET) de catálogos y personal sigue permitida a CONSULTA porque los filtros y el detalle de equipos y movimientos la necesitan. La escritura sigue siendo solo del Administrador y la API responde 403 aunque el cliente falle.
Impacto: RF-13, RF-15, RNF-02; frontend; pruebas de permisos.
Implementación: cliente listo y probado (01/11/2026).
