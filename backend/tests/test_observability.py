"""
Stage 3: Observability tests.

- request_id generated and returned in response
- incoming X-Request-ID propagated
- error path logged
- /metrics contains key metrics
"""
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_response_has_x_request_id(client: AsyncClient):
    """Response includes X-Request-ID header (generated or propagated)."""
    res = await client.get("/")
    assert res.status_code == 200
    assert "X-Request-ID" in res.headers
    rid = res.headers["X-Request-ID"]
    assert rid and len(rid) >= 8


@pytest.mark.asyncio
async def test_incoming_x_request_id_propagated(client: AsyncClient):
    """When client sends X-Request-ID, same value is returned in response."""
    incoming_rid = "abc123def456"
    res = await client.get("/", headers={"X-Request-ID": incoming_rid})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == incoming_rid


@pytest.mark.asyncio
async def test_error_path_logged(client: AsyncClient):
    """Unhandled exception is logged with request_id and stack trace."""
    with patch("app.main.logger") as mock_logger:
        with patch("app.main.tenant_context_middleware", side_effect=RuntimeError("test error")):
            # We need to trigger an error. Patching tenant_context would affect all requests.
            # Instead, create an endpoint that raises, or patch something in the request path.
            pass

    # Simpler: call an endpoint that we can make raise. We'll patch a dependency.
    from app.main import tenant_context_middleware
    original_next = None

    async def failing_next(request):
        raise RuntimeError("observability test error")

    with patch.object(app.router, "routes", []):
        pass

    # Use a dedicated test: GET /nonexistent-route-for-500 - no, that returns 404.
    # Create a test route that raises, or use a different approach.
    # We can add a test-only route, or we can verify the exception handler logs.
    # Simpler: just verify that when we get a 500 from somewhere, the handler logs.
    # We could add a ?raise=1 to an endpoint for testing - but that's invasive.
    # Alternative: verify the global_exception_handler code path by mocking.
    # The test says "error path logged" - we can patch something to raise, then
    # verify logger.exception was called.
    from fastapi import Request
    from starlette.datastructures import Headers

    async def fake_call_next(req):
        raise RuntimeError("test observability error")

    # Build a minimal request with request_id
    scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
    request = Request(scope)
    request.state.request_id = "test-rid-123"

    with patch("app.main.logger") as mock_log:
        from app.main import global_exception_handler
        response = await global_exception_handler(request, RuntimeError("test"))
        assert response.status_code == 500
        mock_log.exception.assert_called_once()
        call_kw = mock_log.exception.call_args[1]
        assert call_kw.get("extra", {}).get("request_id") == "test-rid-123"


@pytest.mark.asyncio
async def test_metrics_contains_key_metrics(client: AsyncClient):
    """GET /metrics returns Prometheus format with key metrics."""
    res = await client.get("/metrics")
    assert res.status_code == 200
    text = res.text
    assert "http_request_duration_seconds" in text or "http_request_duration_seconds_bucket" in text
    assert "http_requests_total" in text
    assert "http_errors_total" in text
    assert "webhook_requests_total" in text
    assert "webhook_rejected_total" in text
    assert "ws_connections_total" in text
    assert "ws_auth_rejected_total" in text
    assert "appointment_status_transitions_total" in text
    assert "ws_active_connections" in text
