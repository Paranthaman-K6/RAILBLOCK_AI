# RailBlock AI — Backend for Voroa (MySQL Aiven) - manual one-time pre-seed
# Frontend is on Vercel (VITE_API_URL -> Voroa URL). DB is pre-seeded manually before hosting.
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source — layout: WORKDIR /app and app/ is /app/app
COPY backend/ ./

# Copy synthetic data (kept for diagnostics, not auto-seeded at runtime)
COPY data/ ./data

# Ensure writable for sqlite fallback and diagnostics
RUN mkdir -p /app/data && chmod 777 /app /app/data

EXPOSE 8000

# Manual pre-seed is done ONCE before hosting via scripts/reset_demo.py + seed_enriched.py.
# Container just ensures schema exists and starts API (no auto-seed delay).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
