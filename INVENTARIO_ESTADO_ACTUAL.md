# INVENTARIO DEL ESTADO ACTUAL — InventaCore

Actualizado: 06/11/2026
Separa lo que cubre la tesina (alcance aprobado: inventario de equipo electrónico del Departamento de Informática, CONALEP Tijuana II) de lo que el software hace además (ampliaciones, DEC-009). Las decisiones están en DECISIONES.md y las dudas en PENDIENTES.md.

Estados: **Implementado y probado** (con pruebas automáticas y prueba de punta a punta contra la API real), **Pendiente** (aún no se construye).

## Funciones

| Función | Alcance de la tesina | Alcance del software (ampliación) | Estado |
|---|---|---|---|
| Inicio de sesión, roles Administrador y Consulta (DEC-001, DEC-019) | Sí | — | Implementado y probado |
| Catálogos (categorías, tipos, ubicaciones, departamentos) y personal | Sí, para equipo electrónico | Catálogos abiertos a cualquier categoría de bien (DEC-002, DEC-015) | Implementado y probado |
| Alta, ficha y corrección de artículos con motivo y bitácora (DEC-011, DEC-013) | Sí, para equipo electrónico | Bienes de cualquier categoría | Implementado y probado |
| Identificadores por origen: marbete, folio, QR (DEC-005, DEC-010) | Sí | — | Implementado y probado (QR: sin escáner) |
| Movimientos: reubicación y cambio de resguardante, reparación, retorno (DEC-006) | Sí | — | Implementado y probado |
| Estado de registro y estado operativo, No localizado (DEC-008, DEC-012) | Sí | — | Implementado y probado |
| Resguardos en PDF consolidados, dos firmas, reimpresión del original (DEC-007, DEC-016) | Sí | — | Implementado y probado |
| Dashboard y reportes: inventario, por resguardante, historial (DEC-020) | Sí | — | Implementado y probado |
| Exportación a Excel (DEC-018) | No | Sí | Implementado y probado |
| Carga masiva desde plantilla de Excel (DEC-017) | No | Sí | Implementado y probado en el cliente y la API; falta probar la plantilla en Excel real |
| Bitácora de auditoría (escritura) (DEC-004) | Sí | — | Implementado |
| Lectura de la bitácora en el cliente | Sí | — | Pendiente |
| Usuarios y Roles, Perfil (PEND-019) | Sí | — | Pendiente |
| Escáner de QR dentro del sistema | Sí | — | Pendiente |

## Pruebas

- Cliente: 180 pruebas automáticas, todas OK (05/11/2026), con la API encendida y apagada.
- Prueba de punta a punta (05/11/2026): altas, reubicaciones con cambio de resguardante, resguardo RES-0001 con 3 de 4 asignaciones, PDF con las dos firmas, Excel del inventario, y Consulta sin poder emitir.
- Sin prueba automática de interfaz: la ventana de confirmación y las pantallas se probaron a mano o con navegador automatizado.
- Falta: prueba manual de Fernando en navegador, prueba de carga con volumen real y prueba de la plantilla en Excel.

## Pendientes principales

Ver PENDIENTES.md: Usuarios y Roles y Perfil (PEND-019), folio obligatorio en carga masiva (PEND-023), "revertir lote" (propuesta), preguntas a la Contadora (Excel o Google Sheets) y despliegue (SECRET_KEY y credenciales de base de datos en variables de entorno).
