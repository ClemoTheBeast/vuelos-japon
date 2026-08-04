"""
Dashboard web del monitor de vuelos SCL → Japón.
Se despliega en Streamlit Community Cloud. Lee la base de datos
data/precios.db que el monitor actualiza en el repositorio.
Local:  streamlit run streamlit_app.py
"""
import os
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = os.getenv("DB_PATH", "data/precios.db")
CURRENCY = os.getenv("CURRENCY", "USD")

st.set_page_config(page_title="Vuelos SCL → Japón", layout="wide")
st.title("✈️ Monitor de vuelos SCL → Japón")
st.caption(
    "Precios de ida y vuelta reales (Google Flights). El monitor corre a "
    "diario y actualiza estos datos automáticamente."
)


def cargar_datos():
    if not os.path.exists(DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM ofertas", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


df = cargar_datos()

if df.empty:
    st.info(
        "Todavía no hay datos registrados. El monitor guarda precios en cada "
        "corrida diaria; vuelve en uno o dos días para ver la primera curva."
    )
    st.stop()

df["consultado_en"] = pd.to_datetime(df["consultado_en"])

destinos = sorted(df["destino"].unique())
sel = st.multiselect("Aeropuertos de destino", destinos, default=destinos)
df = df[df["destino"].isin(sel)]

resumen = (
    df.groupby(["consultado_en", "destino"])["precio"]
    .min()
    .reset_index()
    .sort_values("consultado_en")
)

fig = go.Figure()
for dest in sel:
    sub = resumen[resumen["destino"] == dest]
    fig.add_trace(go.Scatter(
        x=sub["consultado_en"], y=sub["precio"],
        mode="lines+markers", name=dest,
    ))
    if len(sub) >= 3:
        ma = sub["precio"].rolling(5, min_periods=2).mean()
        fig.add_trace(go.Scatter(
            x=sub["consultado_en"], y=ma,
            mode="lines", name=f"{dest} (media móvil)",
            line=dict(dash="dot"),
        ))

fig.update_layout(
    xaxis_title="Fecha de consulta",
    yaxis_title=f"Precio mínimo ({CURRENCY})",
    hovermode="x unified",
    height=500,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Resumen por destino")
cols = st.columns(len(sel) if sel else 1)
for i, dest in enumerate(sel):
    sub = resumen[resumen["destino"] == dest]["precio"]
    if sub.empty:
        continue
    actual = sub.iloc[-1]
    prom = sub.mean()
    minimo = sub.min()
    with cols[i]:
        st.metric(
            label=dest,
            value=f"{actual:.0f} {CURRENCY}",
            delta=f"{(actual - prom) / prom * 100:+.1f}% vs prom",
            delta_color="inverse",
        )
        st.caption(f"Mínimo histórico: {minimo:.0f} {CURRENCY}")

st.subheader("Mejores ofertas de la última revisión")
ultima_fecha = df["consultado_en"].max()
recientes = df[df["consultado_en"] == ultima_fecha].sort_values("precio")
columnas = [c for c in ["destino", "precio", "moneda", "aerolinea", "escalas",
                        "fecha_ida", "fecha_vuelta", "habiles", "deep_link"]
            if c in recientes.columns]
st.dataframe(recientes[columnas], use_container_width=True)
st.caption(f"Última revisión: {ultima_fecha}")
