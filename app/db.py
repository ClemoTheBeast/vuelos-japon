"""
Capa de base de datos (SQLite). Guarda cada oferta consultada
y el historial de alertas enviadas.
"""
import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime

from . import config


def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


@contextmanager
def get_conn():
    _ensure_dir(config.DB_PATH)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ofertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                consultado_en TEXT NOT NULL,
                origen TEXT NOT NULL,
                destino TEXT NOT NULL,
                fecha_ida TEXT,
                fecha_vuelta TEXT,
                precio REAL NOT NULL,
                moneda TEXT NOT NULL,
                aerolinea TEXT,
                escalas INTEGER,
                duracion TEXT,
                deep_link TEXT,
                salida_scl TEXT,
                llegada_scl TEXT,
                habiles INTEGER,
                sale_tarde INTEGER,
                jetlag_extra INTEGER,
                es_viernes INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_ofertas_ruta
                ON ofertas (origen, destino, consultado_en);

            CREATE TABLE IF NOT EXISTS alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enviado_en TEXT NOT NULL,
                origen TEXT,
                destino TEXT,
                precio REAL,
                moneda TEXT,
                motivo TEXT
            );
            """
        )


def guardar_ofertas(ofertas: list[dict]):
    if not ofertas:
        return
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO ofertas
            (consultado_en, origen, destino, fecha_ida, fecha_vuelta,
             precio, moneda, aerolinea, escalas, duracion, deep_link,
             salida_scl, llegada_scl, habiles, sale_tarde, jetlag_extra,
             es_viernes)
            VALUES
            (:consultado_en, :origen, :destino, :fecha_ida, :fecha_vuelta,
             :precio, :moneda, :aerolinea, :escalas, :duracion, :deep_link,
             :salida_scl, :llegada_scl, :habiles, :sale_tarde, :jetlag_extra,
             :es_viernes)
            """,
            ofertas,
        )


def precio_promedio(origen: str, destino: str, dias: int = 30) -> float | None:
    """Promedio del precio mínimo por consulta en los últimos N días."""
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT AVG(min_precio) AS avg_precio FROM (
                SELECT consultado_en, MIN(precio) AS min_precio
                FROM ofertas
                WHERE origen = ? AND destino = ?
                  AND consultado_en >= datetime('now', ?)
                GROUP BY consultado_en
            )
            """,
            (origen, destino, f"-{dias} days"),
        ).fetchone()
        return row["avg_precio"] if row and row["avg_precio"] is not None else None


def ultima_alerta(origen: str, destino: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM alertas
            WHERE origen = ? AND destino = ?
            ORDER BY enviado_en DESC LIMIT 1
            """,
            (origen, destino),
        ).fetchone()
        return dict(row) if row else None


def registrar_alerta(origen, destino, precio, moneda, motivo):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO alertas (enviado_en, origen, destino, precio, moneda, motivo)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (datetime.utcnow().isoformat(), origen, destino, precio, moneda, motivo),
        )


def historico_df():
    """Devuelve todo el histórico como DataFrame para el dashboard."""
    import pandas as pd

    with get_conn() as conn:
        return pd.read_sql_query("SELECT * FROM ofertas ORDER BY consultado_en", conn)
