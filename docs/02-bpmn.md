# 02 — Modelado de procesos (BPMN 2.0)

Este documento explica el proceso actual de presupuestación de Inversiones Rumay Limitada (As-Is) y el proceso propuesto con el nuevo sistema (To-Be final). Ambos diagramas se organizan en las mismas cuatro fases (**Levantamiento, Diseño, Presupuestación y Cierre**) para que la comparación sea directa.

| Archivo | Contenido |
|---|---|
| [`assets/BPMN 2.0 AS IS Rumay.png`](../assets/BPMN%202.0%20AS%20IS%20Rumay.png) | Proceso As-Is (Bizagi). |
| [`assets/BPMN-TO-BE-final.png`](../assets/BPMN-TO-BE-final.png) | Proceso To-Be final de la Entrega 2. |
| [`assets/BPMN-TO-BE-final.bpmn`](../assets/BPMN-TO-BE-final.bpmn) | Fuente del To-Be final en BPMN 2.0 XML. Se abre en Bizagi Modeler o en cualquier modelador BPMN 2.0 (ver sección 4). |
| [`assets/BPMN TO-BE.png`](../assets/BPMN%20TO-BE.png) | To-Be de la Entrega 1. Se conserva solo como referencia para la sección 3. |

## 1. Proceso actual (As-Is)

![BPMN As-Is](../assets/BPMN%202.0%20AS%20IS%20Rumay.png)

Todo el proceso depende del Gerente General y de cálculos manuales en planillas Excel no estandarizadas.

1. **Levantamiento:** el cliente contacta a la empresa y se agenda una reunión para definir los requerimientos del proyecto.
2. **Diseño:** se verifica si el cliente tiene planos; si no, la constructora elabora el proyecto. La fase termina cuando el cliente aprueba el diseño.
3. **Presupuestación (cuello de botella):** el Gerente abre una planilla base, selecciona las partidas, ingresa cantidades y actualiza a mano los precios unitarios, según su conocimiento del mercado o compras recientes. Si la obra requiere especialistas (electricidad, climatización, etc.), el proceso se detiene hasta que los contratistas envían sus valores.
4. **Cierre:** el Gerente aplica a mano los gastos generales (habitualmente 5, 8 o 10 %, hasta 12 %, según ubicación, jornada y fines de semana) y la utilidad (12–20 %), consolida la planilla, la exporta y la envía al cliente por correo.

**Problemas:** cerca de 3 días por cotización y un margen de error de 10–20 % por precios desactualizados y errores de tipeo.

## 2. Proceso propuesto (To-Be final)

![BPMN To-Be final](../assets/BPMN-TO-BE-final.png)

### Participantes

| Pool / carril | Rol en el proceso |
|---|---|
| **Inversiones Rumay Limitada (Constructora Altura)** — carril *Gerente General* | Atiende al cliente en levantamiento y diseño, revisa el presupuesto, confirma los porcentajes, lo aprueba o rechaza y lo emite. |
| Mismo pool — carril *Sistema de presupuestos (app + n8n)* | Calcula subtotales y totales, alerta precios por revisar o vencidos, envía el presupuesto (n8n) y registra el resultado del envío. |
| Mismo pool — carril *Asistente* | Registra al cliente, elabora el presupuesto, actualiza precios del catálogo, gestiona las cotizaciones externas y corrige los presupuestos rechazados. |
| **Cliente** (pool externo) | Solicita el presupuesto, entrega requerimientos, aprueba el diseño y recibe el presupuesto. |
| **Especialistas Externos** (pool externo) | Responden las solicitudes de cotización. |

Los pools externos se comunican con la constructora solo mediante flujos de mensaje. Las tareas de personas son **tareas de usuario** (se ejecutan en la app) y las del sistema son **tareas de servicio**.

### Flujo por fase

**Fase 1 — Levantamiento.** El proceso parte con el mensaje «Solicitud de presupuesto» del cliente. El Gerente ejecuta el subproceso colapsado «Levantar requerimientos del proyecto» (reunión con el cliente, igual que en el As-Is).

**Fase 2 — Diseño.** El subproceso colapsado «Elaborar y validar diseño con el cliente» agrupa los pasos del As-Is: verificar si hay planos, elaborar el proyecto, presentarlo y ajustarlo. Si el cliente no lo aprueba, el gateway «¿Diseño aprobado?» termina el proceso en «Proyecto no concretado». Ambas fases quedan colapsadas porque son el núcleo comercial del negocio y el sistema no las modifica.

