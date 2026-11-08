# PENDIENTES — InventaCore

Última actualización: 08/11/2026
Dudas abiertas, propuestas por validar y preguntas para la Contadora o Adad. No implementar como definitivo nada de aquí.

## Cerrados el 29/10 y 01/11/2026 (pasaron a DECISIONES.md)

- PEND-002 Folios: consecutivo compartido, límite 999 validado, se respetan identificadores históricos, no hay Activo sin marbete (DEC-010).
- PEND-003 Estados: Útil, Obsoleto y No localizado; sin AUTB ni BAJA; no se da de baja un No localizado (DEC-006, DEC-012).
- PEND-006 Resguardos: dos firmas, documento consolidado, sin Monto revalúo, formato propio (DEC-007).
- PEND-008 Campos: color y descripción obligatorios; marca, modelo, serie y fecha opcionales (DEC-011).
- PEND-009 Cambios de estado desde la ficha: Obsoleto desde la ficha con motivo y bitácora (DEC-013).
- Roles en el cliente: Consulta no accede a catálogos, personal, bitácora ni usuarios (DEC-019).
- Error 500 al registrar un tipo de artículo duplicado: corregido en TipoArticuloSerializer (400 con mensaje). Era el único UniqueConstraint del modelo.
- PEND-004 Costo en bienes donados: opcional, ni se exige ni se bloquea; vacío queda NULL (DEC-021, 04/11/2026).
- Costo de adquisición después del alta: se corrige desde la ficha con motivo y bitácora (DEC-013, 03/11/2026). Pendiente de que Adad lo implemente.
- Dashboard y reportes: alcance mínimo en DEC-020.
- Nombre de la Contadora en la firma: dato del sistema (DEC-007).

## Para validar con Adad

PEND-015 — Una sola fuente del esquema: SQL o migraciones
Prioridad: ALTA

- Hoy las tablas se definen dos veces: en InventaCore_db.sql y en los modelos/migraciones de Django (todas las tablas son managed). Si se ejecuta el SQL y luego `migrate`, Django intenta crear tablas que ya existen.
- Propuesta: las migraciones de Django son la fuente que crea la base; el SQL queda como documento de referencia para la tesina, regenerado o revisado al final (`python manage.py sqlmigrate`).
- Antes de tener datos reales, compactar las migraciones de catalogos (0002 siembra categorías de cómputo, 0003 siembra cuentas contables, 0006 las borra).

PEND-016 — Cambios al SQL y a los modelos por las decisiones del 01/11/2026
Prioridad: ALTA
Estado (03/11/2026): Adad ya los aplicó en modelos y migraciones (commit 9c94d01: sin AUTB ni BAJA, folio sin repetir, permisos renombrados). Falta revisar InventaCore_db.sql y los textos del encabezado.

- estado_operativo: quitar AUTB. Quedan UTIL, OBS y NOLOC.
- tipo_movimiento: quitar BAJA y sacarla de los CHECK de movimiento (cambia_algo y requiere_resguardo).
- Validación (servicio): un artículo NOLOC no puede pasar a OBS.
- Folio: el generador no puede repetir un identificador existente (los históricos de la carga también cuentan).
- Textos: docstring de Articulo ("baja con AUTB"), descripción de UBI-NOLOC en el SQL ("Cambio de ubicación" debe decir REUB), encabezado del SQL (título, "Contadora", "OBS (Observador)"), nombre de la clase de permisos y textos que dicen "Observador".

PEND-001 — Diseño relacional de resguardos
Estado: IMPLEMENTADA (05/11/2026, API de Adad y cliente). Probado de punta a punta: se emitió un resguardo consolidado con 3 de 4 asignaciones, el PDF trae las dos firmas y no incluye Monto revalúo. Falta la prueba manual de Fernando en navegador y guardar la evidencia para la tesina
Prioridad: ALTA

