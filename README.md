<div align="center">

<img src="https://img.shields.io/badge/RailBlock_AI-Human--Approved_Prototype-0f2a44?style=for-the-badge&labelColor=2d8b8b" alt="RailBlock AI" />
<br/>
<img src="https://img.shields.io/badge/PostgreSQL-17.6-336791?style=flat-square&logo=postgresql&logoColor=white" />
<img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi&logoColor=white" />
<img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" />
<img src="https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white" />
<img src="https://img.shields.io/badge/OR--Tools-CP--SAT-3DD68C?style=flat-square" />
<img src="https://img.shields.io/badge/License-MIT-2d8b8b?style=flat-square" />
<img src="https://img.shields.io/badge/Deploy-Voroa-0f2a44?style=flat-square" />
<img src="https://img.shields.io/badge/Frontend-Vercel-black?style=flat-square&logo=vercel" />

# 🚆 RailBlock AI
### Human-Approved, Explainable Hybrid AI Decision-Support System
*Prototype — Synthetic Data Only*

**Live Demo** • [Vercel Frontend](https://railblock-ai-gamma.vercel.app) • [Voroa Backend](https://railblock-ai.getvoroa.com) • [API Docs](https://railblock-ai.getvoroa.com/docs) • [Health](https://railblock-ai.getvoroa.com/health)

> **Prototype disclaimer:** This application uses **synthetic demonstration data** and prototype operational rules. It does **not** access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It **must not** be used for real railway operations.

</div>

---

## ✨ Theme — Ocean Depths

> *Professional and calming maritime theme — Navy `#0f2a44` • Teal `#2d8b8b` • Off-white `#f1faee`*

This README and the entire frontend (`frontend/src/index.css`) use the **Ocean Depths** palette from `theme-factory` for a consistent, control-room aesthetic — deep navy sidebar, teal accents, and high-contrast data visualization.

| Role | Color | Hex | Usage |
|------|-------|-----|-------|
| Primary | Navy | `#0f2a44` | Sidebar, headers, primary buttons |
| Accent | Teal | `#2d8b8b` | Active states, charts, Gantt integrated blocks |
| Background | Off-white | `#f1faee` | Page, card titles |
| Surface | White | `#ffffff` | Cards |
| Muted | Slate | `#8896a8` | Secondary text |

---

## 📸 Visualizations — Test Screenshots (OpenChamber Browser)

> All features verified via `openchamber_web` parallel browser + `curl` API probes on **PostgreSQL 17.6** `aws-0-ap-southeast-1.pooler.supabase.com:6543` (Voroa) and **SQLite WAL** `tmp/railblock.db` (Vercel fallback) — `30T · 659W · 19P` healthy.

| Dashboard | Import & Validate |
|-----------|-------------------|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Import](docs/screenshots/import.png) |
| `GET /health` `ok` `PostgreSQL` · `30T` `659W` `19P` · Baseline vs Optimized | `POST /api/import/*` `200` `duplicate:30` idempotent |

| Corridors & Assets | Trains & Windows |
|--------------------|------------------|
| ![Corridors](docs/screenshots/corridors.png) | ![Trains](docs/screenshots/trains.png) |
| `GET /api/corridors 3` `GET /api/assets 12` | `GET /api/trains 133` `GET /api/windows 659` `TRN-0001 06:00→06:30` |

| Task Inbox (P=0.30S+…) | Planner — Generate → Approve |
|------------------------|------------------------------|
| ![Tasks](docs/screenshots/tasks.png) | ![Planner](docs/screenshots/planner.png) |
| `GET /api/tasks 30` `CRITICAL 83.6` | `POST /generate WEEKLY → OPTIMAL 20 blocks` → `Submit → Approve CONTROL_OFFICE` `200` + `TopLoadingBar` + `FrontendOverlay` |

| Optimizer | Execution |
|-----------|-----------|
| ![Optimizer](docs/screenshots/optimizer.png) | ![Execution](docs/screenshots/execution.png) |
| `P=0.30S+0.20U…` `CP-SAT 5s 8 workers` | `POST /blocks/BLK-*/execution 201` `Completed 🔒` |

| Metrics — Baseline vs Optimized | Metrics — Asset Breakdown |
|---------------------------------|---------------------------|
| ![Metrics](docs/screenshots/metrics.png) | ![Asset](docs/screenshots/asset.png) |
| `Baseline 25 → Optimized 20` `2760→2360 min` | `AST-4 98.71%` Gantt + `blocks_detail` |

*Screenshots captured via `openchamber_web` `browser.snapshot` + `browser.capture` on `https://railblock-ai-gamma.vercel.app` (Vercel) and `https://railblock-ai.getvoroa.com` (Voroa) — see `docs/demo-evidence.md` for full gallery.*

---

## 🏗️ Architecture — Hybrid AI Pipeline

