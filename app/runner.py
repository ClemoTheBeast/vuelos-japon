"""
Runner principal. En cada ciclo:
  - genera las combinaciones válidas de fechas (15-16 días hábiles gastados)
  - para cada destino y combinación, consulta Amadeus (máx 2 escalas)
  - guarda las ofertas y registra la mejor por destino
  - evalúa y dispara alertas de WhatsApp

Puede correr una sola vez (--once) o en loop cada CHECK_EVERY_HOURS.
"""
import sys
import time
import traceback
from datetime import datetime

from . import config, db, fechas
from .gflights_client import GoogleFlightsClient, CuotaAgotadaError
from .alertas import evaluar_ruta


def _seleccionar_combos():
    """
    Genera combinaciones de fechas y elige cuáles consultar en esta pasada.

    Estrategia (optimizada para encontrar el precio más bajo):
      - Considera TODOS los días de salida válidos (no solo viernes), porque
        el día de salida afecta mucho el precio y salir jueves/sábado puede
        ser bastante más barato.
      - Como son muchas combinaciones y no queremos gastar de más por pasada,
        ROTAMOS: cada día se consulta un bloque distinto, de modo que a lo
        largo de varios días se cubre todo el espacio de fechas. El punto de
        rotación avanza según el día del año.
      - Dentro del bloque, se priorizan las de MÁS días corridos de viaje
        (aprovechan mejor el viaje) como criterio de orden secundario.

    Si SOLO_VIERNES=true en el .env, vuelve al comportamiento antiguo
    (solo viernes). Por defecto ahora es false = todos los días.
    """
    from datetime import datetime as _dt

    combos = fechas.generar_combinaciones()
    if config.SOLO_VIERNES:
        combos = [c for c in combos if c["es_viernes"]]
        combos.sort(key=lambda c: (-c.get("dur_total", 0), c["ida"]))
        return combos[: config.MAX_COMBOS_POR_CICLO]

    # Todos los días: ordenar de forma estable (por fecha de ida, luego por
    # más días corridos) para tener una lista fija sobre la cual rotar.
    combos.sort(key=lambda c: (c["ida"], -c.get("dur_total", 0)))
    total = len(combos)
    n = config.MAX_COMBOS_POR_CICLO
    if total <= n:
        return combos

    # Rotación diaria: el bloque de inicio avanza cada día, cubriendo toda la
    # lista en ceil(total/n) días y luego repitiendo. Así, en pocos días se
    # exploran TODAS las combinaciones sin gastar todo en una sola pasada.
    dia_del_anio = _dt.utcnow().timetuple().tm_yday
    bloques = (total + n - 1) // n
    inicio = (dia_del_anio % bloques) * n
    seleccion = combos[inicio: inicio + n]
    # Si el bloque quedó corto al final, completar desde el principio
    if len(seleccion) < n:
        seleccion += combos[: n - len(seleccion)]
    return seleccion


def _elegir_mejor(ofertas: list[dict]) -> dict | None:
    """
    Elige la mejor oferta con la regla del usuario:
      1) precio más bajo
      2) si dos están dentro de EMPATE_PRECIO_PCT de diferencia, se consideran
         empatadas y gana la de MÁS días corridos de viaje.

    Implementación: tomamos el precio mínimo como referencia; entre todas las
    ofertas cuyo precio esté dentro del margen respecto a ese mínimo,
    devolvemos la de mayor duración total. Si aún hay empate, la más barata.
    """
    if not ofertas:
        return None
    precio_min = min(o["precio"] for o in ofertas)
    margen = precio_min * (1 + config.EMPATE_PRECIO_PCT / 100)
    candidatas = [o for o in ofertas if o["precio"] <= margen]
    # más días corridos primero; a igualdad, menor precio
    candidatas.sort(key=lambda o: (-_dur_total(o), o["precio"]))
    return candidatas[0]


def _dur_total(oferta: dict) -> int:
    """Días corridos del viaje según fechas de ida y vuelta guardadas."""
    from datetime import date

    def _d(s):
        y, m, dd = map(int, s.split("-"))
        return date(y, m, dd)

    try:
        return (_d(oferta["fecha_vuelta"]) - _d(oferta["fecha_ida"])).days + 1
    except Exception:
        return 0


def un_ciclo():
    print(f"\n=== Ciclo {datetime.utcnow().isoformat()} ===")
    db.init_db()
    cliente = GoogleFlightsClient()
    print(f"Búsquedas usadas este mes: {cliente.llamadas}/{config.MAX_LLAMADAS_MES}")

    combos = _seleccionar_combos()
    print(f"Combinaciones a consultar este ciclo: {len(combos)}")
    print(fechas.resumen_combinaciones())

    mejores = {}

    for destino in config.DESTINATIONS:
        candidatas_destino = []
        for combo in combos:
            try:
                ofertas = cliente.buscar(
                    destino, combo["ida"], combo["vuelta"], combo
                )
                if not ofertas:
                    continue
                db.guardar_ofertas(ofertas)
                # mejor de esta combinación (precio, desempate por días corridos)
                mejor_combo = _elegir_mejor(ofertas)
                if mejor_combo:
                    candidatas_destino.append(mejor_combo)
            except CuotaAgotadaError as e:
                print(f"[cuota] {e}")
                print(f"[cuota] Llamadas usadas este mes: {cliente.llamadas}")
                # cortamos el ciclo completo: no seguimos consultando
                return
            except Exception as e:
                print(f"[{destino} {combo['ida']}->{combo['vuelta']}] ERROR: {e}")
            time.sleep(0.3)

        # mejor global del destino, aplicando la misma regla de desempate
        mejor = _elegir_mejor(candidatas_destino)
        if mejor:
            mejores[destino] = mejor

        if destino in mejores:
            m = mejores[destino]
            vie = "viernes" if m.get("es_viernes") else ""
            libera = "ida-libera" if m.get("sale_tarde") else ""
            jl = "+jetlag" if m.get("jetlag_extra") else ""
            print(f"[{destino}] mejor: {m['precio']:.0f} {m['moneda']} | "
                  f"{m['fecha_ida']}->{m['fecha_vuelta']} "
                  f"({_dur_total(m)} dias corridos, {m['aerolinea']}, "
                  f"{m['escalas']} escalas, {m.get('habiles')} hab "
                  f"{vie} {libera} {jl})")
            alerto = evaluar_ruta(config.ORIGIN, destino, m)
            if alerto:
                print(f"[{destino}] ALERTA ENVIADA")
        else:
            print(f"[{destino}] sin ofertas validas este ciclo.")


def main():
    once = "--once" in sys.argv
    if once:
        un_ciclo()
        return
    print(f"Iniciando loop. Chequeo cada {config.CHECK_EVERY_HOURS}h.")
    while True:
        try:
            un_ciclo()
        except Exception:
            traceback.print_exc()
        time.sleep(config.CHECK_EVERY_HOURS * 3600)


if __name__ == "__main__":
    main()
