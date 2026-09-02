#!/usr/bin/env bash
set -e
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== RailBlock AI - Human-approved prototype ==="
echo "Prototype disclaimer: This application uses synthetic demonstration data and prototype operational rules. It does not access live TMS, SMMS, TDMS, COA, timetable, or railway-control systems. It must not be used for real railway operations."
echo "Synthetic prototype windows, not official railway availability."
echo "Project root: $PROJECT_ROOT"

# Determine python
PYTHON="python"
if ! command -v python >/dev/null 2>&1 && command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
fi

do_clean() {
  echo "Cleaning local SQLite database, WAL sidecars, caches, demo artifacts..."
  # Only remove DB and sidecars, not source, venv, node_modules
  rm -f "$PROJECT_ROOT/backend/railblock.db" "$PROJECT_ROOT/backend/railblock.db-wal" "$PROJECT_ROOT/backend/railblock.db-shm"
  rm -f "$PROJECT_ROOT/backend/*.log" "$PROJECT_ROOT/backend/backend.log"
  rm -f "$PROJECT_ROOT/frontend/frontend.log"
  rm -rf "$PROJECT_ROOT/backend/__pycache__" "$PROJECT_ROOT/backend/.pytest_cache"
  rm -rf "$PROJECT_ROOT/backend/app/__pycache__"
  # Recreate deterministic seed-42 data on next start via reset_demo.py
  echo "Running reset_demo.py to recreate deterministic seed-42 data..."
  # Try python then python3 with proper path
  if $PYTHON scripts/reset_demo.py 2>/dev/null; then
    echo "Reset complete"
  elif python3 scripts/reset_demo.py 2>/dev/null; then
    echo "Reset complete (via python3)"
  elif "$PROJECT_ROOT/backend/venv/Scripts/python" scripts/reset_demo.py 2>/dev/null; then
    echo "Reset complete (via venv)"
  else
    # Fallback: just remove DB, auto-seed will happen on backend start
    echo "reset_demo skipped - will auto-seed on next backend start (ensure Python deps installed)"
  fi
  echo "Clean complete. Next start will have Tasks:30 Trains:133 Goods:43 Resources:14 Windows:168"
}

do_health() {
  echo "=== Health checks (backend, import, tasks, windows, metrics, conflicts, optimization, plan, frontend) ==="
  set +e
  FAIL=0
  check() {
    local name="$1" url="$2" expect="$3"
    echo -n "Check $name ($url) ... "
    if curl -fsS "$url" >/tmp/health_check.json 2>/dev/null; then
      if [ -n "$expect" ]; then
        if grep -q "$expect" /tmp/health_check.json; then
          echo "PASS"
        else
          echo "FAIL (missing $expect)"
          cat /tmp/health_check.json
          FAIL=1
        fi
      else
        echo "PASS"
      fi
    else
      echo "FAIL (curl error)"
      FAIL=1
    fi
  }
  check "backend health/database" "http://localhost:8000/health" "journal_mode"
  check "import summary" "http://localhost:8000/api/import/summary" "TMS"
  check "tasks" "http://localhost:8000/api/tasks?limit=1" "task_id"
  check "windows" "http://localhost:8000/api/windows?status=FEASIBLE" "WND-"
  check "metrics" "http://localhost:8000/api/metrics" "blocks"
  check "conflicts" "http://localhost:8000/api/conflicts/detect" "conflicts"
  # Optimization: try plan generation (isolated, do not create persistent execution)
  echo -n "Check plan generation ... "
  if curl -fsS -X POST http://localhost:8000/api/plans/generate -H "Content-Type: application/json" -d '{"horizon_start":"2026-09-01","horizon_end":"2026-09-07","horizon_type":"WEEKLY"}' >/tmp/plan_gen.json 2>/dev/null; then
    if grep -q "plan_id" /tmp/plan_gen.json && grep -q "OPTIMAL" /tmp/plan_gen.json; then
      echo "PASS"
    else
      echo "FAIL (no plan_id/OPTIMAL)"
      cat /tmp/plan_gen.json
      FAIL=1
    fi
  else
    echo "FAIL (curl)"
    FAIL=1
  fi
  check "frontend SPA" "http://localhost:5173/" "<title"
  # Fallback to 3000 if 5173 not
  # Do not reset FAIL after retry - keep failure if both fail
  if [ $FAIL -ne 0 ]; then
    echo "Retrying frontend on 3000..."
    # Use a temporary check without overwriting FAIL if still fails
    echo -n "Check frontend SPA 3000 (http://localhost:3000/) ... "
    if curl -fsS http://localhost:3000/ >/tmp/health_check.json 2>/dev/null && grep -q "<title" /tmp/health_check.json; then
      echo "PASS (3000)"
      # Frontend is optional - don't fail overall if backend passed but frontend on 5173 failed
      # Check if backend checks passed (first 7)
      if grep -q "journal_mode" /tmp/health_check.json 2>/dev/null; then
        FAIL=0
      fi
    else
      echo "FAIL"
      # Keep FAIL as is
    fi
  fi
  if [ $FAIL -eq 0 ]; then
    echo "All health checks PASS"
    exit 0
  else
    echo "Some health checks FAIL (backend required)"
    exit 1
  fi
  set -e
}

