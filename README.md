# Sistema de Control y Gestión de Inventario para Equipo Electrónico
## CONALEP Tijuana II — Departamento de Informática

**Proyecto de Estadía Profesional — TSU Desarrollo de Software Multiplataforma**  
Universidad Tecnológica de Tijuana

---

## Equipo

- **Fernando Estrada Santos** — Frontend, requerimientos, wireframes/mockups, integración frontend-API
- **Adad Martínez** — Backend (API con Django REST Framework), modelo relacional, script SQL

---

## Arquitectura

Dos proyectos Django separados y desacoplados:

- **`api/`** — Backend DRF puro, puerto **8000**  
  Apps: `usuarios`, `personal`, `catalogos`, `articulos`, `movimientos`, `reportes`, `auditoria`

- **`client/`** — Frontend con templates Django, puerto **8001**  
  Consume la API vía librería `requests` (wrapper propio en `client/client/api.py`).  
  Apps: `client/` (configuración raíz), `usuarios`, `equipos` (módulo Artículos, ruta `/articulos/`), `personal`, `catalogos`, `movimientos`, `reportes`, `auditoria`

**Stack:**
- Python 3.11, Django 4.2, Django REST Framework
- MySQL (base de datos)
- HTML5/CSS3/JavaScript (sin framework SPA)
- Bootstrap 5.3 y CSS propio (el dashboard usa barras con CSS, sin librería de gráficas)
- openpyxl (carga masiva y exportación a Excel), qrcode y Pillow (QR)
- reportlab (generación de PDF de resguardos)

---

## Cómo correr el proyecto localmente

### 1. Clonar el repositorio

\`\`\`bash
git clone https://github.com/TU_USUARIO/InventaCore.git
cd InventaCore
\`\`\`

### 2. Crear entorno virtual e instalar dependencias

\`\`\`bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\\Scripts\\activate
pip install -r requirements.txt
\`\`\`

### 3. Configurar la base de datos

1. Crear la base de datos en MySQL:
   \`\`\`bash
   mysql -u root -p < conalep_db.sql
   \`\`\`

2. Configurar credenciales en `api/api/settings.py` y `client/client/settings.py`:
   \`\`\`python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'conalep_db',
           'USER': 'tu_usuario',
           'PASSWORD': 'tu_contraseña',
           'HOST': 'localhost',
           'PORT': '3306',
           'OPTIONS': {'charset': 'utf8mb4'},
       }
   }
   \`\`\`

3. Aplicar migraciones de Django:
   \`\`\`bash
   cd api
   python manage.py migrate  
   cd ../client
   python manage.py migrate
   \`\`\`

### 4. Levantar ambos servidores

En dos terminales separadas:

**Terminal 1 — Backend:**
\`\`\`bash
cd api
python manage.py runserver
\`\`\`

**Terminal 2 — Frontend:**
\`\`\`bash
cd client
python manage.py runserver 8001
\`\`\`

Acceder a `http://localhost:8001` en el navegador.

---

## Roles del sistema

| Rol | Clave BD | Responsabilidad |
|---|---|---|
| Administrador | `ADMIN` | Control total: altas, correcciones, movimientos, resguardos, carga masiva, catálogos, personal, usuarios y bitácora. Lo usan la Contadora y los jefes |
| Consulta | `CONSULTA` | Solo lectura: Dashboard, Artículos, Movimientos (con resguardos en PDF) y Reportes con Excel. No ve catálogos, personal, bitácora ni usuarios |

---

## Documentación

- **Requerimientos Funcionales (23 RF) y No Funcionales (11 RNF):** `RF y RNF Proyecto Conalep.pdf`
- **Decisiones confirmadas:** `DECISIONES.md`; **dudas y pendientes:** `PENDIENTES.md`
- **Contrato de la API:** `CONTRATO_API_articulos_movimientos.md`
- **Requerimientos actualizados:** `RF_RNF_actualizados.md`
- **Estado del sistema:** `INVENTARIO_ESTADO_ACTUAL.md`
- **Diagrama Entidad-Relación y Modelo Relacional:** `InventaCore_DER_final.md`
- **Script SQL:** `InventaCore_db.sql`
- **Diccionario de Datos:** `Diccionario de datos Conalep.xlsx`

---

## Estado del proyecto

**Actualizado:** 11/11/2026  
**Estado:** API y cliente conectados para catálogos, personal, artículos, movimientos, resguardos en PDF, dashboard, reportes con Excel, carga masiva, usuarios y roles, perfil, escáner de QR y bitácora. Del escáner falta probarlo en un celular real y definir HTTPS. Detalle en `INVENTARIO_ESTADO_ACTUAL.md` y `PENDIENTES.md`.

---

## Licencia

Proyecto académico — Universidad Tecnológica de Tijuana  
No destinado a distribución comercial
