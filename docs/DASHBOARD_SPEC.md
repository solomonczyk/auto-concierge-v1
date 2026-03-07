# Grafana / Prometheus Dashboard Spec

## Data source

- **Prometheus** scraping `/metrics` from autoservice-api (default port 8000)
- Scrape interval: 15s recommended

## Panels

### 1. Request latency (p50, p95, p99)

**Metric:** `http_request_duration_seconds`

**Queries:**
- p50: `histogram_quantile(0.5, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))`
- p95: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))`
- p99: `histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))`

**Visualization:** Time series (line chart)

---

### 2. 5xx error rate

**Metric:** `http_errors_total`

**Query:** `sum(rate(http_errors_total[5m])) by (method, path)`

**Visualization:** Time series or stat

---

### 3. Webhook errors

**Metric:** `webhook_rejected_total`

**Query:** `sum(rate(webhook_rejected_total[5m])) by (reason)`

**Visualization:** Time series, stacked area

---

### 4. WS active connections

**Metric:** `ws_active_connections`

**Query:** `sum(ws_active_connections) by (tenant_id)` or `sum(ws_active_connections)`

**Visualization:** Stat or gauge

---

### 5. Appointments status transitions

**Metric:** `appointment_status_transitions_total`

**Query:** `sum(rate(appointment_status_transitions_total[5m])) by (old_status, new_status)`

**Visualization:** Time series or table

---

### 6. Readiness / health trends

**Metric:** Custom probe or `up` for the service

**Query:** `up{job="autoservice-api"}` — 1 = healthy, 0 = down

**Alternative:** Scrape `/ready` via blackbox exporter, or use `probe_success` if configured.

**Visualization:** Stat (single value) or time series

---

### 7. HTTP request count (optional)

**Metric:** `http_requests_total`

**Query:** `sum(rate(http_requests_total[5m])) by (path, status)`

**Visualization:** Time series

---

## Dashboard JSON (minimal)

```json
{
  "title": "Autoservice API",
  "panels": [
    {
      "title": "Request Latency p95",
      "targets": [{
        "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, path))"
      }]
    },
    {
      "title": "5xx Error Rate",
      "targets": [{
        "expr": "sum(rate(http_errors_total[5m]))"
      }]
    },
    {
      "title": "Webhook Rejected",
      "targets": [{
        "expr": "sum(rate(webhook_rejected_total[5m])) by (reason)"
      }]
    },
    {
      "title": "WS Active Connections",
      "targets": [{
        "expr": "sum(ws_active_connections)"
      }]
    },
    {
      "title": "Appointment Status Transitions",
      "targets": [{
        "expr": "sum(rate(appointment_status_transitions_total[5m])) by (new_status)"
      }]
    }
  ]
}
```

## Prometheus scrape config example

```yaml
scrape_configs:
  - job_name: 'autoservice-api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```
