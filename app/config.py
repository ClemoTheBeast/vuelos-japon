"""
Configuración central. Todo se lee de variables de entorno (.env).
No pongas claves aquí directamente.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Apify (datos de vuelos, actor de Skyscanner, pago por uso) ---
# Consíguelo gratis en https://console.apify.com (trae ~5 USD de crédito).
# Settings -> API & Integrations -> copia tu token.
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
# Mercado/moneda/idioma para los precios (Chile / dólar por defecto)
MARKET = os.getenv("MARKET", "US")
LOCALE = os.getenv("LOCALE", "es-ES")
COUNTRY_CODE = os.getenv("COUNTRY_CODE", "CL")

# Tope de seguridad: máximo de BÚSQUEDAS (ejecuciones del actor) por mes.
# El sistema se detiene al llegar, para no gastar de más. Cada búsqueda
# devuelve varios vuelos y cuesta una fracción de dólar.
MAX_LLAMADAS_MES = int(os.getenv("MAX_LLAMADAS_MES", "400"))

# --- Email (alertas, vía SMTP de Gmail) ---
# Usa una "contraseña de aplicación" de Gmail (no tu clave normal).
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")          # tu_correo@gmail.com
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # contraseña de aplicación
EMAIL_FROM = os.getenv("EMAIL_FROM", os.getenv("SMTP_USER", ""))
# Destinatarios de las alertas, separados por coma:
EMAIL_TO = [
    e.strip() for e in os.getenv("EMAIL_TO", "").split(",") if e.strip()
]

# --- Parámetros de la búsqueda de vuelos ---
ORIGIN = os.getenv("ORIGIN", "SCL")            # Santiago de Chile
# Aeropuertos de Japón a monitorear (Tokio Narita, Tokio Haneda, Osaka Kansai)
DESTINATIONS = [d.strip() for d in os.getenv("DESTINATIONS", "TYO,KIX").split(",")]

ADULTS = int(os.getenv("ADULTS", "1"))
CURRENCY = os.getenv("CURRENCY", "USD")
MAX_OFFERS = int(os.getenv("MAX_OFFERS", "30"))  # ofertas por consulta
# Tope de precio para la BÚSQUEDA (en la moneda de CURRENCY). El scraper solo
# devuelve vuelos a este precio o menos. Ponerlo cerca de tu umbral de interés
# recorta muchísimo los resultados (solo trae lo barato), baja el costo y deja
# capturar todas las aerolíneas baratas. 0 = sin tope.
MAXPRICE_BUSQUEDA = int(os.getenv("MAXPRICE_BUSQUEDA", "2600"))
# Duración máxima de un tramo en HORAS (vuelo + escalas). Los vuelos que tardan
# más se descartan. 0 = sin límite. (Distinto de DUR_TOTAL, que son días de viaje.)
MAX_HORAS_VUELO = float(os.getenv("MAX_HORAS_VUELO", "40"))

# --- Reglas de fechas por días hábiles de vacaciones ---
# Ventana en que puede iniciar el viaje (fecha de salida desde SCL):
MIN_SALIDA = os.getenv("MIN_SALIDA", "2027-03-12")
MAX_SALIDA = os.getenv("MAX_SALIDA", "2027-04-02")
# Días hábiles de vacaciones a gastar (mín y máx):
HABILES_MIN = int(os.getenv("HABILES_MIN", "14"))
HABILES_MAX = int(os.getenv("HABILES_MAX", "16"))
# Rango de duración total del viaje en días corridos (acota la búsqueda):
DUR_TOTAL_MIN = int(os.getenv("DUR_TOTAL_MIN", "20"))
DUR_TOTAL_MAX = int(os.getenv("DUR_TOTAL_MAX", "28"))
# Máximo de escalas permitidas por tramo:
MAX_ESCALAS = int(os.getenv("MAX_ESCALAS", "2"))
# Solo considerar combinaciones que salen en viernes:
SOLO_VIERNES = os.getenv("SOLO_VIERNES", "false").lower() == "true"

# Días de la semana permitidos para SALIR desde SCL (lunes=0 ... domingo=6).
# Por defecto: miércoles(2), jueves(3), viernes(4), sábado(5).
# Se define como lista de números separados por coma en el .env.
DIAS_SALIDA = [
    int(x.strip())
    for x in os.getenv("DIAS_SALIDA", "2,3,4,5").split(",")
    if x.strip() != ""
]
# Hora mínima de salida para el miércoles (formato "HH:MM"). Un vuelo que
# salga miércoles ANTES de esta hora se descarta (para no gastar el día
# laboral completo). No afecta a jueves/viernes/sábado.
HORA_MIN_MIERCOLES = os.getenv("HORA_MIN_MIERCOLES", "19:00")
# Límite de combinaciones a consultar por ciclo (protege tu cuota de API).
# Se priorizan viernes y las más baratas históricamente.
MAX_COMBOS_POR_CICLO = int(os.getenv("MAX_COMBOS_POR_CICLO", "8"))

# Al elegir la mejor oferta: precio primero. Si dos ofertas están dentro de
# este % de diferencia de precio, se consideran "empatadas" y gana la de MÁS
# días corridos de viaje. 0 = empate estricto (solo mismo precio exacto).
EMPATE_PRECIO_PCT = float(os.getenv("EMPATE_PRECIO_PCT", "2"))

# --- Lógica de alertas ---
# Umbral absoluto: avisa si el precio baja de esto (en CURRENCY). 0 = desactivado.
PRICE_THRESHOLD = float(os.getenv("PRICE_THRESHOLD", "0"))
# Umbral relativo: avisa si el precio está X% bajo el promedio histórico. 0 = desactivado.
PCT_BELOW_AVG = float(os.getenv("PCT_BELOW_AVG", "10"))
# No repetir la misma alerta si no bajó al menos este % respecto a la última alertada
ALERT_COOLDOWN_PCT = float(os.getenv("ALERT_COOLDOWN_PCT", "3"))

# --- Ejecución ---
CHECK_EVERY_HOURS = float(os.getenv("CHECK_EVERY_HOURS", "24"))
DB_PATH = os.getenv("DB_PATH", "/data/precios.db")
