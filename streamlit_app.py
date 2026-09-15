import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Control de Créditos y Cobros", page_icon="💰", layout="wide"
)

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def conectar_gsheets():
  try:
    if "connections" not in st.secrets or "gsheets" not in st.secrets["connections"]:
      st.error("⚠️ No se encontró la sección [connections.gsheets] en st.secrets.")
      return None
    
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds_dict.pop("client_secret", None)
    
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client
  except Exception as e:
    st.error(f"❌ Error al autenticar con Google: {e}")
    return None


def cargar_datos(worksheet_name, columnas_por_defecto):
  client = conectar_gsheets()
  if not client:
    return pd.DataFrame(columns=columnas_por_defecto)

  try:
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = client.open_by_url(spreadsheet_url)
    try:
      ws = sh.worksheet(worksheet_name)
      data = ws.get_all_records()
      if not data:
        return pd.DataFrame(columns=columnas_por_defecto)
      df = pd.DataFrame(data)
      for col in columnas_por_defecto:
        if col not in df.columns:
          df[col] = 0.0 if "Monto" in col or "Saldo" in col or "Gasto" in col else ""
      return df
    except Exception:
      ws = sh.add_worksheet(title=worksheet_name, rows="1000", cols="20")
      ws.append_row(columnas_por_defecto)
      return pd.DataFrame(columns=columnas_por_defecto)
  except Exception as e:
    st.warning(f"No se pudo cargar la pestaña '{worksheet_name}': {e}")
    return pd.DataFrame(columns=columnas_por_defecto)


# Inicializar datos en la sesión y forzar tipos numéricos correctos
if "creditos" not in st.session_state:
  df_c = cargar_datos("creditos", ["ID", "Cliente", "Monto_Total", "Monto_Prestado", "Modalidad", "Plazo", "Cuota_Valor", "Metodo_Salida_1", "Monto_Salida_1", "Metodo_Salida_2", "Monto_Salida_2", "Fecha_Prestamo", "Estado"])
  if not df_c.empty:
    df_c["Monto_Total"] = pd.to_numeric(df_c["Monto_Total"], errors="coerce").fillna(0.0)
    df_c["Monto_Prestado"] = pd.to_numeric(df_c["Monto_Prestado"], errors="coerce").fillna(0.0)
    df_c["Monto_Salida_1"] = pd.to_numeric(df_c["Monto_Salida_1"], errors="coerce").fillna(0.0)
    df_c["Monto_Salida_2"] = pd.to_numeric(df_c["Monto_Salida_2"], errors="coerce").fillna(0.0)
    df_c["Cuota_Valor"] = pd.to_numeric(df_c["Cuota_Valor"], errors="coerce").fillna(0.0)
  st.session_state.creditos = df_c.to_dict("records") if not df_c.empty else []

if "pagos" not in st.session_state:
  df_p = cargar_datos("pagos", ["ID_Credito", "Cuota_N", "Monto_Cuota", "Monto_Pagado", "Estado", "Metodo_Pago", "Fecha_Pago"])
  df_p["Monto_Cuota"] = pd.to_numeric(df_p["Monto_Cuota"], errors="coerce").fillna(0.0)
  df_p["Monto_Pagado"] = pd.to_numeric(df_p["Monto_Pagado"], errors="coerce").fillna(0.0)
  st.session_state.pagos = df_p

if "transacciones" not in st.session_state:
  df_t = cargar_datos("transacciones", ["ID_Credito", "Cliente", "Monto_Abonado", "Metodo_Pago", "Fecha_Pago", "Descripcion"])
  df_t["Monto_Abonado"] = pd.to_numeric(df_t["Monto_Abonado"], errors="coerce").fillna(0.0)
  if "Descripcion" not in df_t.columns:
    df_t["Descripcion"] = ""
  st.session_state.transacciones = df_t

if "caja_diaria" not in st.session_state:
  df_cd = cargar_datos("caja_diaria", ["Fecha", "Saldo_Inicial"])
  df_cd["Saldo_Inicial"] = pd.to_numeric(df_cd["Saldo_Inicial"], errors="coerce").fillna(0.0)
  st.session_state.caja_diaria = df_cd

