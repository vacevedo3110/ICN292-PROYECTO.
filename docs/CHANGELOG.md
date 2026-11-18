# CHANGELOG — Cambios desde la Entrega 1

### Agregado
- **Base de datos MySQL 8** ejecutable: `sql/schema.sql` (16 tablas, claves, restricciones y vistas) y `sql/seed.sql` (catálogo real de la empresa y presupuestos de ejemplo).
- **Consultas de negocio** (`sql/consultas.sql`): las 3 preguntas del Gerente General y los KPI de la E1, interpretadas en `docs/04-sql-consultas.md`.
- **Aplicación web** (`app/app.py`, Streamlit): presupuestos con cálculo automático, alertas de precios, flujo de aprobación y PDF.
- **Automatización n8n**: envío del presupuesto emitido al cliente por correo (Outlook) con el PDF adjunto (`docs/05-automatizacion-n8n.md`).
- **Actor Asistente**: elabora presupuestos, registra partidas y pide cotizaciones externas; no puede aprobar. Se separa del Gerente General, que aprueba (`docs/01-requerimientos.md`).
- **RF10**: envío automático del presupuesto emitido al cliente y registro de cada envío.
- **Tablas nuevas:**
  - `HISTORIAL_PRECIO`: qué precio se usa,
  - `PARAMETRO_COSTO`: recargos de mano de obra nocturna y de fin de semana,
  - `OBRA`: plazo ofrecido vs. real,
  - `ENVIO_PRESUPUESTO`: registro de cada envío al cliente,
  - `CORRECCION_PRESUPUESTO`: KPI de correcciones y % de error,
  - `CAPITULO` y `UNIDAD_MEDIDA`: estructura del itemizado real,
  - `ESPECIALIDAD`: las 5 especialidades externas de la entrevista.
- **Columnas nuevas:**
  - en `PARTIDA`: `pct_mano_obra`, `origen_precio`, `fuente` y `activo`;
  - en `PRESUPUESTO`: `superficie_m2` (indicador UF/m²), `plazo_ejecucion_dias`, `ubicacion`, `tipo_jornada`, `trabajo_fin_semana`, `pct_iva`, justificaciones de GG y utilidad, y `id_usuario_aprobador`.
- **Pruebas:** `sql/pruebas_restricciones.sql` (integridad de la base) y `app/pruebas_reglas_app.py` (reglas de la app).

### Cambiado
- **Motor:** MySQL 8 (la E1 indicaba PostgreSQL).
- **Requerimientos:** `01-requerimientos.md` se alinea con la numeración del informe E1 (RF1–RF9, RN-1 a RN-7, RNF-01 a RNF-05). RNF-04 pasa a tener dos roles: Gerente General y Asistente.
- **BPMN to-be:** carril Asistente, carril Sistema, aprobación con retorno a Borrador y envío automático por n8n. Detalle y motivos en `02-bpmn.md`, sección 3.
- **RN-4 (vigencia de precios):** vigente < 3 meses, por revisar 3–6, vencido > 6, porque la empresa actualiza precios con cada obra nueva (cada 3 a 6 meses).
- **RN-5 (gastos generales):** entre 5 % y 12 %, con justificación sobre 10 %, según ubicación, jornada y fines de semana.
- **RN-7 / RF8 (flujo):** se agrega el estado «En revisión». Flujo: Borrador → En revisión → Aprobado → Emitido; solo el Gerente General aprueba.
- **`PRESUPUESTO.fecha_creacion`** se reemplaza por `fecha_inicio`, `fecha_aprobacion` y `fecha_emision`, para medir el tiempo de elaboración en horas (meta: 4 h).
- **`DETALLE_PRESUPUESTO`:** clave compuesta (`id_presupuesto`, `id_partida`), que impide repetir una partida en un presupuesto.
- **`COTIZACION_EXTERNA`:** se agregan `fecha_solicitud` y `seleccionada`; el monto queda vacío mientras la cotización está pendiente.
- **Especialidades:** el texto libre se reemplaza por la tabla `ESPECIALIDAD`.
- **`PARTIDA.ultima_actualizacion`:** ahora se implementa en el SQL.

### Nuevas reglas de negocio
- **RN-8 (utilidad):** habitual 12–20 %; fuera de ese rango (8–25 %) exige justificación.
- **RN-9 (IVA):** 19 % incluido en cada presupuesto.
- **Restricciones de integridad:** `CHECK`, `UNIQUE` y `ENUM` en RUT, montos, cantidades y estados. El SQL de la E1 aceptaba RUT duplicados y cantidades negativas.

### Eliminado
- Totales guardados en tablas: el costo directo, los gastos generales, la utilidad, el IVA y el total se calculan con vistas SQL (3FN).
