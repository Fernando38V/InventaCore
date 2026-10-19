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
  Apps: `usuarios`, `personal`, `catalogos`, `equipos`, `movimientos`, `reportes`, `auditoria`

- **`client/`** — Frontend con templates Django, puerto **8001**  
  Consume la API vía librería `requests` (wrapper propio en `usuarios/wrappers.py`).  
  Apps: `client/` (configuración raíz), `usuarios`, `equipos`, `personal`, `catalogos`, `movimientos`, `reportes`, `auditoria`

**Stack:**
- Python 3.11, Django 4.2, Django REST Framework
- MySQL (base de datos)
- HTML5/CSS3/JavaScript (sin framework SPA)
- Chart.js (para gráficas de reportes)
- reportlab (generación de PDF de resguardos)

---

## Cómo correr el proyecto localmente

### 1. Clonar el repositorio

\`\`\`bash
git clone https://github.com/TU_USUARIO/inventario-conalep.git
cd inventario-conalep
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
| Administrador | `ADMIN` | Control total: altas, bajas, movimientos, catálogos, usuarios, bitácora de auditoría |
| Contadora | `CONT` | Rol de consulta: consulta el inventario y edita puntualmente algún dato. No da de alta equipo ni ejecuta bajas |

---

## Documentación

- **Requerimientos Funcionales (23 RF) y No Funcionales (11 RNF):** `RF y RNF Proyecto Conalep (2).pdf`
- **Diagrama Entidad-Relación y Modelo Relacional:** `CONALEP_DER_final_16-10-2026.md`
- **Diccionario de Datos:** `CONALEP_Diccionario_de_Datos_v2.xlsx`
- **Script SQL inicial:** `InventaCore_db.sql`

---

## Estado del proyecto

**Versión:** Provisional — 16/10/2026  
**Pendiente:** Modelo de datos terminado, estructura de repositorio y aplicaciones Django creada. Backend y frontend en desarrollo.

---

## Licencia

Proyecto académico — Universidad Tecnológica de Tijuana  
No destinado a distribución comercial
