
-- schema.sql presupuestos Constructora Altura (Inversiones Rumay Ltda.)

DROP DATABASE IF EXISTS altura_db;
CREATE DATABASE altura_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE altura_db;
SET NAMES utf8mb4;

-- 1. USUARIO: personas que operan el sistema
CREATE TABLE USUARIO (
    id_usuario     INT           AUTO_INCREMENT,
    nombre         VARCHAR(100)  NOT NULL,
    email          VARCHAR(100)  NOT NULL UNIQUE,
    rol            ENUM('Gerente General', 'Asistente') NOT NULL,
    password_hash  CHAR(64)      NOT NULL,                
    activo         BOOLEAN       NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id_usuario)
);

-- 2. CLIENTE y TELEFONO_CLIENTE 
CREATE TABLE CLIENTE (
    id_cliente      INT           AUTO_INCREMENT,
    rut             VARCHAR(12)   NOT NULL UNIQUE,        
    razon_social    VARCHAR(150)  NOT NULL,
    direccion       VARCHAR(200),
    email_contacto  VARCHAR(100),
    PRIMARY KEY (id_cliente),
    CONSTRAINT ck_cliente_rut_fmt CHECK (rut LIKE '__.___.___-_' OR rut LIKE '_.___.___-_')
);

CREATE TABLE TELEFONO_CLIENTE (
    id_cliente     INT          NOT NULL,
    nro_telefono   INT          NOT NULL,
    numero         VARCHAR(20)  NOT NULL,
    tipo_telefono  VARCHAR(50)  NOT NULL,
    es_preferido   BOOLEAN      NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id_cliente, nro_telefono)
);

-- 3. Catálogo
CREATE TABLE UNIDAD_MEDIDA (
    codigo_unidad  VARCHAR(5)   NOT NULL,                  
    descripcion    VARCHAR(50)  NOT NULL,
    PRIMARY KEY (codigo_unidad)
);

CREATE TABLE CAPITULO (
    id_capitulo        INT           AUTO_INCREMENT,
    codigo             VARCHAR(10)   NOT NULL UNIQUE,      
    nombre             VARCHAR(150)  NOT NULL,
    id_capitulo_padre  INT           NULL,                 
    orden              INT           NOT NULL,             
    PRIMARY KEY (id_capitulo)
);

CREATE TABLE PARTIDA (
    id_partida                   INT            AUTO_INCREMENT,
    codigo                       VARCHAR(12)    NOT NULL UNIQUE,
    id_capitulo                  INT            NOT NULL,
    descripcion                  VARCHAR(255)   NOT NULL,
    codigo_unidad                VARCHAR(5)     NOT NULL,
    precio_unitario_referencial  DECIMAL(12,2)  NULL,      
    ultima_actualizacion         DATE           NULL,     
    origen_precio                ENUM('Planilla empresa', 'Estimación web', 'Sistema') NULL,
    pct_mano_obra                DECIMAL(5,2)   NULL,      
    fuente                       ENUM('Itemizado empresa', 'Entrevista empresa', 'Sistema') NOT NULL DEFAULT 'Itemizado empresa',
    activo                       BOOLEAN        NOT NULL DEFAULT TRUE,   
    orden                        INT            NOT NULL,
    PRIMARY KEY (id_partida),
    CONSTRAINT ck_partida_precio CHECK (precio_unitario_referencial IS NULL OR precio_unitario_referencial > 0),
    
    CONSTRAINT ck_partida_fecha  CHECK ((precio_unitario_referencial IS NULL AND ultima_actualizacion IS NULL AND origen_precio IS NULL)
                                     OR (precio_unitario_referencial IS NOT NULL AND ultima_actualizacion IS NOT NULL AND origen_precio IS NOT NULL)),
    CONSTRAINT ck_partida_mo     CHECK (pct_mano_obra IS NULL OR pct_mano_obra BETWEEN 0 AND 100)
);

