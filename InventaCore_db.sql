/* ==========================================================================
   SISTEMA DE CONTROL Y GESTIÓN DE INVENTARIO PARA EQUIPO ELECTRÓNICO
   CONALEP TIJUANA II — Departamento de Informática
   ==========================================================================
   Script provisional — versión 16/10/2026
   Verificado contra: RF y RNF Proyecto Conalep (2).pdf (23 RF + 11 RNF)
   DER: 14 entidades, 19 relaciones (ver CONALEP_DER_final_16-10-2026.md)
   Diccionario de datos: CONALEP_Diccionario_de_Datos_v2.xlsx

   NOTA: Este script es PROVISIONAL. No se ha ejecutado aún en XAMPP/phpMyAdmin.
   Pendiente de confirmar con Adad antes de usarse como definitivo.

   DECISIONES DE ESTE SCRIPT (para no olvidarlas):
     - USUARIO.ultimo_acceso: NO existe (decisión 16/10/2026, se descartó).
     - UBI-NOLOC: ubicación especial agregada para equipo no localizado
       físicamente. No es un ESTADO_OPERATIVO porque "no localizado" no
       responde si el equipo sirve o no — responde dónde está. Se trata
       igual que cualquier otra ubicación: el equipo llega ahí mediante un
       MOVIMIENTO de tipo "Cambio de ubicación", con motivo documentado.
       Conserva trazabilidad completa (RNF-06) y queda cubierto por los
       filtros de RF-09 sin agregar columnas nuevas a EQUIPO.
     - UBICACION.responsable: queda NULL en los 3+1 registros. Pendiente
       confirmar el nombre completo del nuevo jefe de Informática (Luis)
       antes de poblarlo. RF-12 solo exige el campo, no que esté lleno
       desde el día uno.
     - Sin triggers ni procedimientos almacenados: la bitácora, la
       generación de folios y las validaciones de negocio viven en Django
       (ver justificación en el chat — RNF-09 exige mensajes claros al
       usuario, y un trigger con SIGNAL no los da; además @usuario_actual
       en triggers es poco confiable con pooling de conexiones, problema
       ya documentado en mermax.sql). SQL solo garantiza lo que nunca debe
       romperse: PK, FK, UNIQUE, NOT NULL.
     - Orden de creación ajustado respecto al DER para que ninguna FK
       necesite agregarse después con ALTER TABLE (a diferencia de Mermax).

   CONVENCIÓN DE CÓDIGOS (ver tabla de notación en el chat):
     DEP- (departamento) · CAT- (categoría) · UBI- (ubicación)
     Sin prefijo: ROL, ORIGEN, ESTADO_OPERATIVO, ESTADO_REGISTRO,
                  TIPO_MOVIMIENTO (catálogos de 2 a 4 valores fijos,
                  donde el código corto ya es descriptivo por sí solo)
     MOV- (folio de movimiento) · RES- (folio de resguardo)
   ========================================================================== */

DROP DATABASE IF EXISTS conalep_db;
CREATE DATABASE conalep_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE conalep_db;


/* ==========================================================================
   BLOQUE 1 — CATÁLOGOS SIN DEPENDENCIAS
   ========================================================================== */

CREATE TABLE ROL (
    clave VARCHAR(10) NOT NULL,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    descripcion VARCHAR(100),
    PRIMARY KEY (clave)
);

CREATE TABLE DEPARTAMENTO (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(150),
    PRIMARY KEY (codigo)
);

CREATE TABLE CATEGORIA (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    descripcion VARCHAR(150),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (codigo)
);

CREATE TABLE ORIGEN (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    descripcion VARCHAR(150),
    PRIMARY KEY (codigo)
);

CREATE TABLE ESTADO_OPERATIVO (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (codigo)
);

CREATE TABLE ESTADO_REGISTRO (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(30) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (codigo)
);

CREATE TABLE TIPO_MOVIMIENTO (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    genera_resguardo BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (codigo)
);


/* ==========================================================================
   BLOQUE 2 — ENTIDADES MAESTRAS DE PERSONAS
   (PERSONAL antes que UBICACION, para que UBICACION.responsable
    pueda referenciarlo sin necesitar ALTER TABLE después)
   ========================================================================== */

