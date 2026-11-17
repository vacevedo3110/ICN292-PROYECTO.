# Declaración de uso de Inteligencia Artificial

## Herramienta utilizada
- **Claude** (Anthropic), como asistente de programación y redacción durante la Entrega 2.

## Para qué se usó
Uso de la IA 

## Para qué se usó
- **Limpieza de datos:** ordenar el itemizado real de la empresa (unidades, códigos, partidas sin precio) y registrar cada cambio en un archivo de trazabilidad.
- **Base de datos:** corregir y probar `schema.sql`, `seed.sql`, `consultas.sql` y `pruebas_restricciones.sql`.
- **Aplicación:** (Mayormente se uso en este punto) para generar y apoyar en la programación de la aplicación web en Streamlit y sus pruebas.
  
## Qué hizo el equipo
- Levantó el caso con la empresa (entrevistas, itemizado real, reglas de gastos generales, utilidad y plazos) y definió los requerimientos, los BPMN y el modelo de la E1.
- Decidió el alcance, el motor (MySQL) y las reglas de negocio, y validó las inferencias con la información de la empresa.
- Realizó la parte técnica, normalizacion en 3fn del diagrama entidad-relacion, y la creacion de la base de datos.
- Realizó, Revisó, corrigió y simplificó el código SQL y de la aplicación, verificó los cambios propuestos por la IA y se probó que corra en MySQL 8.
- Interpretó los resultados de las consultas y redactó el informe y la presentación.

## Verificación
Todo el código se ejecutó y se probó:
- `schema.sql` + `seed.sql` cargan sin errores en MySQL 8;
- las consultas reproducen los resultados de `docs/04-sql-consultas.md`;
- las pruebas de restricciones y de reglas de la app dan los resultados esperados.
- todo el trabajo realizado por la IA fue revisado posteriormente por los integrantes del grupo. 

