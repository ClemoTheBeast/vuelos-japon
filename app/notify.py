"""
Envío de alertas por EMAIL (SMTP, por defecto Gmail).

Reemplaza al antiguo notificador de WhatsApp/Twilio.

Para Gmail necesitas una "contraseña de aplicación":
  1. Activa la verificación en 2 pasos en tu cuenta Google.
  2. Ve a https://myaccount.google.com/apppasswords
  3. Genera una contraseña para "Correo" y pégala en el .env como SMTP_PASSWORD.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from . import config


def enviar_email(asunto: str, cuerpo: str):
    """Envía un correo de texto a todos los destinatarios de EMAIL_TO."""
    if not config.EMAIL_TO:
        print("[notify] No hay destinatarios (EMAIL_TO vacío).")
        return
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("[notify] Falta configurar SMTP_USER / SMTP_PASSWORD.")
        return

    msg = MIMEMultipart()
    msg["From"] = config.EMAIL_FROM
    msg["To"] = ", ".join(config.EMAIL_TO)
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())
        print(f"[notify] Email enviado a {', '.join(config.EMAIL_TO)}")
    except Exception as e:
        print(f"[notify] Error enviando email: {e}")


def formatear_alerta(oferta: dict, promedio: float | None, motivo: str) -> tuple[str, str]:
    """Devuelve (asunto, cuerpo) para el correo de alerta."""
    from datetime import date

    p = oferta["precio"]
    m = oferta["moneda"]

    try:
        y1, m1, d1 = map(int, oferta["fecha_ida"].split("-"))
        y2, m2, d2 = map(int, oferta["fecha_vuelta"].split("-"))
        dur = (date(y2, m2, d2) - date(y1, m1, d1)).days + 1
    except Exception:
        dur = None

    asunto = f"✈️ Vuelo {oferta['origen']}→{oferta['destino']} a {p:.0f} {m}"

    lineas = [
        "Se encontró un vuelo que cumple tus criterios:",
        "",
        f"Ruta:      {oferta['origen']} → {oferta['destino']}",
        f"Precio:    {p:.0f} {m}",
        f"Ida:       {oferta['fecha_ida']}",
        f"Vuelta:    {oferta['fecha_vuelta']}",
        f"Aerolínea: {oferta['aerolinea']}",
        f"Escalas:   {oferta['escalas']}",
    ]

    if oferta.get("habiles") is not None:
        det = f"Días hábiles usados: {oferta['habiles']}"
        if dur:
            det += f"  ·  {dur} días corridos de viaje"
        lineas.append(det)
        extras = []
        if oferta.get("sale_tarde"):
            extras.append("la ida libera el día (sale tarde)")
        if oferta.get("jetlag_extra"):
            extras.append("+1 día por jet lag")
        if oferta.get("es_viernes"):
            extras.append("sale viernes")
        if extras:
            lineas.append("  (" + "; ".join(extras) + ")")

    if oferta.get("salida_scl") and oferta.get("llegada_scl"):
        lineas.append(
            f"Sale de SCL: {oferta['salida_scl'].replace('T', ' ')}"
        )
        lineas.append(
            f"Llega a SCL: {oferta['llegada_scl'].replace('T', ' ')}"
        )

    if promedio:
        dif = (p - promedio) / promedio * 100
        lineas.append(f"Comparado con el promedio ({promedio:.0f} {m}): {dif:+.1f}%")

    lineas.append("")
    lineas.append(f"Motivo de la alerta: {motivo}")
    lineas.append("")
    lineas.append(f"Ver / reservar: {oferta['deep_link']}")
    lineas.append("")
    lineas.append("(Precio de ida y vuelta completo. Puede variar levemente al reservar.)")

    return asunto, "\n".join(lineas)