CREATE TABLE PERSONAL (
    numero INT AUTO_INCREMENT NOT NULL,
    nombrePila VARCHAR(80) NOT NULL,
    primerApell VARCHAR(80) NOT NULL,
    segundoApell VARCHAR(80),
    puesto VARCHAR(100),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    departamento VARCHAR(10) NOT NULL,
    PRIMARY KEY (numero),
    CONSTRAINT fk_personal_departamento FOREIGN KEY (departamento) REFERENCES DEPARTAMENTO(codigo)
);


/* ==========================================================================
   BLOQUE 3 — UBICACIÓN (depende de PERSONAL para su responsable)
   ========================================================================== */

CREATE TABLE UBICACION (
    codigo VARCHAR(10) NOT NULL,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion VARCHAR(150),
    responsable INT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (codigo),
    CONSTRAINT fk_ubicacion_responsable FOREIGN KEY (responsable) REFERENCES PERSONAL(numero)
);


/* ==========================================================================
   BLOQUE 4 — USUARIO (depende de PERSONAL y ROL)
   ========================================================================== */

CREATE TABLE USUARIO (
    num INT AUTO_INCREMENT NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    correo VARCHAR(100) NOT NULL UNIQUE,
    contrasena VARCHAR(255) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    personal INT NOT NULL UNIQUE,
    rol VARCHAR(10) NOT NULL,
    PRIMARY KEY (num),
    CONSTRAINT fk_usuario_personal FOREIGN KEY (personal) REFERENCES PERSONAL(numero),
    CONSTRAINT fk_usuario_rol FOREIGN KEY (rol) REFERENCES ROL(clave)
);


/* ==========================================================================
   BLOQUE 5 — EQUIPO (depende de CATEGORIA, UBICACION, PERSONAL, ORIGEN,
   ESTADO_OPERATIVO, ESTADO_REGISTRO)
   ========================================================================== */

CREATE TABLE EQUIPO (
    num INT AUTO_INCREMENT NOT NULL,
    marbete_oficial VARCHAR(25) NULL UNIQUE,
    folio_interno VARCHAR(25) NULL UNIQUE,
    marca VARCHAR(60),
    modelo VARCHAR(60),
    num_serie VARCHAR(60),
    color VARCHAR(30),
    descripcion VARCHAR(150),
    fecha_adquisicion DATE,
    costo_adquisicion DECIMAL(10,2),
    fecha_alta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    categoria VARCHAR(10) NOT NULL,
    ubicacion VARCHAR(10) NOT NULL,
    resguardante INT NULL,
    origen VARCHAR(10) NOT NULL,
    estado_operativo VARCHAR(10) NOT NULL,
    estado_registro VARCHAR(10) NOT NULL,
    PRIMARY KEY (num),
    CONSTRAINT fk_equipo_categoria FOREIGN KEY (categoria) REFERENCES CATEGORIA(codigo),
    CONSTRAINT fk_equipo_ubicacion FOREIGN KEY (ubicacion) REFERENCES UBICACION(codigo),
    CONSTRAINT fk_equipo_resguardante FOREIGN KEY (resguardante) REFERENCES PERSONAL(numero),
    CONSTRAINT fk_equipo_origen FOREIGN KEY (origen) REFERENCES ORIGEN(codigo),
    CONSTRAINT fk_equipo_estado_operativo FOREIGN KEY (estado_operativo) REFERENCES ESTADO_OPERATIVO(codigo),
    CONSTRAINT fk_equipo_estado_registro FOREIGN KEY (estado_registro) REFERENCES ESTADO_REGISTRO(codigo)
);

/* Regla de integridad XOR (marbete_oficial / folio_interno):
   exactamente uno de los dos debe tener valor, según ORIGEN.
   NO se expresa aquí como CHECK condicional — se valida en el
   clean() del modelo de Django, tal como ya se decidió. */


/* ==========================================================================
   BLOQUE 6 — MOVIMIENTO (depende de EQUIPO, TIPO_MOVIMIENTO, UBICACION,
   PERSONAL, USUARIO)
   ========================================================================== */

