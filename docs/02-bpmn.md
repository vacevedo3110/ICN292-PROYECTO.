# 02 — Modelado de procesos (BPMN 2.0)

Este documento explica el proceso actual de presupuestación de Inversiones Rumay Limitada (As-Is) y el proceso propuesto con el nuevo sistema (To-Be). Los diagramas están en `assets/`:

Ambos diagramas se organizan en las mismas cuatro fases (**Levantamiento, Diseño, Presupuestación y Cierre**) para que la comparación sea directa.

## 1. Proceso actual (As-Is)
Todo el proceso depende del Gerente General y de cálculos manuales en planillas Excel no estandarizadas.

1. **Levantamiento:** el cliente contacta a la empresa y se agenda una reunión para definir los requerimientos del proyecto.
2. **Diseño:** se verifica si el cliente tiene planos; si no, la constructora elabora el proyecto. La fase termina cuando el cliente aprueba el diseño.
3. **Presupuestación (cuello de botella):** el Gerente abre una planilla base, selecciona las partidas, ingresa cantidades y actualiza a mano los precios unitarios, según su conocimiento del mercado o compras recientes. Si la obra requiere especialistas (electricidad, climatización, etc.), el proceso se detiene hasta que los contratistas envían sus valores.
4. **Cierre:** el Gerente aplica a mano los gastos generales (habitualmente 5, 8 o 10 %, hasta 12 %, según ubicación, jornada y fines de semana) y la utilidad (12–20 %), consolida la planilla, la exporta y la envía al cliente por correo.

**Problemas:** cerca de 3 días por cotización y un margen de error de 10–20 % por precios desactualizados y errores de tipeo.

## 2. Proceso propuesto (To-Be)

### Participantes
| Pool / carril | Rol |
|---|---|
| **Constructora Altura** — carril *Gerente General* | Define porcentajes, revisa y aprueba o rechaza, y emite. |
| **Constructora Altura** — carril *Asistente* | Elabora el presupuesto en el sistema y gestiona las cotizaciones externas. |
| **Constructora Altura** — carril *Sistema (app + n8n)* | Calcula, alerta, genera el PDF y envía el presupuesto. |
| **Cliente** (pool externo) | Entrega requerimientos, aprueba el diseño y recibe el presupuesto. |
| **Especialistas externos** (pool externo) | Responden las solicitudes de cotización. |

Los pools externos se comunican con la constructora solo mediante flujos de mensaje.

### Flujo por fase
1. **Levantamiento y Diseño (subproceso colapsado):** «Levantar requerimientos y validar diseño con el cliente». Se mantiene igual que en el As-Is, porque es el núcleo comercial del negocio y el sistema no lo modifica.
2. **Presupuestación:**
   - El Asistente crea el presupuesto en el sistema y selecciona las partidas desde el catálogo centralizado, con precios actualizados.
   - El Sistema calcula los subtotales y el costo directo, y avisa si hay precios por revisar o vencidos.
   - Si la obra requiere especialistas (gateway XOR), el Asistente solicita las cotizaciones (flujo de mensaje a Especialistas externos), registra las recibidas y selecciona la que entra al costo.
   - El Asistente envía el presupuesto a revisión.
3. **Cierre:**
   - El Gerente General revisa el presupuesto, define o confirma los gastos generales y la utilidad (con justificación si salen del rango habitual), y el Sistema calcula los totales, el IVA y los valores en UF.
   - **Gateway XOR «¿Aprueba?»:** si rechaza, el presupuesto vuelve al Asistente (Borrador) para corregirlo. Si aprueba, el Gerente lo emite.
   - **«Enviar presupuesto al cliente» (tarea de servicio, n8n):** el sistema genera el PDF y n8n lo envía por correo (Outlook) al cliente (flujo de mensaje al pool Cliente), y registra el envío. Ver [`05-automatizacion-n8n.md`](./05-automatizacion-n8n.md).

## 3. Cambios respecto de la Entrega 1
| Cambio | Motivo |
|---|---|
| Se agrega el carril **Asistente** | La app y la base tienen dos roles. Separar elaborar de aprobar descarga al Gerente del cálculo y le da sentido a la RN-7 (solo el Gerente aprueba). |
| Se agrega el carril **Sistema (app + n8n)** | Deja visibles las tareas automatizadas: cálculo, alertas de precios, PDF y envío. |
| La aprobación pasa a ser un **gateway XOR con retorno a Borrador** | Refleja el flujo real del sistema: Borrador → En revisión → Aprobado / Rechazado → Emitido. |
| Enviar presupuesto al cliente» (tarea de servicio, n8n)| la app genera el PDF y n8n lo envía al cliente por **SMTP** desde la cuenta corporativa. La app registra el resultado del envío. Ver [documentación de n8n](./05-n8n.md).
| Las **cotizaciones externas** quedan expandidas, con flujos de mensaje | Son el cuello de botella real: los presupuestos con externos demoran 7–8 días. |
| Se mantienen las **cuatro fases** del As-Is | Facilita comparar ambos procesos fase por fase. |
| Gastos generales: 5–12 % según ubicación, jornada y fines de semana; se agregan la utilidad (12–20 %) y el IVA | Información de la entrevista final con la empresa; reemplaza la regla de la E1 (diurna 5–8 %, nocturna 8–12 %). |
