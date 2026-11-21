# Declaración de uso de Inteligencia Artificial

## Herramientas utilizadas
- **Claude** (Anthropic)
- **ChatGPT** (OpenAI) 

## Para qué se usó

### Claude
- **Limpieza de datos:** ordenar el itemizado real de la empresa (unidades, códigos, partidas sin precio) y registrar cada cambio en un archivo de trazabilidad.
- **Base de datos:** apoyar la escritura y depuración del código SQL (esquema, datos de demostración, vistas y consultas) en `schema.sql`, `seed.sql`, `consultas.sql` y `pruebas_restricciones.sql`.
- **Aplicación:** (mayormente se usó en este punto) para generar y apoyar la programación de la aplicación web en Streamlit y sus pruebas.

### ChatGPT
- **Informe:** apoyar la organización y redacción del informe de la Entrega 2.

## Qué hizo el equipo
- Levantó el caso con la empresa (entrevistas, itemizado real, reglas de gastos generales, utilidad y plazos) y definió los requerimientos, los BPMN y el modelo de la E1.
- Decidió el alcance, el motor (MySQL) y las reglas de negocio, y validó las inferencias con la información de la empresa.
- Realizó la parte técnica: la normalización en 3FN del diagrama entidad-relación y la creación de la base de datos.
- Realizó, revisó, corrigió y simplificó el código SQL y de la aplicación, verificó los cambios propuestos por la IA y probó que corra en MySQL 8.
- Interpretó los resultados de las consultas y redactó el informe y la presentación.

## Verificación
El equipo revisó, ejecutó y validó todo el material generado:
- `schema.sql` + `seed.sql` cargan sin errores en MySQL 8,
- las consultas reproducen los resultados de `docs/04-sql-consultas.md`,
- las pruebas de restricciones y de reglas de la app dan los resultados esperados,
- todo el trabajo realizado por la IA fue revisado posteriormente por los integrantes del grupo.
