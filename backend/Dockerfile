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
# Optional C++/Rust builds disabled for Voroa free tier (heavy, 90s). Keep deep module files, fallback pure python.
RUN echo "Skipping C++/Rust builds on Voroa — keep files, fallback pure python (fast)"
# Ensure railblock.db directory writable and WAL sidecars persist
RUN mkdir -p /app/data && chmod 777 /app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
