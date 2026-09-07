# Modelo Entidad-Relación (ER) Preliminar

Aquí presentamos la estructura propuesta para la base de datos del sistema de Inversiones Rumay Limitada. El objetivo de este modelo es resolver el problema de la información dispersa, automatizar los cálculos de los presupuestos y eliminar los errores que se generan al depender de la memoria del gerente y de múltiples Excel desactualizados. 

La imagen estática del Diagrama ER está guardada en la carpeta `assets/`.

## 1. Entidades Principales y Justificación

Para que el proceso automatizado (*To-Be*) funcione, definimos las siguientes tablas principales:

* **Cliente:**
  * **Atributos base:** ID_Cliente (PK), Nombre/Razón Social, RUT, Teléfono, Correo.
  * **Justificación:** Nos sirve para identificar al dueño de la obra y mantener un historial claro de a quién se le cotiza cada proyecto.

* **Presupuesto (Proyecto):**
  * **Atributos base:** ID_Presupuesto (PK), ID_Cliente (FK), Fecha_Creacion, Valor_UF_Dia, Tipo_Jornada (Diurna/Nocturna), Porcentaje_Gastos_Generales, Monto_Total.
  * **Justificación:** Guarda el valor de la UF del día para proteger los márgenes frente a la inflación, y registra el tipo de jornada para que el software aplique automáticamente el recargo correcto por gastos generales e imprevistos (5-8% u 8-12%).

* **Partida_Catalogo (Mantenedor de Precios):**
  * **Atributos base:** ID_Partida (PK), Descripcion, Unidad_Medida (ej. m2, ml, global), Precio_Unitario_Referencial, Ultima_Actualizacion.
  * **Justificación:** Funciona como el único catálogo oficial de precios de la constructora. Al centralizar la actualización aquí, nos libramos de los errores por usar versiones viejas de Excel.

* **Detalle_Presupuesto (Relación N:M):**
  * **Atributos base:** ID_Detalle (PK), ID_Presupuesto (FK), ID_Partida (FK), Cantidad_Ingresada, Precio_Aplicado, Subtotal.
  * **Justificación:** Es la tabla intermedia que une las partidas con cada obra específica. Aquí es donde el gerente ingresa los metros cuadrados o unidades requeridas, y el sistema cruza los datos para ejecutar la multiplicación automática del subtotal.

* **Especialidad_Externa (Cotizaciones de Terceros):**
  * **Atributos base:** ID_Especialidad (PK), ID_Presupuesto (FK), Tipo_Especialidad (Ej: Climatización, Electricidad), Nombre_Contratista, Monto_Cotizado.
  * **Justificación:** Como el gerente subcontrata estas áreas, esta tabla nos permite sumar esos montos globales directamente al total del presupuesto, sin mezclarlos ni ensuciar el cálculo de las partidas de construcción directa.

## 2. Reglas de Negocio en el Modelo
* Un **Cliente** puede cotizar y tener asociados uno o muchos **Presupuestos** a lo largo del tiempo.
* Cada **Presupuesto** pertenece exclusivamente a un **Cliente**.
* Un **Presupuesto** está compuesto por uno o muchos **Detalles** (los cuales extraen su información de la tabla **Partida_Catalogo**).
* Un **Presupuesto** puede tener cero, una o muchas **Especialidades_Externas** asociadas, lo cual dependerá exclusivamente de la complejidad técnica de la obra.
