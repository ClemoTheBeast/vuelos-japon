"""
Cliente de vuelos vía Apify — actor memo23/google-flights-scraper.

Lee precios reales de Google Flights (todas las aerolíneas: LATAM, American,
etc.). CONFIRMADO: el precio de cada fila es el del IDA-VUELTA COMPLETO real
(comprable), no un tramo suelto. Se verificó contra el navegador: coincide
al 100%.

Una búsqueda = un par (ida, vuelta) para un destino. Se le pasan ambas
fechas; el actor devuelve itinerarios ida-vuelta con su precio total. Los
"segments" mostrados son los de la ida, pero el precio es del viaje redondo.

Config en .env: APIFY_TOKEN, MARKET=US (CL devuelve vacío), CURRENCY=USD.

Campos por fila (confirmados en pruebas reales):
  price, currency, stops, carrier-name, from-code, to-code,
  depart-date, depart-time, arrive-date, arrive-time, duration-minutes,
  segments-0-depart ... segments-N-arrive (segmentos de la IDA)
"""
import os
import json
import requests
from datetime import datetime, timedelta

from . import config, fechas

_CONTADOR_PATH = os.path.join(os.path.dirname(config.DB_PATH) or ".", "contador_api.json")
ACTOR_ID = "memo23~google-flights-scraper"


def _mes_actual():
    return datetime.utcnow().strftime("%Y-%m")


def _leer_contador():
    try:
        with open(_CONTADOR_PATH) as f:
            data = json.load(f)
        if data.get("mes") == _mes_actual():
            return data.get("llamadas", 0)
    except Exception:
        pass
    return 0


def _guardar_contador(n):
    try:
        os.makedirs(os.path.dirname(_CONTADOR_PATH) or ".", exist_ok=True)
        with open(_CONTADOR_PATH, "w") as f:
            json.dump({"mes": _mes_actual(), "llamadas": n}, f)
    except Exception as e:
        print(f"[api] No se pudo guardar el contador: {e}")


class CuotaAgotadaError(Exception):
    """Se alcanzó el tope mensual de búsquedas configurado."""


