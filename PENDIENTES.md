# PENDIENTES — InventaCore

Última actualización: 01/11/2026
Dudas abiertas, propuestas por validar y preguntas para la Contadora o Adad. No implementar como definitivo nada de aquí.

## Cerrados el 29/10 y 01/11/2026 (pasaron a DECISIONES.md)

- PEND-002 Folios: consecutivo compartido, límite 999 validado, se respetan identificadores históricos, no hay Activo sin marbete (DEC-010).
- PEND-003 Estados: Útil, Obsoleto y No localizado; sin AUTB ni BAJA; no se da de baja un No localizado (DEC-006, DEC-012).
- PEND-006 Resguardos: dos firmas, documento consolidado, sin Monto revalúo, formato propio (DEC-007).
- PEND-008 Campos: color y descripción obligatorios; marca, modelo, serie y fecha opcionales (DEC-011).
- PEND-009 Cambios de estado desde la ficha: Obsoleto desde la ficha con motivo y bitácora (DEC-013).

## Para validar con Adad

PEND-015 — Una sola fuente del esquema: SQL o migraciones
Prioridad: ALTA

- Hoy las tablas se definen dos veces: en InventaCore_db.sql y en los modelos/migraciones de Django (todas las tablas son managed). Si se ejecuta el SQL y luego `migrate`, Django intenta crear tablas que ya existen.
- Propuesta: las migraciones de Django son la fuente que crea la base; el SQL queda como documento de referencia para la tesina, regenerado o revisado al final (`python manage.py sqlmigrate`).
- Antes de tener datos reales, compactar las migraciones de catalogos (0002 siembra categorías de cómputo, 0003 siembra cuentas contables, 0006 las borra).

PEND-016 — Cambios al SQL y a los modelos por las decisiones del 01/11/2026
Prioridad: ALTA

- estado_operativo: quitar AUTB. Quedan UTIL, OBS y NOLOC.
- tipo_movimiento: quitar BAJA y sacarla de los CHECK de movimiento (cambia_algo y requiere_resguardo).
- Validación (servicio): un artículo NOLOC no puede pasar a OBS.
- Folio: el generador no puede repetir un identificador existente (los históricos de la carga también cuentan).
- Textos: docstring de Articulo ("baja con AUTB"), descripción de UBI-NOLOC en el SQL ("Cambio de ubicación" debe decir REUB), encabezado del SQL (título, "Contadora", "OBS (Observador)"), nombre de la clase de permisos y textos que dicen "Observador".

PEND-001 — Diseño relacional de resguardos
Estado: PROPUESTA
Prioridad: ALTA

- RESGUARDO: folio (PK), fecha_emision, resguardante (FK PERSONAL), usuario_emisor (FK USUARIO), ruta_pdf (única), hash_pdf, y opcionalmente fecha_firma.
- RESGUARDO_DETALLE: num (PK), resguardo (FK), movimiento (FK, UNIQUE). Sin FK a ARTICULO: se obtiene por el movimiento.
- Se elimina la relación 1:1 entre MOVIMIENTO y RESGUARDO (hoy en `movimientos.models.Resguardo`).
- Nuevo: de dónde sale el nombre de la Contadora que firma como responsable de seguimiento. Opciones: el usuario que emite, o un dato configurable del sistema.
- PDF en carpeta del servidor, sin sobrescribir; la reimpresión entrega el archivo original.

PEND-005 — Identificadores técnicos
Estado: PROPUESTA
Prioridad: MEDIA

- MOVIMIENTO: Adad dejó folio como PK. Propuesta: aceptarlo y cerrar el punto, actualizando DER y diccionario.
- PERSONAL: numero_empleado está NOT NULL y único. Confirmar que todo empleado tiene número, porque la carga masiva lo usará para identificar al resguardante.

PEND-013 — Diseño técnico de la carga masiva
Estado: PROPUESTA
Prioridad: ALTA

- Librería para leer y escribir Excel: openpyxl (agregar a requirements.txt).
- Identificar al resguardante por número de empleado (la lista muestra número y nombre), no por nombre escrito.
- Coincidencia sin distinguir mayúsculas ni espacios extra en las columnas de catálogo.
- Validación por fila con el mismo servicio que el alta manual, para no tener dos reglas distintas.
- Cada fila válida se guarda en su propia transacción (o todo el archivo en una sola): decidir. Propuesta: vista previa y luego una transacción por archivo con solo las filas válidas.
- Duplicados dentro del mismo archivo, además de contra la base.
- Límite de filas por archivo y tiempo de respuesta: medir en la prueba de carga.
- Registrar en BITACORA la carga (archivo, usuario, filas aceptadas y rechazadas).

PEND-014 — Formato de la exportación
Prioridad: MEDIA

- Confirmar con la Contadora que las columnas de DEC-018 le sirven para la dirección estatal (no compartió un formato oficial; se toma como base el Excel de referencia del Contexto).

## Para la Contadora o la institución

PEND-004 — Bienes donados
Prioridad: MEDIA

- ¿El costo se bloquea o se captura en un bien donado?

PEND-007 — Personal que deja la institución
Prioridad: MEDIA

- El cambio de resguardante se hace con REUB y resguardo nuevo (DEC-007).
- Sin respuesta: si aparece un bien No localizado cuyo último resguardante está inactivo, ¿a quién se asigna al recuperarlo?

PEND-017 — Acta de hechos en la reposición
Prioridad: BAJA

- ¿Se quiere guardar en el sistema el número o archivo del acta de hechos, o basta con el motivo del REUB?

## Verificaciones y avances

PEND-011 — Revisión del repositorio (01/11/2026)

- Frontend: datos de prueba, rol simulado con ?rol=CONT, folio IC-, QR con URL, NOLOC no sincronizado, nombres de campo del DD viejo. Se adapta cuando el backend publique los endpoints de artículos y movimientos.
- SECRET_KEY y usuario root sin contraseña en settings.py: aceptable en desarrollo, mover a variables de entorno antes de desplegar.
- client/ apunta a la misma base inventacore_db como root aunque no tiene modelos.
- requirements.txt: falta qrcode (lo usa client) y openpyxl (carga y exportación).

PEND-012 — Avances de Adad

- 29/10/2026: usuarios, login con token de 24 h, permisos, personal, catálogos, modelos de artículo, movimiento y bitácora, folios, pruebas. Aún no hay endpoints de artículos ni de movimientos.

PEND-018 — Cotejo de la transcripción de la reunión con la Contadora

- Fernando la compartirá para verificar que el resumen coincide.

## Tesina y documentos

- Actualizar RF/RNF, DER y diccionario solo en lo que cambió (DEC-001 a DEC-018), derivando DER y diccionario del esquema final.
- RF nuevos por redactar: carga masiva y exportación a Excel (ampliación, no alcance de la tesina).
- Renombrar EQUIPO a ARTICULO en DER y diccionario.
- Tesina: decidir si dice MySQL o MariaDB, corregir 5.14 y Kanban.
- INVENTARIO_ESTADO_ACTUAL.md: dos columnas, alcance de la tesina y alcance del software.