if "gastos" not in st.session_state:
  df_g = cargar_datos("gastos", ["Fecha", "Monto_Gasto", "Descripcion"])
  df_g["Monto_Gasto"] = pd.to_numeric(df_g["Monto_Gasto"], errors="coerce").fillna(0.0)
  st.session_state.gastos = df_g


def guardar_en_sheets():
  client = conectar_gsheets()
  if not client:
    return

  try:
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = client.open_by_url(spreadsheet_url)

    cols_creditos = ["ID", "Cliente", "Monto_Total", "Monto_Prestado", "Modalidad", "Plazo", "Cuota_Valor", "Metodo_Salida_1", "Monto_Salida_1", "Metodo_Salida_2", "Monto_Salida_2", "Fecha_Prestamo", "Estado"]
    df_creditos_to_save = pd.DataFrame(st.session_state.creditos) if st.session_state.creditos else pd.DataFrame(columns=cols_creditos)
    for col in cols_creditos:
      if col not in df_creditos_to_save.columns:
        df_creditos_to_save[col] = 0.0 if "Monto" in col else ""

    dic_datos = {
        "creditos": df_creditos_to_save,
        "pagos": st.session_state.pagos,
        "transacciones": st.session_state.transacciones,
        "caja_diaria": st.session_state.caja_diaria,
        "gastos": st.session_state.gastos,
    }

    for name, df in dic_datos.items():
      try:
        ws = sh.worksheet(name)
      except:
        ws = sh.add_worksheet(title=name, rows="1000", cols=20)

      ws.clear()
      if not df.empty:
        data_to_write = [df.columns.values.tolist()] + df.values.tolist()
        ws.update(data_to_write)
      else:
        ws.append_row(df.columns.tolist())
  except Exception as e:
    st.error(f"Error al sincronizar con Google Sheets: {e}")


st.title("📊 Sistema de Gestión de Cobros (Conectado a Google Sheets)")

menu = st.sidebar.selectbox(
    "Menú de Navegación",
    [
        "Registrar Nuevo Crédito",
        "Panel de Cobros y Pagos",
        "Historial de Pagos del Día",
        "Historial y Créditos Cerrados",
    ],
)

