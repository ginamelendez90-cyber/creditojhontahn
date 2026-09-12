import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Control de Créditos y Cobros", page_icon="💰", layout="wide"
)

# Configuración de conexión nativa con GSpread usando st.secrets
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def conectar_gsheets():
  try:
    creds_dict = dict(st.secrets["connections"]["gsheets"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client
  except Exception as e:
    st.error(f"Error de credenciales en st.secrets: {e}")
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
      return pd.DataFrame(data)
    except Exception:
      # Si la hoja no existe, la crea automáticamente
      ws = sh.add_worksheet(title=worksheet_name, rows="1000", cols="20")
      ws.append_row(columnas_por_defecto)
      return pd.DataFrame(columns=columnas_por_defecto)
  except Exception as e:
    return pd.DataFrame(columns=columnas_por_defecto)


# Inicializar o sincronizar datos de Google Sheets en la sesión
if "creditos" not in st.session_state:
  st.session_state.creditos = cargar_datos(
      "creditos",
      [
          "ID",
          "Cliente",
          "Monto_Total",
          "Modalidad",
          "Plazo",
          "Cuota_Valor",
          "Estado",
      ],
  ).to_dict("records")

if "pagos" not in st.session_state:
  st.session_state.pagos = cargar_datos(
      "pagos",
      [
          "ID_Credito",
          "Cuota_N",
          "Monto_Cuota",
          "Monto_Pagado",
          "Estado",
          "Metodo_Pago",
          "Fecha_Pago",
      ],
  )
  if "Monto_Pagado" not in st.session_state.pagos.columns:
    st.session_state.pagos["Monto_Pagado"] = 0.0

if "transacciones" not in st.session_state:
  st.session_state.transacciones = cargar_datos(
      "transacciones",
      ["ID_Credito", "Cliente", "Monto_Abonado", "Metodo_Pago", "Fecha_Pago"],
  )


def guardar_en_sheets():
  client = conectar_gsheets()
  if not client:
    return

  try:
    spreadsheet_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    sh = client.open_by_url(spreadsheet_url)

    dic_datos = {
        "creditos": pd.DataFrame(st.session_state.creditos)
        if isinstance(st.session_state.creditos, list)
        else st.session_state.creditos,
        "pagos": st.session_state.pagos,
        "transacciones": st.session_state.transacciones,
    }

    for name, df in dic_datos.items():
      try:
        ws = sh.worksheet(name)
      except:
        ws = sh.add_worksheet(title=name, rows="1000", cols=len(df.columns) + 2)

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

  creditos_activos = [
      c for c in st.session_state.creditos if c["Estado"] == "Activo"
  ]
  if creditos_activos:
    st.warning(
        "⚠️ Hay un crédito activo actualmente. Recuerda cerrarlo si vas a"
        " otorgar uno nuevo."
    )

  with st.form("form_credito", clear_on_submit=True):
    nombre_cliente = st.text_input("Nombre del Cliente")
    monto_total = st.number_input(
        "Monto Total a Deber (con intereses)",
        min_value=0.0,
        step=10.0,
        format="%.2f",
    )
    modalidad = st.selectbox("Modalidad de Cobro", ["Diario", "Semanal"])

    if modalidad == "Diario":
      num_cuotas = st.number_input(
          "Cantidad de Días de Pago",
          min_value=1,
          max_value=365,
          value=24,
          step=1,
      )
    else:
      num_cuotas = st.number_input(
          "Cantidad de Semanas de Pago",
          min_value=1,
          max_value=52,
          value=4,
          step=1,
      )

    submit = st.form_submit_button("Crear Crédito")

    if submit:
      if nombre_cliente and monto_total > 0 and num_cuotas > 0:
        id_credito = len(st.session_state.creditos) + 1
        monto_cuota = monto_total / num_cuotas

        nuevo_credito = {
            "ID": id_credito,
            "Cliente": nombre_cliente,
            "Monto_Total": monto_total,
            "Modalidad": modalidad,
            "Plazo": num_cuotas,
            "Cuota_Valor": monto_cuota,
            "Estado": "Activo",
        }
        st.session_state.creditos.append(nuevo_credito)

        nuevas_filas = []
        for i in range(1, int(num_cuotas) + 1):
          nuevas_filas.append(
              {
                  "ID_Credito": id_credito,
                  "Cuota_N": i,
                  "Monto_Cuota": monto_cuota,
                  "Monto_Pagado": 0.0,
                  "Estado": "Pendiente",
                  "Metodo_Pago": "N/A",
                  "Fecha_Pago": "N/A",
              }
          )

        df_nuevos_pagos = pd.DataFrame(nuevas_filas)
        st.session_state.pagos = pd.concat(
            [st.session_state.pagos, df_nuevos_pagos], ignore_index=True
        )

        guardar_en_sheets()
        st.success(
            f"✅ ¡Crédito #{id_credito} creado y guardado con éxito para"
            f" {nombre_cliente}!"
        )
      else:
        st.error("Por favor completa todos los campos correctamente.")

# ---------------------------------------------------------
# 2. PANEL DE COBROS Y PAGOS
# ---------------------------------------------------------
elif menu == "Panel de Cobros y Pagos":
  st.header("💵 Panel de Cobros Diarios y Semanales")

  creditos_activos = [
      c for c in st.session_state.creditos if c["Estado"] == "Activo"
  ]

  if not creditos_activos:
    st.info("No hay créditos activos en este momento. Crea uno nuevo.")
  else:
    opciones_credito = {
        f"Crédito #{c['ID']} - {c['Cliente']} (Debe: {c['Monto_Total']})": c[
            "ID"
        ]
        for c in creditos_activos
    }
    credito_seleccionado_str = st.selectbox(
        "Seleccione el Crédito a Gestionar", list(opciones_credito.keys())
    )
    id_activo = opciones_credito[credito_seleccionado_str]

    credito_info = next(
        c for c in st.session_state.creditos if c["ID"] == id_activo
    )

    df_pagos_credito = st.session_state.pagos[
        st.session_state.pagos["ID_Credito"] == id_activo
    ]
    total_abonado = df_pagos_credito["Monto_Pagado"].sum()
    saldo_restante = credito_info["Monto_Total"] - total_abonado

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Cliente", credito_info["Cliente"])
    col2.metric("Total Deuda", f"${credito_info['Monto_Total']:.2f}")
    col3.metric("Abonado", f"${total_abonado:.2f}")
    col4.metric("Saldo Restante", f"${saldo_restante:.2f}")

    st.markdown("---")
    st.subheader("📋 Estado de Cuotas")
    st.dataframe(df_pagos_credito, use_container_width=True)

    st.markdown("### 💸 Registrar Pago o Abono Libre")
    with st.form("form_registrar_abono", clear_on_submit=True):
      monto_abono = st.number_input(
          "Monto del Abono / Pago recibido",
          min_value=0.01,
          step=1.0,
          format="%.2f",
      )
      metodo = st.selectbox(
          "Método de Pago", ["Pago Móvil", "Efectivo", "Binance"]
      )
      fecha = st.date_input("Fecha del Pago")

      btn_abonar = st.form_submit_button("Aplicar Abono")

      if btn_abonar:
        restante_por_aplicar = monto_abono
        indices_cuotas = df_pagos_credito.index[
            df_pagos_credito["Estado"] != "Pagado"
        ]

        if len(indices_cuotas) == 0:
          st.warning("⚠️ Este crédito ya está completamente pagado.")
        else:
          for idx in indices_cuotas:
            if restante_por_aplicar <= 0:
              break

            cuota_actual = st.session_state.pagos.loc[idx]
            deuda_cuota = (
                cuota_actual["Monto_Cuota"] - cuota_actual["Monto_Pagado"]
            )

            if restante_por_aplicar >= deuda_cuota:
              restante_por_aplicar -= deuda_cuota
              st.session_state.pagos.loc[idx, "Monto_Pagado"] += deuda_cuota
              st.session_state.pagos.loc[idx, "Estado"] = "Pagado"
              st.session_state.pagos.loc[idx, "Metodo_Pago"] = metodo
              st.session_state.pagos.loc[idx, "Fecha_Pago"] = str(fecha)
            else:
              st.session_state.pagos.loc[idx, "Monto_Pagado"] += (
                  restante_por_aplicar
              )
              st.session_state.pagos.loc[idx, "Estado"] = "Abonado"
              st.session_state.pagos.loc[idx, "Metodo_Pago"] = metodo
              st.session_state.pagos.loc[idx, "Fecha_Pago"] = str(fecha)
              restante_por_aplicar = 0

          nueva_transaccion = pd.DataFrame([
              {
                  "ID_Credito": id_activo,
                  "Cliente": credito_info["Cliente"],
                  "Monto_Abonado": monto_abono,
                  "Metodo_Pago": metodo,
                  "Fecha_Pago": str(fecha),
              }
          ])
          st.session_state.transacciones = pd.concat(
              [st.session_state.transacciones, nueva_transaccion],
              ignore_index=True,
          )

          guardar_en_sheets()
          st.success(
              f"✅ Abono de ${monto_abono:.2f} registrado con éxito y respaldado."
          )

    st.markdown("---")
    st.subheader("🔒 Cerrar Crédito")
    pendientes_restantes = len(
        st.session_state.pagos[
            (st.session_state.pagos["ID_Credito"] == id_activo)
            & (st.session_state.pagos["Estado"] != "Pagado")
        ]
    )

    if pendientes_restantes == 0:
      if st.button("Cerrar Crédito Finalizado"):
        for c in st.session_state.creditos:
          if c["ID"] == id_activo:
            c["Estado"] = "Cerrado"
        guardar_en_sheets()
        st.success("🔒 El crédito se ha cerrado correctamente.")
    else:
      if st.button("Forzar Cierre de Crédito"):
        for c in st.session_state.creditos:
          if c["ID"] == id_activo:
            c["Estado"] = "Cerrado"
        guardar_en_sheets()
        st.warning("⚠️ Crédito cerrado manualmente con deudas.")

# ---------------------------------------------------------
# 3. HISTORIAL DE PAGOS DEL DÍA A DÍA
# ---------------------------------------------------------
elif menu == "Historial de Pagos del Día":
  st.header("📅 Historial de Pagos del Día a Día")

  if st.session_state.transacciones.empty:
    st.info("No hay pagos o abonos registrados todavía.")
  else:
    fechas_disponibles = sorted(
        st.session_state.transacciones["Fecha_Pago"].unique().tolist()
    )
    if not fechas_disponibles:
      st.info("No hay fechas de pago válidas.")
    else:
      fecha_seleccionada = st.selectbox(
          "Seleccionar Fecha de Cobro", fechas_disponibles
      )

      df_filtrado_fecha = st.session_state.transacciones[
          st.session_state.transacciones["Fecha_Pago"] == fecha_seleccionada
      ]

      total_efectivo = df_filtrado_fecha[
          df_filtrado_fecha["Metodo_Pago"] == "Efectivo"
      ]["Monto_Abonado"].sum()
      total_pago_movil = df_filtrado_fecha[
          df_filtrado_fecha["Metodo_Pago"] == "Pago Móvil"
      ]["Monto_Abonado"].sum()
      total_binance = df_filtrado_fecha[
          df_filtrado_fecha["Metodo_Pago"] == "Binance"
      ]["Monto_Abonado"].sum()
      total_dia = total_efectivo + total_pago_movil + total_binance

      st.subheader(f"Resumen de Cobros para el día: {fecha_seleccionada}")
      col1, col2, col3, col4 = st.columns(4)
      col1.metric("💵 Efectivo", f"${total_efectivo:.2f}")
      col2.metric("📱 Pago Móvil", f"${total_pago_movil:.2f}")
      col3.metric("🪙 Binance", f"${total_binance:.2f}")
      col4.metric("📈 Total Día", f"${total_dia:.2f}")

      st.markdown("---")
      st.subheader("Detalle de transacciones de la fecha")
      st.dataframe(df_filtrado_fecha, use_container_width=True)

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
