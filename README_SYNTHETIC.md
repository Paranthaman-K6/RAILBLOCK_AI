# Synthetic Data - Fully Functional Without Interruptions

## Auto-Generation
Synthetic data is auto-generated and auto-loaded on first backend start via `backend/app/main.py`.
- 3 Corridors (Delhi-Howrah, Mumbai-Chennai, Howrah-Chennai)
- 6 Sections, 8 Lines, 12 Assets
- 30 Tasks across ENGINEERING, S_AND_T, TRACTION, PROJECTS with dependencies, overdue, safety scores
- 133 Trains (PASSENGER + GOODS) for 14 days with buffers
- 43 Goods forecasts with varying confidence (0.3-0.9)
- 14 Resources (CREW, MACHINE, MATERIAL) with 30-day availability

## Files
- `data/sample/*.csv` - 7 domain files, ready for manual import via `/import` page or auto-loaded
- `data/synthetic/*.csv` - same for 30-day horizon
- `data/generate_synthetic_full.py` - regenerates all (run from `data` folder: `python generate_synthetic_full.py`)

## Manual Regeneration
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\data"
python generate_synthetic_full.py
# then restart backend or run ingestion
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
python scripts\ingest_synthetic.py
```

## Verification
After auto-load:
```powershell
# health
Invoke-WebRequest http://localhost:8000/health | Select-Object Content
# weekly
Invoke-WebRequest -Method POST -Uri http://localhost:8000/api/plans/generate -ContentType "application/json" -Body '{"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"}' | Select-Object Content
# monthly
Invoke-WebRequest -Method POST -Uri http://localhost:8000/api/plans/generate -ContentType "application/json" -Body '{"horizon_start":"2026-09-01","horizon_end":"2026-09-30","horizon_type":"MONTHLY"}' | Select-Object Content
```

## Docker / Podman
If Docker is available:
```powershell
docker-compose up --build
# or podman
podman-compose up --build
# or podman
podman compose up --build
```
Frontend will proxy `/api` to `backend:8000` via `frontend/nginx.conf`.

If Docker not available (as in this environment), use PowerShell startup:
```powershell
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
.\start.ps1
# or simple
.\start_without_docker.ps1
```

## No Interruptions
- All imports are idempotent (duplicate detection, `duplicate_count`)
- Invalid data -> `rejected_count` with `errors[{row,field,severity,code,message}]`, no crash
- `No data -> no plan` enforced (400 if no tasks)
- Train/goods conflicts -> `HARD_CONFLICT` or `REJECTED` windows, never silent
- Dependency ordering enforced via CP-SAT + validator
- Every change -> `AuditEvent` + `Notification`