CREATE TABLE HISTORIAL_PRECIO (
    id_partida     INT            NOT NULL,
    fecha_desde    DATE           NOT NULL,
    fecha_hasta    DATE           NOT NULL,   
    precio         DECIMAL(12,2)  NOT NULL,
    PRIMARY KEY (id_partida, fecha_desde),
    CONSTRAINT ck_hist_fechas CHECK (fecha_hasta >= fecha_desde),
    CONSTRAINT ck_hist_precio CHECK (precio > 0)
);


CREATE TABLE PARAMETRO_COSTO (
    clave        VARCHAR(40)    NOT NULL,
    valor        DECIMAL(6,2)   NOT NULL,
    descripcion  VARCHAR(255)   NOT NULL,
    fuente       VARCHAR(255)   NOT NULL,
    PRIMARY KEY (clave),
    CONSTRAINT ck_param_valor CHECK (valor BETWEEN 0 AND 100)
);

-- 4. ESPECIALIDAD y CONTRATISTA
CREATE TABLE ESPECIALIDAD (
    id_especialidad  INT           AUTO_INCREMENT,
    nombre           VARCHAR(80)   NOT NULL UNIQUE,
    id_capitulo      INT           NULL,                  
    PRIMARY KEY (id_especialidad)
);

CREATE TABLE CONTRATISTA (
    id_contratista   INT           AUTO_INCREMENT,
    rut              VARCHAR(12)   NOT NULL UNIQUE,
    nombre           VARCHAR(150)  NOT NULL,
    id_especialidad  INT           NOT NULL,               
    email            VARCHAR(100),
    telefono         VARCHAR(20),
    activo           BOOLEAN       NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id_contratista),
    CONSTRAINT ck_contratista_rut_fmt CHECK (rut LIKE '__.___.___-_' OR rut LIKE '_.___.___-_')
);

-- 5. PRESUPUESTO
--    Según la empresa, los gastos generales dependen de la ubicación (dentro o fuera de
--    Santiago), de la jornada, de los fines de semana y de las dificultades de la obra.
CREATE TABLE PRESUPUESTO (
    id_presupuesto         INT            AUTO_INCREMENT,
    id_cliente             INT            NOT NULL,        
    id_usuario             INT            NOT NULL,        
    id_usuario_aprobador   INT            NULL,            
    nombre_proyecto        VARCHAR(150)   NOT NULL,
    direccion_obra         VARCHAR(200),
    superficie_m2          DECIMAL(10,2)  NULL,            
    fecha_inicio           TIMESTAMP      NOT NULL,        
    fecha_aprobacion       TIMESTAMP      NULL,
    fecha_emision          TIMESTAMP      NULL,
    valor_uf_dia           DECIMAL(10,2)  NOT NULL,         
    ubicacion              ENUM('Santiago', 'Fuera de Santiago') NOT NULL,
    tipo_jornada           ENUM('Diurna', 'Nocturna') NOT NULL,
    trabajo_fin_semana     BOOLEAN        NOT NULL DEFAULT FALSE,
    pct_gastos_generales   DECIMAL(5,2)   NOT NULL,         
    justificacion_gg       VARCHAR(255)   NULL,
    pct_utilidad           DECIMAL(5,2)   NOT NULL,         
    justificacion_utilidad VARCHAR(255)   NULL,
    pct_iva                DECIMAL(5,2)   NOT NULL DEFAULT 19,
    plazo_ejecucion_dias   INT            NULL,             
    estado                 ENUM('Borrador', 'En revision', 'Aprobado', 'Rechazado', 'Emitido') NOT NULL DEFAULT 'Borrador',
    PRIMARY KEY (id_presupuesto),
    
    CONSTRAINT ck_ppto_rn5      CHECK (pct_gastos_generales BETWEEN 5 AND 12),
    CONSTRAINT ck_ppto_rn5_just CHECK (pct_gastos_generales <= 10 OR justificacion_gg IS NOT NULL),
    
    CONSTRAINT ck_ppto_rn8      CHECK (pct_utilidad BETWEEN 8 AND 25),
    CONSTRAINT ck_ppto_rn8_just CHECK (pct_utilidad BETWEEN 12 AND 20 OR justificacion_utilidad IS NOT NULL),

    CONSTRAINT ck_ppto_rn9      CHECK (pct_iva BETWEEN 0 AND 30),
    CONSTRAINT ck_ppto_plazo    CHECK (plazo_ejecucion_dias IS NULL OR plazo_ejecucion_dias > 0),
    CONSTRAINT ck_ppto_uf       CHECK (valor_uf_dia > 0),
    CONSTRAINT ck_ppto_m2       CHECK (superficie_m2 IS NULL OR superficie_m2 > 0),
    CONSTRAINT ck_ppto_fechas   CHECK ((fecha_aprobacion IS NULL OR fecha_aprobacion >= fecha_inicio)
                                   AND (fecha_emision IS NULL OR (fecha_aprobacion IS NOT NULL AND fecha_emision >= fecha_aprobacion))),
   
   
    CONSTRAINT ck_ppto_rn7      CHECK ((estado IN ('Borrador', 'En revision') AND id_usuario_aprobador IS NULL AND fecha_aprobacion IS NULL AND fecha_emision IS NULL)
                                    OR (estado = 'Rechazado' AND id_usuario_aprobador IS NOT NULL AND fecha_aprobacion IS NULL AND fecha_emision IS NULL)
                                    OR (estado = 'Aprobado'  AND id_usuario_aprobador IS NOT NULL AND fecha_aprobacion IS NOT NULL AND fecha_emision IS NULL)
                                    OR (estado = 'Emitido'   AND id_usuario_aprobador IS NOT NULL AND fecha_aprobacion IS NOT NULL AND fecha_emision IS NOT NULL))
);

