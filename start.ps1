# RailBlock AI - Windows PowerShell 5.1 startup (robust, SQLite WAL only)
# No &&, uses Set-Location -LiteralPath, detects Python/Node/Docker, falls back to direct startup
# Synthetic prototype disclaimer: This application uses synthetic demonstration data...

Write-Host "=== RailBlock AI - Human-approved planning and decision-support prototype ===" -ForegroundColor Green
Write-Host "Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations. Production use would require authorized data integration, railway-domain validation, cybersecurity review, safety approval, and operational certification." -ForegroundColor Yellow
Write-Host "Synthetic prototype windows, not official railway availability." -ForegroundColor Yellow

$projectRoot = $PSScriptRoot
if (-not $projectRoot) { $projectRoot = "D:\PROJECT2\MAYBE\RAIL" }
Write-Host "Project root: $projectRoot" -ForegroundColor DarkGray

# --- Detect dependencies ---
function Test-Command($cmd) {
    try { Get-Command $cmd -ErrorAction Stop | Out-Null; return $true } catch { return $false }
}
$hasPython = Test-Command "python"
$hasNode = Test-Command "node"
$hasNpm = Test-Command "npm"
$hasDocker = Test-Command "docker"
$hasDockerCompose = $false
if ($hasDocker) {
    try { docker compose version 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $hasDockerCompose = $true } } catch {}
    if (-not $hasDockerCompose) {
        try { docker-compose version 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { $hasDockerCompose = $true } } catch {}
    }
}

Write-Host ""
Write-Host "Dependency check:" -ForegroundColor Cyan
Write-Host "  Python: $(if($hasPython){'FOUND'}else{'MISSING - install Python 3.11+'})" -ForegroundColor $(if($hasPython){"Green"}else{"Red"})
Write-Host "  Node:   $(if($hasNode){'FOUND'}else{'MISSING - install Node 20+'})" -ForegroundColor $(if($hasNode){"Green"}else{"Yellow"})
Write-Host "  npm:    $(if($hasNpm){'FOUND'}else{'MISSING'})" -ForegroundColor $(if($hasNpm){"Green"}else{"Yellow"})
Write-Host "  Docker: $(if($hasDocker){'FOUND'}else{'NOT FOUND - falling back to direct startup'})" -ForegroundColor $(if($hasDocker){"Green"}else{"Yellow"})

if (-not $hasPython) {
    Write-Host "ERROR: Python not found. Install Python 3.11 and ensure 'python' is in PATH." -ForegroundColor Red
    exit 1
}

