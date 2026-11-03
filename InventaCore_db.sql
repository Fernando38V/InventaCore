/* ==========================================================================
   SISTEMA DE CONTROL Y GESTIÓN DE INVENTARIO PARA EQUIPO ELECTRÓNICO
   CONALEP Tijuana II — Departamento de Informática
   ==========================================================================
   Script v3 (reescrito) — compatible con MySQL 8.0 y MariaDB 10.x (XAMPP).
   Fuentes: Diccionario de datos v2 + RF-01..RF-23 + RNF-01..RNF-11.
   Probado: se ejecuta de principio a fin en MariaDB 10.11 sin errores.

   COBERTURA DE REQUERIMIENTOS
     RF-01..03  usuario, rol, personal
     RF-04      categoria
     RF-05..10  articulo, origen, estado_operativo, estado_registro
     RF-11..13  ubicacion
     RF-14..15  personal, departamento
     RF-16..17  movimiento, tipo_movimiento
     RF-18      resguardo
     RF-19,20,23  sobre articulo (el QR se genera al vuelo, no tiene tabla)
     RF-21      bitacora
     RF-22      consultas sobre articulo y movimiento (no necesita tabla)

   CRITERIOS GENERALES
     - Nombres de tablas y columnas en minúsculas y snake_case. Motivo: XAMPP
       en Windows no distingue mayúsculas en tablas, pero un servidor Linux
       sí. Así el script funciona igual en ambos.
     - Ninguna tabla se elimina físicamente (RNF-06): las llaves foráneas usan
       el comportamiento por defecto (RESTRICT) y no hay ON DELETE CASCADE.
     - Sin triggers ni procedimientos por ahora (decisión de diseño abierta: la
       inalterabilidad de bitácora y movimiento depende solo de Django). Las
       reglas de negocio (estado de registro vs costo, folios, fechas,
       bitácora) viven en Django, para dar mensajes claros (RNF-09). SQL
       garantiza PK, FK, UNIQUE, NOT NULL y CHECK sobre reglas ya confirmadas
       (identificador por origen, costo >= 0, estado de registro y que todo
       movimiento cambie algo).
     - Los CHECK se aplican en MySQL >= 8.0.16 y MariaDB >= 10.2. En versiones
       anteriores se aceptan pero se ignoran, sin romper nada.
     - Fechas con hora son DATETIME. Solo fecha_adquisicion es DATE.

   NOMBRES (confirmado 27/10/2026): la tabla se llama articulo (no equipo) y
   su llave a la persona a cargo se llama articulo.resguardante ->
   personal(num), igual que el frontend. El DER la llama "personal"; hay que
   actualizarlo. En movimiento: resguardante_anterior y resguardante_nuevo.

   FUENTE DE VERDAD: DECISIONES.md y PENDIENTES.md (27/10/2026). Este script
   aplica así las decisiones aprobadas por Fernando:
     DEC-001  Roles ADMIN (todo, incluida la bitácora y administrar usuarios)
              y CONSULTA (consulta; no modifica ni ve la bitácora, confirmado
              27/10/2026). La
              contadora y los jefes son ADMIN. El permiso se valida en la API.
     DEC-002  (categorías vacías al arrancar, confirmado 27/10/2026)
              categoria 1:M tipo_articulo 1:M articulo. articulo tiene FK SOLO
              a tipo_articulo; la categoría sale de esa relación. Sin número de
              cuenta contable.
     DEC-003  ubicacion y resguardante NOT NULL desde el alta.
     DEC-004  Sin triggers: la bitácora la escribe Django en la misma
              transacción que el movimiento y la actualización del artículo.
     DEC-005  QR = identificador técnico basado en la PK; sin tabla ni URL.
     DEC-006  Tipos de movimiento: ALTA, REUB, REPA, RETE y BAJA. Ningún
              movimiento sin cambio efectivo.
     DEC-008  Estado de registro: Donado tiene prioridad; si no, con fecha y
              costo es Registrado y si falta alguno, Pendiente.
     DEC-010  Activo -> marbete sin folio; Comodato y Enser -> folio interno
              generado 02143MMYY-NNN (consecutivo mensual desde 001, en
              contador_folio). Serie opcional.
     DEC-011  Obligatorios: tipo_articulo, origen, identificador, ubicación,
              resguardante y estado operativo. Opcionales (NULL): marca,
              modelo, serie, fecha y costo. Color y descripción también son
              NOT NULL (actualizado por Fernando el 27/10/2026: un registro
              no puede quedar tan vacío y son datos visuales del bien).
     DEC-012  UBI-NOLOC y el estado NOLOC van siempre juntos (CHECK).
     DEC-013  Ubicación y resguardante solo cambian por movimiento.
     DEC-014  departamento y ubicacion son entidades distintas, sin relación.
     DEC-015  Los catálogos se amplían desde el sistema y el SISTEMA genera
              los códigos (la API; no hay columna extra).
     DEC-016  movimiento.requiere_resguardo (lo fija el sistema); no existe
              tipo_movimiento.genera_resguardo.

   DECISIONES ANTERIORES QUE SIGUEN VIGENTES (conversaciones con Adad)
     - numero_empleado es complemento de búsqueda; la PK es el consecutivo num.
     - Login solo con usuario y contraseña; el Administrador restablece la
       contraseña de otros y cada quien cambia la suya.
     - fecha_movimiento admite fechas pasadas, no futuras (lo valida la API);
       fecha_registro guarda la hora real de captura.
     - Un empleado dado de baja conserva sus artículos hasta un movimiento; no
       se puede elegir en asignaciones nuevas.
     - Folios MOV-0001 y RES-0001 (contador_folio). El sistema arranca VACÍO;
       no se importa el Excel. Los títulos firmados no cambian.
     - Sesión: tokens de DRF (tabla authtoken_token, la crea Django).
     - Bitácora: alta, modificación y movimiento con usuario, valor anterior,
       valor nuevo y motivo (obligatorio al corregir). Sin inicios de sesión.

   PENDIENTE (no se implementa como definitivo; ver PENDIENTES.md)
     PEND-001  Diseño relacional de resguardos. La tabla resguardo de abajo
               (1:1 con movimiento) es PROVISIONAL: DEC-007 pide resguardos
               bajo demanda para varios artículos de una persona.
     PEND-002  Folios: ¿Comodato y Enser comparten consecutivo? ¿qué pasa al
               llegar a 999? Los folios del Excel tienen 10 dígitos antes del
               guion y el nuevo 9. ¿Activo sin marbete conocido?
     PEND-003  Significado de Obsoleto y AUTB; ¿estado "En reparación"?; ¿baja
               de un bien no localizado? Hoy el CHECK de no localizado impide
               dar de baja (AUTB) un artículo que sigue en UBI-NOLOC.
     PEND-004  ¿El costo de un Donado se bloquea o se captura? Por eso el CHECK
               de Donado NO exige ni prohíbe el costo.
     PEND-005  PK de movimiento (num + folio único) y numero_empleado NULL.
     PEND-006/007  Resguardos y personal que deja la institución.
     PEND-010  valor_anterior y valor_nuevo como texto largo (Django ya los
               crea LONGTEXT).

 v2 (para actualizar el DD)
     Nombres:  Movimiento.Personal_Asigna -> resguardante_nuevo
               Movimiento.Personal_Entrega -> resguardante_anterior
               Movimiento.Ubicacion_Llegada -> ubicacion_destino
               Movimiento.Fecha -> fecha_movimiento
               Equipo.Personal -> articulo.resguardante (la tabla Equipo pasa a articulo)
               Ubicacion.personal -> responsable
               Personal.Num/NombrePila/PrimerApell/SegApell -> num/nombre_pila/
               primer_apellido/segundo_apellido
     Tipos:    Resguardo.movimiento es VARCHAR(20) (el DD decía entero, pero la
               PK de movimiento es el folio de texto).
               Bitacora.valor_* son TEXT (el DD decía 255 caracteres).
     Campos:   personal.numero_empleado (nuevo, decisión 1)
               movimiento.fecha_registro (nuevo: hora real de captura, decisión 7)
               articulo.num_serie pasa a NULL y UNIQUE (decisión 2)
               articulo.marca y articulo.modelo pasan a NULL (decisión 27)
               categoria.nombre pasa a VARCHAR(100) (decisión 26)
               tabla tipo_articulo y articulo.tipo_articulo (decisión 31)
               articulo.fecha_adquisicion pasa a NULL (decisión 3)
     Quitado:  tipo_movimiento.genera_resguardo. Con el tipo fusionado REUB ya
               no es un valor fijo del catálogo: la regla se calcula al crear
               el movimiento (se genera resguardo si es ALTA o si cambió el
               resguardante). Que exista la fila en resguardo ES el dato.
     Datos:    ubicación UBI-NOLOC (decisión 10); estados operativos del
               frontend (decisión 4); tipos de movimiento ALTA, REUB,
               REPA y RETE (decisiones 5 y 14); Rol.nombre "Contadora" (el DD decía "contador";
               RF dice Contadora)
     Cambios del 27/10/2026 (sincronización con DECISIONES.md):
               articulo ya no tiene categoria: solo tipo_articulo NOT NULL (DEC-002)
               articulo.color y articulo.descripcion siguen NOT NULL (DEC-011,
               versión del 27/10/2026); marca, modelo y serie pasan a NULL
               chk_articulo_estado_registro: Donado ya no exige costo vacío
               tipo_movimiento: se agrega BAJA (DEC-006); el CHECK de movimiento
               la trata como REPA y RETE
               movimiento.requiere_resguardo (DEC-016) y su CHECK
               rol: OBS (Observador) se renombra CONSULTA (DEC-001)
     Longitudes ajustadas para que quepan los datos: rol.descripcion 150,
               articulo.modelo 60, categoria.nombre 100.
   ========================================================================== */

