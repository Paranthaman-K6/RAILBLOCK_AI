# RailBlock AI — Backend for Voroa (PostgreSQL Supabase pooler) - project folder tmp
# Frontend is on Vercel (VITE_API_URL -> Voroa URL). DB is postgres pooled 6543; sqlite fallback uses <project>/tmp/railblock.db
FROM python:3.11-slim
WORKDIR /app
# Deep module: C++ optimizer needs build-essential + cmake + python3-dev (pybind11)
# Keep maturin path for Rust extension (backend/Cargo.toml) — optional, never fail build
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential cmake python3-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
# pybind11 + maturin kept for both deep modules (C++ & Rust)
RUN pip install --no-cache-dir pybind11 maturin 2>/dev/null || pip install --no-cache-dir pybind11 2>/dev/null || true

# Copy backend source — layout: WORKDIR /app and app/ is /app/app
COPY backend/ ./

# Optional C++ build — disabled for Voroa free tier (heavy, 90s). Keep files for local, but skip in Docker to keep build fast.
# Enable locally: docker build --build-arg BUILD_CPP=1 . To enable, uncomment below.
# RUN if [ -f optimizer_cpp/CMakeLists.txt ]; then mkdir -p /tmp/cpp_build && cd /tmp/cpp_build && cmake /app/optimizer_cpp -DCMAKE_BUILD_TYPE=Release && make -j$(nproc) && cp *.so /app/ || true; fi
RUN echo "Skipping C++ Rust builds on Voroa (keep deep module files, fallback pure python) — build fast"
# Rust PyO3 also skipped on Voroa (needs rust toolchain, 90s). Local: cargo build + maturin
# Files remain: backend/Cargo.toml, src/lib.rs, heavy_calc.py fallback handles has_rust=False

# Copy synthetic data (kept for diagnostics, not auto-seeded at runtime)
COPY data/ ./data

# Ensure writable for sqlite fallback (project folder tmp) and diagnostics — per user "use project folder for tmp"
RUN mkdir -p /app/data /app/tmp ./tmp && chmod 777 /app /app/data /app/tmp ./tmp 2>/dev/null || chmod 777 /app/tmp 2>/dev/null || true

EXPOSE 8000

# Manual pre-seed is done ONCE before hosting via scripts/reset_demo.py + seed_enriched.py.
# Container just ensures schema exists and starts API (no auto-seed delay).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