CREATE TABLE MOVIMIENTO (
    folio VARCHAR(20) NOT NULL,
    fecha_movimiento DATETIME NOT NULL,
    motivo VARCHAR(255) NOT NULL,
    equipo INT NOT NULL,
    tipo_movimiento VARCHAR(10) NOT NULL,
    ubicacion_origen VARCHAR(10) NULL,
    ubicacion_destino VARCHAR(10) NOT NULL,
    resguardante_anterior INT NULL,
    resguardante_nuevo INT NOT NULL,
    usuario INT NOT NULL,
    PRIMARY KEY (folio),
    CONSTRAINT fk_movimiento_equipo FOREIGN KEY (equipo) REFERENCES EQUIPO(num),
    CONSTRAINT fk_movimiento_tipo_movimiento FOREIGN KEY (tipo_movimiento) REFERENCES TIPO_MOVIMIENTO(codigo),
    CONSTRAINT fk_movimiento_ubicacion_origen FOREIGN KEY (ubicacion_origen) REFERENCES UBICACION(codigo),
    CONSTRAINT fk_movimiento_ubicacion_destino FOREIGN KEY (ubicacion_destino) REFERENCES UBICACION(codigo),
    CONSTRAINT fk_movimiento_resguardante_anterior FOREIGN KEY (resguardante_anterior) REFERENCES PERSONAL(numero),
    CONSTRAINT fk_movimiento_resguardante_nuevo FOREIGN KEY (resguardante_nuevo) REFERENCES PERSONAL(numero),
    CONSTRAINT fk_movimiento_usuario FOREIGN KEY (usuario) REFERENCES USUARIO(num)
);


/* ==========================================================================
   BLOQUE 7 — RESGUARDO (depende de MOVIMIENTO)
   ========================================================================== */

CREATE TABLE RESGUARDO (
    folio VARCHAR(20) NOT NULL,
    fecha_generacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ruta_pdf VARCHAR(255) NOT NULL,
    movimiento VARCHAR(20) NOT NULL UNIQUE,
    PRIMARY KEY (folio),
    CONSTRAINT fk_resguardo_movimiento FOREIGN KEY (movimiento) REFERENCES MOVIMIENTO(folio)
);


/* ==========================================================================
   BLOQUE 8 — BITÁCORA (depende de USUARIO)
   ========================================================================== */

CREATE TABLE BITACORA (
    num INT AUTO_INCREMENT NOT NULL,
    fecha_hora DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modulo VARCHAR(50) NOT NULL,
    accion VARCHAR(20) NOT NULL,
    valor_anterior TEXT,
    valor_nuevo TEXT,
    motivo VARCHAR(255),
    tabla_afectada VARCHAR(50) NOT NULL,
    registro_id VARCHAR(20) NOT NULL,
    usuario INT NOT NULL,
    PRIMARY KEY (num),
    CONSTRAINT fk_bitacora_usuario FOREIGN KEY (usuario) REFERENCES USUARIO(num)
);

/* tabla_afectada y registro_id son VARCHAR, NO claves foráneas:
   la bitácora es polimórfica (apunta a EQUIPO unas veces, a CATEGORIA
   otras). Si fueran FK, MySQL obligaría a elegir una sola tabla. */


/* ==========================================================================
   CATÁLOGO DE DATOS — VALORES PRECARGADOS
   ========================================================================== */

INSERT INTO ROL (clave, nombre, descripcion) VALUES
('ADMIN', 'Administrador', 'Control total: altas, bajas y movimientos. Único rol que crea cuentas y consulta la bitácora'),
('CONT', 'Contadora', 'Rol de consulta: consulta el inventario y edita puntualmente algún dato. No da de alta equipo ni ejecuta bajas');

INSERT INTO DEPARTAMENTO (codigo, nombre, descripcion) VALUES
('DEP-INF', 'Informática', 'Departamento al que pertenecen las 3 ubicaciones del alcance'),
('DEP-ACA', 'Académico', 'Departamento del plantel. Necesario porque el resguardante puede ser de cualquier área'),
('DEP-DIR', 'Dirección', 'Departamento del plantel');
-- Pendiente: agregar más departamentos reales del plantel conforme se identifiquen resguardantes.

