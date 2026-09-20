# 📸 Demo Evidence — RailBlock AI (PostgreSQL + SQLite)

**Live:** [Vercel](https://railblock-ai-gamma.vercel.app) → [Voroa](https://railblock-ai.getvoroa.com) `PostgreSQL 17.6` `pooled 6543` · **Theme:** Ocean Depths `#0f2a44` / `#2d8b8b`

> **All features tested via `openchamber_web` parallel browser + `curl` API on `PostgreSQL` (Supabase) and `SQLite` `tmp/railblock.db` — `30T · 659W · 19P` healthy.**

---

## 1️⃣ Health & DB — `GET /health` `200`

```json
{
  "status": "ok",
  "backend_url": "https://railblock-ai.getvoroa.com",
  "frontend_connected_to": "https://railblock-ai.getvoroa.com",
  "diagnostics": {
    "database": "PostgreSQL 17.6",
    "path": "postgresql://postgres.qgkxdvtrqjhcgnwggzxh:***@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres",
    "journal_mode": "wal",
    "available_connectors": ["TMS","SMMS","TDMS","COA","TRAIN","GOODS"]
  }
}
```

| Metric | Value | Source |
|--------|-------|--------|
| **Database** | `PostgreSQL 17.6` `wal true` | `GET /api/diagnostics` |
| **Fallback** | `SQLite` `tmp/railblock.db` `wal` | `backend/app/database.py:19` |
| **Frontend** | `Vercel` `index-CHfgX0q0.js` baked `getvoroa.com` | `frontend/dist` |

![Dashboard](screenshots/dashboard.png)
*Dashboard — 30T · 659W · 19P · Baseline vs Optimized (DB-driven, not hard-coded)*

---

## 2️⃣ Data Import — 7 Domains

| Source | File | Rows | Endpoint | Result |
|--------|------|------|----------|--------|
| COA | `corridors.csv` | 3 | `POST /api/import/corridors` | `200 duplicate:3` |
| Resources | `resources.csv` | 14 | `POST /api/import/resources` | `200 duplicate:14` |
| Timetable | `trains.csv` | 133 | `POST /api/import/trains` | `200 duplicate:133` |
| Goods | `goods_forecast.csv` | 43 | `POST /api/import/goods-forecast` | `200 duplicate:43` |
| TMS | `tasks.csv` | 30 | `POST /api/import/tasks` | `200 duplicate:30` |

Idempotent — `GET /api/import/summary` shows `received:30 accepted:0 duplicate:30`.

![Import](screenshots/import.png)

---

## 3️⃣ Corridors & Assets

`GET /api/corridors 200` `3` `COR-1 Delhi-Howrah`, `GET /api/assets 12` `AST-1 TRACK` — search filter `COR-1` → 4 assets.

![Corridors](screenshots/corridors.png)

---

## 4️⃣ Trains & Windows

`GET /api/trains 133` `TRN-0001 06:00→06:30` `[departure-buffer, arrival+buffer)` protected, `GET /api/windows?status=FEASIBLE 659` `WND-50D7705D 01:00–03:00 120m FEASIBLE` — templates `01:00–03:00` `13:30–15:30` `02:00–06:00` max `240`.

![Trains](screenshots/trains.png)

---

## 5️⃣ Task Inbox — `P=0.30S+…`

`GET /api/tasks?limit=10 200` `TSK-019 CRITICAL 83.6` `S:89 U:51 C:92 O:85`, `GET /api/tasks/TSK-001/priority-explanation 200` `weights S0.3 U0.2`.

![Tasks](screenshots/tasks.png)

---

## 6️⃣ Planner — Generate → Approve (Fast `<1.2s`)

```bash
POST /api/plans/generate {"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"}
→ 200 PLAN-9FF3B9DD OPTIMAL 20 blocks 1.17s valid:true

POST /api/plans/PLAN-9FF3B9DD/submit-review → 200 UNDER_REVIEW 1.16s
POST /api/plans/PLAN-9FF3B9DD/approve {"CONTROL_OFFICE"} → 200 APPROVED 1.98s
```

Frontend `Planner.tsx` optimistic `setSelected(UNDER_REVIEW)` + `TopLoadingBar` `3px teal` + `FrontendOverlay` `Submitting…`/`Approving…` `Esc` to dismiss.

![Planner](screenshots/planner.png) *Generate → 20 blocks OPTIMAL → Submit → Approve — 17P total*

---

## 7️⃣ Optimizer — Hybrid AI `9` Steps

`GET /api/compatibility/priority-weights 200` `S0.3 U0.2 C0.2 O0.15 D0.1 R0.05`, `POST /api/optimize 200 OPTIMAL 0.07s`, Frontend `Optimizer.tsx` chart `Baseline 25 → Optimized 20`.

![Optimizer](screenshots/optimizer.png)

---

## 8️⃣ Execution — `BLK-* 201` Idempotent

`POST /api/blocks/BLK-0D1EB62C/execution {"COMPLETED"} → 201 EXE-581B4215` `optimistic` `2.3s`, duplicate same → `200`, diff → `409`, `WND-* 400`, `404`, `GET /execution/plan/{id} 20`.

![Execution](screenshots/execution.png)

---

## 9️⃣ Metrics — Baseline vs Optimized (From DB)

`GET /api/metrics 200` `blocks 20` `resource_util 76.7%` `GET /api/metrics/{id} 200` `blocks_detail 20` `schedule 20` → `Gantt` `Baseline 25 2760min → Optimized 20 2360min`.

![Metrics](screenshots/metrics.png) *Bars 25→20, Minutes 2760→2360 + Asset Breakdown `AST-4 98.71%`*

---

## 🔟 Manual Acceptance — `openchamber_web` Parallel

All `14` pages `200`: `Dashboard → Import → Corridors → Trains → Conflicts → Tasks → Planner → Optimizer → Departments → Execution → Metrics` via `browser.open` + `browser.snapshot` + `browser.click` `★ Generate` `200` parallel with `22 curl & wait` `0.99–12s`.

**No `500`** — `400/404/409/422` only, `TopLoadingBar` `5` end options (`response`/`8s timeout`/`popstate`/`hashchange`/`click`).

---

*Captured via `openchamber_web` on `PostgreSQL` (`Voroa`) + `Vercel` (`index-Dob6oTFH.js`), `project tmp/` fallback retained, `C++/Rust` deep modules optional.*

