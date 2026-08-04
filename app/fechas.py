"""
Reglas de conteo de DÍAS HÁBILES DE VACACIONES gastados en el viaje.

A diferencia de una versión anterior, el conteo ya NO se hace sobre fechas
abstractas, sino sobre los datos REALES de cada vuelo:
  - hora de salida desde Santiago (para la ida)
  - fecha y hora de llegada a Santiago (para el regreso)

Reglas (definidas por el usuario):

IDA (según salida desde SCL):
  - Sale VIERNES a las 17:00 o más tarde  -> ese día se LIBERA (no se gasta).
  - Sale otro día hábil a las 20:00 o más tarde -> ese día se LIBERA.
  - En otro caso, el día de salida se cuenta si es hábil.

REGRESO (según llegada a SCL):
  - El día de llegada, si es hábil, se cuenta.
  - Si se llega a las 15:00 o más tarde, el DÍA SIGUIENTE también se cuenta,
    pero solo si es hábil (si cae sáb/dom/feriado, no se descuenta).

Los días intermedios hábiles entre ida y regreso siempre se cuentan.

Además, `generar_combinaciones()` produce el conjunto de pares de FECHAS
(ida, vuelta) a consultar en la API, dentro de la ventana permitida. El
conteo fino y definitivo se hace luego con los horarios reales de cada
oferta mediante `habiles_por_vuelo()`.
"""
from datetime import date, datetime, timedelta

from . import config

# Feriados de Chile relevantes al rango (marzo-abril 2027).
# Semana Santa 2027: Viernes Santo 26-mar, Sábado Santo 27-mar.
FERIADOS_CL = {
    date(2027, 3, 26),
    date(2027, 3, 27),
}


def _parse(d: str) -> date:
    y, m, dd = map(int, d.split("-"))
    return date(y, m, dd)


def es_habil(d: date) -> bool:
    """Lunes a viernes y que no sea feriado chileno."""
    return d.weekday() < 5 and d not in FERIADOS_CL


def _salida_libera_dia(dt_salida: datetime) -> bool:
    """
    True si el día de salida desde SCL se libera (no se gasta):
      - viernes y hora >= 17:00
      - otro día hábil y hora >= 20:00
    """
    if not es_habil(dt_salida.date()):
        return False  # si ya no es hábil, no hay nada que liberar
    es_viernes = dt_salida.weekday() == 4
    if es_viernes:
        return dt_salida.hour >= 17 or (dt_salida.hour == 17 and dt_salida.minute >= 0)
    return dt_salida.hour >= 20


def habiles_por_vuelo(dt_salida_scl: datetime, dt_llegada_scl: datetime) -> int:
    """
    Cuenta los días hábiles de vacaciones gastados usando los horarios reales.

    dt_salida_scl : datetime de salida desde Santiago (ida).
    dt_llegada_scl: datetime de llegada a Santiago (regreso).
    """
    dia_ida = dt_salida_scl.date()
    dia_llegada = dt_llegada_scl.date()

    total = 0
    d = dia_ida
    while d <= dia_llegada:
        if es_habil(d):
            # Excepción de ida: si es el día de salida y la salida lo libera.
            if d == dia_ida and _salida_libera_dia(dt_salida_scl):
                pass
            else:
                total += 1
        d += timedelta(days=1)

    # Regla de jet lag: si se llega >=15:00, el día siguiente cuenta si es hábil.
    if dt_llegada_scl.hour >= 15:
        siguiente = dia_llegada + timedelta(days=1)
        if es_habil(siguiente):
            total += 1

    return total


def generar_combinaciones() -> list[dict]:
    """
    Devuelve los pares de FECHAS (ida, vuelta) a consultar en la API.

    Como los horarios reales aún no se conocen (los trae la API), aquí se usa
    una estimación amplia para no descartar fechas de más: se cuentan los
    días hábiles entre ida y vuelta de forma conservadora y se deja un margen
    de +/-1 respecto al rango objetivo. El filtro EXACTO se aplica después,
    por vuelo, con `habiles_por_vuelo()`.
    """
    min_salida = _parse(config.MIN_SALIDA)
    max_salida = _parse(config.MAX_SALIDA)
    hab_min, hab_max = config.HABILES_MIN, config.HABILES_MAX
    dur_min, dur_max = config.DUR_TOTAL_MIN, config.DUR_TOTAL_MAX

    combos = []
    d = min_salida
    while d <= max_salida:
        # Filtro de DÍA de salida permitido (según DIAS_SALIDA en config).
        # weekday(): lunes=0 ... domingo=6. Por defecto: miér(2), jue(3),
        # vie(4), sáb(5). El corte de hora del miércoles se aplica luego,
        # cuando ya conocemos la hora real del vuelo (en el cliente).
        if d.weekday() not in config.DIAS_SALIDA:
            d += timedelta(days=1)
            continue
        for dur in range(dur_min, dur_max + 1):
            vuelta = d + timedelta(days=dur)
            # estimación conservadora: sin liberar ida, sin jet lag,
            # contando hábiles entre ambas fechas
            est = 0
            dd = d
            while dd <= vuelta:
                if es_habil(dd):
                    est += 1
                dd += timedelta(days=1)
            # margen amplio: aceptamos si la estimación está cerca del objetivo
            if (hab_min - 1) <= est <= (hab_max + 1):
                combos.append(
                    {
                        "ida": d.isoformat(),
                        "vuelta": vuelta.isoformat(),
                        "dur_total": (vuelta - d).days + 1,
                        "es_viernes": d.weekday() == 4,
                    }
                )
        d += timedelta(days=1)
    return combos


def resumen_combinaciones() -> str:
    combos = generar_combinaciones()
    viernes = sorted({c["ida"] for c in combos if c["es_viernes"]})
    return (
        f"{len(combos)} pares de fechas a consultar. "
        f"Salidas en viernes: {', '.join(viernes) if viernes else 'ninguna'}."
    )
