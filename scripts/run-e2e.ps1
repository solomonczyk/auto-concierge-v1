# E2E: проверка backend + frontend + Playwright
# Использование: .\scripts\run-e2e.ps1
# Требуется: Docker Desktop запущен (для backend) или backend уже слушает :8000

$ErrorActionPreference = "Stop"

Write-Host "=== E2E: WebApp, Dashboard, Bot webhook ===" -ForegroundColor Cyan

# Проверка backend
try {
    $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "[OK] Backend на :8000" -ForegroundColor Green
} catch {
    Write-Host "[?] Backend не отвечает на :8000" -ForegroundColor Yellow
    Write-Host "    Запустите: docker-compose up -d" -ForegroundColor Gray
    Write-Host "    или: cd backend && uvicorn app.main:app --reload" -ForegroundColor Gray
    $cont = Read-Host "Продолжить E2E без backend? (y/N)"
    if ($cont -ne "y") { exit 1 }
}

# Проверка frontend
try {
    $r = Invoke-WebRequest -Uri "http://localhost:5173/concierge/" -UseBasicParsing -TimeoutSec 3
    Write-Host "[OK] Frontend на :5173" -ForegroundColor Green
} catch {
    Write-Host "[!] Frontend не запущен. Запускаю npm run dev..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd $PSScriptRoot\..\frontend; npm run dev" -WindowStyle Normal
    Start-Sleep -Seconds 15
}

Set-Location $PSScriptRoot\..\frontend
Write-Host "`nЗапуск Playwright E2E..." -ForegroundColor Cyan
npx playwright test --reporter=list
