# RailBlock AI — Backend-only image for Render (frontend on Vercel)
# Frontend is deployed separately to Vercel with VITE_API_URL=https://<render>.onrender.com
# This image serves API only; no frontend build, no /app/static. See docs/troubleshooting.md
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source — layout: WORKDIR /app and app/ is /app/app (same as backend/Dockerfile)
COPY backend/ ./

# Copy synthetic data for auto-seed fallback (Supabase empty case)
COPY data/ ./data

# Ensure writable for sqlite fallback and diagnostics
RUN mkdir -p /app/data && chmod 777 /app /app/data

EXPOSE 8000

# Render injects $PORT (10000). Fallback 8000 for local docker run.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
