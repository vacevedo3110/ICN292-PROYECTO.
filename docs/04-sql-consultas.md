# 04 — Consultas SQL de negocio

Archivo: [`sql/consultas.sql`](../sql/consultas.sql). Resultados reales de MySQL 8 después de cargar `schema.sql` + `seed.sql`, con fecha de corte 20-11-2026.

> **Datos:** el catálogo y los precios son reales (itemizado de la empresa). El % de mano de obra, los recargos por jornada y 8 precios de materiales son estimaciones. Los presupuestos y las obras son sintéticos (anonimizados). Los resultados demuestran que el sistema responde las preguntas; no miden el desempeño real de la empresa.

## G1. ¿Qué tipo de precio se está usando en los presupuestos?

| Presupuestos | Tipo de precio | % del monto |
|---|---|---|
| 1, 2, 3, 4, 5, 7, 8, 9, 10 | Último precio registrado | 100 % |
| 6 | Último precio registrado / Precio antiguo | 33,6 % / 66,4 % |

**Interpretación.** 9 de 10 presupuestos usan el último precio registrado, que es el criterio de la empresa: reajusta precios con cada obra nueva. El presupuesto 6 cotizó 5 muebles con precios antiguos y subestima su costo en **$163.700**. El último precio queda 2 % sobre el promedio histórico, así que cotizar con el promedio subestimaría costos. FIFO, LIFO o costo medio no aplican: la empresa compra por obra y no tiene inventario.

## G2. ¿Qué % del costo son remuneraciones y qué % materiales?

| Tipo de obra | Remuneraciones | Materiales | Subcontratos |
|---|---|---|---|
| Grandes, diurnas, con especialistas (1, 3, 8, 10) | 22–29 % | 23–33 % | 21–29 % |
| Chicas, nocturnas (2, 5, 9) | 44–63 % | 33–46 % | 0 % |

**Interpretación.** El % de mano de obra de cada partida es una estimación por tipo de partida. A eso se suma un recargo de 25 % en jornada nocturna y de 12,5 % en fines de semana (parámetros editables). **Hallazgo:** la empresa cubre ese recargo con los gastos generales, pero en los 6 presupuestos con trabajo nocturno o de fin de semana los GG de 8–12 % no alcanzan. Harían falta GG de 9–11 % con fines de semana y de 16–28 % de noche. Conviene validarlo con la empresa.

## G3. ¿Cuáles son los plazos promedio de entrega?

| Obras terminadas | Plazo ofrecido promedio | Plazo real promedio | Desviación |
|---|---|---|---|
| 3 | 95 días | 106,3 días | +10,8 % |

**Interpretación.** Las obras se atrasan en promedio 10,8 %; la mayor desviación fue la habilitación de 300 m² (172 días contra 150). De las obras en ejecución, la 2 ya consumió el 102 % de su plazo. Coincide con la empresa: una obra de oficina toma 5-6 meses o más y depende de los materiales.

## Consultas de gestión y KPI

| Consulta | Qué responde | Resultado |
|---|---|---|
| C1 | Cartera y totales con IVA | 10 presupuestos; los 6 emitidos suman $314,6 M netos ($374,4 M con IVA). |
| C2 | Subtotales por capítulo (presupuesto 1) | Instalaciones es el 38,4 % del costo directo. |
| C3 | Precios que vencen antes de terminar la obra | En el borrador 7 (150 días), el 100 % de los precios vencerá durante la obra. |
| C4 | % de precios vigentes | 98 partidas con precio, 100 % vigentes. De las 101 sin precio, 77 se explican (subcontratos o incluidas en otra partida). |
| C5 | Tiempo de elaboración (meta ≤ 4 h) | Sin externos: 3,8–4 h (cumple). Con externos: 7–8 días; el cuello de botella son las cotizaciones de terceros. |
| C6 | Espera de cotizaciones externas | Los contratistas responden en 1–6 días; hay 3 pendientes. |
| C7 | % de error de costo (meta ≤ 5 %) | Entre 0,1 % y 4,1 %: todos cumplen. |
| C8 | Ahorro por comparar cotizaciones | $3.350.000 frente a la cotización más alta. |
| C9 | Partidas con más peso (Pareto) | Las 10 primeras son el 48 % del costo; el esmalte al agua lidera (9,6 %). |
| C10 | Anti-join: proveedores sin uso | Un contratista nunca ha sido cotizado. |
| C11 | Subconsulta: UF/m² sobre el promedio | Habilitaciones completas y kitchenette (hasta 9,0 UF/m²). |

## Pruebas de integridad
- [`sql/pruebas_restricciones.sql`](../sql/pruebas_restricciones.sql): 25 pruebas; las 20 que deben fallar son rechazadas por la base (PK, FK, NOT NULL, UNIQUE, CHECK, ENUM).
- [`app/pruebas_reglas_app.py`](../app/pruebas_reglas_app.py): 9 pruebas de las reglas que controla la app (flujo de estados, solo el Gerente aprueba, presupuestos cerrados, historial de precios).