class GoogleFlightsClient:
    def __init__(self):
        self.token = config.APIFY_TOKEN
        self.base = "https://api.apify.com/v2"
        self.llamadas = _leer_contador()

    def _consumir(self):
        if self.llamadas >= config.MAX_LLAMADAS_MES:
            raise CuotaAgotadaError(
                f"Alcanzado el tope de {config.MAX_LLAMADAS_MES} búsquedas/mes. "
                "Se detiene para no gastar de más."
            )
        self.llamadas += 1
        _guardar_contador(self.llamadas)

    def buscar(self, destino: str, ida: str, vuelta: str, combo: dict | None = None):
        """
        Una búsqueda ida-vuelta SCL<->destino para las fechas dadas.
        Devuelve las ofertas (itinerarios redondos) que cumplen escalas y
        días hábiles. El precio de cada oferta es el del ida-vuelta completo.
        """
        self._consumir()
        combo = combo or {}
        payload = {
            "origin": config.ORIGIN,
            "destination": destino,
            "departDate": ida,
            "returnDate": vuelta,       # ida-vuelta: precio redondo completo
            "adults": config.ADULTS,
            "currency": config.CURRENCY,
            "market": config.MARKET,     # US (CL devuelve vacío)
            "language": "en",
            "maxItems": config.MAX_OFFERS,
            # Filtros NATIVOS del scraper: descartan en origen los vuelos que
            # no sirven, para que cada resultado traído sea útil (y capturar
            # las aerolíneas baratas sin gastar en basura cara / muchas escalas).
            "maxStops": config.MAX_ESCALAS,   # solo <= tus escalas máximas
            "proxy": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
        }
        # Tope de precio opcional: si está configurado, solo trae vuelos a ese
        # precio o menos. Evita llenar la lista con tarifas carísimas y deja
        # espacio para las baratas. Se pone algo por sobre tu umbral para no
        # perder de vista el nivel del mercado.
        if config.MAXPRICE_BUSQUEDA > 0:
            payload["maxPrice"] = config.MAXPRICE_BUSQUEDA
        url = (f"{self.base}/acts/{ACTOR_ID}/run-sync-get-dataset-items"
               f"?token={self.token}")
        resp = requests.post(url, json=payload, timeout=240)
        resp.raise_for_status()
        return self._parsear(resp.json(), destino, ida, vuelta, combo)

    def _parsear(self, filas, destino, ida, vuelta, combo):
        es_viernes = 1 if combo.get("es_viernes") else 0
        ahora = datetime.utcnow().isoformat()
        ofertas = []

        for f in filas:
            precio = f.get("price")
            if precio is None:
                continue
            escalas = f.get("stops", 9)
            if escalas is None or escalas > config.MAX_ESCALAS:
                continue

            # Filtro de duración del tramo (en horas). Descarta vuelos
            # demasiado largos (muchas horas de escalas). 0 = sin límite.
            if config.MAX_HORAS_VUELO > 0:
                dur_min = f.get("duration-minutes")
                if dur_min:
                    try:
                        if float(dur_min) / 60.0 > config.MAX_HORAS_VUELO:
                            continue
                    except (ValueError, TypeError):
                        pass

            # Horario de SALIDA desde SCL = primer segmento de la ida.
            dep = f.get("segments-0-depart")
            if not dep:
                d = f.get("depart-date"); t = f.get("depart-time", "00:00")
                dep = f"{d}T{t}" if d else None
            if not dep:
                continue

            try:
                dt_salida = datetime.fromisoformat(dep.replace("Z", ""))
            except (ValueError, AttributeError):
                continue

            # Regla de ventana de salida: si sale MIÉRCOLES (weekday 2), debe
            # ser a la hora mínima o más tarde (por defecto 19:00), para no
            # gastar el día laboral. Jueves/viernes/sábado: cualquier hora.
            if dt_salida.weekday() == 2:
                try:
                    hmin, mmin = map(int, config.HORA_MIN_MIERCOLES.split(":"))
                except ValueError:
                    hmin, mmin = 19, 0
                if (dt_salida.hour, dt_salida.minute) < (hmin, mmin):
                    continue

            # La LLEGADA a SCL (para el conteo de días hábiles) es en la fecha
            # de vuelta. El actor no expone el horario exacto de llegada del
            # tramo de regreso, así que estimamos: llega en la fecha 'vuelta'.
            # Para las reglas de jet lag usamos una hora conservadora (media
            # tarde) salvo que el propio itinerario indique otra cosa.
            try:
                y, m, dd = map(int, vuelta.split("-"))
                # hora estimada de llegada a SCL: 18:00 (conservador para jetlag)
                dt_llegada = datetime(y, m, dd, 18, 0)
            except ValueError:
                continue

            habiles = fechas.habiles_por_vuelo(dt_salida, dt_llegada)
            if not (config.HABILES_MIN <= habiles <= config.HABILES_MAX):
                continue

            sale_libera = 1 if fechas._salida_libera_dia(dt_salida) else 0
            jetlag_extra = 0
            if dt_llegada.hour >= 15 and fechas.es_habil(dt_llegada.date() + timedelta(days=1)):
                jetlag_extra = 1

            link = (
                "https://www.google.com/travel/flights?q="
                f"flights%20from%20{config.ORIGIN}%20to%20{destino}%20"
                f"{ida}%20through%20{vuelta}"
            )
            ofertas.append({
                "consultado_en": ahora,
                "origen": config.ORIGIN,
                "destino": destino,
                "fecha_ida": ida,
                "fecha_vuelta": vuelta,
                "salida_scl": dt_salida.isoformat(),
                "llegada_scl": dt_llegada.isoformat(),
                "precio": float(precio),
                "moneda": f.get("currency", config.CURRENCY),
                "aerolinea": f.get("carrier-name", ""),
                "escalas": escalas,
                "duracion": str(f.get("duration-minutes", "")),
                "deep_link": link,
                "habiles": habiles,
                "sale_tarde": sale_libera,
                "jetlag_extra": jetlag_extra,
                "es_viernes": es_viernes,
            })
        return ofertas