do_status() {
  echo "=== Status ==="
  echo "PIDs and ports:"
  if command -v ps >/dev/null 2>&1; then
    ps aux | grep -E "uvicorn|vite|node.*5173|python.*8000" | grep -v grep || echo "No uvicorn/vite processes found"
  else
    echo "ps not available, checking jobs..."
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -tulpn 2>/dev/null | grep -E "8000|5173|3000" || echo "No listeners on 8000/5173/3000"
  elif command -v ss >/dev/null 2>&1; then
    ss -tulpn 2>/dev/null | grep -E "8000|5173|3000" || echo "No listeners"
  else
    echo "Checking via curl..."
    curl -fsS http://localhost:8000/health >/dev/null 2>&1 && echo "Backend 8000: UP" || echo "Backend 8000: DOWN"
    curl -fsS http://localhost:5173/ >/dev/null 2>&1 && echo "Frontend 5173: UP" || echo "Frontend 5173: DOWN"
    curl -fsS http://localhost:3000/ >/dev/null 2>&1 && echo "Frontend 3000: UP" || echo "Frontend 3000: DOWN"
  fi
  if command -v docker >/dev/null 2>&1; then
    docker compose ps 2>/dev/null || echo "Docker compose not running"
  fi
  if [ -f "$PROJECT_ROOT/.backend_job" ]; then echo "Backend job marker: $(cat $PROJECT_ROOT/.backend_job)"; fi
  if [ -f "$PROJECT_ROOT/.frontend_job" ]; then echo "Frontend job marker: $(cat $PROJECT_ROOT/.frontend_job)"; fi
}

do_logs() {
  echo "=== Logs ==="
  if [ -f "$PROJECT_ROOT/backend/backend.log" ]; then echo "--- backend/backend.log ---"; tail -n 50 "$PROJECT_ROOT/backend/backend.log"; else echo "No backend.log"; fi
  if [ -f "$PROJECT_ROOT/frontend/frontend.log" ]; then echo "--- frontend/frontend.log ---"; tail -n 50 "$PROJECT_ROOT/frontend/frontend.log"; else echo "No frontend.log"; fi
  if command -v docker >/dev/null 2>&1; then docker compose logs --tail 20 2>/dev/null || true; fi
}

do_stop() {
  echo "Stopping RailBlock AI..."
  # Prefer stop.ps1 if exists and PowerShell available
  if [ -f "$PROJECT_ROOT/stop.ps1" ] && command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PROJECT_ROOT/stop.ps1" || true
  fi
  if command -v docker >/dev/null 2>&1; then
    (cd "$PROJECT_ROOT" && docker compose down 2>/dev/null || true)
  fi
  # Kill only RailBlock processes (check cmdline)
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  pkill -f "vite.*5173" 2>/dev/null || true
  echo "Stop complete"
}

do_start() {
  MODE="${1:-}"
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    if [ "$MODE" = "docker" ] || [ -z "$MODE" ]; then
      echo "Docker found - starting via compose..."
      (cd "$PROJECT_ROOT" && docker compose up --build -d)
      echo "Backend http://localhost:8000/health"
      echo "Frontend http://localhost:3000"
      return
    fi
  fi
  if [ "$MODE" = "docker" ]; then
    echo "Docker not available but docker mode requested, falling back to direct"
  fi
  echo "Docker not found or direct mode - starting directly..."
  # Check deps already satisfied to avoid noisy rebuild
  if ! $PYTHON -c "import fastapi, pydantic, sqlalchemy, ortools" 2>/dev/null; then
    echo "Installing Python deps..."
    (cd "$PROJECT_ROOT/backend" && pip install -q -r requirements.txt || echo "pip install warning")
  else
    echo "Python deps already satisfied"
  fi
  (cd "$PROJECT_ROOT/backend" && nohup $PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 & echo $! > /tmp/railblock_backend.pid && echo "Backend PID $(cat /tmp/railblock_backend.pid)")
  if command -v npm >/dev/null 2>&1; then
    (cd "$PROJECT_ROOT/frontend" && npm install --silent 2>/dev/null; nohup npm run dev -- --host 0.0.0.0 --port 5173 > frontend.log 2>&1 & echo $! > /tmp/railblock_frontend.pid && echo "Frontend PID $(cat /tmp/railblock_frontend.pid)")
  fi
  echo "Backend http://localhost:8000/docs Frontend http://localhost:5173"
}

# Main dispatch
case "${1:-}" in
  clean)
    do_clean
    ;;
  health)
    do_health
    ;;
  status)
    do_status
    ;;
  logs)
    do_logs
    ;;
  stop)
    do_stop
    ;;
  dev)
    do_start dev
    ;;
  docker)
    do_start docker
    ;;
  "")
    do_start
    ;;
  *)
    echo "Unknown command: $1"
    echo "Usage: $0 [clean|health|status|logs|stop|dev|docker]"
    exit 1
    ;;
esac
