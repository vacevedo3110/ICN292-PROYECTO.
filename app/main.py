import streamlit as st
import pandas as pd
import mysql.connector

# 1. Configuración de conexión a MySQL
def conectar_bd():
    try:
        conexion = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Mocoverde11",
            database="altura_db"
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
    
    # Inicializar el "carrito" de materiales en la memoria temporal
    if 'carrito' not in st.session_state:
        st.session_state.carrito = []
        
    conexion = conectar_bd()
    if conexion:
        cursor = conexion.cursor(dictionary=True)
        
        # --- SECCIÓN 1: ENCABEZADO ---
        st.subheader("1. Antecedentes del Proyecto")
        col1, col2 = st.columns(2)
        with col1:
            rut_cliente = st.text_input("RUT Cliente (Ej: 76.123.456-7)")
            nombre_proyecto = st.text_input("Nombre del Proyecto")
        with col2:
            jornada = st.selectbox("Tipo de Jornada", ["Diurna", "Nocturna"])
            valor_uf = st.number_input("Valor UF del Día ($)", min_value=0.0, format="%.2f", value=38000.00)
            
        st.markdown("---")
        
        # --- SECCIÓN 2: AGREGAR PARTIDAS ---
        st.subheader("2. Detalle de Partidas (Materiales y Servicios)")
        
        # Extraer catálogo de MySQL
        cursor.execute("SELECT id_partida, codigo, descripcion, unidad, costo_referencial FROM PARTIDA")
        partidas_db = cursor.fetchall()
        opciones = {f"{p['codigo']} - {p['descripcion']}": p for p in partidas_db}
        
        col_sel, col_cant, col_btn = st.columns([3, 1, 1])
        with col_sel:
            partida_seleccionada = st.selectbox("Seleccione un material/servicio:", list(opciones.keys()))
        with col_cant:
            cantidad = st.number_input("Cantidad", min_value=0.1, value=1.0, step=0.5)
        with col_btn:
            st.write("") 
            st.write("")
            if st.button("➕ Agregar al Presupuesto"):
                item = opciones[partida_seleccionada]
                
                # CORRECCIÓN AQUÍ: Convertimos el formato MySQL Decimal a float nativo
                precio_float = float(item["costo_referencial"])
                
                st.session_state.carrito.append({
                    "id_partida": item["id_partida"],
                    "codigo": item["codigo"],
                    "descripcion": item["descripcion"],
                    "unidad": item["unidad"],
                    "cantidad": cantidad,
                    "precio_aplicado": precio_float,
                    "subtotal": cantidad * precio_float
                })
                st.rerun()
                
        # Mostrar el carrito en pantalla
        if st.session_state.carrito:
            df_carrito = pd.DataFrame(st.session_state.carrito)
            st.dataframe(df_carrito[["codigo", "descripcion", "unidad", "cantidad", "precio_aplicado", "subtotal"]], use_container_width=True)
            
            total_cd = df_carrito["subtotal"].sum()
            st.write(f"**Costo Directo Total: ${total_cd:,.0f}**")
            
        st.markdown("---")
        
        # --- SECCIÓN 3: GUARDAR EN LA BASE DE DATOS ---
        if st.button("💾 Guardar Presupuesto Completo", type="primary"):
            if not st.session_state.carrito:
                st.error("⚠️ Agrega al menos un material/servicio antes de guardar.")
            elif not rut_cliente or not nombre_proyecto:
                st.error("⚠️ Debes llenar el RUT y el Nombre del Proyecto.")
            else:
                try:
                    cursor.execute("SELECT id_cliente FROM CLIENTE WHERE rut = %s", (rut_cliente,))
                    resultado = cursor.fetchone()
                    
                    if resultado:
                        id_cliente = resultado['id_cliente']
                        
                        # 1. Insertar el Proyecto
                        sql_encabezado = """
                        INSERT INTO PRESUPUESTO 
                        (id_cliente, id_usuario, nombre_proyecto, fecha_creacion, valor_uf_dia, tipo_jornada, pct_gastos_generales, estado) 
                        VALUES (%s, %s, %s, CURDATE(), %s, %s, %s, 'Borrador')
                        """
                        cursor.execute(sql_encabezado, (id_cliente, 1, nombre_proyecto, valor_uf, jornada, 8.0))
                        nuevo_id_presupuesto = cursor.lastrowid
                        
                        # 2. Insertar los Materiales (Detalle)
                        sql_detalle = """
                        INSERT INTO DETALLE_PRESUPUESTO 
                        (id_presupuesto, nro_linea, id_partida, cantidad, precio_aplicado) 
                        VALUES (%s, %s, %s, %s, %s)
                        """
                        for i, item in enumerate(st.session_state.carrito, start=1):
                            cursor.execute(sql_detalle, (nuevo_id_presupuesto, i, item["id_partida"], item["cantidad"], item["precio_aplicado"]))
                            
                        conexion.commit() # Confirmar en MySQL
                        st.session_state.carrito = [] # Vaciar carrito
                        st.success(f"✅ ¡Presupuesto '{nombre_proyecto}' guardado en la BD con el ID #{nuevo_id_presupuesto}!")
                    else:
                        st.error("❌ RUT no encontrado en la base de datos.")
                except Exception as e:
                    conexion.rollback()
                    st.error(f"Error técnico en la BD: {e}")
                    
        cursor.close()
        conexion.close()

elif menu == "📦 Catálogo de Partidas":
    st.title("Catálogo Maestro de Costos")
    conexion = conectar_bd()
    if conexion:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT codigo, descripcion, unidad, costo_referencial FROM PARTIDA")
        resultados = cursor.fetchall()
        if resultados:
            st.dataframe(pd.DataFrame(resultados), use_container_width=True)
        else:
            st.warning("La tabla PARTIDA está vacía.")
        cursor.close()
        conexion.close()

elif menu == "⚙️ Configuración":
    st.title("Variables Económicas")
    pct_gg = st.slider("Porcentaje de Gastos Generales (%)", min_value=5, max_value=15, value=8)
    st.button("Actualizar Variables")