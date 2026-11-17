
-- consultas.sql  Consultas de negocio de la bd presupuestos

USE altura_db;
SET NAMES utf8mb4;

SELECT d.id_presupuesto AS id,
       CASE WHEN d.precio_aplicado = v.precio THEN 'Último precio registrado'
            WHEN h.precio IS NOT NULL         THEN 'Precio antiguo'
            ELSE 'Otro (ajustado a mano)' END AS tipo_de_precio,
       COUNT(*) AS lineas,
       ROUND(SUM(d.cantidad * d.precio_aplicado), 0) AS monto,
       ROUND(100 * SUM(d.cantidad * d.precio_aplicado) / cp.costo_partidas, 1) AS pct_del_monto,
       ROUND(100 * SUM(d.cantidad * (d.precio_aplicado - pp.precio_promedio))
                 / SUM(d.cantidad * pp.precio_promedio), 1) AS pct_sobre_precio_promedio
FROM DETALLE_PRESUPUESTO d
JOIN PRESUPUESTO pr       ON pr.id_presupuesto = d.id_presupuesto
JOIN v_costo_partidas cp  ON cp.id_presupuesto = d.id_presupuesto
LEFT JOIN v_precio_en_el_tiempo v
       ON v.id_partida = d.id_partida
      AND v.fecha_desde <= pr.fecha_inicio
      AND (v.fecha_hasta IS NULL OR v.fecha_hasta > pr.fecha_inicio)
LEFT JOIN HISTORIAL_PRECIO h
       ON h.id_partida = d.id_partida
      AND h.precio = d.precio_aplicado
      AND h.fecha_hasta <= pr.fecha_inicio
LEFT JOIN v_precio_promedio pp ON pp.id_partida = d.id_partida
GROUP BY d.id_presupuesto, tipo_de_precio, cp.costo_partidas
ORDER BY d.id_presupuesto, tipo_de_precio;
-- 
SELECT d.id_presupuesto AS id, p.codigo, p.descripcion, d.cantidad,
       d.precio_aplicado, p.precio_unitario_referencial AS precio_vigente,
       ROUND(d.cantidad * (p.precio_unitario_referencial - d.precio_aplicado), 0) AS costo_subestimado
FROM DETALLE_PRESUPUESTO d
JOIN PARTIDA p      ON p.id_partida = d.id_partida
JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
WHERE d.precio_aplicado <> p.precio_unitario_referencial
  AND p.ultima_actualizacion <= pr.fecha_inicio
ORDER BY costo_subestimado DESC;

-- 

SELECT id_presupuesto AS id, nombre_proyecto, estado, tipo_jornada AS jornada,
       IF(trabajo_fin_semana, 'Sí', 'No') AS fin_semana,
       ROUND(100 * remuneraciones_base / total_neto, 1)                     AS pct_remuneraciones_base,
       ROUND(100 * recargo_jornada / total_neto, 1)                         AS pct_recargo_jornada,
       ROUND(100 * (remuneraciones_base + recargo_jornada) / total_neto, 1) AS pct_remuneraciones_total,
       ROUND(100 * materiales / total_neto, 1)                              AS pct_materiales,
       ROUND(100 * costo_externos / total_neto, 1)                          AS pct_subcontratos,
       ROUND(100 * proyectos_y_seguros / total_neto, 1)                     AS pct_proyectos_y_seguros,
       ROUND(100 * gg_neto / total_neto, 1)                                 AS pct_gg_neto,
       ROUND(100 * utilidad / total_neto, 1)                                AS pct_utilidad
FROM v_presupuesto_composicion
ORDER BY id_presupuesto;



SELECT id_presupuesto AS id, nombre_proyecto, tipo_jornada AS jornada, IF(trabajo_fin_semana, 'Sí', 'No') AS fin_semana,
       pct_gastos_generales AS pct_gg, gastos_generales, recargo_jornada, gg_neto, gg_minimo,
       IF(gg_neto >= gg_minimo, 'Alcanza', 'No alcanza') AS gg_cubre_recargo,
       ROUND(100 * (gg_minimo + recargo_jornada) / costo_directo, 1) AS pct_gg_sugerido
FROM v_presupuesto_composicion
WHERE recargo_jornada > 0
ORDER BY id_presupuesto;


