"""Centralized Prometheus metrics for the application.

All counters / histograms / gauges are defined here so that every module
imports from one place and metric names stay consistent.
"""

from prometheus_client import Counter, Histogram, Gauge

# ---------------------------------------------------------------------------
# WebSocket / realtime
# ---------------------------------------------------------------------------
WS_CONNECTIONS_TOTAL = Counter(
    "ws_connections_total",
    "Total accepted WebSocket connections",
    ["tenant_id"],
)
WS_DISCONNECT_TOTAL = Counter(
    "ws_disconnect_total",
    "Total WebSocket disconnections",
    ["tenant_id"],
)
WS_AUTH_REJECTED_TOTAL = Counter(
    "ws_auth_rejected_total",
    "WS connections rejected during auth",
    ["reason"],  # no_ticket | invalid_ticket | replay
)

# ---------------------------------------------------------------------------
# WS ticket
# ---------------------------------------------------------------------------
WS_TICKET_ISSUED_TOTAL = Counter(
    "ws_ticket_issued_total",
    "WS tickets successfully issued",
    ["tenant_id"],
)
WS_TICKET_REJECTED_TOTAL = Counter(
    "ws_ticket_rejected_total",
    "WS ticket issuance rejected (403 / other)",
    ["reason"],
)

# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------
APPOINTMENTS_CREATED_TOTAL = Counter(
    "appointments_created_total",
    "Appointments successfully created",
    ["tenant_id", "source"],  # source: dashboard | public
)
APPOINTMENTS_CREATION_FAILED_TOTAL = Counter(
    "appointments_creation_failed_total",
    "Appointment creation failures",
    ["tenant_id", "reason"],
)
APPOINTMENTS_EXTERNAL_SYNC_FAILED_TOTAL = Counter(
    "appointments_external_sync_failed_total",
    "External integration sync enqueue failures",
    ["tenant_id"],
)

# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------
WEBHOOK_REQUESTS_TOTAL = Counter(
    "webhook_requests_total",
    "Total incoming webhook requests",
)
WEBHOOK_REJECTED_TOTAL = Counter(
    "webhook_rejected_total",
    "Webhook requests rejected (secret / rate limit / 503)",
    ["reason"],
)
WEBHOOK_PROCESSED_TOTAL = Counter(
    "webhook_processed_total",
    "Webhook updates successfully processed",
)

# ---------------------------------------------------------------------------
# HTTP requests
# ---------------------------------------------------------------------------
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path", "status"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)
HTTP_ERROR_TOTAL = Counter(
    "http_errors_total",
    "HTTP 5xx errors",
    ["method", "path"],
)

# ---------------------------------------------------------------------------
# Outbox
# ---------------------------------------------------------------------------
OUTBOX_EVENTS_PROCESSED_TOTAL = Counter(
    "outbox_events_processed_total",
    "Outbox events successfully processed",
)
OUTBOX_EVENTS_FAILED_TOTAL = Counter(
    "outbox_events_failed_total",
    "Outbox events permanently failed (max attempts reached)",
)

# ---------------------------------------------------------------------------
# Appointment status transitions
# ---------------------------------------------------------------------------
APPOINTMENT_STATUS_TRANSITIONS_TOTAL = Counter(
    "appointment_status_transitions_total",
    "Appointment status changes (PATCH / create)",
    ["tenant_id", "old_status", "new_status"],
)

# ---------------------------------------------------------------------------
# WS active connections (gauge)
# ---------------------------------------------------------------------------
WS_ACTIVE_CONNECTIONS = Gauge(
    "ws_active_connections",
    "Current active WebSocket connections",
    ["tenant_id"],
)
