# Development — Local Setup & Testing

> **Project `tmp/` for SQLite** `tmp/railblock.db` `WAL` — no `D:/` hardcode, works on Linux/Mac/Windows

---

## Requirements

- **Backend:** `Python 3.11` `FastAPI 0.110` `SQLAlchemy 2.0` `OR-Tools 9.8` `psycopg2-binary`
- **Frontend:** `Node 20` `React 18` `Vite 5` `TypeScript 5`
- **DB:** `PostgreSQL 17.6` (Supabase pooled `6543`) or `SQLite` `tmp/` fallback

---

## Local — SQLite `tmp/`

```bash
python scripts/reset_demo.py
# RailBlock AI demo reset complete
# Tasks:30 Trains:133 Goods:43 Resources:14 Corridors:3 Windows:659

# Backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend

# Frontend
cd frontend && npm install && npm run dev  # :5173 proxies /api → :8000

curl http://localhost:8000/health | jq
```

---

## Testing

```bash
# Backend
pytest tests -q  # 78 passed

# Frontend
npx tsc --noEmit  # 0
npm run build    # 907 modules

# API parallel
curl -s http://localhost:8000/health -w "%{time_total}s" &
curl -s http://localhost:8000/api/plans -w "%{time_total}s" & wait

# Browser
# open http://localhost:5173/planner → ★ Generate → Submit → Approve → Execution
```

All `22` endpoints `200` on `PostgreSQL` pooled, `Vercel` `200` SPA.

---

## Heavy Calc — C++/Rust (Optional)

- **Rust `PyO3`:** `backend/Cargo.toml` `railblock_rs` `src/lib.rs` `heavy_calc.py` deep module — `maturin build`
- **C++ `pybind11`:** `backend/optimizer_cpp/` `ortools/sat/cp_model.h` `5s 8 workers` — `cmake` `make`
- **Docker:** Skipped on `Voroa` free tier (`Dockerfile` `Skipping` `90s` → keep `<30s`), local `cargo build` optional — fallback pure Python.

See `docs/grill-with-docs/ADR-001-rust-vs-cpp.md`.

---

## Structure

```
backend/app/{routers,services,models}  # 18 orchestrator services
frontend/src/{pages,components,services}
data/sample/*.csv  # 30 tasks, 133 trains
tmp/railblock.db   # SQLite WAL (gitignored)
docs/screenshots/*.webp  # 1280x720 live captures
```
