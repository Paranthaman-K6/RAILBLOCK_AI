# Limitations — RailBlock AI (Prototype)

**Version:** `audit/final-release-2026-09-01` @ `de23bbf`  
**Synthetic prototype — not for real railway operations.**

## 1. Prototype Scope

- No live TMS, SMMS, TDMS, COA, timetable, or railway-control integration. All data is synthetic from `data/sample/*.csv` and seeded corridors/assets. Production use would require authorized interfaces, railway-domain validation, cybersecurity review, safety approval, and operational certification.
- No automatic signal operation, power isolation, or train dispatching. System is **human-approved decision-support only** (`DRAFT → UNDER_REVIEW → APPROVED → PUBLISHED`).

## 2. Data and Validation

- Single `data/sample/tasks.csv` covers TMS/SMMS/TDMS via `department` column (ENGINEERING/S_AND_T/TRACTION/PROJECTS). Separate `smms.csv`/`tdms.csv` not distinct — adapters exist (`adapters/tms.py`, `smms.py`, `tdms.py`, `coa.py`, `timetable.py`, `goods_forecast.py`, `resources.py`) but sample not split. Import preview → confirmation flow not implemented (direct transactional persistence).
- Structural/referential/operational validation implemented, but some errors return `400` instead of `422` per spec (invalid body).
- Duplicate handling deterministic via composite keys (`task_id`, `resource_id|service_date|start_time`, etc.), but no UI for duplicate resolution.

## 3. Planning and Optimization

- Synthetic windows are fixed templates (`01:00–03:00`, `13:30–15:30`, `02:00–06:00`, max 240 mins), not official sectional availability. Labelled `Synthetic prototype windows, not official railway availability.` — not real possession planning.
- Baseline FCFS and CP-SAT (OR-Tools) with `time_limit 5s`, 8 workers. Fallback is deterministic greedy, but timeout path not exercised in tests (CP-SAT usually returns `OPTIMAL` quickly for 30 tasks). No `TIME_LIMIT` simulation via API.
- Grouping via `grouping_compatible_tasks` limited to `MAX_GROUP_SIZE 3`, compatible corridor/section/line/type/power/signal/resources/duration/dependencies — not full cost/crew travel optimization.
- `historical execution` (8th source) is via `ExecutionRecord` delta (`+8` urgency for rework, `-2` for recent completed) — not a trained ML model, explainable only.

## 4. Approval and Visibility

- Unauthorized approval currently falls back to `officer1`/`CONTROL_OFFICE` instead of `403` — `routers/plans.py` should require explicit `approver_id`/`role`.
- Department visibility filters by `department` but `VIEWER` sees `integrated_blocks` only — no row-level security beyond in-memory filtering. No authentication/role context beyond `UserContext` seed.

## 5. Editing and Replanning

- Draft edit on invalid date correctly returns `400`, but one valid edit test failed due to train conflict on chosen date — not a code bug, but test data sensitivity.
- Resource/isolation/dependency conflicting edits not explicitly covered via API tests (validator exists, but no dedicated edit cases).
- Resource availability change not exercised in replan scenario (`ResourceAvailability` table exists, but audit only tested emergency task addition).
- `start.sh` lacks `clean`/`health` subcommands expected by audit; `stop.ps1` required `em-dash` fix already applied in `b911f29`.

## 6. Execution

- Valid `BLK-*` → `201`, duplicate same payload → `200 idempotent`, diff → `409` — documented and correct.
- `WND-*` → `400` with clear message, unknown `BLK-*` → `404`, invalid body → `400` (spec expects `422`).
- `actual_end < actual_start` → `400`, cancelled/deferred without reason → `400` — correct.
- Execution history survives replan (`ExecutionRecord` count 1), but `planned_vs_actual` is per-block delta, not aggregated `completion_rate`/`cancellation_rate` KPI.

## 7. Metrics and Export

- Metrics from DB (`blocks`, `scheduled_tasks`, `block_minutes`, `resource_utilization 64.5`, `planned_vs_actual`, `baseline/optimized/improvement`) — no hard-coded KPI, but `asset downtime`/`availability` fields are proxy via `block_minutes`/`unused_time`/`asset_availability_benefit`, not dedicated per-asset downtime tracking.
- `completion_rate`/`cancellation_rate` not explicit fields — derived from `execution` counts.
- Export `CSV 200 text/csv` and `PDF 200` work, but PDF is plain text with `Content-Disposition: attachment` via `PlainTextResponse` — not a true PDF binary.

## 8. Infrastructure

- **SQLite WAL only** (`backend/railblock.db`, `journal_mode wal`, `foreign_keys ON`, `busy_timeout 5000`) — single-node, no horizontal scaling, no PostgreSQL. `DATABASE_URL=sqlite:////app/railblock.db` in Docker, volume `backend_db:/app/data` persists WAL.
- Docker Compose valid but `docker` not installed in audit env — `docker compose config` not verifiable at runtime (file existence PASS, runtime NOT APPLICABLE).
- Frontend `lint` (`eslint`) not in `devDependencies` — `npm run lint` fails (`eslint not recognized`). `npx tsc --noEmit` and `vite build` pass.
- `CI` workflow (`.github/workflows/ci.yml`) runs `pytest` and `npm run build` but not `eslint` or `health` checks.
- `start.sh` `bash -n` passes, but pip install on Python 3.14 requires `cargo`/`link.exe` for `pydantic-core` — `start.ps1` now skips if imports already satisfied (`de23bbf` fix), `start.sh` still does raw `pip install -q`.

## 9. Documentation

- `README.md` and `docs/architecture.md` align with spec, but `AGENTS.md`, `docs/implementation-spec.md`, `docs/problem-understanding.md`, `docs/manual-acceptance-execution.md` are **missing** — audit claims they should be read per spec.
- `docs/final-release-audit.md` was missing before this audit (now created), `docs/demo-evidence.md` existed minimal (now expanded), `docs/limitations.md` existed minimal (now expanded).

## 10. Testing

- Backend `52 passed` (15 group_optimization tests for first-class CP-SAT grouping) — not `150` as claimed in audit evidence. No 150-test suite exists.
- Frontend manual tests not automated (no Playwright/Cypress).
- No load/performance testing.

## 11. Not for Production

- No safety certification, no cybersecurity review, no operational validation with Indian Railways. Rolling-block guidance and CP-SAT references are prototype only. All `OPTIMAL` statuses are relative to encoded model, not operationally approved.

---

**Recommendation:** Do not declare final release complete until missing docs, 150-test claim, eslint, unauthorized approval, start.sh subcommands, and explicit downtime KPIs are addressed. Prototype is **demo-ready** but **not release-ready**.

