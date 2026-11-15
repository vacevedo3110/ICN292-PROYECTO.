import streamlit as st
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="Sistema de Presupuestos - Altura", page_icon="🏗️", layout="wide")

# 2. Menú lateral (Sidebar)
st.sidebar.title("🏗️ Constructora Altura")
st.sidebar.subheader("Inversiones Rumay Ltda.")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navegación del Sistema",
    ["🏠 Inicio", "📋 Nuevo Presupuesto", "📦 Catálogo de Partidas", "⚙️ Configuración"]
)

# 3. Lógica de navegación
if menu == "🏠 Inicio":
    st.title("Panel Principal")
    st.write("Bienvenido al Sistema de Gestión de Presupuestos.")
    st.info("👈 Selecciona una opción en el menú lateral para comenzar.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Presupuestos Emitidos (Mes)", "12", "2 nuevos")
    col2.metric("Precios Desactualizados", "5", "-1 resuelto", delta_color="inverse")
    col3.metric("Costo Total Cotizado", "$45.2M", "15% vs mes anterior")

elif menu == "📋 Nuevo Presupuesto":
    st.title("Crear Nuevo Presupuesto")
    
    with st.form("form_nuevo_presupuesto"):
        st.subheader("Antecedentes del Proyecto")
        col1, col2 = st.columns(2)
        with col1:
            rut_cliente = st.text_input("RUT Cliente (Ej: 76.380.707-K)")
            nombre_proyecto = st.text_input("Nombre del Proyecto")
        with col2:
            jornada = st.selectbox("Tipo de Jornada", ["Diurna", "Nocturna"])
            valor_uf = st.number_input("Valor UF del Día ($)", min_value=0.0, format="%.2f")
        
        st.markdown("---")
        submit_btn = st.form_submit_button("Guardar Encabezado e Ir a Partidas")
        
        if submit_btn:
            st.success("Los datos se han guardado temporalmente.")

elif menu == "📦 Catálogo de Partidas":
    st.title("Catálogo Maestro de Costos")
    st.write("Aquí se visualizarán las partidas.")
    
    datos_demo = pd.DataFrame({
        "ID": [1, 2, 3],
        "Descripción": ["Hormigón H30", "Volcanita ST 15mm", "Trazado y Niveles"],
        "Unidad": ["m3", "plancha", "GL"],
        "Precio Ref ($)": [85000, 7500, 150000],
        "Última Act.": ["2026-10-01", "2026-11-10", "2026-02-15"]
    })
    
    st.dataframe(datos_demo, use_container_width=True)

elif menu == "⚙️ Configuración":
    st.title("Variables Económicas")
    st.write("Definición de márgenes estándar para la empresa.")
    
    pct_gg = st.slider("Porcentaje de Gastos Generales (%)", min_value=5, max_value=15, value=8)
    st.button("Actualizar Variables")