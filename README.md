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

**Live Demo** • [Frontend](https://railblock-ai-gamma.vercel.app) • [Backend](https://railblock-ai.getvoroa.com) • [API Docs](https://railblock-ai.getvoroa.com/docs) • [Health](https://railblock-ai.getvoroa.com/health)

> **Prototype disclaimer:** Synthetic demonstration data only. No live railway systems are accessed. Not for operational use.

</div>

---

## 🎨 Design — Ocean Depths

Professional maritime palette — **Navy `#0f2a44`** (primary), **Teal `#2d8b8b`** (accents), **Off-white `#f1faee`** (background) — applied across the control-room interface for clarity and trust.

| Role | Color | Usage |
|------|-------|-------|
| Primary | `#0f2a44` | Sidebar, headers, primary actions |
| Accent | `#2d8b8b` | Active states, Gantt integrated blocks |
| Background | `#f1faee` | Page background |
| Surface | `#ffffff` | Cards |

---

## 📸 Product Screenshots — Live Production

*Captured at 1280×720 on live deployment — `30` tasks · `659` windows · `19` plans · PostgreSQL 17.6*

| Dashboard | Import & Validate |
|-----------|-------------------|
| <img src="docs/screenshots/dashboard.webp" width="100%" alt="Dashboard — Health and overview" /> | <img src="docs/screenshots/import.webp" width="100%" alt="Import — CSV validation" /> |
| Health `ok` • `30T` `659W` `19P` • Baseline vs Optimized (live DB) | Idempotent `POST /api/import/*` `200` · Row-level validation |

| Corridors & Assets | Trains & Windows |
|--------------------|------------------|
| <img src="docs/screenshots/corridors.webp" width="100%" alt="Corridors — Network topology" /> | <img src="docs/screenshots/trains.webp" width="100%" alt="Trains — Timetable windows" /> |
| `3` corridors `Delhi-Howrah` · `12` assets `AST-*` | `133` trains · `659` windows `01:00–03:00` |

| Task Inbox | Planner — Generate → Approve |
|------------|------------------------------|
| <img src="docs/screenshots/tasks.webp" width="100%" alt="Task Inbox — Prioritized" /> | <img src="docs/screenshots/planner.webp" width="100%" alt="Planner — 20 blocks OPTIMAL" /> |
| `P=0.30S+0.20U…` `CRITICAL 83.6` | `WEEKLY 01→07` `OPTIMAL 20 blocks` → `Submit` `UNDER_REVIEW` → `Approve` `CONTROL_OFFICE` |

| Optimizer | Execution |
|-----------|-----------|
| <img src="docs/screenshots/optimizer.webp" width="100%" alt="Optimizer — Hybrid AI" /> | <img src="docs/screenshots/execution.webp" width="100%" alt="Execution — Completed" /> |
| `CP-SAT 5s 8 workers` `P` weights | `BLK-* 201` `Completed 🔒` idempotent |

| Metrics — Baseline vs Optimized | |
|---------------------------------|-|
| <img src="docs/screenshots/metrics.webp" width="100%" alt="Metrics — Baseline vs Optimized" /> | |
| `Baseline 25 → Optimized 20` `2760→2360 min` · Gantt + Asset Breakdown `98.71%` | |

*Full gallery: [`docs/screenshots/`](docs/screenshots/) — `webp` 1280×720, ~50KB each. See [`docs/demo-evidence.md`](docs/demo-evidence.md) for detailed evidence.*

---

## 🏗️ Architecture — Hybrid AI Pipeline

```mermaid
graph LR
    A[Synthetic CSV<br/>TMS/SMMS/TDMS/COA] --> B[Import & Validate]
    B --> C[Asset / Corridor Mapping]
    C --> D[Priority P=0.30S+...]
    D --> E[Candidate Windows<br/>01:00–03:00]
    E --> F[CP-SAT Optimizer<br/>5s 8 workers]
    F --> G[Validator 14 checks]
    G --> H[Human Approve<br/>CONTROL_OFFICE]
    H --> I[Execution BLK-*]
    I --> J[Metrics]
    J --> K[(PostgreSQL Supabase<br/>pooled 6543<br/>SQLite tmp/ fallback)]
    K --> L[React 18 + Vite<br/>Vercel]
```

**Key design:** Deep modules with small interfaces — heavy calculations (priority, windows, validation) in optimized native extensions with Python fallback; `CP-SAT` via OR-Tools.

---

## 🚀 Quick Start

### Live — No Install
- **Frontend:** https://railblock-ai-gamma.vercel.app
- **Backend:** https://railblock-ai.getvoroa.com/health → `{"status":"ok","database":"PostgreSQL"}`

### Local — SQLite `tmp/railblock.db`
```bash
python scripts/reset_demo.py        # Tasks 30, Trains 133, Windows 659
.\start.ps1                          # Backend :8000  Frontend :5173
```

### Docker
```bash
docker compose up --build -d
# Frontend :3000  Backend :8000/health
```

### Production — Supabase PostgreSQL (Voroa)
```bash
DATABASE_URL=postgresql://postgres.qgkxdvtrqjhcgnwggzxh:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
DATABASE_MODE=postgres
```

---

## 📚 API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | `ok` + DB mode |
| `GET` | `/api/diagnostics` | `PostgreSQL`/`SQLite` status |
| `POST` | `/api/import/*` | TMS/SMMS/TDMS/COA/Timetable/Goods |
| `GET` | `/api/tasks` | Prioritized `P` |
| `POST` | `/api/plans/generate` | `WEEKLY` `OPTIMAL 20` |
| `POST` | `/api/plans/{id}/submit-review` | `UNDER_REVIEW` `<200ms` |
| `POST` | `/api/plans/{id}/approve` | `CONTROL_OFFICE` `<200ms` |
| `POST` | `/api/blocks/{id}/execution` | `201` idempotent |
| `GET` | `/api/metrics` | Baseline vs Optimized + Gantt |

**Experience:** Top loading bar + fullscreen overlay (`Generating…` `Submitting…` `Approving…` `Recording…`) with instant optimistic updates — dismissible via click, `Esc`, or navigation.

---

## 🧪 Quality

```bash
# Backend
pytest tests -q  # 78 passed
# Frontend
npx tsc --noEmit; npm run build  # 907 modules
# Health
curl https://railblock-ai.getvoroa.com/health
```

All endpoints verified `200` on production `PostgreSQL` `ap-southeast-1:6543` and `Vercel` `Vercel → Voroa`.

---

## 📄 License & Disclaimer

**MIT** — see [LICENSE](LICENSE)

**Prototype only** — synthetic data, no safety certification. Production requires authorized integration, validation, and certification.

*Built for human-approved railway planning — clear, auditable, and explainable.*

