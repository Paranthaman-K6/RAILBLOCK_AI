# RailBlock AI — Single image (frontend + backend) for Render
# Stage 1: build frontend (Vite + tsc) with same-origin API (VITE_API_URL="")

FROM node:20-alpine AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
# Ensure same-origin API in production (Render). Override any baked host.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Stage 2: Python backend + static serving via FastAPI StaticFiles
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source (as /app/backend -> /app/app after move? backend/Dockerfile uses WORKDIR /app and COPY . . so app/ is at /app/app)
# We keep same layout as backend/Dockerfile expects: WORKDIR /app and app/ is /app/app
COPY backend/ ./

# Copy frontend build to /app/static (served by FastAPI)
COPY --from=web /app/frontend/dist ./static

# Copy data for auto-seed fallback (Supabase empty case)
COPY data/ ./data

# Ensure writable for sqlite fallback and diagnostics
RUN mkdir -p /app/data && chmod 777 /app /app/data

EXPOSE 8000

# Render injects $PORT (10000). Fallback 8000 for local docker run.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
