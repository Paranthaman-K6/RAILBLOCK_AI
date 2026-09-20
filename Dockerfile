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

# Optional C++ build (pybind11 + ortools, 5s 8 workers). Graceful fallback if ortools missing.
# .so at top-level /app so `import optimizer_cpp` (C++ extension) does not shadow app.services.optimizer_cpp (adapter)
RUN if [ -f optimizer_cpp/CMakeLists.txt ]; then \
      echo "Building C++ optimizer_cpp..." && \
      mkdir -p /tmp/cpp_build && cd /tmp/cpp_build && \
      cmake /app/optimizer_cpp -DCMAKE_BUILD_TYPE=Release -DPYBIND11_FINDPYTHON=ON 2>&1 | head -n 100 && \
      make -j$(nproc) 2>&1 | tail -n 50 && \
      cp optimizer_cpp*.so /app/ 2>/dev/null || cp *.so /app/ 2>/dev/null || echo "C++ .so copy to /app skipped"; \
      ls -lh /app/*.so 2>/dev/null || true; \
    else echo "No optimizer_cpp, skipping C++ build"; fi
# Optional maturin (Rust) build — keep path, do not break if no Rust toolchain
RUN if [ -f Cargo.toml ] && [ -f pyproject.toml ]; then \
      echo "Attempting maturin build..." && maturin build --release 2>&1 | tail -n 30 || echo "maturin build skipped"; \
      pip install dist/*.whl 2>/dev/null || pip install --no-cache-dir -e . 2>/dev/null || echo "maturin pip install skipped"; \
    else echo "No Cargo/Rust, skipping maturin"; fi

# Copy synthetic data (kept for diagnostics, not auto-seeded at runtime)
COPY data/ ./data

# Ensure writable for sqlite fallback (project folder tmp) and diagnostics — per user "use project folder for tmp"
RUN mkdir -p /app/data /app/tmp ./tmp && chmod 777 /app /app/data /app/tmp ./tmp 2>/dev/null || chmod 777 /app/tmp 2>/dev/null || true

EXPOSE 8000

# Manual pre-seed is done ONCE before hosting via scripts/reset_demo.py + seed_enriched.py.
# Container just ensures schema exists and starts API (no auto-seed delay).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
