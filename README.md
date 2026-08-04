# Monitor de vuelos SCL → Japón ✈️

Revisa precios de vuelos Santiago → Japón una vez al día, guarda el
histórico, dibuja la curva de precios y te avisa por **email** cuando hay
una oferta bajo tu umbral o bajo el promedio.

No necesitas programar nada. Solo crear dos cuentas gratis, pegar tus
claves en un archivo de texto y ejecutarlo.

---

## Qué hace

- Consulta **Google Flights vía Apify** (actor memo23/google-flights-scraper,
  pago por uso ~1 USD/1000 resultados) — precios reales de ida-vuelta de
  todas las aerolíneas (LATAM, American, etc.), verificados contra el
  navegador.
- Monitorea aeropuertos de Japón: Tokio (NRT, HND) y Osaka (KIX).
- Prueba las combinaciones de fechas válidas según tus reglas de días
  hábiles y busca la más barata (precio primero; empate → más días corridos).
- Máximo 2 escalas por tramo.
- Guarda todo en una base de datos y calcula promedio, mínimo y tendencia.
- Envía **email** a los destinatarios que definas cuando el precio baja.
- Dashboard web con la **curva de precios**.
- **Tope de seguridad**: se detiene al llegar al máximo mensual de llamadas
  que configures, para no generar cargos por exceso.

### Lógica de fechas (días hábiles de vacaciones)

Con los horarios reales de cada vuelo, cuenta los días hábiles gastados y
solo alerta ofertas que gastan **14, 15 o 16 días hábiles**.

**Ida** (según hora de salida desde Santiago):
- Sale viernes ≥17:00 → ese día se libera.
- Sale otro día hábil ≥20:00 → ese día se libera.
- En otro caso, el día de salida cuenta si es hábil.

**Regreso** (según fecha y hora de llegada a Santiago):
- El día de llegada, si es hábil, cuenta.
- Si llegas ≥15:00, el día siguiente también cuenta (jet lag), salvo que
  caiga sábado, domingo o feriado.

Feriados considerados: Semana Santa 2027 (Viernes Santo 26-mar, Sábado
Santo 27-mar). Editables en `app/fechas.py`.

---

## Paso 1 — Crear las cuentas (gratis, ~15 min)

### A) Apify (datos de vuelos)
1. Crea cuenta gratis en **console.apify.com** (trae ~5 USD de crédito).
2. Ve a **Settings → API & Integrations** y copia tu **API token**.
3. Agrega el actor *memo23/google-flights-scraper* a tu cuenta (Try for free).
4. Importante: MARKET=US en el .env (con CL, Google devuelve precios vacíos).

### B) Gmail para enviar los avisos
1. En tu cuenta Google, activa la **verificación en 2 pasos**.
2. Ve a **myaccount.google.com/apppasswords**.
3. Genera una **contraseña de aplicación** para "Correo" y guárdala.
   (Es distinta de tu contraseña normal; sirve solo para que el programa
   envíe correos.)

---

## Paso 2 — Configurar

1. Copia `.env.example` a `.env`.
2. Pega tu token de Apify en `APIFY_TOKEN`.
3. Pon tu correo en `SMTP_USER` y la contraseña de aplicación en
   `SMTP_PASSWORD`.
4. Pon en `EMAIL_TO` los correos que recibirán los avisos (separados por
   coma).
5. Ajusta `PRICE_THRESHOLD` (ej. `900`) y demás parámetros a tu gusto.

---

## Paso 3 — Probar en tu PC (Windows)

Ya tienes Python instalado. En la carpeta del proyecto, abre la terminal
(escribe `cmd` en la barra de direcciones del explorador) y ejecuta:

```
pip install -r requirements.txt
```

Luego, una prueba de una sola pasada:

```
python -m app.runner --once
```

Si todo está bien configurado, verás en pantalla las mejores ofertas y, si
alguna cumple el umbral, te llegará un correo.

Para ver la curva de precios (dashboard web):

```
streamlit run app/dashboard.py
```

---

## Cuota de la API (importante)

Apify cobra por uso (~1 USD/1000 resultados). **Cada combinación de fecha
= 1 búsqueda** que devuelve hasta MAX_OFFERS itinerarios ida-vuelta. Con la
config por defecto el costo es ~4-5 USD/mes. Los 5 USD de crédito gratis
cubren el primer mes.

Por eso el `.env` viene **acotado** por defecto (1 destino, pocas
combinaciones). Recomendación:
- Empieza con `DESTINATIONS=NRT` y `MAX_COMBOS_POR_CICLO=5`.
- Corre 1 vez al día (`CHECK_EVERY_HOURS=24`).
- Cuando confirmes que funciona, amplía destinos/combinaciones.

El `MAX_LLAMADAS_MES` (por defecto 500) es un freno de seguridad: el
programa se detiene si lo alcanza, para que nunca gastes de más.

---

## Paso 4 — Dejarlo corriendo 24/7 (opcional)

Para que revise solo todos los días sin tu PC prendido, súbelo a un
servidor con Docker:

```
docker compose up -d --build
```

Levanta el monitor (revisa 1×/día) y el dashboard (`http://IP:8501`).

---

## Estructura

```
app/
  config.py            # lee toda la configuración del .env
  db.py                # base de datos SQLite
  gflights_client.py   # consulta Google Flights vía Apify
  notify.py            # envía los emails de alerta
  alertas.py           # decide cuándo alertar
  fechas.py            # reglas de días hábiles
  runner.py            # el ciclo principal
  dashboard.py         # web con la curva de precios
```

---

## Costos

- **Apify (Google Flights):** pago por uso, ~1 USD/1000 resultados. ~5 USD
  de crédito gratis al empezar. Con la config por defecto (2 aeropuertos,
  5 fechas, 15 resultados, 1 pasada/día) el costo es ~4-5 USD/mes.
- **Email (Gmail):** gratis.
- **Servidor 24/7:** opcional, VPS desde ~5 USD/mes. O usa tu PC gratis.

---

## Correrlo gratis 24/7 con GitHub Actions

Para que el monitor corra solo cada día sin tener tu PC encendido, puedes
usar GitHub Actions (gratis). El proyecto ya trae el archivo
`.github/workflows/monitor.yml` configurado.

### Pasos

1. **Sube el proyecto a un repositorio de GitHub** (puede ser privado).
   Tu archivo `.env` NO se sube (está en `.gitignore`) — las claves van
   como "Secrets", ver siguiente paso.

2. **Configura los Secrets** (tus claves, de forma segura):
   En tu repo → Settings → Secrets and variables → Actions → New repository
   secret. Crea estos secrets (uno por uno):
   - `APIFY_TOKEN` → tu token de Apify
   - `SMTP_USER` → tu correo Gmail
   - `SMTP_PASSWORD` → tu contraseña de aplicación de Gmail (16 letras)
   - `EMAIL_FROM` → tu correo Gmail
   - `EMAIL_TO` → los correos que reciben avisos (separados por coma)

   El resto de la configuración (fechas, destinos, umbral...) ya está en el
   workflow. Si quieres cambiar algo (ej. el umbral), edita los valores en
   `.github/workflows/monitor.yml`.

3. **Listo.** Corre automáticamente cada día a las 12:00 UTC (~09:00 Chile).
   El historial de precios se conserva entre corridas (via cache).

### Probarlo a mano
En tu repo → pestaña **Actions** → elige el workflow → botón **Run workflow**.
Así lo ejecutas cuando quieras sin esperar al horario.

### Ver los resultados
Los avisos llegan por email. Para ver el detalle de cada corrida (precios
encontrados), entra a la pestaña Actions y abre la ejecución del día.