- RESGUARDO: folio (PK), fecha_emision, resguardante (FK PERSONAL), usuario_emisor (FK USUARIO), ruta_pdf (única), hash_pdf, y opcionalmente fecha_firma.
- RESGUARDO_DETALLE: num (PK), resguardo (FK), movimiento (FK, UNIQUE). Sin FK a ARTICULO: se obtiene por el movimiento.
- Se elimina la relación 1:1 entre MOVIMIENTO y RESGUARDO (hoy en `movimientos.models.Resguardo`).
- Nombre de la Contadora que firma: dato configurable del sistema (settings.py), nombre completo. Decidido el 03/11/2026.
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

PEND-021 — Ajustes a la carga masiva y a la plantilla (04/11/2026)
Prioridad: ALTA (antes de entregar la plantilla a la Contadora)
Estado (06/11/2026): casi todo implementado. Cliente: costo en Donados, casilla de folios nuevos, columna de avisos y pantalla de carga. API (Adad, commit a043816): S/S y similares como vacío, aviso de posible duplicado, hojas Listas y Tipos ocultas. Falta revisar en Excel real la plantilla (instrucciones, ejemplo, columnas obligatorias).

- S/S, S/M, N/A o guion en marca, modelo o serie: tratarlos como vacío (`_texto()` en `api/articulos/carga_masiva.py`) con aviso que no bloquea.
- Comodato o Enser sin folio: la vista previa muestra "se asignarán N folios nuevos" y una casilla obligatoria; el resultado lista los folios asignados. Sin la casilla, el botón Confirmar no se habilita.
- Posible duplicado en filas sin folio ni serie: aviso por fila (no rechazo) cuando coinciden tipo, descripción, marca, modelo, color, ubicación y resguardante con un artículo existente o con otra fila del archivo.
- Plantilla: ocultar las hojas Listas y Tipos; instrucciones en 5 pasos con "pegar solo valores", columnas obligatorias marcadas y una fila de ejemplo; entregarla vacía y generada con los catálogos reales (se genera con `generar_plantilla()`, no se edita el .xlsx).
- Propuesta (no es decisión): "revertir lote" solo para Administrador dentro de las primeras 24 horas, porque hoy un artículo cargado por error no se puede borrar ni dar de baja. Pendiente de decidir.
- Quitar el bloqueo del costo en bienes Donados en el cliente (DEC-021): HECHO.
- Preguntar a la Contadora: si usa Excel o Google Sheets (el desplegable dependiente usa INDIRECT) y si todos los bienes tienen folio o marbete.
- Probar en Excel real que los desplegables dependientes funcionan.

PEND-022 — Resguardos como pestañas dentro de Movimientos
Estado: PROPUESTA implementada (05/11/2026); falta que Fernando la acepte
Prioridad: BAJA

- Los resguardos por emitir y emitidos viven en /movimientos/resguardos/, como pestañas de Movimientos, y no como módulo nuevo del menú. Motivo: Consulta mantiene sus cuatro módulos (DEC-019) y puede ver y descargar los PDF.
- Solo el Administrador emite (DEC-001); el cliente oculta las casillas y el botón a Consulta, y rechaza el envío en el servidor.
- Observación: las altas manuales también generan una asignación pendiente de resguardo (primera entrega al resguardante). Lo decide la API.

PEND-024 — Endpoint de lectura de la bitácora (para Adad)
Estado: SOLICITADO a Adad (08/11/2026)
Prioridad: ALTA

- La API escribe la bitácora pero no la publica: `api/auditoria` no tiene vistas ni rutas. Se pidió `GET /bitacora/`, solo Administrador, solo lectura, paginado (más reciente primero), con filtros q, usuario, modulo, accion, fecha_desde, fecha_hasta, y tabla_afectada con registro_id; cada fila con fecha_hora, usuario, módulo, acción, tabla, registro, motivo y valores anterior y nuevo como JSON. Los nombres de filtros y campos son propuesta del cliente; el contrato final es el de Adad.
- Cliente: la pantalla /auditoria/ sigue como placeholder hasta que exista el endpoint.

