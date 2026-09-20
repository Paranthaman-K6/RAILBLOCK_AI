# Deployment — Vercel + Voroa + Supabase + Docker

> **Live:** `Vercel` `https://railblock-ai-gamma.vercel.app` (`index-Dob6oTFH.js`) → `Voroa` `https://railblock-ai.getvoroa.com` (`PostgreSQL 17.6` pooled `6543` `ok`)

---

## Stack

| Layer | Service | Config |
|-------|---------|--------|
| **Frontend** | `Vercel` | `frontend/` `Vite 5` `React 18` `output: frontend/dist` `RENDER_FALLBACK=https://railblock-ai.getvoroa.com` |
| **Backend** | `Voroa` `ckogalwbbeu9qgn5jxvgvn0y` | `Dockerfile` `python:3.11-slim` `uvicorn` `PORT` `https://railblock-ai.getvoroa.com` |
| **DB** | `Supabase` `qgkxdvtrqjhcgnwggzxh` `ap-southeast-1` | `postgresql://postgres.qgkxdvtrqjhcgnwggzxh:***@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require` `DATABASE_MODE=postgres` |
| **Fallback** | `SQLite` | `tmp/railblock.db` `WAL` `project tmp/` `frontend/src/index.css` `api/index.py` |

---

## Vercel

- **Build:** `cd frontend && npm install && npm run build` `output: frontend/dist`
- **Env:** `DATABASE_URL=sqlite:///./tmp/railblock.db` `DATABASE_MODE=sqlite` (fallback only, real data via Voroa)
- **Routing:** `frontend/src/services/api.ts:7` `VITE_API_URL==""` → `RENDER_FALLBACK` `getvoroa.com` (same-origin on `getvoroa.com`)
- **Verify:** `curl https://railblock-ai-gamma.vercel.app/` `200` `index-Dob6oTFH.js`

---

## Voroa

- **Service:** `railblock-ai` `ckogalwbbeu9qgn5jxvgvn0y` `main` auto-deploy on `git push`
- **Docker:** `Dockerfile` `WORKDIR /app` `requirements.txt` `psycopg2-binary` `uvicorn $PORT` `mkdir -p /app/tmp 777`
- **Env:** `DATABASE_URL` pooled `6543` `sslmode=require` `connect_timeout=5` `DATABASE_MODE=postgres` `PORT` auto
- **Pool:** `database.py:290` `pool 3/7 timeout 10` for `pooler.supabase.com:6543` (was `10/20` → `EMAXCONNSESSION 15`), `main.py` skips seeder for `postgres`
- **Verify:** `curl https://railblock-ai.getvoroa.com/health | jq .diagnostics.database` → `PostgreSQL 17.6`

---

## Supabase

- **Project:** `Paranthaman-K6's Project` `qgkxdvtrqjhcgnwggzxh` `ACTIVE_HEALTHY` `17.6.1.166` `ap-southeast-1`
- **Pooled:** `aws-0-ap-southeast-1.pooler.supabase.com:6543` `postgres.qgkxdvtrqjhcgnwggzxh` `transaction` `RailBlock2026!SecurePG` (rotated via Composio `SUPABASE_UPDATE_DATABASE_PASSWORD`)
- **Direct:** `db.qgkxdvtrqjhcgnwggzxh.supabase.co:5432` → `Network is unreachable` IPv6 — use pooled `6543`
- **Data:** `30 tasks` `133 trains` `43 goods` `720 windows` `11 block_plans` `180 blocks` `8 approvals` `22 executions` via `SUPABASE_LIST_TABLES`

---

## Docker Local

```bash
docker compose up --build -d
# Frontend :3000  Backend :8000/health  DB volume backend_db:/app/data
```

See `docker-compose.yml:10` `DATABASE_URL=sqlite:////app/tmp/railblock.db` `healthcheck python -c urllib`.

---

## CI

`git push origin main` → `Vercel` auto-build `frontend/dist` + `Voroa` `Dockerfile` `uvicorn`. `30T·659W·19P` healthy.