# ---------------------------------------------------------
# 1. REGISTRAR NUEVO CRÉDITO
# ---------------------------------------------------------
if menu == "Registrar Nuevo Crédito":
  st.header("📝 Registrar Nuevo Crédito")

  creditos_activos = [c for c in st.session_state.creditos if c.get("Estado") == "Activo"]
  if creditos_activos:
    st.warning("⚠️ Hay un crédito activo actualmente. Recuerda cerrarlo si vas a otorgar uno nuevo.")

  with st.form("form_credito", clear_on_submit=True):
    nombre_cliente = st.text_input("Nombre del Cliente")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
      monto_prestado = st.number_input("Monto Real Prestado Total (Capital que entregas)", min_value=0.0, step=10.0, format="%.2f")
    with col_p2:
      monto_total = st.number_input("Monto Total a Deber (con intereses)", min_value=0.0, step=10.0, format="%.2f")

    st.markdown("### 🏦 ¿De dónde sale el dinero? (Puedes dividirlo en hasta 2 opciones)")
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
      metodo_salida_1 = st.selectbox("Origen 1", ["Efectivo", "Pago Móvil", "Binance"])
    with col_s2:
      monto_salida_1 = st.number_input("Monto de Origen 1", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    with col_s3:
      metodo_salida_2 = st.selectbox("Origen 2 (Opcional)", ["Ninguno", "Efectivo", "Pago Móvil", "Binance"])
    with col_s4:
      monto_salida_2 = st.number_input("Monto de Origen 2", min_value=0.0, value=0.0, step=1.0, format="%.2f")

    col_m1, col_m2 = st.columns(2)
    with col_m1:
      modalidad = st.selectbox("Modalidad de Cobro", ["Diario", "Semanal"])
    with col_m2:
      fecha_prestamo = st.date_input("Fecha del Préstamo")

    if modalidad == "Diario":
      num_cuotas = st.number_input("Cantidad de Días de Pago", min_value=1, max_value=365, value=24, step=1)
    else:
      num_cuotas = st.number_input("Cantidad de Semanas de Pago", min_value=1, max_value=52, value=4, step=1)

    submit = st.form_submit_button("Crear Crédito")

    if submit:
      if metodo_salida_2 == "Ninguno":
        monto_salida_2 = 0.0

      suma_origenes = monto_salida_1 + monto_salida_2

      if not nombre_cliente or monto_total <= 0 or monto_prestado <= 0 or num_cuotas <= 0:
        st.error("Por favor completa todos los campos principales correctamente.")
      elif abs(suma_origenes - monto_prestado) > 0.01:
        st.error(f"⚠️ La suma de los montos de los orígenes (${suma_origenes:.2f}) debe ser igual al Monto Real Prestado (${monto_prestado:.2f}).")
      else:
        id_credito = len(st.session_state.creditos) + 1
        monto_cuota = float(monto_total / num_cuotas)

        nuevo_credito = {
            "ID": id_credito,
            "Cliente": nombre_cliente,
            "Monto_Total": float(monto_total),
            "Monto_Prestado": float(monto_prestado),
            "Modalidad": modalidad,
            "Plazo": int(num_cuotas),
            "Cuota_Valor": monto_cuota,
            "Metodo_Salida_1": metodo_salida_1,
            "Monto_Salida_1": float(monto_salida_1),
            "Metodo_Salida_2": metodo_salida_2 if metodo_salida_2 != "Ninguno" else "",
            "Monto_Salida_2": float(monto_salida_2),
            "Fecha_Prestamo": str(fecha_prestamo),
            "Estado": "Activo",
        }
        st.session_state.creditos.append(nuevo_credito)

        nuevas_filas = []
        for i in range(1, int(num_cuotas) + 1):
          nuevas_filas.append({
              "ID_Credito": id_credito,
              "Cuota_N": i,
              "Monto_Cuota": monto_cuota,
              "Monto_Pagado": 0.0,
              "Estado": "Pendiente",
              "Metodo_Pago": "N/A",
              "Fecha_Pago": "N/A",
          })

        df_nuevos_pagos = pd.DataFrame(nuevas_filas)
        df_nuevos_pagos["Monto_Cuota"] = pd.to_numeric(df_nuevos_pagos["Monto_Cuota"], errors="coerce").fillna(0.0)
        df_nuevos_pagos["Monto_Pagado"] = pd.to_numeric(df_nuevos_pagos["Monto_Pagado"], errors="coerce").fillna(0.0)

        st.session_state.pagos = pd.concat([st.session_state.pagos, df_nuevos_pagos], ignore_index=True)
        st.session_state.pagos["Monto_Pagado"] = pd.to_numeric(st.session_state.pagos["Monto_Pagado"], errors="coerce").fillna(0.0)
        st.session_state.pagos["Monto_Cuota"] = pd.to_numeric(st.session_state.pagos["Monto_Cuota"], errors="coerce").fillna(0.0)

        guardar_en_sheets()
        st.success(f"✅ ¡Crédito #{id_credito} creado para {nombre_cliente} correctamente!")

# ---------------------------------------------------------
# 2. PANEL DE COBROS Y PAGOS
# ---------------------------------------------------------
elif menu == "Panel de Cobros y Pagos":
  st.header("💵 Panel de Cobros Diarios y Semanales")

  creditos_activos = [c for c in st.session_state.creditos if c.get("Estado") == "Activo"]

  if not creditos_activos:
    st.info("No hay créditos activos en este momento. Crea uno nuevo.")
  else:
    opciones_credito = {f"Crédito #{c['ID']} - {c['Cliente']} (Debe: {c['Monto_Total']})": c['ID'] for c in creditos_activos}
    credito_seleccionado_str = st.selectbox("Seleccione el Crédito a Gestionar", list(opciones_credito.keys()))
    id_activo = opciones_credito[credito_seleccionado_str]

    credito_info = next(c for c in st.session_state.creditos if c['ID'] == id_activo)

    st.session_state.pagos["Monto_Pagado"] = pd.to_numeric(st.session_state.pagos["Monto_Pagado"], errors="coerce").fillna(0.0).astype(float)
    st.session_state.pagos["Monto_Cuota"] = pd.to_numeric(st.session_state.pagos["Monto_Cuota"], errors="coerce").fillna(0.0).astype(float)

    df_pagos_credito = st.session_state.pagos[st.session_state.pagos["ID_Credito"] == id_activo]
    total_abonado = float(df_pagos_credito["Monto_Pagado"].sum())
    saldo_restante = float(credito_info["Monto_Total"]) - total_abonado

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cliente", credito_info["Cliente"])
    col2.metric("Total Deuda", f"${float(credito_info['Monto_Total']):.2f}")
    col3.metric("Abonado", f"${total_abonado:.2f}")
    col4.metric("Saldo Restante", f"${saldo_restante:.2f}")

    st.markdown("---")
    st.subheader("📋 Estado de Cuotas")
    st.dataframe(df_pagos_credito, use_container_width=True)

    # NUEVO: Cuadro con la lista exacta de abonos realizados por el cliente
    st.markdown("---")
    st.subheader(f"📜 Historial de Abonos Recibidos ({credito_info['Cliente']})")
    if not st.session_state.transacciones.empty:
      df_trans_cliente = st.session_state.transacciones[st.session_state.transacciones["ID_Credito"] == id_activo]
      if not df_trans_cliente.empty:
        # Mostramos los campos limpios y ordenados (Monto, Método, Fecha, Nota)
        df_mostrar_abonos = df_trans_cliente[["Fecha_Pago", "Monto_Abonado", "Metodo_Pago", "Descripcion"]].copy()
        df_mostrar_abonos.columns = ["Fecha", "Monto Abonado", "Método de Pago", "Descripción / Nota"]
        st.dataframe(df_mostrar_abonos.reset_index(drop=True), use_container_width=True)
      else:
        st.info("Aún no se han registrado abonos para este crédito.")
    else:
      st.info("Aún no hay transacciones registradas.")

    st.markdown("---")
    st.subheader("💸 Registrar Pago o Abono Libre")
    with st.form("form_registrar_abono", clear_on_submit=True):
      monto_abono = st.number_input("Monto del Abono / Pago recibido", min_value=0.01, step=1.0, format="%.2f")
      metodo = st.selectbox("Método de Pago", ["Pago Móvil", "Efectivo", "Binance"])
      fecha = st.date_input("Fecha del Pago")
      descripcion_pago = st.text_input("Descripción / Nota del Pago (Opcional)", placeholder="Ej. Abono adelantado, pago parcial...")

      btn_abonar = st.form_submit_button("Aplicar Abono")

      if btn_abonar:
        st.session_state.pagos["Monto_Pagado"] = st.session_state.pagos["Monto_Pagado"].astype(float)
        st.session_state.pagos["Monto_Cuota"] = st.session_state.pagos["Monto_Cuota"].astype(float)

        restante_por_aplicar = float(monto_abono)
        indices_cuotas = df_pagos_credito.index[df_pagos_credito["Estado"] != "Pagado"]

        if len(indices_cuotas) == 0:
          st.warning("⚠️ Este crédito ya está completamente pagado.")
        else:
          for idx in indices_cuotas:
            if restante_por_aplicar <= 0:
              break

            monto_cuota_val = float(st.session_state.pagos.at[idx, "Monto_Cuota"])
            monto_pagado_val = float(st.session_state.pagos.at[idx, "Monto_Pagado"])
            deuda_cuota = monto_cuota_val - monto_pagado_val

            if restante_por_aplicar >= deuda_cuota:
              restante_por_aplicar -= deuda_cuota
              st.session_state.pagos.at[idx, "Monto_Pagado"] = monto_pagado_val + deuda_cuota
              st.session_state.pagos.at[idx, "Estado"] = "Pagado"
              st.session_state.pagos.at[idx, "Metodo_Pago"] = metodo
              st.session_state.pagos.at[idx, "Fecha_Pago"] = str(fecha)
            else:
              st.session_state.pagos.at[idx, "Monto_Pagado"] = monto_pagado_val + restante_por_aplicar
              st.session_state.pagos.at[idx, "Estado"] = "Abonado"
              st.session_state.pagos.at[idx, "Metodo_Pago"] = metodo
              st.session_state.pagos.at[idx, "Fecha_Pago"] = str(fecha)
              restante_por_aplicar = 0.0

          nueva_transaccion = pd.DataFrame([{
              "ID_Credito": id_activo,
              "Cliente": credito_info["Cliente"],
              "Monto_Abonado": float(monto_abono),
              "Metodo_Pago": metodo,
              "Fecha_Pago": str(fecha),
              "Descripcion": descripcion_pago if descripcion_pago else "N/A",
          }])
          nueva_transaccion["Monto_Abonado"] = pd.to_numeric(nueva_transaccion["Monto_Abonado"], errors="coerce").fillna(0.0)
          
          st.session_state.transacciones = pd.concat([st.session_state.transacciones, nueva_transaccion], ignore_index=True)
          st.session_state.transacciones["Monto_Abonado"] = pd.to_numeric(st.session_state.transacciones["Monto_Abonado"], errors="coerce").fillna(0.0)

          guardar_en_sheets()
          st.success(f"✅ Abono de ${monto_abono:.2f} registrado y respaldado en Google Sheets.")
          st.rerun()

    st.markdown("---")
    st.subheader("🔒 Cerrar Crédito")
    pendientes_restantes = len(st.session_state.pagos[(st.session_state.pagos["ID_Credito"] == id_activo) & (st.session_state.pagos["Estado"] != "Pagado")])

    if pendientes_restantes == 0:
      if st.button("Cerrar Crédito Finalizado"):
        for c in st.session_state.creditos:
          if c['ID'] == id_activo:
            c['Estado'] = "Cerrado"
        guardar_en_sheets()
        st.success("🔒 El crédito se ha cerrado correctamente.")
        st.rerun()
    else:
      if st.button("Forzar Cierre de Crédito"):
        for c in st.session_state.creditos:
          if c['ID'] == id_activo:
            c['Estado'] = "Cerrado"
        guardar_en_sheets()
        st.warning("⚠️ Crédito cerrado manualmente con deudas.")
        st.rerun()

# ---------------------------------------------------------
# 3. HISTORIAL DE PAGOS DEL DÍA Y CUADRE DE CAJA
# ---------------------------------------------------------
elif menu == "Historial de Pagos del Día":
  st.header("📅 Historial de Pagos y Cuadre de Caja Diario")

  fechas_transacciones = st.session_state.transacciones["Fecha_Pago"].unique().tolist() if not st.session_state.transacciones.empty else []
  fechas_prestamos = [c.get("Fecha_Prestamo") for c in st.session_state.creditos if c.get("Fecha_Prestamo")]
  fechas_gastos = st.session_state.gastos["Fecha"].unique().tolist() if not st.session_state.gastos.empty else []
  fechas_caja = st.session_state.caja_diaria["Fecha"].unique().tolist() if not st.session_state.caja_diaria.empty else []

  fechas_disponibles = sorted(list(set(fechas_transacciones + fechas_prestamos + fechas_gastos + fechas_caja)))
  
  if not fechas_disponibles:
    st.info("No hay registros de pagos, gastos o préstamos todavía.")
  else:
    fecha_seleccionada = st.selectbox("Seleccionar Fecha de Operación", fechas_disponibles)

    # 1. Cobros del día
    df_filtrado_fecha = pd.DataFrame()
    if not st.session_state.transacciones.empty and "Fecha_Pago" in st.session_state.transacciones.columns:
      df_filtrado_fecha = st.session_state.transacciones[st.session_state.transacciones["Fecha_Pago"] == fecha_seleccionada]

    total_efectivo_cobrado = float(df_filtrado_fecha[df_filtrado_fecha["Metodo_Pago"] == "Efectivo"]["Monto_Abonado"].sum()) if not df_filtrado_fecha.empty else 0.0
    total_pago_movil_cobrado = float(df_filtrado_fecha[df_filtrado_fecha["Metodo_Pago"] == "Pago Móvil"]["Monto_Abonado"].sum()) if not df_filtrado_fecha.empty else 0.0
    total_binance_cobrado = float(df_filtrado_fecha[df_filtrado_fecha["Metodo_Pago"] == "Binance"]["Monto_Abonado"].sum()) if not df_filtrado_fecha.empty else 0.0
    total_cobrado_dia = total_efectivo_cobrado + total_pago_movil_cobrado + total_binance_cobrado

    # 2. Préstamos otorgados en el día
    creditos_del_dia = [c for c in st.session_state.creditos if c.get("Fecha_Prestamo") == fecha_seleccionada]
    
    prestado_efectivo = 0.0
    prestado_pago_movil = 0.0
    prestado_binance = 0.0

    for c in creditos_del_dia:
      m1 = float(c.get("Monto_Salida_1", 0))
      s1 = c.get("Metodo_Salida_1", "")
      if s1 == "Efectivo": prestado_efectivo += m1
      elif s1 == "Pago Móvil": prestado_pago_movil += m1
      elif s1 == "Binance": prestado_binance += m1

      m2 = float(c.get("Monto_Salida_2", 0))
      s2 = c.get("Metodo_Salida_2", "")
      if s2 == "Efectivo": prestado_efectivo += m2
      elif s2 == "Pago Móvil": prestado_pago_movil += m2
      elif s2 == "Binance": prestado_binance += m2

    total_prestado_dia = prestado_efectivo + prestado_pago_movil + prestado_binance

    # 3. Gastos del día
    gastos_del_dia = pd.DataFrame()
    total_gastos_dia = 0.0
    if not st.session_state.gastos.empty and "Fecha" in st.session_state.gastos.columns:
      st.session_state.gastos["Monto_Gasto"] = pd.to_numeric(st.session_state.gastos["Monto_Gasto"], errors="coerce").fillna(0.0)
      gastos_del_dia = st.session_state.gastos[st.session_state.gastos["Fecha"] == fecha_seleccionada]
      total_gastos_dia = float(gastos_del_dia["Monto_Gasto"].sum()) if not gastos_del_dia.empty else 0.0

    st.subheader(f"📊 Resumen de Movimientos: {fecha_seleccionada}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 Efectivo Cobrado", f"${total_efectivo_cobrado:.2f}", delta=f"Prestado: -${prestado_efectivo:.2f}" if prestado_efectivo > 0 else None)
    col2.metric("📱 Pago Móvil", f"${total_pago_movil_cobrado:.2f}", delta=f"Prestado: -${prestado_pago_movil:.2f}" if prestado_pago_movil > 0 else None)
    col3.metric("🪙 Binance", f"${total_binance_cobrado:.2f}", delta=f"Prestado: -${prestado_binance:.2f}" if prestado_binance > 0 else None)
    col4.metric("📈 Total Cobrado", f"${total_cobrado_dia:.2f}", delta=f"Total Prestado: -${total_prestado_dia:.2f}" if total_prestado_dia > 0 else None)

    st.markdown("---")
    st.subheader("⚙️ Configuración de Caja del Día")

    st.session_state.caja_diaria["Saldo_Inicial"] = pd.to_numeric(st.session_state.caja_diaria["Saldo_Inicial"], errors="coerce").fillna(0.0)
    df_caja = st.session_state.caja_diaria
    registro_existente = df_caja[df_caja["Fecha"] == fecha_seleccionada]

    default_saldo_inicial = 0.0
    if not registro_existente.empty:
      default_saldo_inicial = float(registro_existente.iloc[0]["Saldo_Inicial"])

    # Formulario para el Saldo Inicial
    with st.form(f"form_caja_{fecha_seleccionada}"):
      saldo_inicial = st.number_input("¿Con cuánto saldo/efectivo sales hoy?", min_value=0.0, value=default_saldo_inicial, step=1.0, format="%.2f")
      btn_guardar_caja = st.form_submit_button("Guardar Saldo Inicial")

      if btn_guardar_caja:
        if not registro_existente.empty:
          idx_reg = registro_existente.index[0]
          st.session_state.caja_diaria.loc[idx_reg, "Saldo_Inicial"] = float(saldo_inicial)
        else:
          nuevo_registro_caja = pd.DataFrame([{
              "Fecha": fecha_seleccionada,
              "Saldo_Inicial": float(saldo_inicial),
          }])
          nuevo_registro_caja["Saldo_Inicial"] = pd.to_numeric(nuevo_registro_caja["Saldo_Inicial"], errors="coerce").fillna(0.0)
          st.session_state.caja_diaria = pd.concat([st.session_state.caja_diaria, nuevo_registro_caja], ignore_index=True)

        guardar_en_sheets()
        st.success("✅ ¡Saldo inicial guardado en Google Sheets!")
        st.rerun()

    # Formulario para registrar un gasto nuevo del día
    st.markdown("### 💸 Registrar Gasto del Día")
    with st.form(f"form_registrar_gasto_{fecha_seleccionada}", clear_on_submit=True):
      col_g1, col_g2 = st.columns(2)
      with col_g1:
        monto_gasto = st.number_input("Monto del Gasto", min_value=0.01, step=1.0, format="%.2f")
      with col_g2:
        desc_gasto = st.text_input("Descripción del Gasto", placeholder="Ej. Almuerzo, pasaje, repuesto...")
      
      btn_agregar_gasto = st.form_submit_button("Agregar Gasto")

      if btn_agregar_gasto:
        if desc_gasto and monto_gasto > 0:
          nuevo_gasto = pd.DataFrame([{
              "Fecha": fecha_seleccionada,
              "Monto_Gasto": float(monto_gasto),
              "Descripcion": desc_gasto
          }])
          nuevo_gasto["Monto_Gasto"] = pd.to_numeric(nuevo_gasto["Monto_Gasto"], errors="coerce").fillna(0.0)
          
          st.session_state.gastos = pd.concat([st.session_state.gastos, nuevo_gasto], ignore_index=True)
          guardar_en_sheets()
          st.success("✅ Gasto registrado correctamente.")
          st.rerun()
        else:
          st.error("Por favor ingresa un monto y una descripción válida para el gasto.")

    # Cálculos restando gastos y créditos otorgados
    efectivo_final_caja = float(saldo_inicial) + total_efectivo_cobrado - total_gastos_dia - prestado_efectivo
    total_general_dia = float(saldo_inicial) + total_cobrado_dia - total_gastos_dia - total_prestado_dia

    st.markdown("### 💰 Resultado del Cuadre")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saldo Inicial", f"${saldo_inicial:.2f}")
    c2.metric("Total Cobrado (General)", f"${total_cobrado_dia:.2f}", delta=f"Efectivo cobrado: ${total_efectivo_cobrado:.2f}")
    c3.metric("Salidas del Día", f"-${(total_gastos_dia + total_prestado_dia):.2f}", delta=f"Prestado hoy: ${total_prestado_dia:.2f} | Gastos: ${total_gastos_dia:.2f}")
    c4.metric("Total General Disponible", f"${total_general_dia:.2f}", delta=f"Efectivo en mano: ${efectivo_final_caja:.2f}")

    st.markdown("---")
    st.subheader("📋 Créditos otorgados en esta fecha")
    if creditos_del_dia:
      st.dataframe(pd.DataFrame(creditos_del_dia), use_container_width=True)
    else:
      st.info("No se otorgaron créditos en esta fecha específica.")

    st.subheader("💸 Gastos registrados en esta fecha")
    if not gastos_del_dia.empty:
      st.dataframe(gastos_del_dia[["Monto_Gasto", "Descripcion"]], use_container_width=True)
    else:
      st.info("No hay gastos registrados para esta fecha.")

    st.subheader("💳 Detalle de pagos/abonos recibidos en la fecha")
    if not df_filtrado_fecha.empty:
      st.dataframe(df_filtrado_fecha, use_container_width=True)
    else:
      st.info("No hay transacciones de cobro registradas para esta fecha.")

# ---------------------------------------------------------
# 4. HISTORIAL Y CRÉDITOS CERRADOS
# ---------------------------------------------------------
elif menu == "Historial y Créditos Cerrados":
  st.header("📂 Historial General de Créditos")

  if not st.session_state.creditos:
    st.info("No hay registros de créditos creados.")
  else:
    df_creditos = pd.DataFrame(st.session_state.creditos)
    st.dataframe(df_creditos, use_container_width=True)

    st.subheader("Detalle completo de todas las cuotas")
    st.dataframe(st.session_state.pagos, use_container_width=True)
