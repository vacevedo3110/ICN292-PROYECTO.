# Modelo de Datos y Normalización (3FN)

## 1. Introducción
Base de datos del Sistema de Presupuestos de Constructora Altura, en 3FN e implementada en MySQL 8 ([`sql/schema.sql`](../sql/schema.sql)). Reemplaza las planillas Excel del proceso As-Is y elimina sus anomalías de actualización, inserción y borrado.

| Grupo | Tablas |
|---|---|
| Usuarios y clientes | `USUARIO`, `CLIENTE`, `TELEFONO_CLIENTE` |
| Catálogo de precios | `UNIDAD_MEDIDA`, `CAPITULO`, `PARTIDA`, `HISTORIAL_PRECIO`, `PARAMETRO_COSTO` |
| Externos | `ESPECIALIDAD`, `CONTRATISTA` |
| Presupuestos | `PRESUPUESTO`, `DETALLE_PRESUPUESTO`, `COTIZACION_EXTERNA`, `CORRECCION_PRESUPUESTO` |
| Ejecución y envío | `OBRA`, `ENVIO_PRESUPUESTO` |

## 2. Normalización

**1FN — atributos atómicos.** Los teléfonos de un cliente van en `TELEFONO_CLIENTE` (PK `id_cliente`, `nro_telefono`), no en columnas `telefono_1`, `telefono_2`. Cada partida de un presupuesto es un registro de `DETALLE_PRESUPUESTO`.

**2FN — dependencia de la clave completa.** En `DETALLE_PRESUPUESTO` (PK `id_presupuesto`, `id_partida`), `cantidad` y `precio_aplicado` dependen de ambas claves. La descripción y la unidad de la partida no se repiten aquí: dependen solo de `id_partida` y están en `PARTIDA`. Lo mismo vale para `COTIZACION_EXTERNA`, `HISTORIAL_PRECIO` y `CORRECCION_PRESUPUESTO`.

**3FN — sin dependencias transitivas.** Los datos que dependen de otra entidad se guardan una sola vez en su propia tabla:
- `CLIENTE` y `CONTRATISTA`: el presupuesto y la cotización solo guardan su id.
- `ESPECIALIDAD`, `UNIDAD_MEDIDA` y `CAPITULO`: este último es jerárquico (`id_capitulo_padre`).
- `PARAMETRO_COSTO`: recargos de mano de obra nocturna y de fin de semana, y GG base.

**Campos calculados.** Ninguna tabla guarda subtotales ni totales, porque dependerían de otros atributos. Se calculan con vistas SQL encadenadas: `v_costo_partidas` → `v_presupuesto_costo` → `v_presupuesto_neto` → `v_presupuesto_totales` (costo directo, gastos generales, utilidad, IVA y UF).

**Desnormalización controlada.** `DETALLE_PRESUPUESTO.precio_aplicado` y `PRESUPUESTO.valor_uf_dia` guardan el precio y la UF del momento de cotizar. Es deliberado: un presupuesto emitido no puede cambiar cuando cambia el catálogo. Además, permite saber qué tipo de precio se usó (último, antiguo o ajustado), comparándolo con `HISTORIAL_PRECIO`.

## 3. Anomalías evitadas

| Anomalía | Planilla (As-Is) | Modelo (To-Be) |
|---|---|---|
| Actualización | Un cambio de precio hay que corregirlo en cada planilla. | El precio vive solo en `PARTIDA`; el anterior pasa a `HISTORIAL_PRECIO`. |
| Inserción | No se puede registrar un contratista o una partida sin un presupuesto. | `CONTRATISTA` y `PARTIDA` existen por sí solas. |
| Borrado | Al borrar un presupuesto se pierden los datos del cliente. | Clientes y contratistas tienen tabla propia; las FK impiden borrar datos en uso. |

## 4. Integridad
- PK y FK en todas las relaciones; `NOT NULL`, `UNIQUE` y `ENUM`.
- `CHECK` para las reglas de negocio:
  - gastos generales 5–12 % (RN-5);
  - utilidad 8–25 % (RN-8);
  - estados con su aprobador y sus fechas (RN-7);
  - montos positivos y formato de RUT.

Pruebas en [`sql/pruebas_restricciones.sql`](../sql/pruebas_restricciones.sql).