INSERT INTO CATEGORIA (codigo, nombre, descripcion, activo) VALUES
('CAT-MON', 'Monitor', 'Monitor de cualquier tipo', TRUE),
('CAT-PCE', 'Computadora de escritorio', 'Equipo de cómputo fijo', TRUE),
('CAT-LAP', 'Laptop', 'Equipo de cómputo portátil', TRUE),
('CAT-TIP', 'Teléfono IP', 'Teléfono de voz sobre IP', TRUE),
('CAT-SWT', 'Switch', 'Conmutador de red', TRUE),
('CAT-ALT', 'Altavoz de entrada', 'Bocina o altavoz de acceso', TRUE),
('CAT-SRV', 'Servidor físico', 'Servidor de gabinete o torre', TRUE);
-- Precargado con las 7 categorías confirmadas por RF-04. Catálogo extensible.

INSERT INTO ORIGEN (codigo, nombre, descripcion) VALUES
('ACT', 'Activo', 'Bien patrimonial del gobierno del estado, identificado por MARBETE SAACG.NET'),
('COM', 'Comodato', 'Bien recibido en comodato, identificado por folio interno del plantel'),
('ENS', 'Enser', 'Bien menor del plantel, identificado por folio interno');
-- Fijo: 3 valores del inventario patrimonial. No administrable por el usuario.

INSERT INTO ESTADO_OPERATIVO (codigo, nombre, activo) VALUES
('UTIL', 'Útil', TRUE),
('REP', 'En reparación', TRUE),
('BAJA', 'De baja', TRUE),
('INAC', 'Inactivo', TRUE);
-- No incluye "No localizado": ese caso se resuelve con la ubicación
-- especial UBI-NOLOC, no como estado operativo (ver nota de cabecera).

INSERT INTO ESTADO_REGISTRO (codigo, nombre, activo) VALUES
('PEND', 'Pendiente', TRUE),
('REG', 'Registrado', TRUE),
('DON', 'Donado', TRUE);

INSERT INTO TIPO_MOVIMIENTO (codigo, nombre, genera_resguardo) VALUES
('ALTA', 'Alta de equipo', TRUE),
('CAMB_RESG', 'Cambio de resguardante', TRUE),
('CAMB_UBI', 'Cambio de ubicación', FALSE);

-- PERSONAL: sin datos de prueba por el momento. Se decidió no crear la
-- base de datos en el DBMS (XAMPP/phpMyAdmin) todavía, por lo que no se
-- insertan registros de PERSONAL, USUARIO ni EQUIPO en esta versión.

INSERT INTO UBICACION (codigo, nombre, descripcion, responsable, activo) VALUES
('UBI-OFI', 'Oficina de Informática', 'Oficina del Departamento de Informática', NULL, TRUE),
('UBI-LAB1', 'Laboratorio de Informática 1', 'Laboratorio de cómputo 1', NULL, TRUE),
('UBI-LAB2', 'Laboratorio de Informática 2', 'Laboratorio de cómputo 2', NULL, TRUE),
('UBI-NOLOC', 'Sin ubicar / No localizado', 'Ubicación temporal cuando el equipo no se encuentra físicamente en una revisión. El equipo llega aquí mediante un movimiento de tipo Cambio de ubicación, con motivo documentado, y conserva su trazabilidad completa', NULL, TRUE);
-- Responsable NULL en las 4: pendiente confirmar nombre completo del
-- nuevo jefe de Informática antes de poblarlo (decisión 16/10/2026).

/* ==========================================================================
   FIN DEL SCRIPT PROVISIONAL
   Pendiente antes de considerarlo definitivo:
     1. Confirmar con Adad la nomenclatura final (este script ya sigue
        snake_case parejo y las correcciones de la sección 8 del DER).
     2. Decidir si se cargan los equipos reales del Excel patrimonial
        (228 Activos + ~31 Comodatos + ~12-19 Enseres, tras revisión
        manual) como INSERT de prueba, o se deja la tabla EQUIPO vacía.
     3. Ejecutar en XAMPP/phpMyAdmin y validar que las 19 FK se crean
        sin error en el orden en que están declaradas.
     4. Confirmar nombre del responsable de ubicaciones cuando se tenga.
   ========================================================================== */
