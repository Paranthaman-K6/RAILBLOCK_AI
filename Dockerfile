# RailBlock AI — Backend for Voroa (PostgreSQL Supabase pooler) - project folder tmp
# Frontend is on Vercel (VITE_API_URL -> Voroa URL). DB is postgres pooled 6543; sqlite fallback uses <project>/tmp/railblock.db
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source — layout: WORKDIR /app and app/ is /app/app
COPY backend/ ./

# Copy synthetic data (kept for diagnostics, not auto-seeded at runtime)
COPY data/ ./data

# Ensure writable for sqlite fallback (project folder tmp) and diagnostics — per user "use project folder for tmp"
RUN mkdir -p /app/data /app/tmp ./tmp && chmod 777 /app /app/data /app/tmp ./tmp 2>/dev/null || chmod 777 /app/tmp 2>/dev/null || true

EXPOSE 8000

# Manual pre-seed is done ONCE before hosting via scripts/reset_demo.py + seed_enriched.py.
# Container just ensures schema exists and starts API (no auto-seed delay).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
