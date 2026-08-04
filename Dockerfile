FROM python:3.12-slim

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Carpeta persistente para la base de datos
VOLUME ["/data"]

# Por defecto corre el runner en loop
CMD ["python", "-m", "app.runner"]
