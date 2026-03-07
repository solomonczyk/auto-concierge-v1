"""
Focused tests for NotificationService.dispatch() routing.
Mocks internal methods (not Telegram API). Verifies routing logic.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.notification_service import NotificationService


@pytest.fixture
def mock_internal_methods():
    """Mock all internal notification methods to avoid Telegram calls."""
    with patch.object(
        NotificationService, "notify_client_status_change", new_callable=AsyncMock
    ) as mock_client_status, patch.object(
        NotificationService, "send_raw_message", new_callable=AsyncMock
    ) as mock_raw, patch.object(
        NotificationService, "notify_admin", new_callable=AsyncMock
    ) as mock_admin, patch.object(
        NotificationService, "send_booking_confirmation", new_callable=AsyncMock
    ) as mock_booking:
        yield {
            "notify_client_status_change": mock_client_status,
            "send_raw_message": mock_raw,
            "notify_admin": mock_admin,
            "send_booking_confirmation": mock_booking,
        }


@pytest.mark.asyncio
async def test_appointment_confirmed_routes_to_client(mock_internal_methods):
    """appointment_confirmed + client_telegram_id → notify_client_status_change called."""
    mocks = mock_internal_methods
    await NotificationService.dispatch(
        event_type="appointment_confirmed",
        appointment_id=1,
        tenant_id=1,
        recipient_ids={"client_telegram_id": 12345},
        context={"service_name": "Диагностика"},
    )
    mocks["notify_client_status_change"].assert_called_once_with(
        chat_id=12345,
        service_name="Диагностика",
        new_status="confirmed",
    )
    mocks["send_raw_message"].assert_not_called()
    mocks["notify_admin"].assert_not_called()
    mocks["send_booking_confirmation"].assert_not_called()


@pytest.mark.asyncio
async def test_appointment_cancelled_routes_to_client(mock_internal_methods):
    """appointment_cancelled + client_telegram_id → notify_client_status_change called."""
    mocks = mock_internal_methods
    await NotificationService.dispatch(
        event_type="appointment_cancelled",
        appointment_id=2,
        tenant_id=1,
        recipient_ids={"client_telegram_id": 67890},
        context={"service_name": "Замена масла"},
    )
    mocks["notify_client_status_change"].assert_called_once_with(
        chat_id=67890,
        service_name="Замена масла",
        new_status="cancelled",
    )
    mocks["send_raw_message"].assert_not_called()
    mocks["notify_admin"].assert_not_called()
    mocks["send_booking_confirmation"].assert_not_called()


@pytest.mark.asyncio
async def test_appointment_no_show_routes_to_manager_only(mock_internal_methods):
    """appointment_no_show + manager_chat_id → send_raw_message to manager, NOT to client."""
    mocks = mock_internal_methods
    await NotificationService.dispatch(
        event_type="appointment_no_show",
        appointment_id=3,
        tenant_id=1,
        recipient_ids={
            "client_telegram_id": 11111,
            "manager_chat_id": 99999,
        },
        context={"service_name": "Шиномонтаж"},
    )
    mocks["send_raw_message"].assert_called_once()
    call_args = mocks["send_raw_message"].call_args
    assert call_args[0][0] == 99999
    assert "Клиент не явился" in call_args[0][1]
    mocks["notify_client_status_change"].assert_not_called()
    mocks["send_booking_confirmation"].assert_not_called()


@pytest.mark.asyncio
async def test_appointment_no_show_does_not_send_to_client(mock_internal_methods):
    """appointment_no_show: client_telegram_id present but client must NOT receive notification."""
    mocks = mock_internal_methods
    await NotificationService.dispatch(
        event_type="appointment_no_show",
        appointment_id=4,
        tenant_id=1,
        recipient_ids={
            "client_telegram_id": 22222,
            "manager_chat_id": 88888,
        },
        context={"service_name": "Услуга"},
    )
    mocks["notify_client_status_change"].assert_not_called()
    mocks["send_booking_confirmation"].assert_not_called()
    mocks["send_raw_message"].assert_called_once()
    call_args = mocks["send_raw_message"].call_args
    assert call_args[0][0] == 88888
    assert "Клиент не явился" in call_args[0][1]


@pytest.mark.asyncio
async def test_appointment_created_both_routes_when_not_waitlist(mock_internal_methods):
    """appointment_created + recipient_roles=[client,manager] + is_waitlist=False → both routes."""
    mocks = mock_internal_methods
    await NotificationService.dispatch(
        event_type="appointment_created",
        appointment_id=5,
        tenant_id=1,
        recipient_roles=["client", "manager"],
        recipient_ids={
            "client_telegram_id": 33333,
            "manager_chat_id": 77777,
        },
        context={
            "service_name": "ТО",
            "slot_time": "10.03.2025 14:00",
            "is_waitlist": False,
            "client_name": "Иван",
        },
    )
    mocks["send_booking_confirmation"].assert_called_once()
    call = mocks["send_booking_confirmation"].call_args
    assert call[0][0] == 33333
    assert "Запись подтверждена" in call[0][1]
    mocks["send_raw_message"].assert_called_once()
    call_raw = mocks["send_raw_message"].call_args
    assert call_raw[0][0] == 77777
    assert "Новая запись" in call_raw[0][1]
    mocks["notify_client_status_change"].assert_not_called()
