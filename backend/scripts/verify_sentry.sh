#!/bin/bash
# Manual Sentry verification: call _sentry-test with JWT.
# Prereqs: backend running, SENTRY_DSN in .env, valid admin credentials.
set -e
BASE="${BASE_URL:-http://localhost:8000}"
TOKEN=$(curl -s -X POST "$BASE/api/v1/login/access-token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin" | python -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")
[ -z "$TOKEN" ] && { echo "Login failed"; exit 1; }
echo "Calling GET $BASE/api/v1/_sentry-test ..."
curl -s -w "\nHTTP %{http_code}\n" -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/_sentry-test" || true
echo "Check Sentry: event appeared, tenant_id tag present, no sensitive data."
