# RailBlock AI — Human-Approved, Explainable Hybrid AI Decision-Support System (Prototype)

**Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.**

**Synthetic prototype data — not for real railway operations.** — All block windows are `Synthetic prototype windows, not official railway availability.` The system is a local-first planning *prototype*, not an autonomous railway-control system and not a railway-certified safety system.

Integrated railway maintenance block planning combining TMS, SMMS, TDMS, COA, timetable, goods forecast, resources with priority scoring, conflict detection, candidate window generation, CP-SAT optimization, independent validation, human approval workflow, department visibility, execution tracking, replanning, metrics, and audit.

## Requirements

- **Backend:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, SQLite WAL, OR-Tools 9.8
- **Frontend:** Node 20, React 18, Vite 5, React Router 6, TypeScript 5, Axios, Recharts
- **Database:** **SQLite only** (`D:\PROJECT2\MAYBE\RAIL\backend\railblock.db`, WAL, `check_same_thread=False`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`)
- **OS:** Windows PowerShell 5.1 (no `&&`, use `Set-Location -LiteralPath` and `; if ($?) {}`) + Docker Compose optional
- **No paid services, no external railway APIs**

## Quick Start

### PowerShell (no Docker, SQLite WAL)
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
# Safe reset (idempotent) — removes data, preserves schema, re-enables WAL/FK, seeds, ingests synthetic, recalculates, verifies:
python scripts\reset_demo.py
# Start backend + frontend (auto-detects Python/Node/Docker, falls back to direct):
.\start.ps1
# Or manual:
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
# new terminal:
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"
npm install
npm run dev
# URLs:
# health http://localhost:8000/health  diagnostics http://localhost:8000/api/diagnostics  docs http://localhost:8000/docs
# frontend http://localhost:5173  (Vite proxies /api and /health to backend)
# To stop:
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
.\stop.ps1
```

### Docker (when available, still SQLite only)
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
docker compose up --build -d
# or docker-compose up --build -d
# Frontend http://localhost:3000  Backend http://localhost:8000/health  Docs http://localhost:8000/docs
# Healthcheck uses python urllib (no curl dependency)
# DB volume backend_db:/app/data persists railblock.db + -wal/-shm (not excluded)
# To stop:
docker compose down
# or .\stop.ps1 (stops both Docker and PowerShell jobs)
```
*Compose uses `DATABASE_URL=sqlite:////app/railblock.db`, `WORKDIR /app`, `healthcheck` via `python -c "urllib..."`, `depends_on: condition: service_healthy`, no PostgreSQL.*

## Reset Procedure
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\reset_demo.py
# with force if server running:
python scripts\reset_demo.py --force
```
Reset does: reject if DB locked (warn or abort), `PRAGMA foreign_keys=OFF` delete in child-first order, preserve schema, `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL`, `busy_timeout=5000`, delete + reseed departments if missing, ingest `data/sample/*.csv` in order COA→RESOURCES→TIMETABLE→GOODS→TMS, `recalculate_all` priorities, generate weekly windows if none, print compact report:
```
RailBlock AI demo reset complete
Tasks: 30
Trains: 133
Goods forecasts: 43
Resources: 14
Corridors: 3
Windows: 168
Invalid records: 0
Duplicate records: 0
Database journal mode: wal
```
Idempotent — running twice produces same counts, no duplicates.

## Synthetic-Data Generation
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\data"
python generate_synthetic_full.py
# outputs sample/ (7-day) and synthetic/ (30-day) — 30 tasks, 14 resources, 12 assets, 3 corridors, 6 sections, 8 lines, 133 trains, 43 goods forecasts
# Auto-ingests on next backend start or:
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\ingest_synthetic.py
# Also auto-ingests via backend/app/main.py if Task empty
```
Synthetic data clearly labeled via `availability_source="Synthetic prototype windows, not official railway availability."` and banners.

## API Documentation
- Swagger: http://localhost:8000/docs  (OpenAPI)
- Health: http://localhost:8000/health
- Diagnostics: http://localhost:8000/api/diagnostics  → `{database:"SQLite", journal_mode:"wal", foreign_keys:true, path:"D:/.../railblock.db"}`
- Horizon examples:
```powershell
# Weekly
$body='{"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"}'
Invoke-WebRequest -Method POST -Uri http://localhost:8000/api/plans/generate -ContentType "application/json" -Body $body
# Monthly
$body2='{"horizon_start":"2026-09-01","horizon_end":"2026-09-30","horizon_type":"MONTHLY"}'
Invoke-WebRequest -Method POST -Uri http://localhost:8000/api/plans/generate -ContentType "application/json" -Body $body2
```

## Frontend
- http://localhost:5173 (Vite) or http://localhost:3000 (Docker Nginx)
- Pages: Dashboard, Import, TaskInbox, Planner (weekly/monthly), DepartmentPlans, Execution, Metrics, Conflicts, Optimizer
- All pages show synthetic banner; Planner/Import/Dashboard/Footer/README/PPT require full disclaimer verbatim
- Dates in Asia/Kolkata, colors: Red safety, Orange conflict, Green feasible, Blue approved, pagination for large lists, CSV/PDF export with error display, no hardcoded metrics (charts from `/api/metrics`)

## Testing
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"
python -m pytest tests -q
# 53 tests (52 + docs verification) cover empty DB, auto-ingest, duplicate composite keys, FK, missing domains/columns, durations, boundary overlap, goods risk, resource conflict, dependency ordering, no-feasible-window, invalid solver, fallback, approval before validation, approved mutation, completed movement, duplicate execution, weekly/monthly/daily, integrated grouping, editing, execution, replanning, audit, docs existence

Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"
npx tsc --noEmit
npm run build
```

## Known Limitations
- Prototype only — no live TMS/SMMS/TDMS/COA/timetable integration, no safety certification
- SQLite only, single-node, no horizontal scaling
- Synthetic windows are templates (01:00-03:00, 13:30-15:30, 02:00-06:00), not real sectional availability
- Optimizer is CP-SAT with 5s limit, grouping limited to window capacity 1 per task (grouping via compatibility service)
- Notifications are in-app only, no email/SMS
- No PostgreSQL; no external APIs; no paid services

## Explicit SQLite-Only Statement
**This project uses SQLite WAL only (`backend/railblock.db`). `DATABASE_URL` defaults to `sqlite:///D:/PROJECT2/MAYBE/RAIL/backend/railblock.db` or `sqlite:////app/railblock.db` in Docker. PostgreSQL is not used and not required. All connections set `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`.**

## No Live Railway API Claim
**No live railway APIs are used. No TMS, SMMS, TDMS, COA, timetable, or railway-control systems are accessed. All data is synthetic.**

## Immutable Rule
No data → 400 no plan. Invalid → rejected no planning. Missing domains → no planning. Invalid refs → rejected. Duplicates → deterministic duplicate response. Train/goods hard conflicts → no assignment. Duration/resource/dependency violations → no assignment. Invalid solver → no draft. Failed validation → no draft. Unvalidated → no approval. Unapproved → no publication. Approved → immutable, revisions required. Completed → locked. Duplicate execution → 409/idempotent. Every state change → AuditEvent.

## Architecture
React 18 + Vite + FastAPI + SQLAlchemy (SQLite WAL) + OR-Tools CP-SAT + Validator + Nginx. See docs/architecture.md.

## Troubleshooting
See docs/troubleshooting.md. Common: `The token '&&' is not a valid statement separator` → use `;` + `if ($?)`. `docker not recognized` → uses direct startup. `Database is locked` → `.\stop.ps1` then `python scripts\reset_demo.py --force`.
