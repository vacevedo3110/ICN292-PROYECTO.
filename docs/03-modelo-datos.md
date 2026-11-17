# Modelo de Datos y Normalización (3FN)

## 1. Introducción
Este documento justifica el diseño de la base de datos relacional del Sistema de Gestión de Presupuestos de Inversiones Rumay Limitada (Constructora Altura). El modelo cumple la Tercera Forma Normal (3FN), asegura la integridad referencial y elimina las anomalías de actualización, inserción y borrado que tenía el proceso As-Is basado en planillas Excel.

El modelo se implementa en MySQL 8 en [`sql/schema.sql`](../sql/schema.sql) y tiene 16 tablas:

| Grupo | Tablas |
|---|---|
| Usuarios y clientes | `USUARIO`, `CLIENTE`, `TELEFONO_CLIENTE` |
| Catálogo de precios | `UNIDAD_MEDIDA`, `CAPITULO`, `PARTIDA`, `HISTORIAL_PRECIO`, `PARAMETRO_COSTO` |
| Externos | `ESPECIALIDAD`, `CONTRATISTA` |
| Presupuestos | `PRESUPUESTO`, `DETALLE_PRESUPUESTO`, `COTIZACION_EXTERNA`, `CORRECCION_PRESUPUESTO` |
| Ejecución y envío | `OBRA`, `ENVIO_PRESUPUESTO` |

## 2. Justificación de la normalización

### 2.1. Primera Forma Normal (1FN): atributos atómicos y sin grupos repetidos
La 1FN exige que todos los atributos sean atómicos (indivisibles) y que no haya grupos repetidos.

- **Teléfonos de clientes:** un cliente puede tener varios teléfonos (celular, oficina). En vez de columnas `telefono_1`, `telefono_2`, se creó la entidad débil `TELEFONO_CLIENTE`, con clave primaria compuesta (`id_cliente`, `nro_telefono`) y los campos `tipo_telefono` y `es_preferido`.
- **Partidas de un presupuesto:** en la planilla, cada presupuesto es una hoja con muchas filas de partidas. En el modelo, cada fila es un registro de `DETALLE_PRESUPUESTO`.
- **Código de partida:** el código del itemizado (por ejemplo `5.3.2`) no se usa para deducir el capítulo. La relación con el capítulo va en una clave foránea explícita (`id_capitulo`).

### 2.2. Segunda Forma Normal (2FN): dependencia de la clave completa
La 2FN exige estar en 1FN y que, en las tablas con clave compuesta, cada atributo no clave dependa de la clave completa y no solo de una parte.

- **`DETALLE_PRESUPUESTO`** (PK `id_presupuesto`, `id_partida`): `cantidad` y `precio_aplicado` dependen de la combinación presupuesto + partida. La descripción y la unidad de la partida **no** se guardan aquí, porque dependerían solo de `id_partida` (dependencia parcial); se obtienen desde `PARTIDA`. La clave compuesta, igual que el «detalle de compra» visto en clases, impide además repetir una partida en el mismo presupuesto.
- **`COTIZACION_EXTERNA`** (PK `id_presupuesto`, `nro_cotizacion`): el monto, las fechas de solicitud y recepción y si fue seleccionada dependen de esa cotización puntual. Los datos del presupuesto (cliente, obra) no se repiten aquí.
- **`HISTORIAL_PRECIO`** (PK `id_partida`, `fecha_desde`): el precio y la fecha de término dependen de la partida en ese período.
- **`CORRECCION_PRESUPUESTO`** (PK `id_presupuesto`, `nro_correccion`): los costos antes y después, el motivo y el usuario dependen de esa corrección.

### 2.3. Tercera Forma Normal (3FN): sin dependencias transitivas
La 3FN exige estar en 2FN y que ningún atributo no clave dependa de otro atributo no clave.

- **`CONTRATISTA` separado de `COTIZACION_EXTERNA`:** si el nombre, el RUT y el teléfono del contratista estuvieran en cada cotización, dependerían del contratista y no de la cotización (dependencia transitiva). Por eso se guardan una vez en `CONTRATISTA` y la cotización solo guarda `id_contratista`.
- **`ESPECIALIDAD` como tabla propia:** las especialidades externas (climatización, sistemas de emergencia, datos y conectividad, electricidad, seguridad) y el capítulo del itemizado que cubren se guardan una vez. La cotización registra la especialidad cotizada en esa obra, que puede ser distinta de la especialidad principal del contratista; por eso no es un dato redundante.
- **`CLIENTE` separado de `PRESUPUESTO`:** la razón social, el RUT y el correo dependen del cliente, no del presupuesto. El presupuesto solo guarda `id_cliente`.
- **`UNIDAD_MEDIDA` y `CAPITULO`:** la descripción de la unidad y el nombre del capítulo se guardan una vez. `CAPITULO` es jerárquica: cada capítulo apunta a su capítulo padre (`id_capitulo_padre`), así que un subcapítulo no repite el nombre de su capítulo principal.
- **`PARAMETRO_COSTO`:** los supuestos de costo (recargo de mano de obra nocturna y de fin de semana, gastos generales base) se guardan una vez y no en cada presupuesto. Si el Gerente cambia un parámetro, todos los cálculos lo usan de inmediato.