--
SELECT o.id_presupuesto AS id, pr.nombre_proyecto, pr.plazo_ejecucion_dias AS plazo_ofrecido,
       o.fecha_inicio_obra, o.fecha_termino_obra,
       IF(o.fecha_termino_obra IS NULL, 'En ejecución', 'Terminada') AS situacion,
       IF(o.fecha_termino_obra IS NULL, DATEDIFF('2026-11-20', o.fecha_inicio_obra),
                                        DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra)) AS dias_reales_o_transcurridos,
       IF(o.fecha_termino_obra IS NULL, NULL,
          DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra) - pr.plazo_ejecucion_dias) AS desviacion_dias,
       IF(o.fecha_termino_obra IS NULL, NULL,
          ROUND(100 * (DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra) - pr.plazo_ejecucion_dias)
                    / pr.plazo_ejecucion_dias, 1)) AS desviacion_pct,
       ROUND(100 * IF(o.fecha_termino_obra IS NULL, DATEDIFF('2026-11-20', o.fecha_inicio_obra),
                                                    DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra))
                 / pr.plazo_ejecucion_dias, 1) AS pct_plazo_consumido
FROM OBRA o
JOIN PRESUPUESTO pr ON pr.id_presupuesto = o.id_presupuesto
ORDER BY o.fecha_inicio_obra;

-- 
SELECT COUNT(*) AS obras_terminadas,
       ROUND(AVG(pr.plazo_ejecucion_dias), 1) AS plazo_ofrecido_promedio,
       ROUND(AVG(DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra)), 1) AS plazo_real_promedio,
       ROUND(AVG(100 * (DATEDIFF(o.fecha_termino_obra, o.fecha_inicio_obra) - pr.plazo_ejecucion_dias)
                     / pr.plazo_ejecucion_dias), 1) AS desviacion_promedio_pct
FROM OBRA o
JOIN PRESUPUESTO pr ON pr.id_presupuesto = o.id_presupuesto
WHERE o.fecha_termino_obra IS NOT NULL;



-- C1. Cartera de presupuestos: costo directo, GG, utilidad, total neto, IVA

SELECT id_presupuesto AS id, nombre_proyecto, cliente, estado, ubicacion, tipo_jornada AS jornada,
       IF(trabajo_fin_semana, 'Sí', 'No') AS fin_semana,
       costo_partidas, costo_externos, costo_directo,
       pct_gastos_generales AS pct_gg, gastos_generales, pct_utilidad AS pct_util, utilidad,
       total_neto, iva, total_con_iva, total_neto_uf, total_con_iva_uf, uf_neto_por_m2
FROM v_presupuesto_totales
ORDER BY id_presupuesto;


-- C2. Subtotales por capítulo del presupuesto 

SELECT r.codigo_raiz AS capitulo, r.nombre_raiz AS nombre,
       ROUND(SUM(m.monto), 0) AS subtotal,
       ROUND(100 * SUM(m.monto) / t.costo_directo, 1) AS pct_costo_directo
FROM v_monto_por_capitulo m
JOIN v_capitulo_raiz r       ON r.id_capitulo = m.id_capitulo
JOIN v_presupuesto_totales t ON t.id_presupuesto = m.id_presupuesto
WHERE m.id_presupuesto = 1
GROUP BY r.codigo_raiz, r.nombre_raiz, r.orden_raiz, t.costo_directo
ORDER BY r.orden_raiz;


-- C3. La empresa actualiza precios
--     con cada obra (cada 3 a 6 meses) y una obra de oficina dura 5-6 meses o más, así que un
--     precio vigente hoy puede quedar vencido antes de comprar los materiales.
--     Vencido = más de 180 días; por revisar = 90 a 180 días.

SELECT pr.id_presupuesto AS id, pr.nombre_proyecto, pr.estado, pr.plazo_ejecucion_dias AS plazo,
       COUNT(*) AS lineas,
       SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) > 180, 1, 0)) AS vencidas_hoy,
       SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) BETWEEN 90 AND 180, 1, 0)) AS por_revisar_hoy,
       SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) + pr.plazo_ejecucion_dias > 180, 1, 0)) AS vencidas_al_termino,
       ROUND(100 * SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) + pr.plazo_ejecucion_dias > 180,
                          d.cantidad * d.precio_aplicado, 0))
                 / SUM(d.cantidad * d.precio_aplicado), 1) AS pct_monto_vencido_al_termino,
       MIN(p.ultima_actualizacion) AS precio_mas_antiguo,
       180 - MAX(DATEDIFF('2026-11-20', p.ultima_actualizacion)) AS dias_hasta_primer_vencimiento
FROM DETALLE_PRESUPUESTO d
JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
JOIN PARTIDA p      ON p.id_partida = d.id_partida
WHERE pr.estado IN ('Borrador', 'En revision', 'Aprobado')
GROUP BY pr.id_presupuesto, pr.nombre_proyecto, pr.estado, pr.plazo_ejecucion_dias
ORDER BY pr.id_presupuesto;


-- C4. KPI "% de precios vigentes" (< 90 días) del catálogo por capítulo, y
--     partidas que la empresa aún no tiene con precio de referencia.

