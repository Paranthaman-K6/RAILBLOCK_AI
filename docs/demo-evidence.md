# Demo Evidence — RailBlock AI (Prototype)

**Branch:** `audit/final-release-2026-09-01` @ `de23bbf`  
**Date:** 2026-09-01  (horizon `2026-09-01` to `2026-09-30`)  
**Synthetic prototype — not for real railway operations.**

## 1. Reset and Health

```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\reset_demo.py
# RailBlock AI demo reset complete
# Tasks:30 Trains:133 Goods:43 Resources:14 Corridors:3 Windows:168 Invalid:0 Duplicate:0 journal_mode:wal Foreign keys: True
# Database path: D:/PROJECT2/MAYBE/RAIL/backend/railblock.db

.\start.ps1
# Backend health: {"status":"ok","prototype":"human-approved...","diagnostics":{"journal_mode":"wal","foreign_keys":true,"busy_timeout":5000}}
# Backend Job: Id=1 State=Running Frontend Job: Id=3 State=Running
# Backend: http://localhost:8000/health Frontend: http://localhost:5173

Invoke-WebRequest http://localhost:8000/health -UseBasicParsing | Select-Object -Expand Content
# {"status":"ok","diagnostics":{"journal_mode":"wal","foreign_keys":true}}
```

## 2. Data Import (7 domains)

- `data/sample/corridors.csv` → 3 corridors / 6 sections / 8 lines (seeded)
- `data/sample/resources.csv` → 14 resources + 98 availability rows
- `data/sample/trains.csv` → 133 TrainMovements (PASSENGER, 15/15 buffers)
- `data/sample/goods_forecast.csv` → 43 GoodsForecasts
- `data/sample/tasks.csv` → 30 Tasks (ENGINEERING 8, S_AND_T 8, TRACTION 7, PROJECTS 7) — covers TMS/SMMS/TDMS via department column; separate SMMS/TDMS files not distinct (PARTIAL)
- `POST /api/import/tasks` with valid CSV → `200` `ImportRun` `received 30 accepted 30`
- Re-import same → `duplicate 30 accepted 0` (deterministic)
- Missing column → `rejected 1 errors 11` with `{row,field,severity,code,message}` e.g., `UNKNOWN_CORRIDOR`

## 3. Tasks and Priority

```powershell
GET /api/tasks?limit=1 → {task_id:TSK-001, priority_score:78.1, band:HIGH}
GET /api/tasks/TSK-001/priority-explanation → {score:78.1, S:89, U:51, C:92, O:85, D:58, R:85, weights:{S:0.3,U:0.2,C:0.2,O:0.15,D:0.1,R:0.05}, reason:"high safety criticality; 5 overdue days...", version:v1}
# Weights sum 1.0, reproducible, six factors normalized
# Change via RuleConfiguration priority_weights → re-run recalculate_all → score changes (direct DB, no PUT API)
```

## 4. Windows and Conflicts

- `POST /api/plans/generate WEEKLY 2026-09-01→07` → `solver_status:OPTIMAL` `windows total 168 feasible 134 rejected 34`
- Rejected reasons: `Train overlap 1 trains` (protected `[departure-15, arrival+15)`), `Goods forecast high confidence overlap` (confidence 0.9)
- Exact boundary: `120==135` no overlap (tested via `train at block start/end`)
- Corridor/section/line, power `requires_power_isolation`, signalling, resource, buffer all validated.

## 5. Planning

- `generate_baseline` (FCFS, no grouping) → `blocks 22 scheduled 22`
- `run_cpsat_optimizer` → `blocks 20 scheduled 23 integrated_groups 3 candidate 134` `runtime 0.03s` `OPTIMAL`
- `POST /api/plans/{id}/validate` → `valid:true`
- `GET /api/metrics/{id}` → `baseline vs optimized improvement {blocks_reduced:2 tasks_added:1}` `objective_breakdown {priority_value:1530.6 ...}`
- Invalid solver output not persisted → `400 VALIDATION_FAILED`

## 6. Approval

- `POST /api/plans/{id}/submit-review → 200`
- `POST /api/plans/{id}/approve {CONTROL_OFFICE} → 200 status APPROVED`
- `Approval` record + `AuditEvent APPROVE` + `Notification` to 4 departments
- `POST /api/plans/{id}/approve {empty} → 200` (should be 400 — FAIL, fallback to officer1)
- `GET /api/approved-plans?department=ENGINEERING` excludes `DRAFT` (verified `PLAN-024263FD not in ...`)

