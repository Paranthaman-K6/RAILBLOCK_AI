FROM python:3.11-slim
WORKDIR /app
# curl not needed for healthcheck now (uses python urllib), but keep for debug
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Ensure railblock.db directory writable and WAL sidecars persist
RUN mkdir -p /app/data && chmod 777 /app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
