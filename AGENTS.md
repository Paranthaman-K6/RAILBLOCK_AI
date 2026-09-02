# AGENTS — RailBlock AI Delivery Contract (Prototype)

**Version:** `main` @ `de23bbf` / `7c97bc5` (audit `0f78a7c`)  
**Date:** 2026-09-01 (horizon `2026-09-01` to `2026-09-30`)  
**Prototype disclaimer:** This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Synthetic prototype windows, not official railway availability.

## 1. Purpose

This file is the **delivery contract** for the RailBlock AI prototype: a human-approved, explainable hybrid AI decision-support system for integrated railway maintenance block planning. It is **not** an autonomous railway-control system and **not** a railway-certified safety system.

## 2. System Boundary

### In scope

```text
Synthetic or authorized source ingestion (TMS→ENGINEERING, SMMS→S_AND_T, TDMS→TRACTION, COA→assets)
Structural / referential / operational validation with ImportRun and row-level errors
Asset and corridor mapping (COR-*/SEC-*/LIN-*/AST-*)
Task prioritization P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R + historical execution delta
Timetable conflict checking (protected [departure-buffer, arrival+buffer))
Goods forecast risk (confidence ≥0.7 HARD, ≥0.4 SOFT)
Resource feasibility (per-date non-overlap)
Multi-department grouping (MAX_GROUP_SIZE 3, compatible corridor/section/line/type/power/signal/duration/resources/dependencies)
Candidate-window generation (templates 01:00–03:00, 13:30–15:30, 02:00–06:00, max 240)
Weekly (2026-09-01→07) and monthly (→30) and DAILY (single day) plan generation
CP-SAT optimization (5s, 8 workers) + baseline FCFS + deterministic fallback
Independent plan validator (14 checks A-L + grouping)
Officer editing with validation, approval and publication (CONTROL_OFFICE/ADMIN final)
Department-wise visibility (ENGINEERING, S_AND_T, TRACTION, PROJECTS, VIEWER, CONTROL_OFFICE, ADMIN)
Execution recording (POST /api/blocks/{BLK-*}/execution, 201) with idempotent 409
Performance metrics from DB (baseline vs optimized, planned vs actual)
Versioned replanning (preserved/moved/displaced/new) with audit history
CSV/PDF export
```

### Out of scope

```text
Autonomous railway control, signal operation, power isolation, train dispatching, final safety authorization,
unsupervised publication, live deployment without authorization
```

## 3. High-Level Architecture

```text
Users → React 18 + Vite → FastAPI REST → Planning Orchestrator → SQLite WAL (D:/PROJECT2/MAYBE/RAIL/backend/railblock.db) → Nginx (Docker) / Vite proxy (local)
```

Orchestrator services (18): Import, Validation, Normalization, AssetMapping, Priority, Risk, CandidateWindow, Compatibility, Grouping, Baseline, CP-SAT Optimizer, Fallback, Validator, Approval, Visibility, Execution, Metrics, Revision/Notification/Export.

## 4. Canonical Entities (27)

`Department, UserContext, Corridor, Section, Line, Asset, Task, TaskDependency, TrainMovement, GoodsForecast, Resource, ResourceAvailability, CandidateWindow, TaskWindowCandidate, TaskGroup, BlockPlan, Block, BlockTask, PlanRevision, PlanChange, Approval, ExecutionRecord, Notification, RuleConfiguration, ImportRun, AuditEvent`

IDs: `COR-*, SEC-*, LIN-*, AST-*, TSK-*, TRN-*, RES-*, WND-*, GRP-*, BLK-*, PLAN-*, REV-*, EXE-*`. Never use `WND-*` where `BLK-*` required.

## 5. Actual Commands (verified 2026-09-01)

```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\reset_demo.py
# → Tasks:30 Trains:133 Goods:43 Resources:14 Corridors:3 Windows:168 Duplicate:0 wal

.\start.ps1
# → Backend http://localhost:8000/health  Docs http://localhost:8000/docs  Frontend http://localhost:5173
# Weekly: POST http://localhost:8000/api/plans/generate {"horizon_start":"2026-09-01",... "WEEKLY"}
# Monthly: POST http://localhost:8000/api/plans/generate {"horizon_start":"2026-09-01",... "MONTHLY"}

# Manual
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npm install; npm run dev

# Tests
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; python -m pytest tests -q
# → 52 passed, 518 warnings (2026-09-01)
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npx tsc --noEmit; npm run build
# → 907 modules ✓

# Docker (when available, still SQLite only)
docker compose up --build -d
docker compose ps; docker compose config
```

