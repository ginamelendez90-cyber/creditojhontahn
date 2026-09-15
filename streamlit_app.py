import datetime
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. CONFIGURACIÓN DE LA PÁGINA Y CONEXIÓN
# ==========================================
st.set_page_config(
    page_title="Gestión de Créditos",
    page_icon="💳",
    layout="centered"
)

# Configuración de visibilidad del API de Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def conectar_google_sheets():
    """Conecta con Google Sheets usando las credenciales guardadas en st.secrets"""
    try:
        # Carga credenciales desde .streamlit/secrets.toml
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(credentials)
        
        # Abre el libro por su nombre (Asegúrate de cambiar 'Gestion_Creditos' por el nombre exacto de tu archivo)
        spreadsheet = client.open("Gestion_Creditos") 
        return spreadsheet
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

# ==========================================
# 2. FUNCIONES AUXILIARES DE BASE DE DATOS
# ==========================================
def obtener_hoja(sheet_name):
    """Obtiene una pestaña específica del libro. Si no existe, la crea con encabezados."""
    spreadsheet = conectar_google_sheets()
    if not spreadsheet:
        return None
    
    try:
        hoja = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        # Si la pestaña no existe, se crea con los encabezados correspondientes
        if sheet_name == "Clientes":
            hoja = spreadsheet.add_worksheet(title="Clientes", rows="1000", cols="5")
            hoja.append_row(["ID_Cliente", "Nombre", "Cedula", "Telefono", "Direccion"])
        elif sheet_name == "Creditos":
            hoja = spreadsheet.add_worksheet(title="Creditos", rows="1000", cols="10")
            hoja.append_row([
                "ID_Credito", "Fecha_Registro", "Cliente", "Monto", 
                "Tasa_Interes", "Cuotas", "Frecuencia", "Valor_Cuota", 
                "Total_Pagar", "Notas"
            ])
    return hoja

def obtener_lista_clientes():
    """Recupera la lista de nombres de clientes de la hoja 'Clientes'"""
    hoja_clientes = obtener_hoja("Clientes")
    if hoja_clientes:
        records = hoja_clientes.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty and "Nombre" in df.columns:
            return sorted(df["Nombre"].dropna().unique().tolist())
    return []

def guardar_nuevo_cliente(nombre, cedula, telefono, direccion):
    """Guarda un nuevo cliente en la pestaña 'Clientes'"""
    hoja_clientes = obtener_hoja("Clientes")
    if hoja_clientes:
        nuevo_id = f"CLI-{int(datetime.datetime.now().timestamp())}"
        hoja_clientes.append_row([nuevo_id, nombre, cedula, telefono, direccion])
        return True
    return False

def guardar_nuevo_credito(cliente, monto, tasa, cuotas, frecuencia, valor_cuota, total_pagar, notas):
    """Guarda el nuevo registro de crédito en la pestaña 'Creditos'"""
    hoja_creditos = obtener_hoja("Creditos")
    if hoja_creditos:
        nuevo_id_credito = f"CRE-{int(datetime.datetime.now().timestamp())}"
        fecha_actual = datetime.date.today().strftime("%Y-%m-%d")
        
        hoja_creditos.append_row([
            nuevo_id_credito, fecha_actual, cliente, monto, 
            tasa, cuotas, frecuencia, valor_cuota, total_pagar, notas
        ])
        return True
    return False

# ==========================================
# 3. INTERFAZ EN STREAMLIT
# ==========================================
st.title("💳 Registro de Nuevo Crédito")

# Obtener clientes guardados
clientes_existentes = obtener_lista_clientes()
opciones_clientes = ["➕ Registrar Cliente Nuevo"] + clientes_existentes

# Selector principal
cliente_seleccionado = st.selectbox(
    "Selecciona un cliente o crea uno nuevo:",
    options=opciones_clientes,
    help="Elige un cliente existente o selecciona la primera opción para dar de alta uno nuevo."
)

st.markdown("---")