SET NAMES utf8mb4;

-- ⚠ Descomentar SOLO para recrear la base en desarrollo: borra todos los datos.
-- DROP DATABASE IF EXISTS inventacore_db;

CREATE DATABASE IF NOT EXISTS inventacore_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE inventacore_db;


/* ==========================================================================
   BLOQUE 1 — CATÁLOGOS SIN DEPENDENCIAS
   ========================================================================== */

CREATE TABLE rol (
    clave        VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(50)  NOT NULL UNIQUE,
    descripcion  VARCHAR(150) NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE departamento (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL UNIQUE,
    descripcion  VARCHAR(150) NOT NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE categoria (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL UNIQUE,   -- DEC-002: sin número de cuenta contable
    descripcion  VARCHAR(150) NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

/* Decisión 37: último número usado de cada serie de folios. Claves: FI-MMAA
   (folio interno de ese mes, p. ej. FI-1026), MOV y RES. Django bloquea la
   fila al avanzarla, así dos altas simultáneas no reciben el mismo folio. */
CREATE TABLE contador_folio (
    clave   VARCHAR(30)  NOT NULL PRIMARY KEY,
    ultimo  INT UNSIGNED NOT NULL DEFAULT 0
) ENGINE=InnoDB;

/* DEC-002: categoria 1:M tipo_articulo 1:M articulo. El tipo clasifica el
   artículo dentro de su categoría (cámara dentro de audiovisuales, silla
   dentro de mobiliario...). Extensible desde el sistema; arranca vacío. El
   nombre puede repetirse entre categorías, no dentro de una. */
CREATE TABLE tipo_articulo (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL,
    descripcion  VARCHAR(150) NULL,
    categoria    VARCHAR(10)  NOT NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE,
    UNIQUE KEY uq_tipo_articulo_categoria_nombre (categoria, nombre),
    CONSTRAINT fk_tipo_articulo_categoria
        FOREIGN KEY (categoria) REFERENCES categoria (codigo)
) ENGINE=InnoDB;

-- Catálogo fijo de 3 valores; por eso no lleva "activo" (igual que el DD).
CREATE TABLE origen (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(50)  NOT NULL UNIQUE,
    descripcion  VARCHAR(150) NULL
) ENGINE=InnoDB;

CREATE TABLE estado_operativo (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(50)  NOT NULL UNIQUE,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE estado_registro (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(50)  NOT NULL UNIQUE,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE tipo_movimiento (
    codigo            VARCHAR(10) NOT NULL PRIMARY KEY,
    nombre            VARCHAR(50) NOT NULL UNIQUE,
    activo            BOOLEAN     NOT NULL DEFAULT TRUE
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 2 — PERSONAL (depende de departamento)
   ========================================================================== */

CREATE TABLE personal (
    num               INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    /* Decisión 1: "num" es el consecutivo interno que usan las FK;
       "numero_empleado" es el número del plantel, complemento para búsquedas
       y filtros (RF-15). Único; se asume que todo empleado tiene uno. */
    numero_empleado   VARCHAR(20)  NOT NULL UNIQUE,
    nombre_pila       VARCHAR(50)  NOT NULL,
    primer_apellido   VARCHAR(50)  NOT NULL,
    segundo_apellido  VARCHAR(50)  NULL,
    puesto            VARCHAR(50)  NOT NULL,
    activo            BOOLEAN      NOT NULL DEFAULT TRUE,
    departamento      VARCHAR(10)  NOT NULL,
    CONSTRAINT fk_personal_departamento
        FOREIGN KEY (departamento) REFERENCES departamento (codigo)
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 3 — UBICACION (depende de personal, por su responsable)
   ========================================================================== */

CREATE TABLE ubicacion (
    codigo       VARCHAR(10)  NOT NULL PRIMARY KEY,
    nombre       VARCHAR(100) NOT NULL UNIQUE,
    descripcion  VARCHAR(150) NULL,
    responsable  INT          NULL,
    activo       BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_ubicacion_responsable
        FOREIGN KEY (responsable) REFERENCES personal (num)
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 4 — USUARIO (depende de personal y rol)
   ========================================================================== */

/* Decisión 6: login solo con usuario y contraseña (RF-01); no hay correo.
   Django exige "last_login" en su modelo base; el modelo lo desactivará
   (last_login = None) para respetar el DD. */
CREATE TABLE usuario (
    num         INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)   NOT NULL UNIQUE,
    contrasena  VARCHAR(255)  NOT NULL,   -- hash, nunca texto plano (RNF-01)
    activo      BOOLEAN       NOT NULL DEFAULT TRUE,   -- baja lógica (RF-03)
    personal    INT           NOT NULL UNIQUE,   -- cuenta ligada a un empleado (RF-02)
    rol         VARCHAR(10)   NOT NULL,
    CONSTRAINT fk_usuario_personal
        FOREIGN KEY (personal) REFERENCES personal (num),
    CONSTRAINT fk_usuario_rol
        FOREIGN KEY (rol) REFERENCES rol (clave)
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 5 — ARTICULO
   ========================================================================== */

CREATE TABLE articulo (
    num                INT           NOT NULL AUTO_INCREMENT PRIMARY KEY,
    marbete_oficial    VARCHAR(25)   NULL UNIQUE,   -- solo Activos (DEC-010)
    folio_interno      VARCHAR(25)   NULL UNIQUE,   -- solo Comodato y Enser, generado
    -- DEC-011: marca, modelo, serie, fecha y costo son opcionales; color y
    -- descripción son obligatorios. Django envía NULL, nunca cadena vacía. La
    -- interfaz muestra "Sin especificar"; no se guardan textos como S/M o S/S.
    marca              VARCHAR(50)   NULL,
    modelo             VARCHAR(60)   NULL,
    num_serie          VARCHAR(50)   NULL UNIQUE,   -- único si existe (RF-09 y RF-23)
    color              VARCHAR(25)   NOT NULL,
    descripcion        VARCHAR(150)  NOT NULL,
    fecha_adquisicion  DATE          NULL,
    costo_adquisicion  DECIMAL(12,2) NULL,
    fecha_alta         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    /* DEC-002: SOLO tipo_articulo; la categoría se obtiene por
       tipo_articulo.categoria. */
    tipo_articulo      VARCHAR(10)   NOT NULL,
    ubicacion          VARCHAR(10)   NOT NULL,   -- ubicación ACTUAL (DEC-003)
    resguardante       INT           NOT NULL,   -- resguardante ACTUAL (DEC-003)
    origen             VARCHAR(10)   NOT NULL,
    estado_operativo   VARCHAR(10)   NOT NULL,
    estado_registro    VARCHAR(10)   NOT NULL,   -- lo calcula el sistema
    CONSTRAINT fk_articulo_tipo_articulo
        FOREIGN KEY (tipo_articulo) REFERENCES tipo_articulo (codigo),
    CONSTRAINT fk_articulo_ubicacion
        FOREIGN KEY (ubicacion) REFERENCES ubicacion (codigo),
    CONSTRAINT fk_articulo_resguardante
        FOREIGN KEY (resguardante) REFERENCES personal (num),
    CONSTRAINT fk_articulo_origen
        FOREIGN KEY (origen) REFERENCES origen (codigo),
    CONSTRAINT fk_articulo_estado_operativo
        FOREIGN KEY (estado_operativo) REFERENCES estado_operativo (codigo),
    CONSTRAINT fk_articulo_estado_registro
        FOREIGN KEY (estado_registro) REFERENCES estado_registro (codigo),
    /* DEC-010: Activo -> marbete y sin folio; Comodato/Enser -> folio y sin
       marbete. Usa los códigos fijos ACT, COM y ENS del catálogo origen. */
    CONSTRAINT chk_articulo_identificador CHECK (
        (origen = 'ACT'
            AND marbete_oficial IS NOT NULL AND marbete_oficial <> ''
            AND folio_interno IS NULL)
        OR
        (origen IN ('COM', 'ENS')
            AND folio_interno IS NOT NULL AND folio_interno <> ''
            AND marbete_oficial IS NULL)
    ),
    CONSTRAINT chk_articulo_serie CHECK (
        num_serie IS NULL OR num_serie <> ''
    ),
    -- DEC-011: obligatorios también en el sentido de no estar vacíos.
    CONSTRAINT chk_articulo_color_descripcion CHECK (
        color <> '' AND descripcion <> ''
    ),
    CONSTRAINT chk_articulo_costo CHECK (
        costo_adquisicion IS NULL OR costo_adquisicion >= 0
    ),
    /* DEC-008: Donado tiene prioridad (PEND-004: el costo de un Donado ni se
       exige ni se prohíbe). Si no es Donado: Registrado con costo y fecha;
       Pendiente si falta alguno de los dos. */
    CONSTRAINT chk_articulo_estado_registro CHECK (
        estado_registro = 'DON'
        OR (estado_registro = 'REG'
            AND costo_adquisicion IS NOT NULL AND fecha_adquisicion IS NOT NULL)
        OR (estado_registro = 'PEND'
            AND (costo_adquisicion IS NULL OR fecha_adquisicion IS NULL))
    ),
    /* DEC-012: UBI-NOLOC y el estado NOLOC van siempre juntos. Se permite un
       alta histórica de un bien no localizado. */
    CONSTRAINT chk_articulo_no_localizado CHECK (
        (ubicacion = 'UBI-NOLOC' AND estado_operativo = 'NOLOC')
        OR (ubicacion <> 'UBI-NOLOC' AND estado_operativo <> 'NOLOC')
    )
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 6 — MOVIMIENTO (historial; nunca se edita ni se elimina, RNF-06)
   ========================================================================== */

CREATE TABLE movimiento (
    folio                  VARCHAR(20)  NOT NULL PRIMARY KEY,   -- MOV-0001 (lo genera Django). PEND-005: ¿num + folio único?
    /* Fecha en que ocurrió: por defecto la hora actual; admite fechas pasadas
       y NO futuras (lo valida la API). PEND: ¿puede ser anterior al último
       movimiento del artículo? Propuesta: no. */
    fecha_movimiento       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Hora real de captura: nadie la edita (RNF-06 y RNF-07).
    fecha_registro         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    motivo                 VARCHAR(255) NOT NULL,   -- obligatorio (RF-16)
    articulo               INT          NOT NULL,
    tipo_movimiento        VARCHAR(10)  NOT NULL,
    ubicacion_origen       VARCHAR(10)  NULL,       -- NULL solo en el Alta
    ubicacion_destino      VARCHAR(10)  NOT NULL,
    resguardante_anterior  INT          NULL,       -- NULL solo en el Alta
    resguardante_nuevo     INT          NOT NULL,
    /* DEC-016: lo fija el sistema al crear el movimiento. ALTA: lo decide la
       API (no se genera en el alta histórica de un bien no localizado).
       REUB: verdadero si cambió el resguardante. REPA, RETE y BAJA: falso. */
    requiere_resguardo     BOOLEAN      NOT NULL,
    usuario                INT          NOT NULL,   -- sellado de auditoría (RF-16)
    KEY ix_movimiento_articulo_fecha (articulo, fecha_movimiento),   -- RF-17
    CONSTRAINT fk_movimiento_articulo
        FOREIGN KEY (articulo) REFERENCES articulo (num),
    CONSTRAINT fk_movimiento_tipo
        FOREIGN KEY (tipo_movimiento) REFERENCES tipo_movimiento (codigo),
    CONSTRAINT fk_movimiento_ubicacion_origen
        FOREIGN KEY (ubicacion_origen) REFERENCES ubicacion (codigo),
    CONSTRAINT fk_movimiento_ubicacion_destino
        FOREIGN KEY (ubicacion_destino) REFERENCES ubicacion (codigo),
    CONSTRAINT fk_movimiento_resguardante_anterior
        FOREIGN KEY (resguardante_anterior) REFERENCES personal (num),
    CONSTRAINT fk_movimiento_resguardante_nuevo
        FOREIGN KEY (resguardante_nuevo) REFERENCES personal (num),
    CONSTRAINT fk_movimiento_usuario
        FOREIGN KEY (usuario) REFERENCES usuario (num),
    /* DEC-006: ALTA no tiene origen ni anterior. REUB cambia ubicación,
       resguardante o ambos: no hay movimientos sin cambio efectivo. REPA,
       RETE y BAJA conservan el resguardante (la ubicación puede o no cambiar);
       lo que no cambia se repite igual, nunca NULL. Usa los códigos fijos. */
    CONSTRAINT chk_movimiento_cambia_algo CHECK (
        (tipo_movimiento = 'ALTA'
            AND ubicacion_origen IS NULL
            AND resguardante_anterior IS NULL)
        OR
        (tipo_movimiento = 'REUB'
            AND ubicacion_origen IS NOT NULL
            AND resguardante_anterior IS NOT NULL
            AND (ubicacion_origen <> ubicacion_destino
                 OR resguardante_anterior <> resguardante_nuevo))
        OR
        (tipo_movimiento IN ('REPA', 'RETE', 'BAJA')
            AND ubicacion_origen IS NOT NULL
            AND resguardante_anterior IS NOT NULL
            AND resguardante_anterior = resguardante_nuevo)
    ),
    -- DEC-016. SUPUESTO: la regla de RF-18 (resguardo si cambia la persona).
    CONSTRAINT chk_movimiento_requiere_resguardo CHECK (
        tipo_movimiento = 'ALTA'
        OR (tipo_movimiento = 'REUB'
            AND requiere_resguardo = (resguardante_anterior <> resguardante_nuevo))
        OR (tipo_movimiento IN ('REPA', 'RETE', 'BAJA')
            AND requiere_resguardo = FALSE)
    )
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 7 — RESGUARDO (PROVISIONAL: ver PEND-001)

   DEC-007 pide resguardos bajo demanda para uno o varios artículos de una
   persona, con el PDF conservado. Esta tabla 1:1 con movimiento se reemplaza
   por RESGUARDO + RESGUARDO_DETALLE (propuesta PEND-001) cuando Adad la
   valide. No se implementa más sobre ella hasta entonces.
   ========================================================================== */

CREATE TABLE resguardo (
    folio             VARCHAR(20)  NOT NULL PRIMARY KEY,   -- RES-0001 (lo genera Django, decisión 16)
    fecha_generacion  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ruta_pdf          VARCHAR(255) NULL,       -- NULL permitido, como en el DD
    movimiento        VARCHAR(20)  NOT NULL UNIQUE,
    CONSTRAINT fk_resguardo_movimiento
        FOREIGN KEY (movimiento) REFERENCES movimiento (folio)
) ENGINE=InnoDB;


/* ==========================================================================
   BLOQUE 8 — BITACORA (auditoría inalterable, RF-21, RNF-06, RNF-07)
   ========================================================================== */

/* valor_anterior y valor_nuevo guardan un JSON con todos los campos que
   cambiaron en la acción, por ejemplo {"estado_operativo": "UTIL"} -> así
   no hace falta una columna "campo" y se registra una sola fila por acción.
   tabla_afectada y registro_id NO son FK: la bitácora es polimórfica.
   motivo es obligatorio en la API para las correcciones (RNF-06). */
CREATE TABLE bitacora (
    num             INT          NOT NULL AUTO_INCREMENT PRIMARY KEY,
    fecha_hora      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modulo          VARCHAR(50)  NOT NULL,
    accion          VARCHAR(20)  NOT NULL,   -- INSERT, UPDATE o DELETE (lógico)
    tabla_afectada  VARCHAR(50)  NOT NULL,
    registro_id     VARCHAR(50)  NOT NULL,
    valor_anterior  TEXT         NULL,
    valor_nuevo     TEXT         NULL,
    motivo          VARCHAR(255) NULL,
    usuario         INT          NOT NULL,
    KEY ix_bitacora_registro (tabla_afectada, registro_id),
    KEY ix_bitacora_fecha (fecha_hora),
    CONSTRAINT fk_bitacora_usuario
        FOREIGN KEY (usuario) REFERENCES usuario (num)
) ENGINE=InnoDB;


/* ==========================================================================
   DATOS PRECARGADOS (catálogos)
   ========================================================================== */

/* DEC-001: dos roles. La contadora y los jefes usan ADMIN. */
INSERT INTO rol (clave, nombre, descripcion) VALUES
('ADMIN',    'Administrador', 'Todo, incluida la bitácora y administrar usuarios'),
('CONSULTA', 'Consulta',      'Dashboard, consultas, historial, resguardos y reportes PDF. No modifica nada ni ve la bitácora');

/* Decisión 9: solo Informática por ahora. Habrá un botón para agregar más
   departamentos (falta el RF correspondiente). DUDA 13: los códigos como
   DEP-INF, ¿los escribe el usuario o los genera el sistema? */
INSERT INTO departamento (codigo, nombre, descripcion) VALUES
('DEP-INF', 'Informática', 'Departamento al que pertenecen las ubicaciones del alcance');

/* categoria y tipo_articulo arrancan VACÍAS (confirmado 27/10/2026): el
   Administrador las agrega desde el sistema y el sistema genera los códigos
   (DEC-015). Hasta que exista al menos una categoría con un tipo no se puede
   dar de alta ningún artículo. */

-- Códigos fijos: el CHECK de articulo depende de ACT, COM y ENS.
INSERT INTO origen (codigo, nombre, descripcion) VALUES
('ACT', 'Activo',    'Bien patrimonial del gobierno del estado, identificado por marbete SAACG.NET'),
('COM', 'Comodato',  'Bien recibido en comodato, identificado por folio interno del plantel'),
('ENS', 'Enser',     'Bien menor del plantel, identificado por folio interno');

/* Estados provisionales (DEC-012; reglas de transición en PEND-003 y
   PEND-009). NOLOC y UBI-NOLOC están protegidos: no se desactivan ni se
   renombran. */
INSERT INTO estado_operativo (codigo, nombre) VALUES
('UTIL',  'Útil'),
('OBS',   'Obsoleto'),
('AUTB',  'Autorizado para baja'),
('NOLOC', 'No localizado');

INSERT INTO estado_registro (codigo, nombre) VALUES
('PEND', 'Pendiente'),
('REG',  'Registrado'),
('DON',  'Donado');

/* DEC-006: cinco tipos internos. ALTA se registra sola al crear un artículo
   (no es opción manual); el formulario "Nuevo movimiento" ofrece REUB, REPA,
   RETE y BAJA. */
INSERT INTO tipo_movimiento (codigo, nombre) VALUES
('ALTA', 'Alta de artículo'),
('REUB', 'Reubicación y/o cambio de resguardante'),
('REPA', 'Envío a reparación'),
('RETE', 'Retorno de reparación'),
('BAJA', 'Baja');

/* RF-11: oficina y dos laboratorios. Responsable NULL hasta confirmar el
   nombre del jefe de Informática (RF-12 solo exige que el campo exista).
   Decisiones 10 y 15: UBI-NOLOC existe para artículo que no se puede ubicar;
   hay que agregarla a RF-11. Va siempre junto con el estado NOLOC y se
   permite también en un Alta. */
INSERT INTO ubicacion (codigo, nombre, descripcion, responsable) VALUES
('UBI-OFI',   'Oficina de Informática',       'Oficina del Departamento de Informática', NULL),
('UBI-LAB1',  'Laboratorio de Informática 1', 'Laboratorio de cómputo 1', NULL),
('UBI-LAB2',  'Laboratorio de Informática 2', 'Laboratorio de cómputo 2', NULL),
('UBI-NOLOC', 'Sin ubicar / No localizado',   'Ubicación temporal para artículo no localizado en una revisión. Se llega con un Cambio de ubicación con motivo documentado', NULL);

/* ==========================================================================
   PENDIENTE DE ARRANQUE (no se puede hacer desde SQL)
     El primer Administrador necesita un registro en personal y otro en
     usuario con la contraseña ya hasheada. Se hará con un comando de Django
     (por ejemplo "crear_admin_inicial"), no con INSERT.
     El folio de Comodato/Enser sigue la fórmula de la decisión 37.
   ========================================================================== */

INSERT INTO personal (numero_empleado, nombre_pila, primer_apellido, puesto, activo, departamento)
VALUES ('DEMO-001', 'Usuario', 'Demo', 'Administrador del sistema', 1, 'DEP-INF');

INSERT INTO usuario (username, contrasena, activo, personal, rol)
VALUES ('admin',
        'pbkdf2_sha256$600000$4JxeXPbLTp4PQWZUreCJLF$tBckIY6KXy5ctkajRZOsenwtvz5LsvJNIZvbUIhL5Ow=',
        1,
        (SELECT num FROM personal WHERE numero_empleado = 'DEMO-001'),
        'ADMIN');