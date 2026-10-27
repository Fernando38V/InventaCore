# DECISIONES — InventaCore

Última actualización: 27/10/2026
Aquí solo van decisiones que Fernando aprobó. Las propuestas y dudas van en PENDIENTES.md.

## DEC-001 — Roles del sistema

Estado: CONFIRMADA (25/10/2026)
Decisión: Dos roles, ADMINISTRADOR y CONSULTA. La Contadora y los jefes usan rol ADMINISTRADOR (incluye administrar usuarios). No hay rol Contadora ni Gestor.
ADMINISTRADOR: todo, incluida la bitácora. CONSULTA: dashboard, consultas, historial, resguardos y reportes PDF; no modifica nada ni ve la bitácora.
Los permisos se validan en el backend; ?rol= del frontend es solo simulación.
Impacto: RF-01, 02, 03, 08, 21; RNF-02; ROL; USUARIO; API; frontend; pruebas de permisos.
Implementación: PENDIENTE

## DEC-002 — Clasificación del inventario

Estado: CONFIRMADA
Decisión: CATEGORIA 1:M TIPO_ARTICULO 1:M EQUIPO. EQUIPO tiene FK solo a TIPO_ARTICULO; la categoría se obtiene por esa relación. La clasificación es independiente de ORIGEN. No se guarda número de cuenta contable. Categorías inspiradas en el inventario institucional, sin reproducir su clasificación contable.
Impacto: RF-04, 05, 09, 22; DER; diccionario; alta y filtros.
Implementación: PENDIENTE

## DEC-003 — Ubicación y resguardante obligatorios

Estado: CONFIRMADA
Decisión: Todo EQUIPO tiene ubicación y resguardante desde el alta. EQUIPO.ubicacion y EQUIPO.personal son FK NOT NULL. No hay borradores ni personas ficticias "Sin asignar". El resguardante es una persona real de PERSONAL; para nuevas asignaciones debe estar activa. El historial de PERSONAL se conserva aunque la persona deje de estar activa.
Implementación: PENDIENTE

## DEC-004 — Bitácora de auditoría

Estado: CONFIRMADA
Decisión: BITACORA la escribe Django desde los servicios del backend, sin triggers ni procedimientos almacenados. Cada operación crítica actualiza EQUIPO, crea MOVIMIENTO y escribe BITACORA en una sola transacción.
Impacto: backend, RF-21, RNF-06, pruebas.
Implementación: PENDIENTE

## DEC-005 — QR con identificador permanente

Estado: CONFIRMADA
Decisión: El QR contiene un identificador técnico basado en la PK de EQUIPO, sin URL ni dominio. No hay entidad QR ni se guarda la imagen. La lectura se hace con un escáner dentro de InventaCore (usuario autenticado) que busca el registro y abre su ficha según permisos. Un equipo dado de baja conserva su registro y su QR. Consecuencia aceptada: la cámara nativa del celular ya no abre la ficha.
Impacto: RF-19, 20, 23; frontend; API.
Implementación: PENDIENTE

## DEC-006 — Movimientos del inventario

Estado: CONFIRMADA
Decisión: Cinco tipos internos: ALTA, REUB, REPA, RETE, BAJA. ALTA se registra automáticamente al crear un equipo (no es opción manual). El formulario "Nuevo movimiento" tiene cuatro opciones: Reubicación y/o cambio de resguardante, Envío a reparación, Retorno de reparación y Baja.
REUB cambia solo ubicación, solo resguardante o ambos en una operación. Lo que no cambia se conserva (campo vacío no es NULL). No se permiten movimientos sin cambio efectivo.
El ALTA es incorporación al sistema, no entrega física.
Implementación: PENDIENTE

## DEC-007 — Resguardos individuales y consolidados

Estado: CONFIRMADA EN LO FUNCIONAL
Decisión: Los resguardos se generan bajo demanda para uno o varios artículos del mismo resguardante. El PDF emitido se conserva sin cambios y se reimprime sin folio ni movimiento nuevos. Generar el PDF no equivale a que esté firmado. El listado de bienes por persona es una consulta aparte. Sin firma digital en esta versión. No se genera comprobante en altas históricas de bienes no localizados.
Pendiente técnico: ver PEND-001.
Implementación: PENDIENTE