### 2.4. Campos calculados: se calculan, no se guardan
En la planilla As-Is se guardan el subtotal de cada línea, el costo directo, los gastos generales, la utilidad, el IVA y el total. Esos valores dependen de otros datos (por ejemplo, subtotal = cantidad × precio), así que guardarlos rompería la 3FN y arriesgaría inconsistencias: si cambia una cantidad y el total guardado no se actualiza, el presupuesto queda mal.

En el modelo To-Be **ninguna tabla guarda totales**. Se calculan con **vistas SQL** encadenadas, cada vez que se consultan:

| Vista | Calcula |
|---|---|
| `v_costo_partidas` | Suma de cantidad × precio aplicado de cada presupuesto |
| `v_costo_externos` | Suma de las cotizaciones externas seleccionadas |
| `v_presupuesto_costo` | Costo directo = partidas + externos |
| `v_presupuesto_neto` | Gastos generales y utilidad sobre el costo directo, y total neto |
| `v_presupuesto_totales` | IVA, total con IVA, totales en UF y UF/m² |
| `v_partida_vigencia` | Estado de cada precio: vigente, por revisar o vencido |

### 2.5. Desnormalización controlada: `precio_aplicado`
`DETALLE_PRESUPUESTO.precio_aplicado` repite el precio de la partida al momento de cotizar. Es una decisión deliberada, no un error de normalización. Un presupuesto emitido es un documento histórico: si mañana cambia el precio del catálogo, el presupuesto ya enviado al cliente no puede cambiar. Además, ese campo permite responder la pregunta del Gerente sobre qué tipo de precio se está usando (último, antiguo o ajustado a mano), comparándolo con `HISTORIAL_PRECIO`. Lo mismo ocurre con `PRESUPUESTO.valor_uf_dia`, que guarda la UF del día en que se elaboró.

## 3. Anomalías evitadas

| Anomalía | En la planilla (As-Is) | En el modelo (To-Be) |
|---|---|---|
| **Actualización** | Al cambiar el precio de una partida hay que corregirlo en cada planilla que la usa; si se olvida una, quedan precios distintos para lo mismo. | El precio vive solo en `PARTIDA`. Al cambiarlo, el precio anterior pasa a `HISTORIAL_PRECIO` y los presupuestos emitidos conservan su `precio_aplicado`. |
| **Inserción** | No hay dónde registrar un contratista o una partida nueva sin crear un presupuesto. | `CONTRATISTA` y `PARTIDA` existen por sí solas y se pueden registrar antes de usarlas. |
| **Borrado** | Al borrar la hoja de un presupuesto se pierden los datos del cliente y de los contratistas que solo aparecían ahí. | Clientes y contratistas están en sus propias tablas. Las claves foráneas impiden borrar un presupuesto o una partida en uso. |

## 4. Integridad y reglas de negocio en la base
- **Claves primarias y foráneas** en todas las relaciones (`ON UPDATE RESTRICT`).
- **`NOT NULL`, `UNIQUE` y `ENUM`** para datos obligatorios, RUT y correos únicos, y listas cerradas (estado, jornada, ubicación).
- **`CHECK`** para las reglas de negocio:
  - gastos generales entre 5 % y 12 %, con justificación sobre 10 % (RN-5);
  - utilidad entre 8 % y 25 %, con justificación fuera de 12–20 % (RN-8);
  - cada estado del presupuesto con su aprobador y sus fechas (RN-7);
  - cantidades y precios positivos;
  - formato de RUT.

Las pruebas que demuestran estas restricciones están en [`sql/pruebas_restricciones.sql`](../sql/pruebas_restricciones.sql).

## 5. Conclusión
El esquema relacional entrega una base transaccional sólida para Constructora Altura. Elimina la redundancia de las planillas y mantiene la trazabilidad de los precios en el tiempo (`HISTORIAL_PRECIO` y `precio_aplicado`). Además, calcula los totales siempre desde los datos, sin riesgo de que queden desactualizados, y puede crecer con nuevas partidas, clientes y contratistas sin cambios en su estructura.
