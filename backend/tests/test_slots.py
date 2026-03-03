import pytest
from datetime import date, datetime, time, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from app.core.slots import get_available_slots, WORK_START, WORK_END
from app.models.models import Appointment

@pytest.mark.asyncio
async def test_get_available_slots_empty_day():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = []
    db.execute.return_value = mock_result

    shop_id = 1
    duration = 60
    target_date = date(2026, 2, 20)

    slots = await get_available_slots(shop_id, duration, target_date, db)

    assert len(slots) > 0
    # slots are UTC-aware
    expected_start = datetime.combine(target_date, WORK_START).replace(tzinfo=timezone.utc)
    expected_end = datetime.combine(target_date, WORK_END).replace(tzinfo=timezone.utc) - timedelta(minutes=duration)
    assert slots[0] == expected_start
    assert slots[-1] == expected_end

@pytest.mark.asyncio
async def test_get_available_slots_with_appointment():
    # Mock DB session
    db = AsyncMock()
    
    target_date = date(2026, 2, 20)
    shop_id = 1
    
    # Existing appointment: 10:00 - 11:00 (UTC-aware for slot comparison)
    utc = timezone.utc
    appt = Appointment(
        shop_id=shop_id,
        start_time=datetime.combine(target_date, time(10, 0)).replace(tzinfo=utc),
        end_time=datetime.combine(target_date, time(11, 0)).replace(tzinfo=utc),
        status='confirmed'
    )
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [appt]
    db.execute.return_value = mock_result
    
    duration = 60
    slots = await get_available_slots(shop_id, duration, target_date, db)
    
    utc = timezone.utc
    def _t(h, m):
        return datetime.combine(target_date, time(h, m)).replace(tzinfo=utc)
    assert _t(9, 0) in slots
    assert _t(9, 30) not in slots
    assert _t(10, 0) not in slots
    assert _t(10, 30) not in slots
    assert _t(11, 0) in slots

@pytest.mark.asyncio
async def test_get_available_slots_full_day_blocked():
    db = AsyncMock()
    target_date = date(2026, 2, 20)
    utc = timezone.utc
    appt = Appointment(
        shop_id=1,
        start_time=datetime.combine(target_date, WORK_START).replace(tzinfo=utc),
        end_time=datetime.combine(target_date, WORK_END).replace(tzinfo=utc),
        status='confirmed'
    )
    
    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [appt]
    db.execute.return_value = mock_result
    
    slots = await get_available_slots(1, 60, target_date, db)
    assert len(slots) == 0
