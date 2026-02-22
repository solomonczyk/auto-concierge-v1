"""
Telegram bot handlers.
Main entry point for bot commands and callbacks.
"""

import json
import logging
from datetime import datetime, timedelta, timezone as tz
from typing import Optional

from aiogram import Router, F, html
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from app.db.session import async_session_local
from app.models.models import Client, Appointment, Service, AppointmentStatus, Shop
from app.bot.keyboards import get_main_keyboard, get_appointment_keyboard
from app.bot.messages import (
    _welcome_msg, _contact_linked_msg, _contact_new_msg,
    _appointment_card, _booking_confirmed_msg, _waitlist_msg,
    _main_menu_msg, _no_appointments_msg, _appointments_header,
    _need_https_msg, _phone_required_msg, _appointment_cancelled_msg,
    _appointment_not_found_msg, _service_not_found_msg,
    _invalid_webapp_data_msg, _original_appointment_not_found_msg,
    _slot_unavailable_msg, _shop_not_configured_msg,
    _waitlist_submitted_msg, _booking_created_msg, _booking_edited_msg
)
from app.bot.tenant import get_or_create_tenant, get_tenant_shop
from app.core.slots import get_available_slots
from app.services.redis_service import RedisService
from app.core.config import settings
from app.services.ai_core import ai_core, DiagnosticResult

logger = logging.getLogger(__name__)
router = Router()


