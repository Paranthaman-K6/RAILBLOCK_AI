# RailBlock AI - Safe stop for PowerShell 5.1
# Stops only RailBlock AI processes started by the project (jobs + docker compose + uvicorn)
# Usage:
#   Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL"
#   .\stop.ps1

$projectRoot = $PSScriptRoot
if (-not $projectRoot) { $projectRoot = "D:\PROJECT2\MAYBE\RAIL" }
Write-Host "Stopping RailBlock AI (project root: $projectRoot)..." -ForegroundColor Yellow

# 1. Stop PowerShell jobs named RailBlock-*
try {
    $jobs = Get-Job -Name "RailBlock-*" -ErrorAction SilentlyContinue
    if ($jobs) {
        foreach ($j in $jobs) {
            Write-Host "Stopping job: $($j.Name) Id=$($j.Id) State=$($j.State)" -ForegroundColor Cyan
            try { Stop-Job -Id $j.Id -ErrorAction SilentlyContinue } catch {}
            try { Remove-Job -Id $j.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
        Write-Host "PowerShell jobs stopped." -ForegroundColor Green
    } else {
        Write-Host "No RailBlock jobs found." -ForegroundColor DarkGray
    }
    # Also check .backend_job / .frontend_job files
    foreach ($marker in @(".backend_job",".frontend_job")) {
        $p = Join-Path $projectRoot $marker
        if (Test-Path -LiteralPath $p) {
            try { Remove-Item -LiteralPath $p -Force } catch {}
            Write-Host "Removed marker $marker" -ForegroundColor DarkGray
        }
    }
    # Clean any remaining jobs (fallback)
    $allJobs = Get-Job -ErrorAction SilentlyContinue
    if ($allJobs) {
        $left = $allJobs | Where-Object { $_.Name -like "*uvicorn*" -or $_.Name -like "*vite*" }
        foreach ($j in $left) {
            Write-Host "Cleaning leftover job $($j.Id) $($j.Name)" -ForegroundColor DarkGray
            try { Stop-Job $j -ErrorAction SilentlyContinue; Remove-Job $j -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
} catch {
    Write-Host "Job stop warning: $($_.Exception.Message)" -ForegroundColor DarkGray
}

# 2. Stop Docker Compose if running (only this project's compose)
try {
    $hasDocker = Get-Command docker -ErrorAction SilentlyContinue
    if ($hasDocker) {
        Set-Location -LiteralPath $projectRoot
        # Check if compose file exists and any containers running
        $composePs = docker compose ps -q 2>$null
        if ($composePs) {
            Write-Host "Stopping Docker Compose..." -ForegroundColor Cyan
            docker compose down
            Write-Host "Docker Compose stopped." -ForegroundColor Green
        } else {
            # Try legacy
            try { docker-compose ps -q 2>$null | Out-Null; if ($LASTEXITCODE -eq 0) { docker-compose down } } catch {}
            Write-Host "No Docker Compose containers running." -ForegroundColor DarkGray
        }
    }
} catch {
    Write-Host "Docker stop warning: $($_.Exception.Message)" -ForegroundColor DarkGray
}

# 3. As last resort, stop orphan uvicorn/python listening on 8000 and node on 5173 (pid via netstat)
try {
    Write-Host "Checking for orphan processes on ports 8000/5173..." -ForegroundColor DarkGray
    $conns = Get-NetTCPConnection -LocalPort 8000,5173 -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $procId = $c.OwningProcess
        if ($procId -and $procId -ne 0) {
            try {
                $proc = Get-Process -Id $procId -ErrorAction SilentlyContinue
                if ($proc -and $proc.ProcessName -in @("python","python3","node","uvicorn")) {
                    Write-Host "Stopping orphan $($proc.ProcessName) PID $procId on port $($c.LocalPort)" -ForegroundColor Yellow
                    # Only stop if parent is this project? Check command line via WMI
                    try {
                        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId=$procId" -ErrorAction SilentlyContinue).CommandLine
                        if ($cmd -and ($cmd -like "*railblock*" -or $cmd -like "*uvicorn*app.main*" -or $cmd -like "*vite*")) {
                            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                            Write-Host "Stopped PID $procId" -ForegroundColor Green
                        } else {
                            Write-Host "Skipping PID $procId (not RailBlock): $cmd" -ForegroundColor DarkGray
                        }
                    } catch {
                        Write-Host "Could not verify PID $procId, skipping." -ForegroundColor DarkGray
                    }
                }
            } catch {}
        }
    }
} catch {
    Write-Host "Port check skipped (Get-NetTCPConnection not available): $($_.Exception.Message)" -ForegroundColor DarkGray
}

Write-Host "Stop complete. Verify:" -ForegroundColor Green
Write-Host "  Get-Job -Name RailBlock-* ; docker compose ps ; Invoke-WebRequest http://localhost:8000/health -UseBasicParsing" -ForegroundColor DarkGray
Set-Location -LiteralPath $projectRoot