**Fase 3 — Presupuestación** (Asistente y Sistema).
1. «¿Cliente nuevo?»: si lo es, el Asistente lo registra; si no, lo selecciona desde la base.
2. «Crear presupuesto en borrador»: condiciones de la obra (ubicación, jornada, fines de semana) y porcentajes de gastos generales, utilidad e IVA. La app propone la UF del día.
3. «Seleccionar partidas del catálogo e ingresar cantidades».
4. El Sistema calcula los subtotales y alerta los precios por revisar o vencidos (RN-4). Si hay alertas, el Asistente actualiza los precios en el catálogo (el precio anterior pasa a `HISTORIAL_PRECIO`) y el Sistema vuelve a calcular.
5. «¿Requiere especialistas externos?»: si es así, el Asistente solicita las cotizaciones, espera cada «Cotización recibida» (evento intermedio de mensaje), las registra hasta que no falte ninguna y selecciona una por especialidad.
6. El Sistema calcula los totales (costo directo, gastos generales, utilidad, IVA y UF) y el Asistente envía el presupuesto a revisión.

**Fase 4 — Cierre.**
1. El Gerente revisa el presupuesto y confirma los gastos generales y la utilidad. Todo cambio que altere el costo queda registrado con su motivo en `CORRECCION_PRESUPUESTO`.
2. «¿Aprueba el presupuesto?»: si no, queda **Rechazado**; el Asistente lo corrige y lo reabre como borrador, y vuelve al cálculo de totales y a revisión. Si aprueba, queda **Aprobado** y el Gerente lo emite.
3. «Enviar presupuesto al cliente» (tarea de servicio, n8n) envía el PDF por correo, y «Registrar resultado del envío» lo guarda en `ENVIO_PRESUPUESTO`.
4. «¿Envío exitoso?»: si falló, el Asistente verifica el correo del cliente y se reintenta el envío. Si salió, el proceso termina en «Presupuesto enviado al cliente».

### Trazabilidad con el modelo de datos

Cada tarea del To-Be lee o escribe datos del modelo de [`03-modelo-datos.md`](./03-modelo-datos.md). El estado del presupuesto sigue el `ENUM` de `PRESUPUESTO.estado` y la restricción `ck_ppto_rn7` de [`sql/schema.sql`](../sql/schema.sql). Los requisitos y reglas usan la numeración del informe E1 (RF1–RF9, RN-1 a RN-7) más los agregados de la E2 (RF10, RN-8 y RN-9; ver [`CHANGELOG.md`](./CHANGELOG.md)).

| Tarea (carril) | Estado del presupuesto | Requisito / regla | Tablas o vistas |
|---|---|---|---|
| Registrar cliente (Asistente) | — | RN-1 | `CLIENTE`, `TELEFONO_CLIENTE` |
| Crear presupuesto en borrador (Asistente) | → Borrador | RF2, RF5, RN-2, RN-5, RN-8, RN-9 | `PRESUPUESTO` |
| Seleccionar partidas del catálogo e ingresar cantidades (Asistente) | Borrador | RF2 | `DETALLE_PRESUPUESTO`, `PARTIDA` |
| Calcular subtotales y alertar precios por revisar o vencidos (Sistema) | Borrador | RF3, RF7, RN-4 | `v_costo_partidas`, `v_partida_vigencia` |
| Actualizar precios en el catálogo (Asistente) | Borrador | RF1, RN-3 | `PARTIDA`, `HISTORIAL_PRECIO` |
| Solicitar cotizaciones a especialistas (Asistente) | Borrador | RF6, RN-6 | `COTIZACION_EXTERNA` (`fecha_solicitud`, monto vacío), `CONTRATISTA`, `ESPECIALIDAD` |
| Registrar cotización recibida (Asistente) | Borrador | RF6 | `COTIZACION_EXTERNA` (`monto_cotizado`, `fecha_recepcion`) |
| Seleccionar cotización por especialidad (Asistente) | Borrador | RF6 | `COTIZACION_EXTERNA` (`seleccionada`) |
| Calcular totales: costo directo, GG, utilidad, IVA y UF (Sistema) | Borrador | RF4, RN-5, RN-8, RN-9 | `v_costo_externos`, `v_presupuesto_totales` |
| Enviar presupuesto a revisión (Asistente) | Borrador → En revisión | RF8, RN-7 | `PRESUPUESTO.estado` |
| Revisar presupuesto y confirmar gastos generales y utilidad (Gerente) | En revisión | RF8, RN-5, RN-7, RN-8 | `CORRECCION_PRESUPUESTO` |
| «¿Aprueba el presupuesto?» Sí / No (Gerente) | → Aprobado / → Rechazado | RF8, RN-7 | `PRESUPUESTO` (`id_usuario_aprobador`, `fecha_aprobacion`) |
| Corregir presupuesto y reabrir como borrador (Asistente) | Rechazado → Borrador | RF8, RN-7 | `PRESUPUESTO.estado` |
| Emitir presupuesto (Gerente) | Aprobado → Emitido | RF8, RF9 | `PRESUPUESTO.fecha_emision` |
| Enviar presupuesto al cliente (Sistema, n8n) | Emitido | RF10 | Webhook de n8n |
| Registrar resultado del envío (Sistema) | Emitido | RF10 | `ENVIO_PRESUPUESTO` (`resultado`: Enviado / Error) |
| Verificar correo del cliente (Asistente) | Emitido | RF10 | `ENVIO_PRESUPUESTO` (historial de intentos) |