SELECT r.codigo_raiz AS capitulo, r.nombre_raiz AS nombre,
       COUNT(*) AS partidas,
       SUM(IF(p.precio_unitario_referencial IS NULL, 1, 0)) AS sin_precio,
       SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) < 90, 1, 0)) AS vigentes,
       SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) BETWEEN 90 AND 180, 1, 0)) AS por_revisar,
       SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) > 180, 1, 0)) AS vencidas,
       CASE WHEN COUNT(p.precio_unitario_referencial) = 0 THEN NULL
            ELSE ROUND(100 * SUM(IF(DATEDIFF('2026-11-20', p.ultima_actualizacion) < 90, 1, 0))
                           / COUNT(p.precio_unitario_referencial), 1) END AS pct_vigentes_sobre_con_precio
FROM PARTIDA p
JOIN v_capitulo_raiz r ON r.id_capitulo = p.id_capitulo
WHERE p.activo = TRUE
GROUP BY r.codigo_raiz, r.nombre_raiz, r.orden_raiz
ORDER BY r.orden_raiz;

-- Total del catálogo (KPI global). COUNT(columna) cuenta solo las partidas que tienen precio.
SELECT COUNT(*) AS partidas,
       COUNT(*) - COUNT(precio_unitario_referencial) AS sin_precio,
       SUM(IF(DATEDIFF('2026-11-20', ultima_actualizacion) < 90, 1, 0)) AS vigentes,
       SUM(IF(DATEDIFF('2026-11-20', ultima_actualizacion) BETWEEN 90 AND 180, 1, 0)) AS por_revisar,
       SUM(IF(DATEDIFF('2026-11-20', ultima_actualizacion) > 180, 1, 0)) AS vencidas,
       ROUND(100 * SUM(IF(DATEDIFF('2026-11-20', ultima_actualizacion) < 90, 1, 0))
                 / COUNT(precio_unitario_referencial), 1) AS pct_vigentes_sobre_con_precio,
       SUM(IF(DATEDIFF('2026-11-20', ultima_actualizacion) BETWEEN 91 AND 180, 1, 0)) AS vencen_en_3_meses,
       SUM(IF(origen_precio = 'Estimación web', 1, 0)) AS precios_estimados_web
FROM PARTIDA
WHERE activo = TRUE;


-- C5. KPI tiempo de elaboración (inicio -> emisión) de los presupuestos emitidos,
--     separando los que requirieron especialistas externos. Meta E1: <= 4 horas.



SELECT pr.id_presupuesto AS id, pr.nombre_proyecto,
       IF(COUNT(x.nro_cotizacion) > 0, 'Sí', 'No') AS con_externos,
       pr.fecha_inicio, pr.fecha_emision,
       ROUND(TIMESTAMPDIFF(MINUTE, pr.fecha_inicio, pr.fecha_emision) / 60, 1)   AS horas_elaboracion,
       ROUND(TIMESTAMPDIFF(MINUTE, pr.fecha_inicio, pr.fecha_emision) / 1440, 2) AS dias_elaboracion,
       IF(TIMESTAMPDIFF(MINUTE, pr.fecha_inicio, pr.fecha_emision) <= 240, 'Cumple', 'No cumple') AS meta_4_horas
FROM PRESUPUESTO pr
LEFT JOIN COTIZACION_EXTERNA x ON x.id_presupuesto = pr.id_presupuesto
WHERE pr.estado = 'Emitido'
GROUP BY pr.id_presupuesto, pr.nombre_proyecto, pr.fecha_inicio, pr.fecha_emision
ORDER BY horas_elaboracion;


-- C6. KPI espera de cotizaciones externas por especialidad y contratista,
--     y cotizaciones pendientes a la fecha de corte.

SELECT e.nombre AS especialidad, c.nombre AS contratista,
       COUNT(*) AS solicitadas,
       COUNT(x.fecha_recepcion) AS recibidas,
       ROUND(AVG(DATEDIFF(x.fecha_recepcion, x.fecha_solicitud)), 1) AS dias_promedio_respuesta,
       SUM(IF(x.seleccionada, 1, 0)) AS veces_seleccionado
FROM COTIZACION_EXTERNA x
JOIN ESPECIALIDAD e ON e.id_especialidad = x.id_especialidad
JOIN CONTRATISTA c  ON c.id_contratista  = x.id_contratista
GROUP BY e.nombre, c.nombre
ORDER BY e.nombre, dias_promedio_respuesta;

SELECT x.id_presupuesto AS id, pr.nombre_proyecto, e.nombre AS especialidad, c.nombre AS contratista,
       x.fecha_solicitud, DATEDIFF('2026-11-20', x.fecha_solicitud) AS dias_esperando
FROM COTIZACION_EXTERNA x
JOIN PRESUPUESTO pr ON pr.id_presupuesto = x.id_presupuesto
JOIN ESPECIALIDAD e ON e.id_especialidad = x.id_especialidad
JOIN CONTRATISTA c  ON c.id_contratista  = x.id_contratista
WHERE x.fecha_recepcion IS NULL
ORDER BY dias_esperando DESC;


