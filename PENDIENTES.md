# PENDIENTES — InventaCore

Última actualización: 27/10/2026
Dudas abiertas, propuestas por validar y preguntas para la Contadora o Adad. No implementar como definitivo nada de aquí.

## Para la Contadora y los jefes (reunión 28/10/2026)

PEND-002 — Folios internos
Prioridad: ALTA
Formato confirmado: 02143MMYY-NNN.

- ¿Comodatos y Enseres comparten el consecutivo mensual?
- ¿Qué pasa al llegar a 999?
- ¿Se conservan los identificadores históricos al registrar bienes anteriores?
- Pedir un ejemplo de cómo calcula hoy un folio nuevo. En el Excel los existentes tienen 10 dígitos antes del guion (ej. 0214300168-001) y el nuevo tendría 9; confirmar que es la misma numeración.
- ¿Puede registrarse un Activo cuyo marbete aún no se conoce?

PEND-003 — Estados operativos y movimientos
Prioridad: ALTA

- ¿Qué significa "Obsoleto": no funciona, está desactualizado o ambas?
- ¿"Autorizado para baja" es una etapa previa a la baja definitiva?
- ¿Cómo registran hoy la salida y el retorno de reparación? ¿Se necesita el estado "En reparación"?
- ¿Se puede tramitar la baja de un bien que sigue sin localizarse?

PEND-004 — Bienes donados
Prioridad: MEDIA

- ¿El costo se bloquea o se captura en un bien donado?

PEND-006 — Resguardos e institución
Prioridad: ALTA

- ¿Quién firma como responsable de seguimiento? ¿Qué procedimiento se sigue cuando cambia el resguardante?
- ¿Se firma un documento por entrega o un consolidado de todos los bienes asignados?
- ¿Pueden compartir el formato de cambio de resguardante? ¿Se conserva "Monto revalúo"?
- El campo "Área" del formato: ¿es el departamento de la persona o el lugar del bien?
- Al dar de alta bienes que ya existen, ¿necesitan un resguardo nuevo o basta el de papel?

PEND-007 — Personal que deja la institución
Prioridad: MEDIA

- ¿Qué pasa con sus bienes? ¿Se reasignan antes de desactivarlo?
- Si aparece un bien No localizado cuyo último resguardante está inactivo, ¿a quién se asigna al recuperarlo?
- Propuesta técnica (sujeta a la respuesta): el alta histórica no cuenta como entrega nueva, pide motivo y no genera resguardo.

PEND-008 — Campos de bienes sin marca, modelo o serie
Prioridad: BAJA
Ya son opcionales (DEC-011). Preguntar si la institución considera indispensable algún dato adicional.

## Para validar con Adad

PEND-001 — Diseño relacional de resguardos
Estado: PROPUESTA
Prioridad: ALTA

- RESGUARDO: folio (PK), fecha_emision, resguardante (FK PERSONAL), usuario_emisor (FK USUARIO), ruta_pdf (única), hash_pdf, y opcionalmente tipo_documento y fecha_firma.
- RESGUARDO_DETALLE: num (PK), resguardo (FK), movimiento (FK, UNIQUE). Así una asignación no puede documentarse dos veces. No lleva FK a EQUIPO: se obtiene por el movimiento.
- Se elimina la relación 1:1 entre MOVIMIENTO y RESGUARDO.
- Pendiente de asignaciones por documentar: requiere_resguardo = verdadero, sin detalle y con la asignación todavía vigente.
- PDF guardado en una carpeta del servidor (no en la base), sin sobrescribir; la reimpresión entrega el archivo original.
- Validar en el servicio que todos los movimientos de un documento correspondan al resguardante indicado.

PEND-005 — Identificadores técnicos
Estado: PROPUESTA
Prioridad: ALTA

- MOVIMIENTO: PK num numérica y folio único (propuesta); el DER dice num, el diccionario dice folio.
- USUARIO: sin correo y ajustar RNF-01 (propuesta). Definir si será el modelo de usuario de Django antes de crear datos.
- PERSONAL: num autoincremental como PK y NumEmp como texto, NULL, único (conserva ceros a la izquierda).

PEND-009 — Cambios de estado desde la ficha
Estado: PROPUESTA (depende de PEND-003)

- Útil ↔ Obsoleto, directo con motivo y bitácora.
- No localizado: solo por REUB. Autorizado para baja: por BAJA. Reparación: por REPA y RETE.

PEND-010 — Bitácora e historial de estados
Estado: PROPUESTA

- No agregar columnas de estado a MOVIMIENTO. Basta con BITACORA si cada cambio de estado se registra en la misma transacción, referencia el folio del movimiento si lo hubo, y ValorAnterior/ValorNuevo pasan a texto largo.

## Verificaciones y avances

PEND-011 — Revisar el repositorio

- Solo lectura, antes de cambiar el DER. Revisar: modelos de Adad en api/, db.sqlite3 en api/ y client/ (debería ser MariaDB), estado NOLOC y folio IC- en el frontend, QR con URL, y que no haya claves en archivos versionados.

PEND-012 — Avances de Adad

- Fernando los recibirá y los compartirá. Comparar contra DECISIONES.md.

## Tesina y documentos

- Actualizar RF/RNF, DER y diccionario solo en lo que cambió (ver DEC-001 a DEC-016).
- Tesina: decidir si dice MySQL o MariaDB, corregir 5.14 (flujo real SVG a Figma) y Kanban (4 o 5 columnas).
- INVENTARIO_ESTADO_ACTUAL.md: dos columnas, alcance de la tesina y alcance del software.