-- 5b. OBRA: presupuesto emitido que el cliente aceptó y se ejecuta.
CREATE TABLE OBRA (
    id_presupuesto      INT   NOT NULL,
    fecha_inicio_obra   DATE  NOT NULL,
    fecha_termino_obra  DATE  NULL,          -- NULL = en ejecución
    PRIMARY KEY (id_presupuesto),
    CONSTRAINT ck_obra_fechas CHECK (fecha_termino_obra IS NULL OR fecha_termino_obra >= fecha_inicio_obra)
);

-- 5c. ENVIO_PRESUPUESTO: cada envío del PDF al cliente outlook
CREATE TABLE ENVIO_PRESUPUESTO (
    id_envio         INT           AUTO_INCREMENT,
    id_presupuesto   INT           NOT NULL,
    fecha_envio      TIMESTAMP     NOT NULL,
    email_destino    VARCHAR(100)  NOT NULL,
    canal            VARCHAR(30)   NOT NULL DEFAULT 'Outlook (n8n)',
    resultado        ENUM('Enviado', 'Error') NOT NULL,
    detalle          VARCHAR(255)  NULL,
    PRIMARY KEY (id_envio),
    CONSTRAINT ck_envio_email CHECK (email_destino LIKE '%_@_%._%')
);

-- 6. DETALLE_PRESUPUESTO (RF3).
CREATE TABLE DETALLE_PRESUPUESTO (
    id_presupuesto   INT            NOT NULL,
    id_partida       INT            NOT NULL,
    nro_linea        INT            NOT NULL,   
    cantidad         DECIMAL(10,2)  NOT NULL,
    precio_aplicado  DECIMAL(12,2)  NOT NULL,
    PRIMARY KEY (id_presupuesto, id_partida),
    CONSTRAINT ck_detalle_cantidad CHECK (cantidad > 0),
    CONSTRAINT ck_detalle_precio   CHECK (precio_aplicado > 0)
);

