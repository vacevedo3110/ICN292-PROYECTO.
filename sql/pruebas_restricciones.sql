
-- pruebas_restricciones.sql 
USE altura_db;
SET NAMES utf8mb4;
START TRANSACTION;

-- A. Claves, NOT NULL, UNIQUE y ENUM

SELECT 'P01 DEBE FALLAR: RUT de cliente duplicado (UNIQUE)' AS prueba;
INSERT INTO CLIENTE (rut, razon_social)
SELECT rut, 'Cliente duplicado' FROM CLIENTE WHERE id_cliente = 1;

SELECT 'P02 DEBE FALLAR: RUT con formato inválido (CHECK con LIKE)' AS prueba;
INSERT INTO CLIENTE (rut, razon_social) VALUES ('768412353', 'Formato malo');

SELECT 'P03 DEBE FALLAR: estado que no existe en el flujo (ENUM)' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad, estado)
VALUES (1, 1, 'Prueba estado', '2026-11-15 10:00:00', 41180, 'Santiago', 'Diurna', 5, 15, 'Cerrado');

SELECT 'P04 DEBE FALLAR: presupuesto de un cliente que no existe (FOREIGN KEY)' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad)
VALUES (999, 1, 'Prueba FK', '2026-11-15 10:00:00', 41180, 'Santiago', 'Diurna', 5, 15);

SELECT 'P05 DEBE FALLAR: misma partida dos veces en un presupuesto (PRIMARY KEY compuesta)' AS prueba;
INSERT INTO DETALLE_PRESUPUESTO (id_presupuesto, id_partida, nro_linea, cantidad, precio_aplicado)
VALUES (7, 1, 99, 1, 871666);

SELECT 'P06 DEBE FALLAR: línea sin precio aplicado (NOT NULL): una partida sin precio de referencia se cotiza' AS prueba;
INSERT INTO DETALLE_PRESUPUESTO (id_presupuesto, id_partida, nro_linea, cantidad)
SELECT 7, id_partida, 99, 1 FROM PARTIDA WHERE precio_unitario_referencial IS NULL LIMIT 1;

SELECT 'P07 DEBE FALLAR: eliminar una partida usada en presupuestos (FOREIGN KEY)' AS prueba;
DELETE FROM PARTIDA WHERE codigo = '1.1';

SELECT 'P08 DEBE FALLAR: eliminar un presupuesto Emitido que tiene detalle, correcciones y envíos (FOREIGN KEY)' AS prueba;
DELETE FROM PRESUPUESTO WHERE id_presupuesto = 1;


-- B. Reglas de negocio con CHECK (RN-5, RN-7, RN-8)

SELECT 'P09 DEBE FALLAR: RN-5, gastos generales de 15 % (la empresa usa entre 5 y 12 %)' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad)
VALUES (1, 1, 'Prueba RN-5', '2026-11-15 10:00:00', 41180, 'Santiago', 'Nocturna', 15, 15);

SELECT 'P10 DEBE FALLAR: RN-5, 12 % de gastos generales sin justificar las condiciones de la obra' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad)
VALUES (1, 1, 'Prueba RN-5 justificación', '2026-11-15 10:00:00', 41180, 'Fuera de Santiago', 'Nocturna', 12, 15);

SELECT 'P11 DEBE FALLAR: RN-8, utilidad de 25 % sin justificación (habitual 12-20 %)' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad)
VALUES (1, 1, 'Prueba RN-8', '2026-11-15 10:00:00', 41343.55, 'Santiago', 'Diurna', 5, 25);

SELECT 'P12 DEBE FALLAR: RN-8, utilidad de 30 % aunque se justifique (máximo 25 %)' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad, justificacion_utilidad)
VALUES (1, 1, 'Prueba RN-8 máximo', '2026-11-15 10:00:00', 41343.55, 'Santiago', 'Diurna', 5, 30, 'Cliente nuevo, alto riesgo');

SELECT 'P13 OK: RN-8, utilidad de 11 % (como la planilla real) con justificación' AS prueba;
INSERT INTO PRESUPUESTO (id_cliente, id_usuario, nombre_proyecto, fecha_inicio, valor_uf_dia, ubicacion, tipo_jornada, pct_gastos_generales, pct_utilidad, justificacion_utilidad)
VALUES (1, 1, 'Prueba RN-8 justificada', '2026-11-15 10:00:00', 41343.55, 'Santiago', 'Diurna', 9, 11, 'Obra grande y cliente recurrente');
SELECT nombre_proyecto, estado, pct_gastos_generales, pct_utilidad, justificacion_utilidad
FROM PRESUPUESTO WHERE nombre_proyecto = 'Prueba RN-8 justificada';

SELECT 'P14 DEBE FALLAR: RN-7, pasar a Emitido sin aprobación ni fecha de emisión (CHECK ck_ppto_rn7)' AS prueba;
UPDATE PRESUPUESTO SET estado = 'Emitido' WHERE id_presupuesto = 7;

