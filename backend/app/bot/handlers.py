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
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

from app.db.session import async_session_local
from app.models.models import Client, Appointment, Service, AppointmentStatus, Shop
from app.bot.keyboards import (
    get_main_keyboard,
    get_appointment_keyboard,
    get_consultation_keyboard,
    get_consultation_result_keyboard,
    get_service_suggestion_keyboard,
)
from app.bot.messages import (
    _welcome_msg, _contact_linked_msg, _contact_new_msg,
    _appointment_card, _booking_confirmed_msg, _waitlist_msg,
    _main_menu_msg, _no_appointments_msg, _appointments_header,
    _need_https_msg, _phone_required_msg, _appointment_cancelled_msg,
    _appointment_not_found_msg, _service_not_found_msg,
    _invalid_webapp_data_msg, _original_appointment_not_found_msg,
    _slot_unavailable_msg, _shop_not_configured_msg,
    _waitlist_submitted_msg, _booking_created_msg, _booking_edited_msg,
    # New
    _consultation_start_msg, _diagnostic_result_msg, _consultation_ai_reply_msg,
    _consultation_error_msg, _legal_info_msg, _unknown_text_msg,
    _admin_new_booking_msg, _admin_cancelled_msg,
)
from app.bot.states import ConsultForm
from app.bot.tenant import get_or_create_tenant, get_tenant_shop
from app.core.slots import get_available_slots
from app.services.redis_service import RedisService
from app.core.config import settings
from app.services.ai_core import ai_core, DiagnosticResult
from app.services.ai_service import ai_service

logger = logging.getLogger(__name__)
router = Router()


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

async def _notify_admin(text: str) -> None:
    """Send a message to the admin chat if ADMIN_CHAT_ID is configured."""
    if not settings.ADMIN_CHAT_ID:
        return
    try:
        from app.bot.loader import bot
        if bot:
            await bot.send_message(
                chat_id=settings.ADMIN_CHAT_ID,
                text=text,
                parse_mode="HTML",
            )
    except Exception as e:
        logger.warning(f"Admin notification failed: {e}")


