FROM python:3.11-slim
WORKDIR /app
# Deep module: C++ optimizer needs build-essential + cmake + python3-dev (pybind11)
# Keep maturin path for Rust extension (Cargo.toml/pyproject.toml) — optional, never fail build
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential cmake python3-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# pybind11 for C++ optimizer (optional) + maturin for Rust (optional) — keep both paths
RUN pip install --no-cache-dir pybind11 maturin 2>/dev/null || pip install --no-cache-dir pybind11 2>/dev/null || true
COPY . .
# Optional C++ build (pybind11 + ortools). Fails gracefully if ortools not available — Python fallback remains.
# Deep module: .so placed at top-level /app so `import optimizer_cpp` works from adapter without shadowing app.services.optimizer_cpp
RUN if [ -f optimizer_cpp/CMakeLists.txt ]; then \
      echo "Building C++ optimizer_cpp (pybind11, 8 workers, 5s)..." && \
      mkdir -p /tmp/cpp_build && cd /tmp/cpp_build && \
      cmake /app/optimizer_cpp -DCMAKE_BUILD_TYPE=Release -DPYBIND11_FINDPYTHON=ON 2>&1 | head -n 100 && \
      make -j$(nproc) 2>&1 | tail -n 50 && \
      cp optimizer_cpp*.so /app/ 2>/dev/null || cp *.so /app/ 2>/dev/null || echo "C++ .so copy to /app skipped"; \
      ls -lh /app/*.so 2>/dev/null || true; \
    else echo "No optimizer_cpp/CMakeLists.txt, skipping C++ build"; fi
# Optional Rust build via maturin (keep path, do not break if no Rust toolchain/Cargo.toml)
RUN if [ -f Cargo.toml ] && [ -f pyproject.toml ]; then \
      echo "Attempting maturin build (Rust deep module)..." && \
      maturin build --release 2>&1 | tail -n 30 || echo "maturin build skipped (no Rust toolchain)"; \
      pip install dist/*.whl 2>/dev/null || pip install --no-cache-dir -e . 2>/dev/null || echo "maturin pip install skipped"; \
    else echo "No Cargo.toml/pyproject.toml, skipping maturin"; fi
# Ensure railblock.db directory writable and WAL sidecars persist
RUN mkdir -p /app/data && chmod 777 /app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