SELECT 'P15 DEBE FALLAR: RN-7, marcar Aprobado sin indicar quién aprueba' AS prueba;
UPDATE PRESUPUESTO SET estado = 'Aprobado', fecha_aprobacion = '2026-11-20 10:00:00' WHERE id_presupuesto = 6;

SELECT 'P16 OK: pasar el presupuesto 7 a revisión' AS prueba;
UPDATE PRESUPUESTO SET estado = 'En revision' WHERE id_presupuesto = 7;
SELECT id_presupuesto, estado FROM PRESUPUESTO WHERE id_presupuesto = 7;


-- C. Otras restricciones CHECK

SELECT 'P17 DEBE FALLAR: cantidad negativa en el detalle (CHECK)' AS prueba;
UPDATE DETALLE_PRESUPUESTO SET cantidad = -5 WHERE id_presupuesto = 7 AND id_partida = 1;

SELECT 'P18 DEBE FALLAR: seleccionar una cotización que aún no llega (CHECK)' AS prueba;
UPDATE COTIZACION_EXTERNA SET seleccionada = TRUE WHERE id_presupuesto = 7 AND nro_cotizacion = 2;

SELECT 'P19 DEBE FALLAR: obra con fecha de término anterior al inicio (CHECK)' AS prueba;
UPDATE OBRA SET fecha_termino_obra = '2026-10-01' WHERE id_presupuesto = 3;  

SELECT 'P20 DEBE FALLAR: envío a un correo mal escrito (CHECK con LIKE)' AS prueba;
INSERT INTO ENVIO_PRESUPUESTO (id_presupuesto, fecha_envio, email_destino, resultado)
VALUES (1, '2026-11-20 10:00:00', 'cliente-sin-arroba', 'Enviado');

SELECT 'P21 DEBE FALLAR: parámetro de costo sobre 100 % (CHECK)' AS prueba;
UPDATE PARAMETRO_COSTO SET valor = 150 WHERE clave = 'RECARGO_NOCTURNO_MO';


-- D. Transacciones DML

SELECT 'P22 OK: RN-3 y pregunta 3.1, actualizar el precio de 5.1.9 dejando el anterior en el historial' AS prueba;
SELECT codigo, precio_unitario_referencial, ultima_actualizacion, origen_precio FROM PARTIDA WHERE codigo = '5.1.9';

INSERT INTO HISTORIAL_PRECIO (id_partida, fecha_desde, fecha_hasta, precio)
SELECT id_partida, ultima_actualizacion, '2026-11-20', precio_unitario_referencial
FROM PARTIDA WHERE codigo = '5.1.9';

UPDATE PARTIDA
SET precio_unitario_referencial = 92500, ultima_actualizacion = '2026-11-20', origen_precio = 'Sistema'
WHERE codigo = '5.1.9';

SELECT codigo, precio_unitario_referencial, ultima_actualizacion, origen_precio FROM PARTIDA WHERE codigo = '5.1.9';
SELECT h.fecha_desde, h.fecha_hasta, h.precio
FROM HISTORIAL_PRECIO h JOIN PARTIDA p ON p.id_partida = h.id_partida
WHERE p.codigo = '5.1.9'
ORDER BY h.fecha_desde;

SELECT 'P23 OK: el presupuesto 1 (emitido) conserva el precio con que se cotizó 5.1.9 (trazabilidad)' AS prueba;
SELECT d.id_presupuesto, p.codigo, d.precio_aplicado, p.precio_unitario_referencial AS precio_catalogo_actual
FROM DETALLE_PRESUPUESTO d JOIN PARTIDA p ON p.id_partida = d.id_partida
WHERE p.codigo = '5.1.9' AND d.id_presupuesto = 1;

SELECT 'P24 DEBE FALLAR: cambiar un precio sin registrar su fecha (CHECK ck_partida_fecha)' AS prueba;
UPDATE PARTIDA SET ultima_actualizacion = NULL WHERE codigo = '5.1.10';

SELECT 'P25 OK: eliminar un borrador en el orden que exigen las claves foráneas (DELETE, Sesión 09)' AS prueba;
DELETE FROM COTIZACION_EXTERNA WHERE id_presupuesto = 7;
DELETE FROM DETALLE_PRESUPUESTO WHERE id_presupuesto = 7;
DELETE FROM PRESUPUESTO WHERE id_presupuesto = 7;
SELECT COUNT(*) AS presupuestos_con_id_7 FROM PRESUPUESTO WHERE id_presupuesto = 7;

-- Se usa rollback para volver al incio
ROLLBACK;
SELECT 'Fin de las pruebas: se hizo ROLLBACK, la base quedó como después del seed' AS fin;
SELECT COUNT(*) AS presupuestos, SUM(IF(id_presupuesto = 7, 1, 0)) AS sigue_el_7 FROM PRESUPUESTO;