-- 7. COTIZACION_EXTERNA 
CREATE TABLE COTIZACION_EXTERNA (
    id_presupuesto    INT            NOT NULL,
    nro_cotizacion    INT            NOT NULL,
    id_contratista    INT            NOT NULL,
    id_especialidad   INT            NOT NULL,     
    monto_cotizado    DECIMAL(14,2)  NULL,           -- NULL mientras está pendiente
    fecha_solicitud   DATE           NOT NULL,
    fecha_recepcion   DATE           NULL,
    seleccionada      BOOLEAN        NOT NULL DEFAULT FALSE,   
    PRIMARY KEY (id_presupuesto, nro_cotizacion),
    CONSTRAINT ck_cotiz_recepcion CHECK ((fecha_recepcion IS NULL AND monto_cotizado IS NULL)
                                      OR (fecha_recepcion IS NOT NULL AND monto_cotizado > 0)),
    CONSTRAINT ck_cotiz_fechas    CHECK (fecha_recepcion IS NULL OR fecha_recepcion >= fecha_solicitud),
    CONSTRAINT ck_cotiz_sel       CHECK (seleccionada = FALSE OR fecha_recepcion IS NOT NULL)
);

-- 8. CORRECCION_PRESUPUESTO 
CREATE TABLE CORRECCION_PRESUPUESTO (
    id_presupuesto         INT            NOT NULL,
    nro_correccion         INT            NOT NULL,
    fecha                  TIMESTAMP      NOT NULL,
    id_usuario             INT            NOT NULL,
    costo_directo_antes    DECIMAL(14,2)  NOT NULL,
    costo_directo_despues  DECIMAL(14,2)  NOT NULL,
    motivo                 VARCHAR(255)   NOT NULL,
    PRIMARY KEY (id_presupuesto, nro_correccion),
    CONSTRAINT ck_corr_costos CHECK (costo_directo_antes >= 0 AND costo_directo_despues >= 0)
);


-- PARTE 2. RELACIONES: claves foráneas 

ALTER TABLE TELEFONO_CLIENTE ADD CONSTRAINT fk_tel_cliente
    FOREIGN KEY (id_cliente) REFERENCES CLIENTE(id_cliente) ON UPDATE RESTRICT;
ALTER TABLE CAPITULO ADD CONSTRAINT fk_capitulo_padre
    FOREIGN KEY (id_capitulo_padre) REFERENCES CAPITULO(id_capitulo) ON UPDATE RESTRICT;
ALTER TABLE PARTIDA ADD CONSTRAINT fk_partida_capitulo
    FOREIGN KEY (id_capitulo) REFERENCES CAPITULO(id_capitulo) ON UPDATE RESTRICT;
ALTER TABLE PARTIDA ADD CONSTRAINT fk_partida_unidad
    FOREIGN KEY (codigo_unidad) REFERENCES UNIDAD_MEDIDA(codigo_unidad) ON UPDATE RESTRICT;
ALTER TABLE HISTORIAL_PRECIO ADD CONSTRAINT fk_hist_partida
    FOREIGN KEY (id_partida) REFERENCES PARTIDA(id_partida) ON UPDATE RESTRICT;
ALTER TABLE ESPECIALIDAD ADD CONSTRAINT fk_especialidad_cap
    FOREIGN KEY (id_capitulo) REFERENCES CAPITULO(id_capitulo) ON UPDATE RESTRICT;
ALTER TABLE CONTRATISTA ADD CONSTRAINT fk_contratista_esp
    FOREIGN KEY (id_especialidad) REFERENCES ESPECIALIDAD(id_especialidad) ON UPDATE RESTRICT;
ALTER TABLE PRESUPUESTO ADD CONSTRAINT fk_ppto_cliente
    FOREIGN KEY (id_cliente) REFERENCES CLIENTE(id_cliente) ON UPDATE RESTRICT;
ALTER TABLE PRESUPUESTO ADD CONSTRAINT fk_ppto_usuario
    FOREIGN KEY (id_usuario) REFERENCES USUARIO(id_usuario) ON UPDATE RESTRICT;
ALTER TABLE PRESUPUESTO ADD CONSTRAINT fk_ppto_aprobador
    FOREIGN KEY (id_usuario_aprobador) REFERENCES USUARIO(id_usuario) ON UPDATE RESTRICT;