PEND-025 — Escáner de QR y búsqueda rápida (RF-19, RF-20, RF-23)
Estado: objetivo y diseño confirmados por Fernando el 08/11/2026; sin construir
Prioridad: ALTA

- Objetivo (confirmado): consulta rápida de un artículo, abriendo su ficha completa desde el celular. No incluye toma de inventario por escaneo.
- El QR debe codificar solo un identificador técnico, sin URL (DEC-005). Hoy el cliente genera el QR con la URL completa del artículo (`equipos/views.py`, `_url_equipo`), lo que contradice DEC-005 y RF-19: hay que cambiarlo. Formato propuesto: texto corto con prefijo, por ejemplo `IC:<num>`; falta confirmarlo.
- Escáner dentro de InventaCore con sesión iniciada: librería de JavaScript (propuesta `html5-qrcode`) guardada en `client/static/vendor`, sin CDN. Fernando aprobó usar una librería para el escáner.
- El navegador solo permite la cámara en `localhost` o con HTTPS: para probar en celular y para la demostración hace falta HTTPS (túnel o certificado). Decisión pendiente.
- Los QR ya impresos con URL (si los hay) dejarían de coincidir con el formato nuevo: confirmar que todavía no se imprimieron etiquetas.
- Buscador único en el Dashboard (RF-23): pendiente.

PEND-023 — Carga masiva: folio obligatorio
Estado: SIN DECIDIR
Prioridad: MEDIA

- Propuesta de Fernando: que la Contadora deba traer folio en toda fila. Hoy los folios faltantes se asignan con confirmación (DEC-010, DEC-017). Forzarlo cambiaría esas decisiones; en el Excel de referencia faltan 420 de 12,464 filas de Enseres. Decisión de negocio, a consultar con la Contadora.

## Para la Contadora o la institución

PEND-007 — Personal que deja la institución
Prioridad: MEDIA

- El cambio de resguardante se hace con REUB y resguardo nuevo (DEC-007).
- Sin respuesta: si aparece un bien No localizado cuyo último resguardante está inactivo, ¿a quién se asigna al recuperarlo?

PEND-017 — Acta de hechos en la reposición
Prioridad: BAJA

- ¿Se quiere guardar en el sistema el número o archivo del acta de hechos, o basta con el motivo del REUB?

## Verificaciones y avances

PEND-011 — Revisión del repositorio (01/11/2026)

- Frontend: login real, rol real y pantallas de catálogos y personal conectadas a la API (01/11/2026). Artículos (la URL pasó de /equipos/ a /articulos/, con redirección), movimientos y carga masiva conectados (04/11/2026). Resguardos (pestañas dentro de Movimientos), Dashboard y Reportes con Excel conectados a la API y unidos a main (05/11/2026). Suite del cliente: 180 pruebas OK. Usuarios y Roles y Perfil conectados el 08/11/2026 (PEND-019). Siguen pendientes la bitácora (PEND-024) y el escáner de QR (PEND-025).
- Nombre de la Contadora en settings.py: confirmado como Lic. Jania Elizabeth Cardenas Vela (04/11/2026); moverlo a variable de entorno es opcional (repositorio privado).
- SECRET_KEY y usuario root sin contraseña en settings.py: aceptable en desarrollo, mover a variables de entorno antes de desplegar.
- client/ apunta a la misma base inventacore_db como root aunque no tiene modelos.

PEND-012 — Avances de Adad

- 05/11/2026: publicados resguardos (pendientes, emitir, listar y PDF), dashboard, reportes de inventario, por resguardante e historial con Excel, y carga masiva con avisos. Quedan sin publicar el escáner de QR y la lectura de la bitácora.