```mermaid
graph LR
    A[TMS/SMMS/TDMS/COA<br/>Synthetic CSV] --> B[Import & Validate<br/>ImportRun + row errors]
    B --> C[Asset/Corridor<br/>Mapping COR-/SEC-]
    C --> D[Priority P=0.30S+...<br/>Rust PyO3 / Python]
    D --> E[Candidate Windows<br/>01:00-03:00 etc.]
    E --> F[CP-SAT Optimizer<br/>5s 8 workers<br/>C++ pybind11]
    F --> G[Validator 14 checks A-L]
    G --> H[Human Approve<br/>CONTROL_OFFICE]
    H --> I[Execution<br/>BLK-* 201]
    I --> J[Metrics<br/>baseline vs optimized]
    J --> K[PostgreSQL Supabase<br/>pooled 6543<br/>or SQLite tmp/]
    K --> L[Vercel Frontend<br/>React 18 + Vite]
```

**Deep modules** (`codebase-design` skill): `heavy_calc` (Rust `rayon`) + `optimizer_cpp` (C++ `ortools/sat/cp_model.h`) behind small `Python` seams — `fallback` pure Python if `.so` missing.

---

## 🚀 Quick Start

### Live (no install)
- **Frontend:** https://railblock-ai-gamma.vercel.app
- **Backend:** https://railblock-ai.getvoroa.com/health → `{"status":"ok","database":"PostgreSQL",...}`

### Local — PowerShell (SQLite WAL `tmp/railblock.db`, project folder for tmp)
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\reset_demo.py        # idempotent: Tasks 30, Trains 133, Windows 659
.\start.ps1                          # auto-detects Python/Node/Docker
# Backend http://localhost:8000/health  Frontend http://localhost:5173
```

### Local — Docker (PostgreSQL Supabase)
```bash
docker compose up --build -d
# Frontend http://localhost:3000  Backend http://localhost:8000/health
```

### Supabase PostgreSQL (Voroa)
```bash
# Voroa env (already set)
DATABASE_URL=postgresql://postgres.qgkxdvtrqjhcgnwggzxh:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
DATABASE_MODE=postgres
# Health: curl https://railblock-ai.getvoroa.com/health | jq .diagnostics.database
```

---

## 📚 API — Fast + Loading Bar

| Method | Endpoint | Description | Status |
|--------|----------|-------------|--------|
| `GET` | `/health` | `ok` + `backend_url`/`frontend_connected_to` | `200` |
| `GET` | `/api/diagnostics` | DB `PostgreSQL`/`SQLite` `wal` | `200` |
| `POST` | `/api/import/*` | TMS/SMMS/TDMS/COA/Timetable/Goods | `200` |
| `GET` | `/api/tasks` | Prioritized `P` | `200` |
| `POST` | `/api/plans/generate` | `WEEKLY` `OPTIMAL 20` | `200` |
| `POST` | `/api/plans/{id}/submit-review` | Lightweight `<200ms` | `200` |
| `POST` | `/api/plans/{id}/approve` | `CONTROL_OFFICE` `<200ms` | `200` |
| `POST` | `/api/blocks/{id}/execution` | `201` idempotent `200`/`409` | `201` |
| `GET` | `/api/metrics` | `blocks` + `schedule` Gantt | `200` |

**Loading UX:** `TopLoadingBar` teal `3px` top (`start` on `request`, `done` on `response`/`error`/`8s timeout`/`popstate`/`hashchange`/`visibility`/`click` to dismiss) + `FrontendOverlay` blur `Generating plan…` `Submitting…` `Approving…` `Recording…` (Esc to clear) — no more stuck spinner.

---

## 🧪 Testing — Parallel & Browser

```powershell
# Backend
Set-Location backend; python -m pytest tests -q  # 78 passed

# Frontend type + build
Set-Location frontend; npx tsc --noEmit; npm run build

# API parallel
curl -s https://railblock-ai.getvoroa.com/health -w "%{time_total}s" &
curl -s https://railblock-ai.getvoroa.com/api/plans -w "%{time_total}s" & wait

# Browser
openchamber_web browser.open https://railblock-ai-gamma.vercel.app/planner → click ★ Generate → Submit → Approve → Execution → Metrics
```

All `22` endpoints `200` on `PostgreSQL` pooled, `Vercel` `200` SPA + `api.ts` fallback `https://railblock-ai.getvoroa.com`.

---

## 🎨 Theme Factory & Grill-With-Docs

- **Theme Factory** (`theme-factory` skill): `Ocean Depths` applied to `frontend/src/index.css` and this README — see `docs/theme-factory/theme-showcase.md`.
- **Grill-With-Docs** (`grill-with-docs` skill): `docs/grill-with-docs/` contains `ADR-001.md` (Rust vs C++), `GLOSSARY.md` (Module/Interface/Seam), grilled via parallel `explore` agents.
- **Context7 via OmniRoute** (`omniroute-mcp_omniroute_web_search` `upstash/context7` 61k★) for `pybind11`/`FastAPI`/`Supabase` docs — no hallucinated APIs.

---

## 📄 License

MIT — see [LICENSE](LICENSE). Prototype disclaimer applies.

---

## ⚠️ Prototype Disclaimer

**Not** an autonomous railway-control system. **Not** railway-certified. Uses synthetic data only. Production requires authorized integration, validation, and certification.

*Built with `codebase-design` deep modules, `Rust` + `C++` heavy calc, `Supabase` pooled `6543`, `Vercel` + `Voroa`, `openchamber` browser verification.*
