# Modelo de Datos y Normalización (3FN)

## 1. Introducción
El presente documento detalla la justificación técnica del diseño de la base de datos relacional para el Sistema de Gestión de Presupuestos de Inversiones Rumay Limitada (Constructora Altura). El modelo de datos ha sido estructurado garantizando el cumplimiento de la Tercera Forma Normal (3FN), asegurando la integridad referencial y eliminando anomalías de actualización, inserción y borrado que presentaba el modelo As-Is basado en planillas[cite: 10, 11].

## 2. Justificación de Normalización

### 2.1. Primera Forma Normal (1FN): Resolución de atributos multivaluados
La 1FN exige que todos los atributos de una tabla sean atómicos (indivisibles) y monovalorados. En el levantamiento inicial de la PYME, un cliente podía tener múltiples números de contacto (ej. celular personal, teléfono de oficina). 
- **Solución implementada:** Se extrajo el atributo de teléfonos de la tabla principal `CLIENTE` y se creó la entidad débil `TELEFONO_CLIENTE`. Esta nueva tabla utiliza una clave primaria compuesta (`id_cliente`, `nro_telefono`) y cuenta con el campo `tipo_telefono` para clasificar la naturaleza del contacto. De esta manera, se elimina la necesidad de crear columnas redundantes como `telefono_1` o `telefono_2`, cumpliendo a cabalidad con la 1FN.

### 2.2. Segunda Forma Normal (2FN): Dependencia funcional completa
La 2FN requiere que el modelo esté en 1FN y que todos los atributos no clave dependan funcionalmente por completo de la clave primaria.
- **Solución implementada:** En tablas con claves compuestas como `DETALLE_PRESUPUESTO` (cuyas PK son `id_presupuesto` y `nro_linea`), los atributos como `cantidad` y `precio_aplicado` dependen exclusivamente de la combinación de ambas claves. Ningún atributo depende solo de una parte de la clave. Del mismo modo, en `COTIZACION_EXTERNA`, el `monto_cotizado` y la `fecha_recepcion` dependen totalmente del proyecto en cuestión y de la cotización específica, satisfaciendo la 2FN.

### 2.3. Tercera Forma Normal (3FN): Eliminación de dependencias transitivas y campos calculados
La 3FN exige que el modelo esté en 2FN y que no existan dependencias transitivas entre atributos no clave (ningún atributo no clave debe depender de otro atributo no clave).

- **Separación de `CONTRATISTA` y `COTIZACION_EXTERNA`:** Si los datos del especialista externo (nombre, especialidad, teléfono) se hubieran incluido directamente en la tabla transaccional de cotizaciones, estos habrían dependido del RUT del contratista y no de la clave primaria de la cotización, generando una dependencia transitiva. Para evitar esta anomalía y alcanzar la 3FN, se creó la entidad maestra `CONTRATISTA`[cite: 12] y se enlazó a `COTIZACION_EXTERNA`[cite: 12] mediante la clave foránea `id_contratista`.

- **Eliminación de campos calculados:** En el proceso actual (As-Is)[cite: 9, 10], es habitual almacenar el subtotal por línea o el costo directo total dentro de las planillas. En nuestro diseño To-Be, estos campos fueron estrictamente eliminados de `PRESUPUESTO` y `DETALLE_PRESUPUESTO`. Almacenar un "subtotal" generaría una dependencia funcional directa sobre la `cantidad` y el `precio_aplicado`. Su eliminación evita anomalías de actualización y pérdida de integridad; en la arquitectura lógica propuesta, estos valores son calculados de manera automatizada en tiempo de ejecución por la lógica de negocio (Python/n8n)[cite: 11, 14], asegurando el cumplimiento íntegro de la 3FN.

## 3. Conclusión
El esquema relacional propuesto entrega una base transaccional sólida para Constructora Altura. Permite mantener la trazabilidad histórica de los precios al momento de cotizar (mediante el campo `precio_aplicado`)[cite: 11, 13] y escalar a futuro sin riesgo de redundancia estructural.
