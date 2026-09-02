# Troubleshooting — RailBlock AI

**Prototype — synthetic data only.**

## PowerShell 5.1
- **Error:** `The token '&&' is not a valid statement separator`
  - **Fix:** Use `;` and `if ($?) {}`. Example: `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` then new terminal `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npm install; npm run dev` . Or `.\start.ps1` (already handles).
- **Error:** `Set-Location : Cannot find path ...`
  - **Fix:** Use literal path with quotes: `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"`.

## Python / Backend
- **Error:** `ModuleNotFoundError: No module named 'app'` or `ortools`
  - **Fix:** `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; pip install -q -r requirements.txt`
- **Error:** `Database is locked` or `sqlite3.OperationalError: database is locked` on reset
  - **Fix:** Stop server first: `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"; .\stop.ps1` then `python scripts\reset_demo.py` or `python scripts\reset_demo.py --force`. WAL `busy_timeout=5000` helps, but exclusive `BEGIN IMMEDIATE` will still fail if server writes.
- **Health:** `Invoke-WebRequest http://localhost:8000/health` → `status:ok, journal_mode:wal, foreign_keys:true`
- **Diagnostics:** `Invoke-WebRequest http://localhost:8000/api/diagnostics` → `{database:"SQLite", journal_mode:"wal", path:"D:/..."}`

## Frontend
- **Error:** `API unavailable — backend may be stopped` or `Network Error`
  - **Fix:** Ensure backend on 8000: `Test-NetConnection -ComputerName 127.0.0.1 -Port 8000`. Start backend as above. Check `frontend/vite.config.ts` proxy `/api→8000`.
- **Error:** `npm ERR!` or `vite not found`
  - **Fix:** `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npm install`
- **Blank page / crash:** Frontend now handles API unavailable with loading/empty/error states, not crash. Check browser console, ensure `npm run build` succeeded: `npx tsc --noEmit` (via `npm run build` runs tsc).

## Docker
- **Error:** `docker: command not found` or `docker: The term 'docker' is not recognized`
  - **Fix:** `start.ps1` auto-falls back to direct startup. Install Docker Desktop if you want `docker compose up --build -d`.
- **Healthcheck fails:** Now uses `python -c "urllib..."` not `curl`, so no curl install needed. Check `docker compose ps` and `docker compose logs backend --tail 20`.
- **Volume:** `backend_db:/app/data` persists `railblock.db` and `-wal/-shm`. Do not mount `*-wal` separately. `DATABASE_URL=sqlite:////app/railblock.db` inside container, `/app/railblock.db` on host via bind `./backend:/app`.
- **PostgreSQL errors:** Should not occur — compose has no postgres service. Ensure env does not override `DATABASE_URL` to postgres.

## Data / Planning
- **Error:** `No data -> no plan. Import tasks first. (400)`
  - **Fix:** `python scripts\reset_demo.py` auto-loads synthetic 30 tasks. Or import `data/sample/*.csv` via `/import`.
- **Duplicate on import:** `Duplicate: N` is expected on second import (idempotent composite keys `task_id`, `train_id`, `resource|date|start`, `asset_id`, `corridor|date|start|line`). Running reset twice should be `Duplicate:0` (verified).
- **No plan generated:** Check `/api/windows` feasible count; if all REJECTED due to train/goods, reduce high-confidence goods or overlapping trains in `data/sample/*.csv`.
- **Validation failed:** `POST /api/plans/{id}/validate` shows violations (train conflict, dependency order, duration, etc). Invalid solver output is not saved as draft (returns `FALLBACK_USED` or `VALIDATION_FAILED`).

## Ports
- Backend 8000, Frontend 5173 (Vite) / 3000 (Docker). Check `Get-NetTCPConnection -LocalPort 8000,5173` and `.\stop.ps1` to clean orphans.

## Tests
- `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"; python -m pytest tests -q` → 37 passed expected. Frontend `Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"; npm run build` → `✓ built`.

## Still stuck
- Run `python scripts\reset_demo.py --force`, check `backend/railblock.db` exists, check `backend/backend.log` and `frontend/frontend.log` (when using `start.ps1`), and `Invoke-WebRequest http://localhost:8000/health -UseBasicParsing | Select-Object Content`.
