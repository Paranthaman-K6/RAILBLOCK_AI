# Architecture — RailBlock AI (Prototype)

## Disclaimer
**Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification.** — Shown in Dashboard, Import, Planner, Footer, README, and presentation.

## High-level
`Users → React (Dashboard/Planner) → FastAPI REST → Planning Orchestrator → SQLite WAL (D:/PROJECT2/MAYBE/RAIL/backend/railblock.db) → Nginx (Docker) / Vite proxy (local)`

## Stack (Fixed)
- **Frontend:** React 18, Vite 5, React Router 6, TypeScript 5, Axios, Recharts, Vite proxy `/api→8000`, `/health→8000`
- **Backend:** FastAPI 0.110, Pydantic 2.6, SQLAlchemy 2.0, Alembic, SQLite WAL, OR-Tools 9.8 CP-SAT
- **DB:** SQLite only — `check_same_thread=False`, `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout=5000`, `synchronous=NORMAL`, `cache_size=-64000`, verified not merely requested; absolute path `D:/PROJECT2/MAYBE/RAIL/backend/railblock.db` (Docker `//app/railblock.db`), volume `backend_db:/app/data` persists WAL sidecars
- **Deploy:** Docker Compose (2 services, healthcheck via `python -c urllib`, no PostgreSQL), `start.ps1`/`start.sh`/`stop.ps1` for PowerShell 5.1 (no `&&`, `Set-Location -LiteralPath`)

## Orchestrator Services (18)
`ImportService → ValidationService → NormalizationService → AssetMapping → PriorityEngine (P=0.30S+0.20U+0.20C+0.15O+0.10D+0.05R) → RiskEngine (train_conflict_check, goods_risk) → CandidateWindowEngine (idempotent, bulk, interval rule) → CompatibilityEngine → GroupingEngine → Baseline (FCFS, no grouping) → CP-SAT Optimizer (integer, time_limit, resource/dependency constraints) → Fallback → Validator (14 checks) → ApprovalService → VisibilityService → ExecutionService → MetricsService → RevisionService → NotificationService → ExportService`

## Layers
1. **UI:** Components `Navbar`, `Card`, `Gantt`, `PlanStatus` (Red safety `#f44336`, Orange conflict `#ff9800`, Green feasible `#4caf50`, Blue approved `#1976d2`), `WarningBanner`, pages all handle API unavailable, loading, empty states, plain-language errors, Asia/Kolkata dates, pagination, export errors.
2. **API:** FastAPI routers (`/health`, `/api/diagnostics`, `/api/tasks` paginated, `/api/windows`, `/api/plans/*`, `/api/metrics`, `/api/blocks/*/execution`, etc), Pydantic models, consistent error envelope `{error:{code,message,details}, detail}` without tracebacks, IDs canonical (`COR-`, `TSK-`), ISO dates, documented timezone (`Asia/Kolkata` display, UTC storage), weekly/monthly horizons validated.
3. **Domain:** Priority, compatibility (`check_task_window_fit`), grouping, risk (`train_conflict_check` with buffer, `goods_risk_classify`), interval rule `overlap = train_start < block_end and train_end > block_start` with exact-boundary tests.
4. **Integration:** 7 adapters (`TMS`, `SMMS`, `TDMS`, `COA`, `Timetable`, `GoodsForecast`, `Resources`) with expected_columns, normalize, validate.
5. **Persistence:** SQLAlchemy models with 27 entities, indexes on FKs (`corridor_id`, `service_date`, `status`, etc), explicit transactions, savepoints per-record, `PRAGMA foreign_keys=ON` per connection, busy_timeout, no long transactions, bulk conflict lookups, no N+1, pagination for tasks/audits, avoids `SELECT *` by filtered queries.
6. **Optimization:** Pre-filters infeasible windows, creates `x[tid,wid]` BoolVar only for compatible pairs grouped by corridor/date, integer times, objective `int((benefit-penalty)*10)` avoids float, weights configurable via `RuleConfiguration`, dependency ordering `var_task <= sum(earlier_dep_vars)`, resource non-overlap per date, window ≤1, time_limit 5s, status `OPTIMAL|FEASIBLE|INFEASIBLE|TIME_LIMIT|FALLBACK_USED|VALIDATION_FAILED`, fallback validated independently, never treats `FEASIBLE` as `OPTIMAL`.
7. **Validation:** Independent validator checks train conflict (with buffer), goods risk, duration, resource, corridor/section/line, block/power/signalling, duplicate, dependency order, horizon, completed preservation, max duration.
8. **State Machine:** `DRAFT→UNDER_REVIEW→APPROVED→PUBLISHED→SUPERSEDED` (plus `REJECTED`), drafts editable, approved immutable (revisions via `PlanRevision` with `expected_version` 409 on stale), published in department views, concurrent protections (approval 400 if not DRAFT/UNDER_REVIEW, execution 409 duplicate, replanning reports preserved/moved/displaced), every transition → `AuditEvent`.

## Data Flow
Synthetic CSVs (`data/sample/*.csv`) → `run_import` (header validation streaming, composite duplicate keys, cached existing sets, bulk, savepoints, structured errors `{row,field,severity,code,message}`, `ImportRun` audit) → `recalculate_all` → `generate_candidate_windows` (bulk train/goods maps, idempotent update, rejection reasons, `expected_train_count`, `goods_risk_score`) → `generate_baseline_plan` → `run_cpsat_optimizer` → `validate_plan` → `approve/reject/publish` → `department-view` → `record_execution` → `calculate_metrics` (from real dataset) → `export`.

## Security / Prototype Limits
- No live railway APIs, no paid services, synthetic labeled everywhere.
- Every state change → `AuditEvent` + `Notification`.
- `approved plans are immutable`, completed blocks locked, no silent movement.
- SQLite only, WAL verified, foreign_keys per-connection.
