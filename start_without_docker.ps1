# Alternative simple startup without Jobs (foreground)
Write-Host "Starting RailBlock AI without Docker..."

# Backend
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\backend"
Start-Process -FilePath "python" -ArgumentList "-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000" -WindowStyle Normal

Start-Sleep -Seconds 4

# Frontend
Set-Location -LiteralPath "D:\PROJECT2\MAYBE\RAIL\frontend"
if (-not (Test-Path "node_modules")) { npm install }
Start-Process -FilePath "npm" -ArgumentList "run","dev","--","--host","0.0.0.0","--port","5173" -WindowStyle Normal

Write-Host "Backend http://localhost:8000/health"
Write-Host "Frontend http://localhost:5173"