# ──────────────────────────────────────────────
#  Command Handlers
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Handle /start command - show welcome message."""
    # Clear any lingering FSM state
    await state.clear()

    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)

        stmt = select(Client).where(
            and_(Client.telegram_id == message.from_user.id, Client.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if client:
            await message.answer(
                _welcome_msg(client.full_name, returning=True),
                parse_mode="HTML",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
        else:
            await message.answer(
                _welcome_msg(message.from_user.full_name, returning=False),
                parse_mode="HTML",
                reply_markup=get_main_keyboard(message.from_user.id)
            )


# ──────────────────────────────────────────────
#  Contact / Registration
# ──────────────────────────────────────────────

@router.message(F.contact)
async def contact_handler(message: Message) -> None:
    """Handle phone number contact sharing."""
    contact = message.contact
    phone = contact.phone_number.replace("+", "")

    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)

        stmt = select(Client).where(
            and_(Client.phone == phone, Client.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if client:
            client.telegram_id = message.from_user.id
            await db.commit()
            await message.answer(
                _contact_linked_msg(client.full_name, phone),
                parse_mode="HTML",
                reply_markup=get_main_keyboard(message.from_user.id)
            )
        else:
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
                reply_markup=get_main_keyboard(message.from_user.id)
            )


# ──────────────────────────────────────────────
#  Static Button Handlers
# ──────────────────────────────────────────────

@router.message(F.text == "🔧 Записаться (⚠️ нужен HTTPS)")
async def need_https_handler(message: Message) -> None:
    """Handle booking button when HTTPS not configured."""
    await message.answer(_need_https_msg(), parse_mode="HTML")


@router.message(F.text == "📄 Правовая информация")
async def legal_info_handler(message: Message) -> None:
    """Show legal / privacy policy information."""
    await message.answer(
        _legal_info_msg(),
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# ──────────────────────────────────────────────
#  My Appointments
# ──────────────────────────────────────────────

@router.message(F.text == "📋 Мои записи")
async def my_appointments(message: Message) -> None:
    """Show user's active appointments."""
    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)

        stmt = select(Client).where(
            and_(Client.telegram_id == message.from_user.id, Client.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()

        if not client:
            await message.answer(_phone_required_msg(), parse_mode="HTML")
            return

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
            logger.info(f"No appointments found for client {client.id}")
            await message.answer(_no_appointments_msg(), parse_mode="HTML")
            return

        logger.info(f"Showing {len(appointments)} appointments for client {client.id}")
        await message.answer(
            _appointments_header(len(appointments)),
            parse_mode="HTML"
        )

        for appt in appointments:
            text = _appointment_card(appt)
            keyboard = get_appointment_keyboard(appt.id, message.from_user.id)
            await message.answer(text, parse_mode="HTML", reply_markup=keyboard)


# ──────────────────────────────────────────────
#  Consultation / AI Chat
# ──────────────────────────────────────────────

@router.message(F.text == "💬 Консультация")
async def consultation_start_handler(message: Message, state: FSMContext) -> None:
    """Start AI consultation dialog."""
    await state.set_state(ConsultForm.waiting_for_description)
    await message.answer(
        _consultation_start_msg(),
        parse_mode="HTML",
        reply_markup=get_consultation_keyboard()
    )


@router.message(F.text == "❌ Выйти из консультации")
async def consultation_exit_handler(message: Message, state: FSMContext) -> None:
    """Exit consultation, return to main menu."""
    await state.clear()
    await message.answer(
        _main_menu_msg(),
        parse_mode="HTML",
        reply_markup=get_main_keyboard(message.from_user.id)
    )


@router.message(ConsultForm.waiting_for_description)
@router.message(ConsultForm.waiting_for_followup)
async def consultation_message_handler(message: Message, state: FSMContext) -> None:
    """Handle user's description of car problem, call AI for diagnosis."""
    user_text = message.text or ""

    # Show typing action while AI thinks
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # Get chat history from state
    state_data = await state.get_data()
    history = state_data.get("history", [])

    try:
        async with async_session_local() as db:
            tenant = await get_or_create_tenant(db)

            # Load available services for matching
            stmt = select(Service).where(Service.tenant_id == tenant.id)
            result = await db.execute(stmt)
            db_services = result.scalars().all()

        # Run AI classification + diagnosis, passing conversation history
        diagnosis = await ai_core.classify_and_diagnose(user_text, history)
        matched = []
        reply_text = ""

        if diagnosis and diagnosis.confidence > 0.4:
            # We got a confident technical diagnosis — match services
            matched = ai_core.planner(diagnosis, db_services, context_text=user_text)
            reply = _diagnostic_result_msg(
                category=diagnosis.category,
                urgency=diagnosis.urgency,
                summary=diagnosis.summary,
                clarifying_question=diagnosis.clarifying_question,
                services=matched,
            )
            reply_text = f"{diagnosis.summary} {diagnosis.clarifying_question}"
        else:
            # Low confidence or general question — use conversational reply
            reply_text = await ai_service.get_consultation(
                user_message=user_text,
                services=db_services,
                history=history
            )
            reply = _consultation_ai_reply_msg(reply_text)
            
            # Try to match services based on AI reply text or user text
            matched = ai_core.planner(None, db_services, context_text=f"{user_text} {reply_text}")

        # Update and save history (keep last 10 messages)
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply_text})
        history = history[-10:]
        await state.update_data(history=history)

        # Stay in followup state so user can ask more
        await state.set_state(ConsultForm.waiting_for_followup)

        # If we have matched services, show an inline button for the best match
        if matched:
            # Sort by name length to pick most specific match first (e.g. specific diagnostics)
            matched.sort(key=lambda s: len(s.name), reverse=True)
            reply_markup = get_consultation_result_keyboard(matched[0].id, telegram_id=message.from_user.id)
        else:
            # Fallback: allow manual selection even if no specific match
            reply_markup = get_consultation_result_keyboard(telegram_id=message.from_user.id) # None id is handled
            
            # Special case: if involves a car problem, suggest any diagnostics
            diagnostic_svc = None
            text_to_match = (user_text + reply_text).lower()
            if any(kw in text_to_match for kw in ["диагност", "сломал", "проблем", "помощ", "нужн", "завод", "горит", "чек"]):
                # Order of preference for diagnostics
                diag_prefs = ["компьютерная диагностика", "диагностика электрооборудования", "диагностика ходовой", "диагностика"]
                for pref in diag_prefs:
                    for s in db_services:
                        if pref in s.name.lower():
                            diagnostic_svc = s
                            break
                    if diagnostic_svc:
                        break
            
            if diagnostic_svc:
                reply_markup = get_consultation_result_keyboard(diagnostic_svc.id, telegram_id=message.from_user.id)
            else:
                # Fallback to the persistent consultation keyboard
                reply_markup = get_consultation_result_keyboard(telegram_id=message.from_user.id)

        await message.answer(
            reply,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Consultation AI error: {e}")
        await message.answer(
            _consultation_error_msg(),
            parse_mode="HTML",
            reply_markup=get_consultation_keyboard()
        )


# ──────────────────────────────────────────────
#  Callback Query Handlers
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("cancel_appt:"))
async def cancel_appointment_handler(callback_query: CallbackQuery) -> None:
    """Handle appointment cancellation."""
    appt_id = int(callback_query.data.split(":")[1])

    async with async_session_local() as db:
        tenant = await get_or_create_tenant(db)

        stmt = select(Appointment).options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
        ).where(
            and_(Appointment.id == appt_id, Appointment.tenant_id == tenant.id)
        )
        result = await db.execute(stmt)
        appt = result.scalar_one_or_none()

        if appt:
            client_name = appt.client.full_name if appt.client else "Неизвестно"
            service_name = appt.service.name if appt.service else "Неизвестно"

            appt.status = AppointmentStatus.CANCELLED
            await db.commit()

            await callback_query.message.edit_text(
                _appointment_cancelled_msg(appt_id),
                parse_mode="HTML"
            )

            # Notify admin
            await _notify_admin(
                _admin_cancelled_msg(appt_id, client_name, service_name)
            )

            # Broadcast to dashboard via Redis
            try:
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
            except Exception as e:
                logger.error(f"Failed to publish update: {e}")
        else:
            await callback_query.answer(_appointment_not_found_msg())


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_handler(callback_query: CallbackQuery) -> None:
    """Handle back to menu button."""
    await callback_query.message.answer(
        _main_menu_msg(),
        parse_mode="HTML",
        reply_markup=get_main_keyboard(callback_query.from_user.id)
    )
    await callback_query.answer()