- 03/11/2026: publicados artículos (listar, ficha, alta, corrección con motivo, historial por artículo) y movimientos (listar, ficha, crear REUB, REPA y RETE); módulo de usuarios; sin BAJA ni AUTB. Reglas propias de Adad por confirmar: REPA y RETE van en pareja (no hay RETE sin REPA abierta). Sin publicar: dashboard, reportes, resguardos en PDF, escáner de QR, exportación y carga masiva.

- 29/10/2026: usuarios, login con token de 24 h, permisos, personal, catálogos, modelos de artículo, movimiento y bitácora, folios, pruebas. Aún no hay endpoints de artículos ni de movimientos.

PEND-018 — Cotejo de la transcripción de la reunión con la Contadora

- Fernando la compartirá para verificar que el resumen coincide.

- 01/11/2026: publicados categorias, tipos-articulo, ubicaciones, departamentos y personal (CRUD sin DELETE, baja lógica con `activo`, motivo obligatorio, código automático) y, de solo lectura, origenes, estados-operativos, estados-registro y tipos-movimiento. También existen usuarios, auth/yo y auth/cambiar-password. Sin publicar: artículos, movimientos, resguardos, lectura de bitácora y reportes.

PEND-019 — Pantallas del cliente con API ya publicada
Estado: CERRADO el 08/11/2026 en el cliente (pruebas automáticas y recorrido contra la API real).

- Usuarios y Roles (/cuentas/): listado con búsqueda y filtros por rol y estado, alta de cuenta (empleado activo sin cuenta, usuario, rol y contraseña inicial), cambio de rol con motivo, activar y desactivar con motivo, y restablecer la contraseña de otra persona con motivo (RF-02). Solo Administrador.
- Regla propia del cliente (no viene de un RF): una cuenta no se cambia el rol, no se desactiva ni se restablece la contraseña a sí misma desde esta pantalla, porque la API cierra las sesiones de la cuenta que cambia. Su contraseña la cambia desde Perfil.
- Perfil (/cuentas/perfil/), para cualquier rol: nombre, usuario y rol, y cambio de contraseña. Al cambiarla la API cierra todas las sesiones y se vuelve a iniciar sesión. No hay un RF explícito de perfil: el contenido es el que publica la API.
- Cambios de API necesarios: ninguno.

PEND-020 — Deuda técnica menor del cliente
Prioridad: BAJA

- client/utils.py: TAM_PAGINA=10 está atado al PAGE_SIZE de la API.
- catalogos.css repite estilos de equipos; unificar después.
- personal/views.py (listado_personal) ya no se usa.
- La ventana de confirmación (JavaScript) solo se probó a mano, sin prueba automática de interfaz.
- Para Adad (opcional): departamentos no filtra por `?activo=`. Si se quiere cerrar también en la API la lectura de catálogos y personal para Consulta, hay que separar permisos de lectura, porque los filtros de equipos hoy los necesitan.

## Tesina y documentos

- Actualizar RF/RNF, DER y diccionario solo en lo que cambió (DEC-001 a DEC-018), derivando DER y diccionario del esquema final.
- RF nuevos por redactar: carga masiva y exportación a Excel (ampliación, no alcance de la tesina).
- Renombrar EQUIPO a ARTICULO en DER y diccionario.
- Tesina: decidir si dice MySQL o MariaDB, corregir 5.14 y Kanban.
- INVENTARIO_ESTADO_ACTUAL.md: dos columnas, alcance de la tesina y alcance del software.
- Evidencia de pruebas de resguardos, dashboard y reportes (05/11/2026): capturas, PDF RES-0001 de ejemplo y las pruebas automáticas del cliente (`python manage.py test`). Guardarlas para la tesina.
- Evidencia de pruebas de catálogos y personal: pruebas automáticas del cliente (`python manage.py test catalogos`) y pruebas manuales del 01/11/2026 con capturas y registros de bitácora. Guardar las capturas.