# ──────────────────────────────────────────────
#  Command Handlers
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """Handle /start command - show welcome message."""
    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)
        
        # Check if user is already registered
        stmt = select(Client).where(
            and_(Client.telegram_id == message.from_user.id, Client.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if client:
            await message.answer(
                _welcome_msg(client.full_name, returning=True),
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer(
                _welcome_msg(message.from_user.full_name, returning=False),
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )


@router.message(F.contact)
async def contact_handler(message: Message) -> None:
    """Handle phone number contact sharing."""
    contact = message.contact
    phone = contact.phone_number.replace("+", "")

    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)
        
        # Check if client with this phone already exists
        stmt = select(Client).where(
            and_(Client.phone == phone, Client.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if client:
            # Link existing client to Telegram
            client.telegram_id = message.from_user.id
            await db.commit()
            await message.answer(
                _contact_linked_msg(client.full_name, phone),
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )
        else:
            # Create new client
            new_client = Client(
                tenant_id=tenant.id,
                full_name=message.from_user.full_name,
                phone=phone,
                telegram_id=message.from_user.id
            )
            db.add(new_client)
            await db.commit()
            await message.answer(
                _contact_new_msg(),
                parse_mode="HTML",
                reply_markup=get_main_keyboard()
            )


@router.message(F.text == "🔧 Записаться (⚠️ нужен HTTPS)")
async def need_https_handler(message: Message) -> None:
    """Handle booking button - explain HTTPS requirement."""
    await message.answer(
        _need_https_msg(),
        parse_mode="HTML"
    )


@router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message) -> None:
    """Handle 'My Appointments' button - show user's appointments."""
    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)
        
        # Find client by Telegram ID
        stmt = select(Client).where(
            and_(Client.telegram_id == message.from_user.id, Client.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            await message.answer(_phone_required_msg(), parse_mode="HTML")
            return

        # Get appointments
        stmt = select(Appointment).options(
            joinedload(Appointment.service)
        ).where(
            and_(
                Appointment.client_id == client.id,
                Appointment.status != AppointmentStatus.CANCELLED
            )
        ).order_by(Appointment.start_time.desc())

        result = await db.execute(stmt)
        appointments = result.scalars().all()

        if not appointments:
            await message.answer(_no_appointments_msg(), parse_mode="HTML")
            return

        # Send header
        await message.answer(
            _appointments_header(len(appointments)),
            parse_mode="HTML"
        )

        # Send each appointment as a card
        for appt in appointments:
            text = _appointment_card(appt)
            keyboard = get_appointment_keyboard(appt.id)
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ──────────────────────────────────────────────
#  Callback Query Handlers
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_appt:"))
async def cancel_appointment_handler(callback_query: Message) -> None:
    """Handle appointment cancellation."""
    appt_id = int(callback_query.data.split(":")[1])
    
    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)
        
        # Get appointment with tenant isolation
        stmt = select(Appointment).where(
            and_(Appointment.id == appt_id, Appointment.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        appt = result.scalar_one_or_none()
        
        if appt:
            appt.status = AppointmentStatus.CANCELLED
            await db.commit()
            
            await callback_query.message.edit_text(
                _appointment_cancelled_msg(appt_id),
                parse_mode="HTML"
            )

            # Broadcast update to dashboard
            redis = RedisService.get_redis()
            msg = {
                "type": "STATUS_UPDATE",
                "data": {
                    "id": appt.id,
                    "shop_id": appt.shop_id,
                    "status": "cancelled"
                }
            }
            await redis.publish("appointments_updates", json.dumps(msg))
        else:
            await callback_query.answer(_appointment_not_found_msg())


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback_query: Message) -> None:
    """Handle back to menu button."""
    await callback_query.message.answer(
        _main_menu_msg(),
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await callback_query.answer()


# ──────────────────────────────────────────────
#  Web App Data Handler
# ──────────────────────────────────────────────

@router.message(F.web_app_data)
async def web_app_data_handler(message: Message) -> None:
    """Handle data received from Telegram Web App."""
    try:
        data = json.loads(message.web_app_data.data)
        service_id = data.get("service_id")
        date_str = data.get("date")
        appointment_id = data.get("appointment_id")
        is_waitlist = data.get("is_waitlist", False)

        if not service_id or not date_str:
            await message.answer(_invalid_webapp_data_msg(), parse_mode="HTML")
            return

        start_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        start_time_naive = start_time.replace(tzinfo=None)

        async with async_session_local() as db:
            tenant = await get_or_create_tenant(db)
            
            # Get service
            stmt = select(Service).where(
                and_(Service.id == service_id, Service.tenant_id == tenant.id)
            )
            result = await db.execute(stmt)
            service = result.scalar_one_or_none()
            
            if not service:
                await message.answer(_service_not_found_msg(), parse_mode="HTML")
                return

            # Check for existing appointment if rescheduling
            existing_appt = None
            if appointment_id:
                stmt = select(Appointment).where(
                    and_(Appointment.id == int(appointment_id), Appointment.tenant_id == tenant.id)
                )
                result = await db.execute(stmt)
                existing_appt = result.scalar_one_or_none()
                
                if not existing_appt:
                    await message.answer(_original_appointment_not_found_msg(), parse_mode="HTML")
                    return

            if not is_waitlist:
                # Check slot availability
                available_slots = await get_available_slots(
                    shop_id=1,  # Default shop for MVP
                    service_duration_minutes=service.duration_minutes,
                    date=start_time_naive.date(),
                    db=db,
                    exclude_appointment_id=int(appointment_id) if appointment_id else None
                )

                if not any(slot == start_time_naive for slot in available_slots):
                    await message.answer(_slot_unavailable_msg(), parse_mode="HTML")
                    return

            # Get or create client
            if not appointment_id:
                stmt = select(Client).where(
                    and_(Client.telegram_id == message.from_user.id, Client.tenant_id == tenant.id)
                )
                result = await db.execute(stmt)
                client = result.scalar_one_or_none()

                if not client:
                    client = Client(
                        tenant_id=tenant.id,
                        telegram_id=message.from_user.id,
                        full_name=message.from_user.full_name,
                        phone="unknown"
                    )
                    db.add(client)
                    await db.flush()
            else:
                client = await db.get(Client, existing_appt.client_id)

            end_time = start_time_naive + timedelta(minutes=service.duration_minutes)

            # Mark as UTC-aware so asyncpg doesn't convert from local timezone
            start_time_utc = start_time_naive.replace(tzinfo=tz.utc)
            end_time_utc = end_time.replace(tzinfo=tz.utc)

            status = AppointmentStatus.WAITLIST if is_waitlist else (
                AppointmentStatus.CONFIRMED if appointment_id else AppointmentStatus.NEW
            )

            # Get shop for tenant
            shop = await get_tenant_shop(db, tenant)
            if not shop:
                await message.answer(_shop_not_configured_msg())
                return

            if appointment_id:
                # Update existing appointment
                existing_appt.service_id = service_id
                existing_appt.start_time = start_time_utc
                existing_appt.end_time = end_time_utc
                existing_appt.status = status
                appt = existing_appt
            else:
                # Create new appointment
                new_appt = Appointment(
                    tenant_id=tenant.id,
                    shop_id=shop.id,
                    client_id=client.id,
                    service_id=service_id,
                    start_time=start_time_utc,
                    end_time=end_time_utc,
                    status=status
                )
                db.add(new_appt)
                appt = new_appt

            await db.commit()
            await db.refresh(appt)

            # Send confirmation message
            if is_waitlist:
                msg = _waitlist_msg(
                    service.name,
                    start_time_naive.strftime('%d.%m.%Y')
                )
            else:
                msg = _booking_confirmed_msg(
                    service.name,
                    start_time_naive.strftime('%d.%m.%Y  %H:%M'),
                    is_edit=bool(appointment_id)
                )

            await message.answer(msg, parse_mode="HTML")

            # Broadcast update
            try:
                redis = RedisService.get_redis()
                event_type = "WAITLIST_ADD" if is_waitlist else (
                    "APPOINTMENT_UPDATED" if appointment_id else "NEW_APPOINTMENT"
                )
                broadcast_message = {
                    "type": event_type,
                    "data": {
                        "id": appt.id,
                        "shop_id": appt.shop_id,
                        "start_time": appt.start_time.isoformat(),
                        "status": appt.status.value
                    }
                }
                await redis.publish("appointments_updates", json.dumps(broadcast_message))
            except Exception as e:
                logger.error(f"Failed to publish update: {e}")

    except json.JSONDecodeError:
        await message.answer(_invalid_webapp_data_msg(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error processing web app data: {e}")
        await message.answer(_invalid_webapp_data_msg(), parse_mode="HTML")
