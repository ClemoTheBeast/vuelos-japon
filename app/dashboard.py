"""
Dashboard web con la curva de precios y tendencias.
Ejecutar: streamlit run app/dashboard.py
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from . import db, config

st.set_page_config(page_title="Vuelos SCL → Japón", layout="wide")
st.title("✈️ Monitor de vuelos SCL → Japón")

db.init_db()
df = db.historico_df()

if df.empty:
    st.info("Todavía no hay datos. Deja correr el runner unas horas.")
    st.stop()

df["consultado_en"] = pd.to_datetime(df["consultado_en"])

destinos = sorted(df["destino"].unique())
sel = st.multiselect("Destinos", destinos, default=destinos)

df = df[df["destino"].isin(sel)]

# Precio mínimo por consulta y destino
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
    # media móvil
    if len(sub) >= 3:
        ma = sub["precio"].rolling(5, min_periods=2).mean()
        fig.add_trace(go.Scatter(
            x=sub["consultado_en"], y=ma,
            mode="lines", name=f"{dest} (media móvil)",
            line=dict(dash="dot"),
        ))

fig.update_layout(
    xaxis_title="Fecha de consulta",
    yaxis_title=f"Precio mínimo ({config.CURRENCY})",
    hovermode="x unified",
    height=500,
)
st.plotly_chart(fig, width="stretch")

# Métricas
st.subheader("Resumen por destino")
cols = st.columns(len(sel) if sel else 1)
for i, dest in enumerate(sel):
    sub = resumen[resumen["destino"] == dest]["precio"]
    actual = sub.iloc[-1]
    prom = sub.mean()
    minimo = sub.min()
    with cols[i]:
        st.metric(
            label=dest,
            value=f"{actual:.0f} {config.CURRENCY}",
            delta=f"{(actual - prom) / prom * 100:+.1f}% vs prom",
            delta_color="inverse",
        )
        st.caption(f"Mínimo histórico: {minimo:.0f} {config.CURRENCY}")

# Tabla de mejores ofertas actuales
st.subheader("Mejores ofertas registradas")
ultima_fecha = df["consultado_en"].max()
recientes = df[df["consultado_en"] == ultima_fecha].sort_values("precio")
st.dataframe(
    recientes[["destino", "precio", "moneda", "aerolinea",
               "escalas", "fecha_ida", "fecha_vuelta", "deep_link"]],
    width="stretch",
)