-- C7. KPI correcciones por presupuesto y % de error de costo (E1, ec. **):
--     error = |C_inicial - C_revisado| / C_revisado. Meta E1: <= 5 %.


SELECT pr.id_presupuesto AS id, pr.nombre_proyecto, pr.estado,
       COUNT(k.nro_correccion) AS correcciones,
       ini.costo_directo_antes AS costo_inicial,
       t.costo_directo         AS costo_revisado,
       ROUND(100 * IF(ini.costo_directo_antes > t.costo_directo,
                      ini.costo_directo_antes - t.costo_directo,
                      t.costo_directo - ini.costo_directo_antes) / t.costo_directo, 2) AS pct_error_costo,
       IF(IF(ini.costo_directo_antes > t.costo_directo,
             ini.costo_directo_antes - t.costo_directo,
             t.costo_directo - ini.costo_directo_antes) / t.costo_directo <= 0.05, 'Cumple', 'No cumple') AS meta_5_pct
FROM PRESUPUESTO pr
JOIN v_presupuesto_totales t    ON t.id_presupuesto = pr.id_presupuesto
JOIN CORRECCION_PRESUPUESTO k   ON k.id_presupuesto = pr.id_presupuesto
JOIN CORRECCION_PRESUPUESTO ini ON ini.id_presupuesto = pr.id_presupuesto AND ini.nro_correccion = 1
GROUP BY pr.id_presupuesto, pr.nombre_proyecto, pr.estado, ini.costo_directo_antes, t.costo_directo
ORDER BY pct_error_costo DESC;


-- C8. Ahorro por comparar cotizaciones externas, diferencia entre la cotización
--     seleccionada y la más cara recibida de la misma especialidad. HAVING deja solo
--     las especialidades con más de una cotización.

SELECT x.id_presupuesto AS id, e.nombre AS especialidad,
       COUNT(*) AS cotizaciones_recibidas,
       MAX(IF(x.seleccionada, x.monto_cotizado, NULL)) AS monto_seleccionado,
       MAX(x.monto_cotizado) AS monto_mas_alto,
       MAX(x.monto_cotizado) - MAX(IF(x.seleccionada, x.monto_cotizado, NULL)) AS ahorro
FROM COTIZACION_EXTERNA x
JOIN ESPECIALIDAD e ON e.id_especialidad = x.id_especialidad
WHERE x.fecha_recepcion IS NOT NULL
GROUP BY x.id_presupuesto, e.nombre
HAVING COUNT(*) > 1
ORDER BY ahorro DESC;


-- C9. Partidas que más pesan en los presupuestos emitidos, indican qué precios que conviene tener actualizados



SELECT p.codigo, p.descripcion, p.codigo_unidad AS unidad,
       COUNT(DISTINCT d.id_presupuesto) AS presupuestos,
       ROUND(SUM(d.cantidad * d.precio_aplicado), 0) AS monto_total,
       ROUND(100 * SUM(d.cantidad * d.precio_aplicado) / te.monto_emitido, 1) AS pct_del_total
FROM DETALLE_PRESUPUESTO d
JOIN PRESUPUESTO pr ON pr.id_presupuesto = d.id_presupuesto
JOIN PARTIDA p      ON p.id_partida = d.id_partida
CROSS JOIN v_total_partidas_emitidas te
WHERE pr.estado = 'Emitido'
GROUP BY p.codigo, p.descripcion, p.codigo_unidad, te.monto_emitido
ORDER BY monto_total DESC
LIMIT 10;


-- C10. Anti-join: clientes sin presupuestos y contratistas a los que nunca
--      se les ha pedido una cotización. Patrón A LEFT JOIN B ... WHERE B.clave IS NULL.

SELECT 'Cliente' AS tipo, c.razon_social AS nombre
FROM CLIENTE c
LEFT JOIN PRESUPUESTO pr ON pr.id_cliente = c.id_cliente
WHERE pr.id_presupuesto IS NULL
UNION ALL
SELECT 'Contratista', k.nombre
FROM CONTRATISTA k
LEFT JOIN COTIZACION_EXTERNA x ON x.id_contratista = k.id_contratista
WHERE x.id_presupuesto IS NULL;


-- C11. Subconsulta escalar en el WHERE (Ayudantía 6): presupuestos cuyo valor por m2 supera el
--      promedio de la cartera. El promedio se calcula una vez y cada presupuesto se compara con él.

SELECT id_presupuesto AS id, nombre_proyecto, superficie_m2, total_neto_uf, uf_neto_por_m2
FROM v_presupuesto_totales
WHERE uf_neto_por_m2 > (SELECT AVG(uf_neto_por_m2) FROM v_presupuesto_totales)
ORDER BY uf_neto_por_m2 DESC;
