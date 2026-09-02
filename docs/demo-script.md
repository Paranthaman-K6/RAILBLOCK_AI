# Demo Script — RailBlock AI (5 Minutes)

**Prototype disclaimer (say + show):** *Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.*

**Pre-check (30s):** `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"; python scripts\reset_demo.py` → expect `Tasks:30 Trains:133 Goods:43 Resources:14 Corridors:3 Windows:168 Duplicate:0 WAL:wal`. Then `.\start.ps1` or manual `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` and `npm run dev`.

**0:00-0:45 Dashboard:** Open http://localhost:5173 and http://localhost:8000/docs . Show synthetic banner top + footer disclaimer, health `Synthetic prototype windows`, counts Tasks 30 Windows 134 feasible. Show no crash if backend stopped then restarted.

**0:45-1:30 Import:** /import — show `Synthetic data auto-loads, no manual import required` + idempotent. Upload `data/sample/tasks.csv` → `Duplicate:30 Accepted:0` (deterministic duplicate). Show rejected row-level errors if invalid CSV (e.g., missing corridor).

**1:30-2:30 Planner Weekly:** /planner — select `WEEKLY 2026-09-01 to 2026-09-07` → Generate → `OPTIMAL` valid true, blocks ~23, baseline vs optimized metrics from real dataset (not hardcoded). Show `Validation` panel, `Gantt` with colors (green feasible, orange conflict, blue approved, red safety). Show weekly→monthly switch without stale: change to `MONTHLY 2026-09-01 to 2026-09-30` → Generate → `OPTIMAL`.

**2:30-3:15 Approval Workflow:** Select weekly plan `DRAFT` → Submit for Review → Approve as `CONTROL_OFFICE` → status becomes `APPROVED` (blue). Try editing approved block → `Approved and published plans are immutable. Create revision.` (409). Show immutable rule.

**3:15-4:00 Departments & Execution:** /departments — select `ENGINEERING` → my_blocks vs integrated. /execution — select plan → Record `COMPLETED` for one block → show `🔒 Locked` indicator, then try duplicate execution → `409 Duplicate execution` or idempotent. Show completed block cannot be moved via Planner edit → `Completed and approved work cannot be moved.`

**4:00-4:45 Metrics & Export & Replan:** /metrics — select plan → show Blocks, Scheduled, Critical, Conflicts, Unused, Resource utilization (real). Charts from API. Export CSV/PDF buttons → downloads or error if fails. Back to Planner → Replan with reason `Emergency` → show `preserved_tasks`, `displaced_tasks`, new plan.

**4:45-5:00 Close:** Show `/api/diagnostics` → `SQLite WAL, foreign_keys true, path D:/.../railblock.db` and `/health`. Emphasize: local-first, SQLite WAL only, no live railway APIs, prototype not for operations. Stop via `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"; .\stop.ps1` or `docker compose down`.

**Slide 4/5 Disclaimer:** Copy verbatim prototype disclaimer above.

**If API unavailable:** Show graceful `API unavailable — backend may be stopped` message, not crash, loading spinner, empty state `No plans — generate weekly`.

**Commands for proctor:**
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"; python scripts\reset_demo.py
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npm run dev
```
