# 01 — Requerimientos del sistema

## 1. Actores y roles
| Actor | Tipo | Rol en el sistema |
|---|---|---|
| **Gerente General** | Principal (usuario) | Define los porcentajes (gastos generales, utilidad), mantiene el catálogo de precios, revisa y **aprueba o rechaza** los presupuestos, y los emite. Es el único que aprueba (RN-7). |
| **Asistente** *(E2)* | Principal (usuario) | Elabora los presupuestos: registra partidas y cantidades, pide y registra las cotizaciones externas y envía el presupuesto a revisión. **No puede aprobar.** Corresponde a la «persona autorizada» de RF8 y RNF-04 de la E1. |
| **Cliente** | Secundario (externo) | No usa el sistema; recibe el presupuesto emitido por correo. |
| **Especialistas externos** | Externo | Entregan cotizaciones (climatización, sistemas de emergencia, datos y conectividad, electricidad, seguridad), que el Asistente registra. |
| **n8n** *(E2)* | Sistema externo | Envía automáticamente el presupuesto emitido al cliente por correo (Outlook). |

**Cambio respecto de la E1:** hoy el dueño hace todo. En el To-Be se separa **elaborar** (Asistente) de **aprobar** (Gerente General). Así el Gerente deja de calcular y solo revisa, que es el control que pide la RN-7.

## 2. Alcance
**Dentro del alcance (In)**
- Catálogo centralizado de partidas y precios, con unidad de medida y fecha de actualización.
- Variables económicas por presupuesto: valor de la UF, gastos generales, utilidad *(E2)* e IVA *(E2)*.
- Creación y edición de presupuestos, con cálculo automático de subtotales, costo directo, gastos generales, utilidad, IVA y totales en UF.
- Registro de cotizaciones de especialistas externos, separadas de las partidas propias.
- Control de vigencia de precios.
- Flujo de aprobación: Borrador → En revisión → Aprobado / Rechazado → Emitido.
- Documento estandarizado del presupuesto (PDF) y envío automático al cliente *(E2)*.
- Registro de fechas de inicio y término de obra, solo para medir plazos *(E2, pregunta del Gerente 3.3)*.

**Fuera del alcance (Out)**
- Diseño arquitectónico o planos.
- Facturación, contabilidad y remuneraciones.
- Control de avance físico de obras (la planificación sigue en las cartas Gantt de la empresa).
- Compras, bodegas e inventarios.
- Pago a proveedores o contratistas.
- CRM o gestión comercial posterior a la cotización.
- Aplicación móvil.

## 3. Reglas de negocio
| ID | Regla |
|---|---|
| RN-1 | Un presupuesto pertenece a un único cliente; un cliente puede tener varios presupuestos. |
| RN-2 | El valor de la UF usado queda guardado en el presupuesto. |
| RN-3 | Cada precio del catálogo registra su fecha de última actualización. |
| RN-4 | Vigencia de precios: vigente < 3 meses, por revisar 3–6 meses, vencido > 6 meses. *(E2: la empresa actualiza precios con cada obra nueva, cada 3 a 6 meses.)* |
| RN-5 | Gastos generales sobre el costo directo, entre 5 % y 12 %, según ubicación, jornada y fines de semana; sobre 10 % hay que justificar. *(E2: reemplaza diurna 5–8 % / nocturna 8–12 %.)* |
| RN-6 | Las cotizaciones externas se registran separadas de las partidas propias; solo la seleccionada entra al costo. |
| RN-7 | Solo el Gerente General aprueba o rechaza un presupuesto; sin aprobación no se emite. *(E2: el Asistente no puede aprobar.)* |
| RN-8 *(E2)* | Utilidad sobre el costo directo, habitual 12–20 %; fuera de ese rango (8–25 %) hay que justificar. |
| RN-9 *(E2)* | Cada presupuesto incluye el IVA (19 %). |

## 4. Requisitos funcionales
| ID | Prioridad | Requisito | Problema que ataca |
|---|---|---|---|
| RF1 | Must | Registrar, editar y desactivar partidas del catálogo, con unidad, precio y fecha de actualización. | Precios dispersos en planillas. |
| RF2 | Must | Crear y editar presupuestos asociados a un único cliente. | Pérdida de información. |
| RF3 | Must | Calcular automáticamente el subtotal de cada línea (cantidad × precio aplicado). | Errores de cálculo manual. |
| RF4 | Must | Calcular automáticamente el costo directo, los gastos generales, la utilidad, el IVA y los totales en UF. | Omisiones al cerrar el presupuesto. |
| RF5 | Must | Registrar en cada presupuesto la UF, la jornada, la ubicación y los porcentajes usados. | Trazabilidad de las variables. |
| RF6 | Should | Registrar cotizaciones de especialistas externos (especialidad, contratista, monto, fechas) y seleccionar la que entra al costo. | Espera de terceros sin control. |
| RF7 | Must | Identificar los precios por revisar o vencidos y avisar antes de emitir. | Error de 10–20 % por precios desactualizados. |
| RF8 | Must | Controlar el estado del presupuesto y bloquear su emisión hasta que el Gerente General lo apruebe. | Envíos sin revisión final. |
| RF9 | Should | Generar un documento estandarizado (PDF) con partidas, externos, gastos generales, utilidad, IVA y total. | Tiempo de formateo. |
| RF10 *(E2)* | Should | Enviar automáticamente el presupuesto emitido al cliente por correo (n8n + Outlook) y registrar cada envío. | Envío manual y sin registro. |

## 5. Requisitos no funcionales
| ID | Prioridad | Requisito |
|---|---|---|
| RNF-01 | Must | Base de datos relacional con restricciones de integridad (PK, FK, CHECK). |
| RNF-02 | Must | Cálculos en tiempo interactivo, sin esperas perceptibles. |
| RNF-03 | Should | Interfaz web de escritorio, sin software propietario. |
| RNF-04 | Should | Acceso con autenticación y dos roles: Gerente General y Asistente *(E2)*. |
| RNF-05 | Must | Prototipo ejecutable en localhost siguiendo el README. |