ALTER TABLE OBRA ADD CONSTRAINT fk_obra_ppto
    FOREIGN KEY (id_presupuesto) REFERENCES PRESUPUESTO(id_presupuesto) ON UPDATE RESTRICT;
ALTER TABLE ENVIO_PRESUPUESTO ADD CONSTRAINT fk_envio_ppto
    FOREIGN KEY (id_presupuesto) REFERENCES PRESUPUESTO(id_presupuesto) ON UPDATE RESTRICT;
ALTER TABLE DETALLE_PRESUPUESTO ADD CONSTRAINT fk_detalle_ppto
    FOREIGN KEY (id_presupuesto) REFERENCES PRESUPUESTO(id_presupuesto) ON UPDATE RESTRICT;
ALTER TABLE DETALLE_PRESUPUESTO ADD CONSTRAINT fk_detalle_partida
    FOREIGN KEY (id_partida) REFERENCES PARTIDA(id_partida) ON UPDATE RESTRICT;
ALTER TABLE COTIZACION_EXTERNA ADD CONSTRAINT fk_cotiz_ppto
    FOREIGN KEY (id_presupuesto) REFERENCES PRESUPUESTO(id_presupuesto) ON UPDATE RESTRICT;
ALTER TABLE COTIZACION_EXTERNA ADD CONSTRAINT fk_cotiz_contratista
    FOREIGN KEY (id_contratista) REFERENCES CONTRATISTA(id_contratista) ON UPDATE RESTRICT;
ALTER TABLE COTIZACION_EXTERNA ADD CONSTRAINT fk_cotiz_especialidad
    FOREIGN KEY (id_especialidad) REFERENCES ESPECIALIDAD(id_especialidad) ON UPDATE RESTRICT;
ALTER TABLE CORRECCION_PRESUPUESTO ADD CONSTRAINT fk_corr_ppto
    FOREIGN KEY (id_presupuesto) REFERENCES PRESUPUESTO(id_presupuesto) ON UPDATE RESTRICT;
ALTER TABLE CORRECCION_PRESUPUESTO ADD CONSTRAINT fk_corr_usuario
    FOREIGN KEY (id_usuario) REFERENCES USUARIO(id_usuario) ON UPDATE RESTRICT;


-- PARTE 3. VISTAS:



CREATE VIEW v_partida_vigencia AS
SELECT p.id_partida, p.codigo, p.descripcion, p.codigo_unidad,
       p.precio_unitario_referencial, p.ultima_actualizacion, p.origen_precio,
       DATEDIFF(NOW(), p.ultima_actualizacion) AS dias_desde_actualizacion,
       CASE WHEN p.precio_unitario_referencial IS NULL THEN 'Sin precio'
            WHEN DATEDIFF(NOW(), p.ultima_actualizacion) > 180 THEN 'Vencido (> 6 meses)'
            WHEN DATEDIFF(NOW(), p.ultima_actualizacion) >= 90 THEN 'Por revisar (3 a 6 meses)'
            ELSE 'Vigente' END AS estado_precio
FROM PARTIDA p
WHERE p.activo = TRUE;

-- RF3: costo de las partidas propias de cada presupuesto
CREATE VIEW v_costo_partidas AS
SELECT d.id_presupuesto,
       COUNT(*)                            AS lineas,
       SUM(d.cantidad * d.precio_aplicado) AS costo_partidas
FROM DETALLE_PRESUPUESTO d
GROUP BY d.id_presupuesto;

-- RN-6: costo de las cotizaciones externas seleccionadas de cada presupuesto
CREATE VIEW v_costo_externos AS
SELECT x.id_presupuesto,
       SUM(x.monto_cotizado) AS costo_externos
FROM COTIZACION_EXTERNA x
WHERE x.seleccionada = TRUE
GROUP BY x.id_presupuesto;

-- RF4: costo directo = partidas propias + externos seleccionados. LEFT JOIN para incluir