### Automatización con n8n

La única tarea del To-Be que ejecuta n8n es **«Enviar presupuesto al cliente»**. Se activa con el presupuesto en estado Emitido, cuando el usuario pulsa *Enviar presupuesto* en la app: la app genera el PDF y lo envía al webhook, y n8n lo convierte en archivo y lo despacha por SMTP desde la cuenta corporativa. n8n responde 200 si el correo salió y 500 si falló. Con esa respuesta, la app ejecuta «Registrar resultado del envío» y el gateway «¿Envío exitoso?» decide si el proceso termina o se reintenta.

Las demás tareas del carril Sistema las ejecuta la app (Streamlit) con las vistas de MySQL. El flujo, sus nodos y la prueba realizada están en [`05-n8n.md`](./05-n8n.md).

## 3. Cambios respecto de la Entrega 1

Comparación con el To-Be de la E1 ([`assets/BPMN TO-BE.png`](../assets/BPMN%20TO-BE.png)).

| Cambio | Motivo |
|---|---|
| Se agrega el carril **Asistente**, y el Gerente General deja de elaborar el presupuesto. | La app y la base tienen dos roles (`USUARIO.rol`). Separar elaborar de aprobar descarga al Gerente del cálculo y le da sentido a la RN-7 (solo el Gerente aprueba). |
| El carril del sistema pasa a ser **Sistema de presupuestos (app + n8n)** y suma «Enviar presupuesto al cliente» y «Registrar resultado del envío». | En la E1 el sistema solo calculaba; en la E2 también envía el presupuesto y deja registro del envío. |
| «Revisar presupuesto calculado» y «¿Presupuesto correcto?» se reemplazan por la revisión del Gerente y el gateway **«¿Aprueba el presupuesto?»**, con retorno a borrador. | Refleja el flujo real de la app: Borrador → En revisión → Aprobado / Rechazado → Emitido. |
| Se agrega **«Emitir presupuesto»** antes del envío. | La app solo permite enviar presupuestos en estado Emitido. |
| **«Enviar presupuesto al cliente»** pasa de tarea manual del Gerente a tarea de servicio automatizada con n8n. | La app genera el PDF y n8n lo envía por SMTP desde la cuenta corporativa. Ver [`05-n8n.md`](./05-n8n.md). |
| Se agregan **«¿Envío exitoso?»** y **«Verificar correo del cliente»**, con reintento. | n8n responde 200 o 500 y la app guarda el resultado (Enviado / Error) en `ENVIO_PRESUPUESTO`. |
| En las cotizaciones externas se agrega **«Seleccionar cotización por especialidad»**. | Solo la cotización seleccionada suma al costo. Las fechas de solicitud y recepción permiten medir la espera, que es el cuello de botella real: los presupuestos con externos demoran 7–8 días. |
| «Crear presupuesto y registrar cliente y proyecto» se separa en **«¿Cliente nuevo?»**, **«Registrar cliente»** y **«Crear presupuesto en borrador»**. | En 3FN el cliente existe por sí solo y se reutiliza entre presupuestos. |
| «Registrar UF día, jornada y porcentaje de gastos generales» se integra en **«Crear presupuesto en borrador»**, y el Gerente confirma los porcentajes al revisar. | Así funciona el formulario de la app, que además propone la UF del día. |
| El subproceso de levantamiento y diseño se divide en dos, uno por fase, y se recupera la salida **«Proyecto no concretado»** del As-Is. | Permite usar las mismas fases del As-Is. |
| Se incorporan las **cuatro fases** del As-Is, el pool principal toma el nombre de la empresa y el diagrama se modela en Bizagi, igual que el As-Is. | Facilita comparar ambos procesos fase por fase. |
| Gastos generales: 5–12 % según ubicación, jornada y fines de semana; se agregan la utilidad (12–20 %) y el IVA. | Información de la entrevista final con la empresa; reemplaza la regla de la E1 (diurna 5–8 %, nocturna 8–12 %). |

## 4. Abrir y editar el diagrama

1. En Bizagi Modeler: pestaña **Exportar/Importar** → grupo **Importar** → **BPMN**, y seleccionar [`assets/BPMN-TO-BE-final.bpmn`](../assets/BPMN-TO-BE-final.bpmn).
2. Las cuatro fases se agregan en Bizagi con el elemento *Fase* (*Milestone*), porque no forman parte del estándar BPMN 2.0 XML y no se guardan en el archivo `.bpmn`.
3. El archivo también se abre en [bpmn.io](https://demo.bpmn.io) o Camunda Modeler. Cada tarea trae en su documentación el requisito, la regla y las tablas que usa.
