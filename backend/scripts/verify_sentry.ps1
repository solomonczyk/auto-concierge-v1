# Sentry verification script (Windows)
# Prerequisites: backend running with SENTRY_DSN in .env
# 1. Login, 2. Call _sentry-test, 3. Check Sentry dashboard for event, tenant_id, no sensitive data

$base = "http://localhost:8000"
$loginUrl = "$base/api/v1/login/access-token"
$testUrl = "$base/api/v1/_sentry-test"

Write-Host "1. Login..."
$loginRes = Invoke-WebRequest -Uri $loginUrl -Method POST -Body @{username="admin"; password="admin"} -ContentType "application/x-www-form-urlencoded" -SessionVariable session -UseBasicParsing
$token = $session.Cookies.GetCookies($loginUrl) | Where-Object { $_.Name -eq "access_token" } | Select-Object -ExpandProperty Value
if (-not $token) { Write-Host "Login failed. Ensure backend is running and admin user exists."; exit 1 }

Write-Host "2. Call GET /api/v1/_sentry-test (expect 500)..."
try {
    $testRes = Invoke-WebRequest -Uri $testUrl -Headers @{Authorization="Bearer $token"} -WebSession $session -UseBasicParsing
} catch {
    if ($_.Exception.Response.StatusCode -eq 500) {
        Write-Host "OK: Endpoint returned 500 (ValueError). Event should be in Sentry."
        Write-Host "3. Check Sentry: event present, tenant_id tag, no sensitive data."
    } elseif ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "Endpoint returns 404 (disabled in production or SENTRY_DSN not set)."
    } else { throw }
}