CREATE VIEW v_presupuesto_costo AS
SELECT pr.id_presupuesto, pr.nombre_proyecto, c.razon_social AS cliente, pr.estado,
       pr.ubicacion, pr.tipo_jornada, pr.trabajo_fin_semana,
       pr.superficie_m2, pr.valor_uf_dia, pr.pct_gastos_generales, pr.pct_utilidad, pr.pct_iva,
       ROUND(IF(cp.costo_partidas IS NULL, 0, cp.costo_partidas), 0) AS costo_partidas,
       IF(ce.costo_externos IS NULL, 0, ce.costo_externos)           AS costo_externos,
       ROUND(IF(cp.costo_partidas IS NULL, 0, cp.costo_partidas)
             + IF(ce.costo_externos IS NULL, 0, ce.costo_externos), 0) AS costo_directo
FROM PRESUPUESTO pr
JOIN CLIENTE c                ON c.id_cliente = pr.id_cliente
LEFT JOIN v_costo_partidas cp ON cp.id_presupuesto = pr.id_presupuesto
LEFT JOIN v_costo_externos ce ON ce.id_presupuesto = pr.id_presupuesto;


CREATE VIEW v_presupuesto_neto AS
SELECT t.*,
       ROUND(t.costo_directo * t.pct_gastos_generales / 100, 0) AS gastos_generales,
       ROUND(t.costo_directo * t.pct_utilidad / 100, 0)         AS utilidad,
       t.costo_directo + ROUND(t.costo_directo * t.pct_gastos_generales / 100, 0)
                       + ROUND(t.costo_directo * t.pct_utilidad / 100, 0) AS total_neto
FROM v_presupuesto_costo t;

-- RF4 / RN-9 / RN-2: IVA, total con IVA y valores en UF
CREATE VIEW v_presupuesto_totales AS
SELECT n.*,
       ROUND(n.total_neto * n.pct_iva / 100, 0)                                              AS iva,
       n.total_neto + ROUND(n.total_neto * n.pct_iva / 100, 0)                               AS total_con_iva,
       ROUND(n.total_neto / n.valor_uf_dia, 2)                                               AS total_neto_uf,
       ROUND((n.total_neto + ROUND(n.total_neto * n.pct_iva / 100, 0)) / n.valor_uf_dia, 2)  AS total_con_iva_uf,
       ROUND(n.total_neto / n.valor_uf_dia / n.superficie_m2, 2)                             AS uf_neto_por_m2
FROM v_presupuesto_neto n;

-- Pregunta 3.2: mano de obra y materiales de las partidas de cada presupuesto.

CREATE VIEW v_composicion_partidas AS
SELECT d.id_presupuesto,
       SUM(IF(p.pct_mano_obra IS NULL, 0, d.cantidad * d.precio_aplicado * p.pct_mano_obra / 100))         AS rem_base,
       SUM(IF(p.pct_mano_obra IS NULL, 0, d.cantidad * d.precio_aplicado * (100 - p.pct_mano_obra) / 100)) AS materiales,
       SUM(IF(p.pct_mano_obra IS NULL, d.cantidad * d.precio_aplicado, 0))                                 AS otros
FROM DETALLE_PRESUPUESTO d
JOIN PARTIDA p ON p.id_partida = d.id_partida
GROUP BY d.id_presupuesto;

-- Pregunta 3.2: composición del costo de cada presupuesto.
-- Recargo de jornada = remuneraciones base × (recargo nocturno si la obra es nocturna + recargo de
-- fin de semana si se trabaja en fines de semana). Según la empresa, ese mayor costo se cubre con
-- los gastos generales: por eso se descuenta de ellos (gg_neto) y se compara con el GG base.
CREATE VIEW v_presupuesto_composicion AS
SELECT t.id_presupuesto, t.nombre_proyecto, t.estado, t.ubicacion, t.tipo_jornada, t.trabajo_fin_semana,
       t.pct_gastos_generales, t.costo_directo, t.costo_externos, t.gastos_generales, t.utilidad, t.total_neto,
       ROUND(c.rem_base, 0)   AS remuneraciones_base,
       ROUND(c.rem_base * (IF(t.tipo_jornada = 'Nocturna', pn.valor, 0) + IF(t.trabajo_fin_semana, pf.valor, 0)) / 100, 0) AS recargo_jornada,
       ROUND(c.materiales, 0) AS materiales,
       ROUND(c.otros, 0)      AS proyectos_y_seguros,
       t.gastos_generales
         - ROUND(c.rem_base * (IF(t.tipo_jornada = 'Nocturna', pn.valor, 0) + IF(t.trabajo_fin_semana, pf.valor, 0)) / 100, 0) AS gg_neto,
       ROUND(t.costo_directo * gb.valor / 100, 0) AS gg_minimo
