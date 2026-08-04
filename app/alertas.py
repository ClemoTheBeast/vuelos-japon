"""
Decide cuándo disparar una alerta, según umbral absoluto y/o
desviación respecto al promedio histórico.
"""
from . import config, db
from .notify import enviar_email, formatear_alerta


def evaluar_ruta(origen: str, destino: str, mejor_oferta: dict):
    """
    Evalúa la mejor oferta de una ruta y envía alerta si corresponde.
    Devuelve True si alertó.
    """
    precio = mejor_oferta["precio"]
    promedio = db.precio_promedio(origen, destino, dias=30)

    motivos = []

    # 1) Umbral absoluto
    if config.PRICE_THRESHOLD > 0 and precio <= config.PRICE_THRESHOLD:
        motivos.append(f"Bajo umbral de {config.PRICE_THRESHOLD:.0f}")

    # 2) Umbral relativo (bajo el promedio)
    if promedio and config.PCT_BELOW_AVG > 0:
        umbral_rel = promedio * (1 - config.PCT_BELOW_AVG / 100)
        if precio <= umbral_rel:
            motivos.append(f"{config.PCT_BELOW_AVG:.0f}% bajo el promedio")

    if not motivos:
        return False

    # Anti-spam: no repetir si no bajó lo suficiente desde la última alerta
    ult = db.ultima_alerta(origen, destino)
    if ult and ult["precio"]:
        mejora = (ult["precio"] - precio) / ult["precio"] * 100
        if mejora < config.ALERT_COOLDOWN_PCT:
            print(f"[alertas] {origen}->{destino} en cooldown "
                  f"(solo {mejora:.1f}% mejor que última alerta).")
            return False

    motivo = " + ".join(motivos)
    asunto, cuerpo = formatear_alerta(mejor_oferta, promedio, motivo)
    enviar_email(asunto, cuerpo)
    db.registrar_alerta(origen, destino, precio,
                        mejor_oferta["moneda"], motivo)
    return True