## 7. Department Visibility

- `GET /api/plans/{id}/department-view?department=ENGINEERING` → `my_blocks 7 integrated 13`
- `S_AND_T` → `5/15`, `TRACTION` → `6/14`, `CONTROL_OFFICE` → `0/20`
- Own tasks prominent, cross-department visible as coordination context, `VIEWER` sees `0/20` (no leak)
- `GET /api/notifications?department=ENGINEERING` → `count 3` after approval

## 8. Editing

- `PATCH /api/plans/{id}/draft-blocks/{blk} {service_date:2026-09-03} → 400` (train conflict — correct rejection, but test expected 200 for valid date)
- Valid edit on revision `2026-09-04` → `200`
- `PATCH` on `APPROVED` → `400 PLAN_IMMUTABLE`
- `POST /api/plans/{id}/revisions → 200 new_plan_id` → original stays `APPROVED`
- `AuditEvent REVISION_CREATE` + old/new values, editor, timestamp, reason
- Stale `expected_version:999 → 409`

## 9. Execution

- `POST /api/blocks/BLK-C9F6FC42/execution {COMPLETED} → 201` `execution_id EXE-250FC681`
- `GET /api/execution/plan/{id}` → `count 1` persists, `Block.status COMPLETED`
- Duplicate same payload → `200 idempotent`, diff → `409` (tested: duplicate 200, diff 409)
- `POST /api/blocks/WND-TEST1234/execution → 400 Never use a WND-* ...`
- `POST /api/blocks/BLK-UNKNOWN123/execution → 404`
- Invalid body (missing actual_end) → `400` (spec expects `422` — PARTIAL)
- No `500` in any scenario (generic handler hides tracebacks)

## 10. Replanning

- Complete `BLK-xxx` → `COMPLETED` → add `TSK-2000 EMERGENCY` → `POST /api/plans/{id}/replan → 200`
- Response: `base PLAN-5860CF0A new PLAN-F235098A preserved 19 displaced [TSK-010,TSK-001] new [TSK-2000]`
- `ExecutionRecord` for `BLK-xxx` persists `count 1`
- New plan `DRAFT`, old remains `APPROVED` until new approved

## 11. Metrics and Export

- `GET /api/metrics/{id}` → `blocks 18 = DB count 18` `resource_utilization 64.5` `planned_vs_actual [{planned:120 actual:70 delta:-50}]`
- `GET /api/plans/{id}/export?format=csv → 200 text/csv` contains `PLAN-*` and `rows 21`
- `?format=pdf → 200`

## 12. Frontend (Manual)

- `Dashboard` → synthetic banner, `Tasks 30 Windows 134 feasible`, health `wal`, `API unavailable` handling
- `Import` → `Synthetic data auto-loads` `Duplicate:30`
- `TaskInbox` → `priority_score`, `priority_band`, `breakdown`
- `Planner` → `WEEKLY/MONTHLY/DAILY` switch, `Generate → OPTIMAL`, `Gantt` colors (red/orange/green/blue), `ValidationPanel`
- `DepartmentPlans` → selector `ENGINEERING/S_AND_T/TRACTION/CONTROL_OFFICE` → `my vs integrated`
- `Execution` → `BLK-*` selector → `COMPLETED → 🔒 Locked`
- `Metrics` → `baseline vs optimized` chart from `/api/metrics`
- `npm run build` → `907 modules ✓ 616kB` `npx tsc --noEmit` → `0`

## 13. Docker / CI / OpenAPI

- `docker-compose.yml` valid (2 services, `healthcheck python -c urllib`, `backend_db:/app/data`) — `docker not recognized` in this env (NOT APPLICABLE)
- `start.sh` `bash -n` → `0`, but no `clean`/`health` subcommands (PARTIAL)
- `.github/workflows/ci.yml` → 2 jobs (backend `pytest`, frontend `npm run build`) — `eslint` not in workflow (PARTIAL)
- OpenAPI → `openapi 3.1.0` with `/health`, `/api/import/*`, `/api/plans/*`, `/api/blocks/*/execution` etc.
- `GET /openapi.json` → 200

---

**Screenshots / Logs:** See `final-release-audit.md` §16 for raw logs (52 passed, health JSON, windows, etc.). No manual screenshots captured in this audit — API evidence via `TestClient`.

