@echo off
echo === RailBlock AI - Easy Start ===
echo Prototype disclaimer: Synthetic demo data only. Not for real railway operations.
echo.
echo Step 1: Resetting demo data...
python scripts\reset_demo.py
if %errorlevel% neq 0 (
  echo Reset failed, trying with --force...
  python scripts\reset_demo.py --force
)
echo.
echo Step 2: Starting backend and frontend...
echo This will open two new windows. Keep them open.
echo Backend: http://localhost:8000/health
echo Frontend: http://localhost:5173
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