## 6. Actual Routes (verified via OpenAPI)

```
GET  /health
GET  /api/diagnostics
GET  /api/departments, /api/corridors, /api/assets, /api/tasks, /api/trains, /api/resources
POST /api/import/tasks etc (via adapters), GET /api/import/summary
GET  /api/windows, GET /api/windows/{window_id}
POST /api/plans/generate, GET /api/plans, GET /api/plans/{plan_id}, POST /api/plans/{plan_id}/validate
POST /api/plans/{plan_id}/approve, POST /api/plans/{plan_id}/reject, POST /api/plans/{plan_id}/replan
GET  /api/plans/{plan_id}/history, GET /api/plans/{plan_id}/changes, GET /api/plans/{plan_id}/export
POST /api/plans/{plan_id}/revisions, PATCH /api/plans/{plan_id}/draft-blocks/{block_id}, POST /api/plans/{plan_id}/submit-review
GET  /api/approved-plans, GET /api/plans/{plan_id}/department-view, GET /api/notifications
POST /api/blocks/{block_id}/execution, GET /api/execution/plan/{plan_id}, GET /api/execution
POST /api/conflicts/detect, POST /api/optimize, GET /api/metrics, GET /api/metrics/{plan_id}
GET  /api/compatibility/priority-weights, GET /api/compatibility/optimizer-weights, GET /api/compatibility/hard-constraints, GET /api/compatibility/ai-model
GET  /api/tasks/{task_id}/priority-explanation, GET /api/plans/{plan_id}/explanations
```

## 7. Acceptance Criteria (current, not invented)

- `python -m pytest tests -q` → all collected pass (52 at audit)
- `npx tsc --noEmit` → 0, `npm run build` → 907 modules
- `GET /health` → `journal_mode wal, foreign_keys true`
- `POST /api/plans/generate WEEKLY` → `OPTIMAL` `valid:true` `blocks 18-20 integrated 2-3`
- `POST .../submit-review → approve CONTROL_OFFICE → APPROVED`, draft excluded from `approved-plans`
- Department views: `my_blocks` prominent, `integrated_blocks` visible, no leak
- Draft edit `200` on valid window, `400` on train/resource/isolation/dependency conflict, approved immutable `400`, revision `200`, stale `409`, audit contains old/new/editor/reason
- Execution `BLK-* →201`, duplicate same → `200`, diff → `409`, `WND-* →400`, unknown → `404`, malformed body → `422` (after fix), no `500`
- Replan preserves completed/locked, new version, moved/displaced reasons, execution history
- Metrics from DB (`blocks`, `resource_utilization`, `planned_vs_actual`), not hard-coded, export CSV/PDF contains `PLAN-*`

## 8. Explicit Limitations

- Synthetic windows, single-node SQLite WAL, no live APIs, no safety certification, grouping max 3, notifications in-app only, `eslint` not yet in devDependencies (to be fixed), `start.sh clean/health` partial (to be fixed).

## 9. Immutable Rule

```text
No data → 400, Invalid → rejected, Infeasible window → no assignment, Train/Goods hard → no assignment,
Duration/resource/dependency → no assignment, Invalid solver → no draft, Failed validation → no draft,
Unvalidated → no approval, Unapproved → no publication, Approved → immutable revision required,
Completed → locked, Duplicate execution → 409/idempotent, Every change → AuditEvent.
```

## 10. Testing the Contract

```python
# docs verification test (to be added)
# - AGENTS.md exists and contains "Prototype disclaimer" and "Immutable Rule"
# - docs/implementation-spec.md contains "Canonical Entities" and "Routes"
# - docs/problem-understanding.md contains "Rolling-block" and "Current vs Required"
# - docs/manual-acceptance-execution.md contains 30-step demo
```