## DEC-008 — Estados de registro

Estado: CONFIRMADA
Decisión: Registrado, Pendiente y Donado. Donado tiene prioridad. Si no es donado: con fecha y costo de adquisición completos es Registrado; si falta alguno, Pendiente. Si un Administrador corrige un Donado por error, queda en BITACORA y se recalcula. El frontend muestra mensajes distintos según el estado; las reglas se validan también en el backend.
Pendiente institucional: costo en bienes donados (PEND-004).
Implementación: PENDIENTE

## DEC-009 — Alcance del software y de la tesina

Estado: CONFIRMADA
Decisión: El software administra inventario general (mobiliario, herramientas, equipo electrónico y otros). La tesina conserva título, objetivos y alcance aprobados (equipo electrónico del Departamento de Informática). La ampliación se documenta como mejora adicional, separando lo implementado de lo evaluado. No se precarga el inventario institucional completo.

## DEC-010 — Identificadores por origen y folio

Estado: CONFIRMADA (formato); casos especiales en PEND-002
Decisión: Activos usan marbete oficial, sin folio interno. Comodatos y Enseres usan folio interno generado por el sistema, no editable. Formato 02143MMYY-NNN (MMYY = mes y año de registro en el sistema, NNN consecutivo mensual desde 001). El marbete de un Activo puede corregirse con operación autorizada y auditada, sin cambiar la identidad del registro ni su QR. Número de serie opcional.

## DEC-011 — Campos opcionales de EQUIPO

Estado: CONFIRMADA
Decisión: Obligatorios: tipo de artículo, origen, identificador, ubicación, resguardante y estado operativo. Pueden ser NULL: marca, modelo, número de serie, color, descripción, fecha de adquisición y costo. La interfaz muestra "Sin especificar"; no se guardan textos como S/M o S/S.

## DEC-012 — Estado operativo y No localizado

Estado: CONFIRMADA (reglas de transición en PEND-003)
Decisión: Estados provisionales: Útil, Obsoleto, Autorizado para baja y No localizado. "No localizado" existe como estado y como ubicación (UBI-NOLOC) y se sincronizan en ambos sentidos, validado en frontend y backend. NOLOC y UBI-NOLOC son valores protegidos (no se desactivan ni renombran). La pérdida y la recuperación se registran con REUB; al recuperar se elige la ubicación real y se reconfirma el estado, sin restaurar el anterior. Se permite el alta histórica de un bien no localizado, conservando su último resguardante conocido.

## DEC-013 — Edición de la ficha

Estado: CONFIRMADA
Decisión: Ubicación y resguardante solo cambian por MOVIMIENTO. Marca, modelo, serie, color y descripción se corrigen desde la ficha con registro en BITACORA. El estado operativo solo se edita directo en cambios ordinarios autorizados; localización, reparación y baja siguen sus reglas.

## DEC-014 — DEPARTAMENTO y UBICACION

Estado: CONFIRMADA
Decisión: Son entidades distintas. DEPARTAMENTO es la unidad organizativa de PERSONAL; UBICACION es el espacio físico del bien. No hay entidad EDIFICIO ni relación obligatoria entre ambas. Cada ubicación se selecciona directamente y el catálogo se amplía con las áreas del plantel. La ubicación del bien y el departamento del resguardante no tienen que coincidir.

## DEC-015 — Catálogos ampliables

Estado: CONFIRMADA
Decisión: Los usuarios autorizados amplían categorías, tipos de artículo y ubicaciones sin tocar código. El sistema genera los códigos de catálogo; el usuario no los escribe.

## DEC-016 — Resguardo: PK y atributo requiere_resguardo

Estado: CONFIRMADA (pendiente de validar con Adad)
Decisión: RESGUARDO usa folio como PK. Se agrega MOVIMIENTO.requiere_resguardo (booleano, lo fija el sistema al crear el movimiento) para saber qué asignaciones deben documentarse, y se retira TIPO_MOVIMIENTO.genera_resguardo.
