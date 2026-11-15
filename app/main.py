import streamlit as st
import pandas as pd
import mysql.connector

# 1. Configuración de conexión a MySQL
def conectar_bd():
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Mocoverde11",  # <-- CAMBIA ESTO por tu clave de MySQL Workbench
            database="altura_db"           # <-- CAMBIA ESTO por el nombre de tu esquema
        )
        return conexion
    except Exception as e:
        st.error(f"Error conectando a la base de datos: {e}")
        return None

# 2. Configuración de la página
st.set_page_config(page_title="Sistema de Presupuestos - Altura", page_icon="🏗️", layout="wide")

# 3. Menú lateral (Sidebar)
st.sidebar.title("🏗️ Constructora Altura")
st.sidebar.subheader("Inversiones Rumay Ltda.")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navegación del Sistema",
    ["🏠 Inicio", "📋 Nuevo Presupuesto", "📦 Catálogo de Partidas", "⚙️ Configuración"]
)

# 4. Lógica de navegación
if menu == "🏠 Inicio":
    st.title("Panel Principal")
    st.write("Bienvenido al Sistema de Gestión de Presupuestos.")
    
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
            rut_cliente = st.text_input("RUT Cliente (Ej: 76.123.456-7)")
            nombre_proyecto = st.text_input("Nombre del Proyecto")
        with col2:
            jornada = st.selectbox("Tipo de Jornada", ["Diurna", "Nocturna"])
            valor_uf = st.number_input("Valor UF del Día ($)", min_value=0.0, format="%.2f")
        
        submit_btn = st.form_submit_button("Guardar Encabezado")
        if submit_btn:
            st.success("Próximamente conectará al INSERT de MySQL.")

elif menu == "📦 Catálogo de Partidas":
    st.title("Catálogo Maestro de Costos")
    st.write("Datos cargados en tiempo real desde la tabla `PARTIDA` de MySQL.")
    
    conexion = conectar_bd()
    if conexion:
        cursor = conexion.cursor(dictionary=True)
        # Hacemos la consulta SQL real a tu base de datos
        cursor.execute("SELECT codigo, descripcion, unidad, costo_referencial FROM PARTIDA")
        resultados = cursor.fetchall()
        
        if resultados:
            df = pd.DataFrame(resultados)
            # Mostramos los datos reales en pantalla
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("La tabla PARTIDA está vacía. ¡Asegúrate de ejecutar seed.sql en Workbench!")
            
        cursor.close()
        conexion.close()

elif menu == "⚙️ Configuración":
    st.title("Variables Económicas")
    pct_gg = st.slider("Porcentaje de Gastos Generales (%)", min_value=5, max_value=15, value=8)
    st.button("Actualizar Variables")