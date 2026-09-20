# API Reference — RailBlock AI

> **Base URL:** `https://railblock-ai.getvoroa.com` (Vercel `https://railblock-ai-gamma.vercel.app` proxies via `RENDER_FALLBACK`)
> **Auth:** `X-Department` header (`VIEWER` default) · **All responses** `200` on success, `400/401/404/409/422` on invalid, **no `500`** (generic handler)

---

## Health & Diagnostics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | `ok` + `backend_url` `frontend_connected_to` + `diagnostics` |
| `GET` | `/api/diagnostics` | `database` `PostgreSQL`/`SQLite` `wal` `path` `cursor_summary` |

```bash
curl https://railblock-ai.getvoroa.com/health | jq
# {"status":"ok","backend_url":"https://railblock-ai.getvoroa.com","diagnostics":{"database":"PostgreSQL 17.6"}}
```

---

## Import — 7 Domains

| Method | Endpoint | Source | File |
|--------|----------|--------|------|
| `POST` | `/api/import/tasks` | `TMS` `SMMS` `TDMS` | `tms_tasks.csv` `15` `smms 8` `tdms 7` |
| `POST` | `/api/import/corridors` | `COA` | `corridors.csv` `3` |
| `POST` | `/api/import/assets` | `COA` | `assets.csv` `12` |
| `POST` | `/api/import/trains` | `TIMETABLE` | `trains.csv` `133` |
| `POST` | `/api/import/goods-forecast` | `GOODS_FORECAST` | `goods_forecast.csv` `43` |
| `POST` | `/api/import/resources` | `RESOURCES` | `resources.csv` `14` |
| `GET` | `/api/import/summary` | — | `20` runs |

Idempotent — `duplicate:30` on re-import.

---

## Tasks & Windows

| Method | Endpoint | Example |
|--------|----------|---------|
| `GET` | `/api/tasks?limit=10` | `30` `TSK-019 CRITICAL 83.6` |
| `GET` | `/api/tasks/{id}/priority-explanation` | `P=0.30S+…` `S0.3 U0.2` |
| `GET` | `/api/windows?status=FEASIBLE` | `659` `WND-50D7705D 01:00–03:00` |
| `GET` | `/api/windows/{id}` | `FEASIBLE 120m` |
| `POST` | `/api/conflicts/detect` | `{"compatible":true}` |

---

## Planner — Generate → Approve

| Method | Endpoint | Payload | Response |
|--------|----------|---------|----------|
| `POST` | `/api/plans/generate` | `{"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"}` | `200 PLAN-XXXX OPTIMAL 20 blocks 1.17s` |
| `GET` | `/api/plans` | — | `20` `DRAFT`/`APPROVED` |
| `GET` | `/api/plans/{id}` | — | `blocks[]` `validation` `approvals` |
| `POST` | `/api/plans/{id}/validate` | — | `{"valid":true}` |
| `POST` | `/api/plans/{id}/submit-review` | — | `200 UNDER_REVIEW` `<200ms` |
| `POST` | `/api/plans/{id}/approve` | `{"approver_id":"x","approver_role":"CONTROL_OFFICE"}` | `200 APPROVED` `<200ms` |
| `DELETE` | `/api/plans/{id}` | `{"approver_role":"CONTROL_OFFICE"}` | `200 DELETED` |
| `POST` | `/api/plans/bulk-delete` | `{"plan_ids":[...]}` | `200` |
| `GET` | `/api/plans/{id}/export?format=csv` | — | `200` `PLAN-XXXX.csv` `9` lines |
| `GET` | `/api/plans/{id}/export?format=pdf` | — | `200` `PDF 1.4` `2086 bytes` |
| `PATCH` | `/api/plans/{id}/draft-blocks/{bid}` | `{"service_date":"2026-09-03"}` | `200` or `400 PLAN_IMMUTABLE` |

---

## Optimizer & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/compatibility/priority-weights` | `S0.3 U0.2 C0.2 O0.15 D0.1 R0.05` |
| `POST` | `/api/optimize` | `200 OPTIMAL` `0.07s` |
| `GET` | `/api/metrics` | `blocks 20` `resource_util 76.7%` |
| `GET` | `/api/metrics/{id}` | `blocks_detail 20` `schedule` `Gantt` |
| `GET` | `/api/export/postgres/status` | `PostgreSQL` `counts` `export_ready` |
| `GET` | `/api/export/postgres/csv?table=tasks` | `CSV` `tasks` |
| `GET` | `/api/export/postgres/dump` | `JSON` full dump |

---

## Execution & Departments

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/blocks/{id}/execution` | `201` `EXE-*` idempotent `200`/`409` `400 WND-*` |
| `GET` | `/api/execution/plan/{id}` | `20` `COMPLETED` |
| `GET` | `/api/approved-plans` | `2` `APPROVED` |
| `GET` | `/api/plans/{id}/department-view?department=ENGINEERING` | `my 2` `integrated` |
| `GET` | `/api/notifications?department=ENGINEERING` | `9` `APPROVAL` |