FROM v_presupuesto_totales t
JOIN v_composicion_partidas c ON c.id_presupuesto = t.id_presupuesto
JOIN PARAMETRO_COSTO pn ON pn.clave = 'RECARGO_NOCTURNO_MO'
JOIN PARAMETRO_COSTO pf ON pf.clave = 'RECARGO_FIN_SEMANA_MO'
JOIN PARAMETRO_COSTO gb ON gb.clave = 'GG_BASE';

-- Pregunta 3.1: precio de cada partida en el tiempo (precios reemplazados + precio vigente).

CREATE VIEW v_precio_en_el_tiempo AS
SELECT id_partida, fecha_desde, fecha_hasta, precio, 'Histórico' AS tipo
FROM HISTORIAL_PRECIO
UNION ALL
SELECT id_partida, ultima_actualizacion, NULL, precio_unitario_referencial, 'Vigente'
FROM PARTIDA
WHERE precio_unitario_referencial IS NOT NULL;

-- Pregunta 3.1: precio promedio de cada partida considerando todos sus valores en el tiempo
CREATE VIEW v_precio_promedio AS
SELECT id_partida, COUNT(*) AS valores, AVG(precio) AS precio_promedio
FROM v_precio_en_el_tiempo
GROUP BY id_partida;


CREATE VIEW v_capitulo_raiz AS
SELECT c.id_capitulo,
       r.id_capitulo AS id_raiz, r.codigo AS codigo_raiz, r.nombre AS nombre_raiz, r.orden AS orden_raiz
FROM CAPITULO c
LEFT JOIN CAPITULO p1 ON p1.id_capitulo = c.id_capitulo_padre
LEFT JOIN CAPITULO p2 ON p2.id_capitulo = p1.id_capitulo_padre
LEFT JOIN CAPITULO p3 ON p3.id_capitulo = p2.id_capitulo_padre
JOIN CAPITULO r ON r.id_capitulo = CASE WHEN p3.id_capitulo IS NOT NULL THEN p3.id_capitulo
                                       WHEN p2.id_capitulo IS NOT NULL THEN p2.id_capitulo
                                       WHEN p1.id_capitulo IS NOT NULL THEN p1.id_capitulo
                                       ELSE c.id_capitulo END;

-- RF9: monto de cada presupuesto por capítulo del itemizado. Las partidas propias van en su capítulo


CREATE VIEW v_monto_por_capitulo AS
SELECT d.id_presupuesto, p.id_capitulo, d.cantidad * d.precio_aplicado AS monto, 'Partida propia' AS origen
FROM DETALLE_PRESUPUESTO d
JOIN PARTIDA p ON p.id_partida = d.id_partida
UNION ALL
SELECT x.id_presupuesto, e.id_capitulo, x.monto_cotizado, 'Cotización externa'
FROM COTIZACION_EXTERNA x
JOIN ESPECIALIDAD e ON e.id_especialidad = x.id_especialidad
WHERE x.seleccionada = TRUE;

-- Monto total de las partidas propias de todos los presupuestos emitidos
CREATE VIEW v_total_partidas_emitidas AS
SELECT SUM(d.cantidad * d.precio_aplicado) AS monto_emitido
FROM DETALLE_PRESUPUESTO d
JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
WHERE pr.estado = 'Emitido';
