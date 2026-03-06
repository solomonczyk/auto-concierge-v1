from app.services.ws_ticket_service import create_ws_ticket, validate_ws_ticket


def test_ws_ticket_create_and_validate_roundtrip():
    ticket = create_ws_ticket(
        user_id=101,
        tenant_id=202,
        role="admin",
    )

    assert isinstance(ticket, str)
    assert ticket

    claims = validate_ws_ticket(ticket=ticket)

    assert claims["type"] == "ws_ticket"
    assert claims["user_id"] == 101
    assert claims["tenant_id"] == 202
    assert claims["role"] == "admin"
    assert "jti" in claims and isinstance(claims["jti"], str) and claims["jti"]
    assert "exp" in claims