# --- Try Docker Compose if available and requested ---
$useDocker = $false
if ($hasDocker -and $hasDockerCompose) {
    Write-Host ""
    Write-Host "Docker is available. Starting via Docker Compose (SQLite at /app/railblock.db, WAL persisted)..." -ForegroundColor Green
    Set-Location -LiteralPath $projectRoot
    try {
        # Use docker compose (new) or docker-compose (old)
        if (Test-Command "docker") {
            docker compose up --build -d
            if ($LASTEXITCODE -eq 0) { $useDocker = $true }
            else {
                Write-Host "docker compose failed, trying docker-compose..." -ForegroundColor Yellow
                docker-compose up --build -d
                if ($LASTEXITCODE -eq 0) { $useDocker = $true }
            }
        }
    } catch {
        Write-Host "Docker startup failed: $($_.Exception.Message)" -ForegroundColor Yellow
        $useDocker = $false
    }
    if ($useDocker) {
        Write-Host "Docker Compose started." -ForegroundColor Green
        Write-Host "Backend:  http://localhost:8000/health  http://localhost:8000/docs" -ForegroundColor Cyan
        Write-Host "Frontend: http://localhost:3000" -ForegroundColor Cyan
        Write-Host "Healthcheck: docker compose ps; docker compose logs backend --tail 20" -ForegroundColor DarkGray
        Write-Host "To stop: docker compose down  OR  Set-Location -LiteralPath `"$projectRoot`"; .\stop.ps1"
        exit 0
    } else {
        Write-Host "Falling back to direct PowerShell startup..." -ForegroundColor Yellow
    }
}

# --- Direct startup (no Docker) ---
Write-Host ""
Write-Host "Starting via direct PowerShell (no Docker) - SQLite WAL at D:\PROJECT2\MAYBE\RAIL\backend\railblock.db" -ForegroundColor Green

# Backend
Set-Location -LiteralPath "$projectRoot\backend"
if (-not (Test-Path -LiteralPath "$projectRoot\backend\railblock.db")) {
    Write-Host "Initializing fresh DB with synthetic data on first run..." -ForegroundColor Cyan
}
Write-Host "Checking Python deps (skip if already satisfied)..." -ForegroundColor DarkGray
# Avoid noisy rebuild of pydantic-core on Python 3.14 without VS Build Tools: only install if import fails
try {
    python -c "import fastapi, pydantic, sqlalchemy, ortools" 2>$null
    if ($LASTEXITCODE -ne 0) { pip install -q -r requirements.txt }
    else { Write-Host "Deps already satisfied, skipping pip install." -ForegroundColor DarkGray }
} catch { Write-Host "pip check warning: $($_.Exception.Message)" -ForegroundColor Yellow }

Write-Host "Starting backend at http://localhost:8000 ..." -ForegroundColor Green
Write-Host "  Docs: http://localhost:8000/docs  Health: http://localhost:8000/health" -ForegroundColor Cyan

# Use Start-Process for independent windows + also Start-Job for headless tracking
$backendLog = "$projectRoot\backend\backend.log"
$backendJob = Start-Job -Name "RailBlock-Backend" -ScriptBlock {
    param($root)
    Set-Location -LiteralPath "$root\backend"
    python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 2>&1 | Tee-Object -FilePath "$root\backend\backend.log"
} -ArgumentList $projectRoot

Start-Sleep -Seconds 4
$backendReady = $false
try {
    $health = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5 | Select-Object -ExpandProperty Content
    Write-Host "Backend health: $health" -ForegroundColor Green
    $backendReady = $true
} catch {
    Write-Host "Backend not yet ready (may still be starting). Check log: $backendLog" -ForegroundColor Yellow
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor DarkGray
}

# Persist backend PID/job for stop.ps1
$backendJob.Id | Out-File -FilePath "$projectRoot\.backend_job" -Encoding ascii
Write-Host "Backend Job: Id=$($backendJob.Id) Name=$($backendJob.Name) State=$($backendJob.State)" -ForegroundColor DarkGray

# Frontend
if ($hasNode -and $hasNpm) {
    Set-Location -LiteralPath "$projectRoot\frontend"
    if (-not (Test-Path -LiteralPath "$projectRoot\frontend\node_modules")) {
        Write-Host "Installing frontend deps..." -ForegroundColor Cyan
        npm install
    }
    Write-Host "Starting frontend at http://localhost:5173 ..." -ForegroundColor Green
    Write-Host "  Vite proxy: /api -> http://localhost:8000 , /health -> http://localhost:8000" -ForegroundColor DarkGray
    $frontendJob = Start-Job -Name "RailBlock-Frontend" -ScriptBlock {
        param($root)
        Set-Location -LiteralPath "$root\frontend"
        npm run dev -- --host 0.0.0.0 --port 5173 2>&1 | Tee-Object -FilePath "$root\frontend\frontend.log"
    } -ArgumentList $projectRoot
    Start-Sleep -Seconds 3
    $frontendJob.Id | Out-File -FilePath "$projectRoot\.frontend_job" -Encoding ascii
    Write-Host "Frontend Job: Id=$($frontendJob.Id) Name=$($frontendJob.Name) State=$($frontendJob.State)" -ForegroundColor DarkGray
} else {
    Write-Host "Node/npm not found: skipping frontend auto-start. Start manually with:" -ForegroundColor Yellow
    Write-Host "  Set-Location -LiteralPath `"$projectRoot\frontend`"; npm install; npm run dev" -ForegroundColor DarkGray
    $frontendJob = $null
}

Set-Location -LiteralPath $projectRoot
Write-Host ""
Write-Host "=== Services ===" -ForegroundColor Green
Write-Host "Backend:   http://localhost:8000/health" -ForegroundColor Cyan
Write-Host "           http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "Frontend:  http://localhost:5173  (Vite)" -ForegroundColor Cyan
Write-Host "Diagnostic: http://localhost:8000/api/diagnostics  (SQLite WAL, foreign_keys, path)" -ForegroundColor DarkGray
Write-Host 'Weekly:  POST http://localhost:8000/api/plans/generate  {"horizon_start":"2026-09-01", "horizon_end":"2026-09-07", "horizon_type":"WEEKLY"}' -ForegroundColor DarkGray
Write-Host 'Monthly: POST http://localhost:8000/api/plans/generate  {"horizon_start":"2026-09-01", "horizon_end":"2026-09-30", "horizon_type":"MONTHLY"}' -ForegroundColor DarkGray
Write-Host ""
Write-Host "To stop: Set-Location -LiteralPath `"$projectRoot`"; .\stop.ps1" -ForegroundColor Yellow
Write-Host "Logs: Get-Job | Receive-Job -Keep; Get-Content $backendLog -Tail 20" -ForegroundColor DarkGray
Write-Host "Jobs: Get-Job -Name RailBlock-*" -ForegroundColor DarkGray
if ($backendJob -and $frontendJob) {
    Write-Host "Waiting for jobs (Ctrl+C to detach, jobs keep running). Use stop.ps1 to terminate." -ForegroundColor DarkGray
    # Do not block forever in CI; if backend not ready, wait briefly
    Wait-Job -Job $backendJob -Timeout 2 | Out-Null
}