# Formulario principal
with st.form("form_registro_credito", clear_on_submit=True):
    
    # DATOS DEL CLIENTE (CONDICIONAL)
    if cliente_seleccionado == "➕ Registrar Cliente Nuevo":
        st.subheader("👤 Datos del Nuevo Cliente")
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            nombre_cliente = st.text_input("Nombre Completo:*")
            cedula_dni = st.text_input("Cédula / Documento de Identidad:")
        with col_c2:
            telefono = st.text_input("Teléfono / WhatsApp:")
            direccion = st.text_input("Dirección de Domicilio / Cobro:")
            
        es_cliente_nuevo = True
    else:
        st.info(f"📌 Cliente seleccionado: **{cliente_seleccionado}**")
        nombre_cliente = cliente_seleccionado
        es_cliente_nuevo = False

    st.markdown("---")
    st.subheader("💵 Detalles del Crédito")
    
    # DATOS DEL CRÉDITO
    col_m1, col_m2 = st.columns(2)
    
    with col_m1:
        monto = st.number_input("Monto Prestado ($):", min_value=0.0, value=100.0, step=10.0)
        tasa_interes = st.number_input("Tasa de Interés Total (%):", min_value=0.0, max_value=100.0, value=20.0, step=1.0)
        frecuencia_pago = st.selectbox("Frecuencia de Pago:", ["Diario", "Semanal", "Quincenal", "Mensual"])

    with col_m2:
        numero_cuotas = st.number_input("Número de Cuotas:", min_value=1, value=10, step=1)
        fecha_desembolso = st.date_input("Fecha de Desembolso:", value=datetime.date.today())
        notas = st.text_input("Notas / Observaciones (Opcional):")

    # CÁLCULOS EN TIEMPO REAL (Muestra rápida para el usuario)
    total_pagar = monto + (monto * (tasa_interes / 100))
    valor_cuota = total_pagar / numero_cuotas if numero_cuotas > 0 else 0

    st.markdown("### 📊 Resumen del Crédito")
    col_r1, col_r2 = st.columns(2)
    col_r1.metric("Total a Cobrar", f"${total_pagar:,.2f}")
    col_r2.metric(f"Valor de cada Cuota ({numero_cuotas})", f"${valor_cuota:,.2f}")

    # BOTÓN DE PROCESAR
    btn_guardar = st.form_submit_button("💾 Guardar y Registrar Crédito", use_container_width=True)

# ==========================================
# 4. PROCESAMIENTO DEL FORMULARIO
# ==========================================
if btn_guardar:
    # Validaciones previas
    if es_cliente_nuevo and not nombre_cliente.strip():
        st.error("⚠️ El campo 'Nombre Completo' del nuevo cliente es obligatorio.")
    elif monto <= 0:
        st.error("⚠️ El monto del crédito debe ser mayor a 0.")
    else:
        error_ocurrido = False
        
        # 1. Guardar cliente si es nuevo
        if es_cliente_nuevo:
            exito_cliente = guardar_nuevo_cliente(nombre_cliente, cedula_dni, telefono, direccion)
            if not exito_cliente:
                st.error("❌ No se pudo registrar el nuevo cliente en la base de datos.")
                error_ocurrido = True
            else:
                st.success(f"✅ Cliente **{nombre_cliente}** guardado con éxito.")
        
        # 2. Guardar crédito
        if not error_ocurrido:
            exito_credito = guardar_nuevo_credito(
                nombre_cliente, monto, tasa_interes, 
                numero_cuotas, frecuencia_pago, valor_cuota, 
                total_pagar, notas
            )
            
            if exito_credito:
                st.balloons()
                st.success(f"🎉 ¡Crédito de **${monto:,.2f}** registrado exitosamente para **{nombre_cliente}**!")
                # Limpiar cache para recargar la lista de clientes en la próxima interacción
                st.cache_data.clear()
            else:
                st.error("❌ Error al guardar el crédito.")