# ──────────────────────────────────────────────
#  Web App Data Handler
# ──────────────────────────────────────────────

@router.message(F.web_app_data)
async def web_app_data_handler(message: Message) -> None:
    """Handle data received from Telegram Web App (booking form)."""
    try:
        data = json.loads(message.web_app_data.data)
        service_id = data.get("service_id")
        date_str = data.get("date")
        appointment_id = data.get("appointment_id")
        is_waitlist = data.get("is_waitlist", False)

        # Vehicle info (new required fields)
        car_make = data.get("car_make", "").strip() or None
        car_year_raw = data.get("car_year")
        car_year = int(car_year_raw) if car_year_raw else None
        vin = (data.get("vin", "").strip().upper() or None)

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
                    shop_id=1,
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
                existing_appt.car_make = car_make
                existing_appt.car_year = car_year
                existing_appt.vin = vin
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
                    status=status,
                    car_make=car_make,
                    car_year=car_year,
                    vin=vin,
                )
                db.add(new_appt)
                appt = new_appt

            await db.commit()
            await db.refresh(appt)

            # Confirmation message
            time_str = start_time_naive.strftime('%d.%m.%Y  %H:%M')
            if is_waitlist:
                msg = _waitlist_msg(
                    service.name,
                    start_time_naive.strftime('%d.%m.%Y')
                )
            else:
                msg = _booking_confirmed_msg(
                    service.name,
                    time_str,
                    is_edit=bool(appointment_id)
                )

            await message.answer(msg, parse_mode="HTML")

            # Admin notification for new bookings (not edits, not waitlist)
            if not is_waitlist and not appointment_id:
                client_phone = client.phone if client else "—"
                await _notify_admin(
                    _admin_new_booking_msg(
                        client_name=client.full_name,
                        phone=client_phone,
                        service_name=service.name,
                        time_str=time_str,
                    )
                )

            # Redis broadcast
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


# ──────────────────────────────────────────────
#  Fallback — any unrecognized text outside FSM
# ──────────────────────────────────────────────

@router.message(F.text)
async def fallback_text_handler(message: Message, state: FSMContext) -> None:
    """Catch-all for unrecognized text messages outside active states."""
    current_state = await state.get_state()
    if current_state:
        # User is in some dialog — shouldn't land here, but just in case
        return

    await message.answer(
        _unknown_text_msg(),
        parse_mode="HTML",
        reply_markup=get_main_keyboard(message.from_user.id)
    )
