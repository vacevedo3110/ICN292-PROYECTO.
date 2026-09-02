# Requerimientos del Sistema

## 1. Actores y Roles
* **Gerente General (Principal):** Interactúa directamente con el sistema para crear presupuestos, actualizar el catálogo de precios y definir el porcentaje de margen.
* **Cliente (Secundario)** No interactúa con el sistema, pero es el destinatario final del documento (presupuesto).
* **Especialistas Externos (Externa):** Proveen información (cotizaciones de electricidad, constructores, etc.) que el Gerente ingresa al sistema.

## 2. Alcance (In / Out)
* **In:** 
  * Catálogo centralizado de precios de materiales.
  * Registro y actualización de variables económicas (UF).
  * Módulo de cálculo automatizado de presupuestos.
  * Generación y exportación del presupuesto final para el cliente.
* **Out:** 
  * Diseño arquitectónico.
  * Gestión de facturación, contabilidad o pago de remuneraciones.
  * Control de avance de obra.
 
## 3. Requisitos Funcionales (RF)
Estos requisitos están pensados para atacar los principales problemas detectados en la entrevista, reducir la demora de 0,5 a 3 días al armar presupuestos grandes, y eliminar el margen de error del 10% al 20%.

1. **RF1 [Must Have]:** El sistema debe permitir crear, editar y eliminar ítems en un catálogo centralizado  (Traza: Evita errores por planillas desactualizadas).
2. **RF2 [Must Have]:** El sistema debe calcular automáticamente el costo total multiplicando el valor unitario por la cantidad ingresada (Traza: Reduce el tiempo de cálculo manual).
3. **RF3 [Must Have]:** El sistema debe calcular y sumar automáticamente los "Gastos Generales", aplicando un porcentaje sobre el costo directo (Traza: Evita errores de omisión en el cálculo final).
4. **RF4 [Must Have]:** El sistema debe permitir registrar el valor diario de la UF para mantener las equivalencias financieras del presupuesto (Traza: Disminuye desvíos de costos por inflación).
5. **RF5 [Should Have]:** El sistema debe permitir ingresar y sumar los montos globales de las cotizaciones entregadas por especialistas externos (Traza: Consolida la información en un solo lugar).
6. **RF6 [Should Have]:** El sistema debe generar un reporte con el detalle del presupuesto para ser presentado al cliente (Traza: Reduce el tiempo de formateo y entrega).
7. **RF7 [Could Have]:** El sistema debe emitir una alerta visual si un precio unitario del catálogo base no ha sido actualizado en los últimos 6 meses (Traza: Control proactivo del margen de error del 10-20%).
8. **RF8 [Won't Have]:** El sistema debe permitir duplicar presupuestos históricos completos para usarlos como plantilla base en cotizaciones de casas con diseños similares (Traza: Acelera cotizaciones que pueden ser estandarizadas.)

## 4. Requisitos No Funcionales (RNF)
1. **RNF01 [Must Have]:** El sistema debe asegurar la consistencia de los datos mediante el uso de una base de datos relacional.
2. **RNF02 [Must Have]:** Los cálculos matemáticos del sistema deben ejecutarse y actualizar la interfaz en poco tiempo para asegurar fluidez. 
3. **RNF03 [Should Have]:** La interfaz de usuario debe ser compatible con navegadores web.
4. **RNF04 [Should Have]:** El acceso al sistema debe estar restringido mediante autenticación básica para uso exclusivo del dueño y/o de personas encargadas del mismo.
