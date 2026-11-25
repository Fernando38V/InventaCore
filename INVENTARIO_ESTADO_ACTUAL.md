# INVENTARIO DEL ESTADO ACTUAL — InventaCore

Actualizado: 24/11/2026
Separa lo que cubre la tesina (alcance aprobado: inventario de equipo electrónico del Departamento de Informática, CONALEP Tijuana II) de lo que el software hace además (ampliaciones, DEC-009). Las decisiones están en DECISIONES.md y las dudas en PENDIENTES.md.

Estados: **Implementado y probado** (con pruebas automáticas y prueba de punta a punta contra la API real), **Pendiente** (aún no se construye).

## Funciones

| Función | Alcance de la tesina | Alcance del software (ampliación) | Estado |
|---|---|---|---|
| Inicio de sesión, roles Administrador y Consulta (DEC-001, DEC-019) | Sí | — | Implementado y probado |
| Catálogos (categorías, tipos, ubicaciones, departamentos) y personal | Sí, para equipo electrónico | Catálogos abiertos a cualquier categoría de bien (DEC-002, DEC-015) | Implementado y probado |
| Alta, ficha y corrección de artículos con motivo y bitácora (DEC-011, DEC-013) | Sí, para equipo electrónico | Bienes de cualquier categoría | Implementado y probado |
| Identificadores por origen: marbete, folio, QR (DEC-005, DEC-010) | Sí | — | Implementado y probado |
| Movimientos: reubicación y cambio de resguardante, reparación, retorno (DEC-006) | Sí | — | Implementado y probado |
| Estado de registro y estado operativo, No localizado (DEC-008, DEC-012) | Sí | — | Implementado y probado |
| Resguardos en PDF consolidados, dos firmas, reimpresión del original (DEC-007, DEC-016, DEC-024) | Sí | — | Implementado y probado; formato de la Contadora desde el 24/11/2026 |
| Dashboard y reportes: inventario, por resguardante, historial (DEC-020) | Sí | — | Implementado y probado |
| Exportación a Excel (DEC-018) | No | Sí | Implementado y probado |
| Carga masiva desde plantilla de Excel (DEC-017) | No | Sí | Implementado y probado en el cliente y la API; plantilla probada en Excel de Windows el 21/11/2026 (desplegables, color con aviso, hojas de consulta protegidas); validación de fecha de adquisición probada por Fernando (PEND-021) |
| Marbete imprimible con QR: hoja carta de 10 etiquetas, desde la ficha y por lote desde el listado (DEC-023, PEND-029) | No | Sí | Implementado y probado (24/11/2026): revisado en pantalla y PDF, impreso en la hoja de etiquetas de la institución y pegado en bienes; QR leído con celular. Formatos B y C diferidos |
| Bitácora de auditoría (escritura) (DEC-004) | Sí | — | Implementado |
| Lectura de la bitácora en el cliente (RF-21) | Sí | — | Implementado y probado (11/11/2026): API de Adad y pantalla `/auditoria/` con filtros, cambios e historial por registro (PEND-024) |
| Usuarios y Roles y Perfil (RF-02, PEND-019) | Sí | — | Implementado y probado (08/11/2026) |
| QR: código sin URL, escáner dentro del sistema y búsqueda rápida (DEC-005, RF-19, RF-20, RF-23) | Sí | — | Implementado y probado en el cliente (08/11/2026): QR `IC:<num>` sin URL, escáner con cámara, foto y búsqueda, y buscador en el Dashboard. Lectura por foto confirmada en un celular real (19/11/2026); falta la cámara en vivo, que exige HTTPS (PEND-025, PEND-028) |

## Pruebas

- Cliente: 321 pruebas automáticas, todas OK (24/11/2026); 291 al 21/11/2026; 269 al 11/11/2026; 244 al 08/11/2026; 180 al 05/11/2026, con la API encendida y apagada.
- Usuarios y Roles y Perfil (08/11/2026): 44 pruebas automáticas y recorrido contra la API real (alta, contraseña débil rechazada, cambio de contraseña propia, cambio de rol, baja y alta, restablecer contraseña, Consulta sin acceso a Usuarios y Roles).
- Bitácora (11/11/2026): 25 pruebas automáticas nuevas y recorrido en Chromium contra la API real (filtros, detalle de cambios, historial desde la ficha, enlaces, Consulta bloqueada, celular).
- Escáner de QR y ojito de contraseña (08/11/2026): 20 pruebas automáticas nuevas y recorrido en Chromium contra la API real (13 comprobaciones OK: foto de QR válido, QR con URL, texto ajeno, artículo inexistente, cámara simulada, sin cámara, tamaño de celular, ojito). No se probó con un celular real.
- Prueba de punta a punta (05/11/2026): altas, reubicaciones con cambio de resguardante, resguardo RES-0001 con 3 de 4 asignaciones, PDF con las dos firmas, Excel del inventario, y Consulta sin poder emitir.
- Sin prueba automática de interfaz: la ventana de confirmación y las pantallas se probaron a mano o con navegador automatizado.
- Catálogos iniciales, colores sugeridos, orden de ubicaciones y Donado violeta (21/11/2026, DEC-022): 14 pruebas automáticas nuevas (10 del cliente y 4 de la API) y prueba manual de Fernando en el sistema y en Excel de Windows. API: 333 pruebas en el entorno de desarrollo del asistente (SQLite); la única falla, `test_busqueda_por_palabras`, depende de MariaDB y se debe correr en el equipo de Fernando.
- Marbete imprimible (24/11/2026, DEC-023): 30 pruebas automáticas nuevas (medidas y reparto en hojas, contenido, tipo de artículo, serie opcional, logos, lote, tope de 50, casillas del listado) y recorrido en Chrome (selección que se conserva, PDF de 2 hojas carta). Fernando revisó la vista y el PDF y leyó el QR con un celular real. Prueba en papel (24/11/2026): 10 marbetes impresos en la hoja de etiquetas de la institución, dos pegados en bienes; la etiqueta física mide 10 × 5 cm, sin cambios de medidas.
- Resguardo con el formato de la Contadora y lista de por emitir corregida (24/11/2026, DEC-024): 3 pruebas automáticas nuevas en la API (formato del PDF, pendientes que ya pasaron a otra persona, artículo que regresa a la misma persona). API: 336 pruebas en el entorno del asistente (SQLite); la única falla sigue siendo `test_busqueda_por_palabras` (MariaDB).
- Falta: prueba de carga con volumen real, prueba de la cámara en vivo con HTTPS y las pruebas de Informática en el servidor.

## Pendientes principales

Ver PENDIENTES.md: despliegue en servidor local y HTTPS (PEND-028, PEND-025), formatos B y C de la etiqueta (PEND-029), folio obligatorio en carga masiva (PEND-023), "revertir lote" (propuesta), preguntas a la Contadora (Excel o Google Sheets) y despliegue (SECRET_KEY y credenciales de base de datos en variables de entorno).
