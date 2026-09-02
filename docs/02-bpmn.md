# Modelado de Procesos (BPMN)

En este documento se explica la lógica del flujo de trabajo de Inversiones Rumay Limitada, detallando el proceso manual actual AS-IS, para luego presentar el proceso TO-BE que corresponde a la mejora del nuevo Sistema. Los diagramas visuales correspondientes se encuentran en la carpeta `assets/`.

## 1. Proceso Actual (As-Is)
El proceso actual del presupuesto está centralizado en el Gerente General y depende de cálculos manuales en planillas no estandarizadas. El flujo es el siguiente:

* **Levantamiento inicial:** El proceso inicia cuando un cliente contacta a la empresa. Se agenda una reunión para los requerimientos del proyecto de construcción y definir necesidades del cliente final. 
* **Diseño y validación:** Se verifica si el cliente final posee planos. De no tenerlos, la constructora elabora un proyecto. Esta fase finaliza cuando el cliente aprueba el diseño.
* **Cálculo de costos (Cuello de botella):** El gerente abre una planilla Excel base y selecciona los materiales a utilizar y todos los costos de partida. Ingresa las cantidades (ej. metros cuadrados) y actualiza los precios unitarios de forma manual, basándose en su conocimiento del mercado o compras recientes.
* **Cotizaciones externas:** Si la obra requiere especialistas (electricidad, climatización), el proceso se pausa a la espera de que los contratistas externos envíen sus valores.
* **Cierre financiero:** Se aplican los gastos generales de forma manual, los cuales varían entre un 5% y un 8% para obras diurnas, y entre un 8% y un 12% para obras nocturnas (estos porcentajes absorben los imprevistos). Finalmente, se consolida la información y se envía al cliente.
  
## 2. Proceso Propuesto (To-Be)
El nuevo modelo optimiza la fase de cálculo y cierre, automatizando las tareas repetitivas y reduciendo el margen de error del 10% al 20% asociado a precios desactualizados o fallas de tipeo.

* **Fase comercial intacta:** El contacto, información y diseño con el cliente se mantienen sin alteraciones, al ser el núcleo estratégico del negocio.
* **Selección automatizada:** Al iniciar la cotización, el gerente interactúa con el sistema seleccionando las partidas constructivas desde un catálogo centralizado (base de datos) que contiene los precios unitarios ya actualizados.
* **Cálculo instantáneo:** El sistema multiplica automáticamente las cantidades ingresadas por los valores unitarios, reduciendo el tiempo de operación.
* **Consolidación de externos:** Los valores enviados por los especialistas se ingresan como un monto global directamente en un módulo específico del presupuesto.
* **Cálculo de márgenes y exportación:** El gerente selecciona el tipo de jornada de la obra y el sistema aplica el porcentaje exacto de gastos generales sobre el costo directo. Para finalizar, el sistema genera el reporte estandarizado listo para entrega al cliente.
