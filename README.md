# Proyecto ICN292 Sistema de presupuestos para Constructora Altura

ICN-292 Sistemas de Información para la Gestión Universidad Técnica Federico Santa María 

## 1. Contexto del proyecto
* **Empresa:** Inversiones Rumay Limitada
* **Rubro:** Construcción (RUT 76.380.707-K)
* **Aclaración:** La constructora usa el nombre "Constructora Altura", pero opera ante el SII como "Inversiones Rumay Ltda.".
* **Problema:** El dueño hace todos los cálculos de costos a mano. Entregar una cotización demora unos 3 días y la estimación de costos tiene un margen de error de entre 10 % y 20 %, lo que alarga la espera de los clientes y el desarrollo de los proyectos.
* **Objetivo del sistema:** Automatizar el cálculo de los presupuestos y mantener una base de precios (materiales, mano de obra, subcontratos) para responder más rápido al cliente y evitar errores de cálculo.
## 2. Solución (Entrega 2)
* **Base de datos MySQL 8** en 3FN: catálogo de partidas con historial de precios, presupuestos, cotizaciones externas, correcciones, obras y envíos. Los totales (costo directo, gastos generales, utilidad, IVA y UF) se calculan con vistas.
* **Aplicación web** (Streamlit, en local host): arma presupuestos con cálculo automático, avisa de precios por revisar o vencidos, controla el flujo Borrador → En revisión → Aprobado → Emitido (solo el Gerente aprueba) y genera el PDF del presupuesto.
* **Automatización (n8n):** desde un presupuesto emitido, el usuario pulsa **Enviar presupuesto**. Streamlit envía el PDF a un webhook protegido con Basic Auth y n8n lo despacha por **SMTP**. Consulta el [workflow exportado](./n8n/flujo-envio-presupuesto.json) y la [documentación de la automatización](./docs/05-n8n.md).

## 3. Organización del repositorio
```
docs/
  00-caso-pyme.md             Datos de la empresa
  01-requerimientos.md        Alcance, actores y requisitos
  02-bpmn.md                  Procesos AS-IS y TO-BE (final)
  03-modelo-datos.md          Cambios E1 → E2, 3FN, diccionario de datos y reglas
  04-sql-consultas.md         Resultados de las consultas e interpretación
  05-n8n.md                   Flujo n8n paso a paso y su tarea en el BPMN to-be
  DECLARACION_IA.md           Uso de herramientas de IA
  CHANGELOG.md                Cambios relevantes desde la Entrega 1
sql/
  schema.sql                  Crea la base, tablas, claves, restricciones y vistas
  seed.sql                    Datos: catálogo real de la empresa y presupuestos de ejemplo
  consultas.sql               Preguntas del Gerente General y KPI
  pruebas_restricciones.sql   Pruebas de integridad de la base
app/
  app.py                      Aplicación web
  requirements.txt            Dependencias de Python
  secrets.toml.example        Plantilla de configuración (MySQL y n8n)
  pruebas_reglas_app.py       Pruebas de las reglas de negocio de la app
n8n/
  flujo-envio-presupuesto.json  Flujo exportado desde n8n
assets/                       Diagramas BPMN y E/R, capturas de respaldo SII
informe/                      Informes E1 y E2 (PDF + Word/LaTeX)
presentacion/                 Diapositivas
```

```
En MySQL Workbench: abrir cada archivo en ese orden y ejecutarlo completo (botón del rayo).
Los resultados esperados y su interpretación están en [`docs/04-sql-consultas.md`](./docs/04-sql-consultas.md).

### 4.2 Ejecutar la aplicación
bash
cd app
python3 -m venv .venv
source .venv/bin/activate                  # en Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
mkdir -p .streamlit
cp secrets.toml.example .streamlit/secrets.toml   # completar usuario y contraseña de MySQL
python -m streamlit run app.py

Se abre en http://localhost:8501. Usuarios de prueba (contraseña `demo123`):
* `gerencia@constructora-altura.example`: Gerente General (aprueba y rechaza)
* `presupuestos@constructora-altura.example`: Asistente

## 5. Datos
* **Reales de la empresa:** catálogo de partidas y precios (itemizado de la empresa, limpio), especialidades externas, rangos de gastos generales y utilidad, y frecuencia de actualización de precio.
* **Estimados:** 8 precios de materiales buscados en la web.
