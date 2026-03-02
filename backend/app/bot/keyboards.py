from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from app.core.config import settings


def get_main_keyboard(telegram_id: int = None) -> ReplyKeyboardMarkup:
    """Main reply keyboard with branded buttons."""
    is_https = settings.WEBAPP_URL.startswith("https://")
    
    webapp_url = settings.WEBAPP_URL
    if telegram_id:
        webapp_url = f"{webapp_url}?telegram_id={telegram_id}"

    buttons = []
    if is_https:
        buttons.append([
            KeyboardButton(
                text="🔧 Записаться на сервис",
                web_app=WebAppInfo(url=webapp_url)
            )
        ])
    else:
        buttons.append([KeyboardButton(text="🔧 Записаться (⚠️ нужен HTTPS)")])

    buttons.append([
        KeyboardButton(text="📋 Мои записи"),
        KeyboardButton(text="💬 Консультация"),
    ])
    buttons.append([
        KeyboardButton(text="📱 Отправить номер", request_contact=True)
    ])
    buttons.append([
        KeyboardButton(text="📄 Правовая информация")
    ])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✍️ Напишите вопрос или выберите действие..."
    )


def get_appointment_keyboard(appointment_id: int, telegram_id: int = None) -> InlineKeyboardMarkup:
    """Inline keyboard for a single appointment card."""
    webapp_url = f"{settings.WEBAPP_URL}?appointment_id={appointment_id}"
    if telegram_id:
        webapp_url += f"&telegram_id={telegram_id}"
        
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Перенести",
                web_app=WebAppInfo(url=webapp_url)
            ),
            InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"cancel_appt:{appointment_id}"
            ),
        ]
    ])


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Simple 'back to menu' inline keyboard."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 В главное меню", callback_data="back_to_menu")]
    ])


def get_consultation_keyboard() -> ReplyKeyboardMarkup:
    """Keyboard shown during AI consultation — only Exit button."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Выйти из консультации")]],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✍️ Опишите проблему с автомобилем..."
    )


def get_consultation_result_keyboard(service_id: int = None, telegram_id: int = None) -> ReplyKeyboardMarkup:
    """Persistent reply keyboard shown after AI has given a recommendation."""
    buttons = []
    
    # Pre-selected booking button if we have a match
    webapp_url = f"{settings.WEBAPP_URL}?service_id={service_id}" if service_id else settings.WEBAPP_URL
    if telegram_id:
        sep = "&" if "?" in webapp_url else "?"
        webapp_url += f"{sep}telegram_id={telegram_id}"
        
    buttons.append([
        KeyboardButton(
            text="🔧 Записаться (выбрано)" if service_id else "🔧 Записаться на сервис",
            web_app=WebAppInfo(url=webapp_url)
        )
    ])
    
    # General buttons
    all_svcs_url = settings.WEBAPP_URL
    if telegram_id:
        all_svcs_url += f"?telegram_id={telegram_id}"
        
    buttons.append([
        KeyboardButton(text="📂 Все услуги", web_app=WebAppInfo(url=all_svcs_url)),
        KeyboardButton(text="❌ Выйти из консультации")
    ])
    
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="✍️ Продолжите вопрос или выберите действие..."
    )


def get_service_suggestion_keyboard(service_id: int, telegram_id: int = None) -> InlineKeyboardMarkup:
    """Inline keyboard with a link to book a specific service."""
    webapp_url = f"{settings.WEBAPP_URL}?service_id={service_id}"
    all_svcs_url = settings.WEBAPP_URL
    
    if telegram_id:
        webapp_url += f"&telegram_id={telegram_id}"
        all_svcs_url += f"?telegram_id={telegram_id}"
        
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔧 Записаться на эту услугу",
                web_app=WebAppInfo(url=webapp_url)
            )
        ],
        [
            InlineKeyboardButton(
                text="📂 Выбрать другую услугу",
                web_app=WebAppInfo(url=all_svcs_url)
            )
        ]
    ])
