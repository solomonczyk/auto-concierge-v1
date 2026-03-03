"""
Message templates for Telegram bot responses.
Centralized text content for consistent messaging.
"""

from aiogram import html

# Status emoji mapping
STATUS_EMOJI = {
    "new": "🆕",
    "confirmed": "✅",
    "in_progress": "🔧",
    "completed": "✔️",
    "cancelled": "❌",
    "waitlist": "📝",
}

# Status labels in Russian
STATUS_LABELS = {
    "new": "Новая",
    "confirmed": "Подтверждена",
    "in_progress": "В работе",
    "completed": "Завершена",
    "cancelled": "Отменена",
    "waitlist": "Лист ожидания",
}


def _welcome_msg(name: str, returning: bool = False) -> str:
    """Generate welcome message for new and returning users."""
    if returning:
        return (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👋 <b>С возвращением, {html.quote(name)}!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"Рады видеть вас снова в <b>AutoService</b>.\n"
            f"Чем могу помочь сегодня?\n\n"
            f"🔧 — Записаться на сервис\n"
            f"📋 — Просмотреть записи\n"
            f"💬 — Задать вопрос мастеру"
        )
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🚗 <b>Добро пожаловать в AutoService!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Привет, <b>{html.quote(name)}</b>!\n"
        f"Я помогу вам записаться в наш автосервис.\n\n"
        f"📱 <b>Первый шаг</b> — отправьте номер телефона\n"
        f"кнопкой ниже для регистрации.\n\n"
        f"⚠️ <i>Нажимая кнопку, вы соглашаетесь на обработку\n"
        f"персональных данных.</i>"
        f"<i>После этого вам станут доступны\n"
        f"запись, консультация и история визитов.</i>"
    )


def _contact_linked_msg(name: str, phone: str) -> str:
    """Message shown when phone number is successfully linked to existing client."""
    return (
        f"✅ <b>Номер привязан!</b>\n\n"
        f"👤 {html.quote(name)}\n"
        f"📞 <code>{phone}</code>\n\n"
        f"Теперь вы можете записываться на услуги.\n"
        f"Нажмите <b>🔧 Записаться на сервис</b> ниже."
    )


def _contact_new_msg() -> str:
    """Message shown when new client is registered."""
    return (
        f"🎉 <b>Регистрация завершена!</b>\n\n"
        f"Ваш номер сохранён.\n"
        f"Теперь вы можете записываться на услуги 🚗💨\n\n"
        f"Нажмите <b>🔧 Записаться на сервис</b> ниже."
    )


def _appointment_card(appt, show_actions: bool = True) -> str:
    """Generate appointment card for displaying in chat."""
    status = appt.status.value if hasattr(appt.status, 'value') else str(appt.status)
    emoji = STATUS_EMOJI.get(status, "📌")
    time_str = appt.start_time.strftime('%d.%m.%Y  %H:%M')
    status_label = STATUS_LABELS.get(status, status)

    return (
        f"┌─────────────────────\n"
        f"│ {emoji} <b>{appt.service.name}</b>\n"
        f"│\n"
        f"│ 📅  {time_str}\n"
        f"│ 📊  {status_label}\n"
        f"│ 🆔  #{appt.id}\n"
        f"└─────────────────────"
    )


def _booking_confirmed_msg(service_name: str, time_str: str, is_edit: bool = False) -> str:
    """Message shown when booking is confirmed."""
    action = "перенесена" if is_edit else "подтверждена"
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ <b>Запись {action}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔧 <b>Услуга:</b> {html.quote(service_name)}\n"
        f"🕐 <b>Время:</b> {time_str}\n\n"
        f"<i>Мы ждём вас! Если планы изменятся,\n"
        f"вы можете перенести или отменить запись\n"
        f"в разделе 📋 Мои записи.</i>"
    )


def _waitlist_msg(service_name: str, date_str: str) -> str:
    """Message shown when client is added to waitlist."""
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Лист ожидания</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔧 <b>Услуга:</b> {html.quote(service_name)}\n"
        f"📅 <b>Дата:</b> {date_str}\n\n"
        f"<i>Если освободится место, мы свяжемся\n"
        f"с вами для уточнения деталей.</i>"
    )


def _main_menu_msg() -> str:
    """Main menu message."""
    return (
        f"🏠 <b>Главное меню</b>\n\nВыберите действие:"
    )


def _no_appointments_msg() -> str:
    """Message shown when user has no appointments."""
    return (
        f"📋 <b>Мои записи</b>\n\n"
        f"<i>У вас пока нет активных записей.</i>\n\n"
        f"Нажмите <b>🔧 Записаться на сервис</b>,\n"
        f"чтобы выбрать услугу и время."
    )


def _appointments_header(count: int) -> str:
    """Header for appointments list."""
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Ваши записи</b>  ({count})\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )


def _need_https_msg() -> str:
    """Message explaining HTTPS requirement for Telegram Web Apps."""
    return (
        f"⚠️ <b>Telegram требует HTTPS</b> для Mini Apps.\n\n"
        f"Для работы записи локально:\n"
        f"1. Используйте туннель (<b>ngrok</b>)\n"
        f"2. Укажите <code>https://...</code> в <code>.env</code>\n\n"
        f"<i>Пока можете тестировать в браузере:</i>\n"
        f"<code>http://localhost:5173/webapp</code>"
    )


def _phone_required_msg() -> str:
    """Message shown when phone number is required."""
    return (
        f"📱 Пожалуйста, сначала отправьте номер\n"
        f"для регистрации."
    )


def _appointment_cancelled_msg(appointment_id: int) -> str:
    """Message shown when appointment is cancelled."""
    return (
        f"❌ <b>Запись #{appointment_id} отменена</b>\n\n"
        f"<i>Вы можете создать новую запись\n"
        f"в любое время.</i>"
    )


def _appointment_not_found_msg() -> str:
    """Message shown when appointment is not found."""
    return "Запись не найдена."


def _service_not_found_msg() -> str:
    """Message shown when service is not found."""
    return (
        f"⚠️ <b>Ошибка</b>\n\n"
        f"Услуга не найдена."
    )


def _invalid_webapp_data_msg() -> str:
    """Message shown when WebApp data is invalid."""
    return (
        f"⚠️ <b>Ошибка</b>\n\n"
        f"Некорректные данные от приложения."
    )


def _original_appointment_not_found_msg() -> str:
    """Message shown when trying to edit non-existent appointment."""
    return (
        f"⚠️ <b>Ошибка</b>\n\n"
        f"Исходная запись не найдена."
    )


def _slot_unavailable_msg() -> str:
    """Message shown when selected time slot is unavailable."""
    return (
        f"⏰ <b>Время занято</b>\n\n"
        f"Это время уже занято.\n"
        f"Пожалуйста, выберите другое."
    )


def _shop_not_configured_msg() -> str:
    """Message shown when shop is not configured for tenant."""
    return "⚠️ Shop not configured for this tenant."


def _waitlist_submitted_msg() -> str:
    """Message shown when waitlist application is submitted."""
    return "Заявка в лист ожидания отправлена!"


def _booking_created_msg() -> str:
    """Message shown when booking is created."""
    return "Запись создана!"


def _booking_edited_msg() -> str:
    """Message shown when booking is edited."""
    return "Запись изменена!"


def _consultation_start_msg() -> str:
    """Prompt user to describe their car problem."""
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Консультация с ИИ-диагностом</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Опишите проблему с вашим автомобилем.\n\n"
        f"<i>Например:</i>\n"
        f"• «Стучит при торможении слева»\n"
        f"• «Двигатель троит на холодную»\n"
        f"• «Не заводится с утра»\n\n"
        f"ИИ проанализирует симптомы и предложит\n"
        f"подходящие услуги. Нажмите <b>❌ Выйти</b>,\n"
        f"чтобы вернуться в меню."
    )


def _diagnostic_result_msg(category: str, urgency: str, summary: str, services: list) -> str:
    """AI diagnostic result with matched services."""
    urgency_emoji = {
        "Low": "🟢", "Medium": "🟡", "High": "🔴",
        "Низкая": "🟢", "Средняя": "🟡", "Высокая": "🔴"
    }.get(urgency, "⚪")
    urgency_label = {
        "Low": "Низкая", "Medium": "Средняя", "High": "Высокая"
    }.get(urgency, urgency)

    service_lines = ""
    if services:
        service_lines = "\n\n🔧 <b>Рекомендуемые услуги:</b>\n"
        for svc in services[:3]:
            price = f" — {svc.base_price} ₽" if hasattr(svc, "base_price") and svc.base_price else ""
            service_lines += f"• {html.quote(svc.name)}{price}\n"

    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Результат диагностики</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 <b>Категория:</b> {html.quote(category)}\n"
        f"⚡ <b>Срочность:</b> {urgency_emoji} {urgency_label}\n\n"
        f"💡 {html.quote(summary)}\n\n"
        f"{service_lines}\n"
        f"<i>Нажмите кнопку записи ниже, чтобы\n"
        f"сразу выбрать время на рекомендованную услугу.</i>"
    )


def _consultation_ai_reply_msg(text: str) -> str:
    """Wrap plain AI consultation answer."""
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Ответ консультанта</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{html.quote(text)}\n\n"
        f"<i>Задайте следующий вопрос или выберите\n"
        f"действие в меню ниже.</i>"
    )


def _consultation_error_msg() -> str:
    """Message when AI fails to respond."""
    return (
        f"⚠️ <b>Не удалось получить ответ</b>\n\n"
        f"Попробуйте переформулировать вопрос\n"
        f"или обратитесь к нам напрямую."
    )


def _legal_info_msg() -> str:
    """Legal information text."""
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 <b>Правовая информация</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Оператор персональных данных:</b>\n"
        f"[Название компании]\n\n"
        f"<b>Используемые данные:</b>\n"
        f"• Имя и фамилия из Telegram\n"
        f"• Номер телефона (при регистрации)\n"
        f"• История записей\n\n"
        f"<b>Цель обработки:</b>\n"
        f"Запись и обслуживание клиентов автосервиса.\n\n"
        f"<b>Хранение:</b>\n"
        f"Данные хранятся на защищённых серверах\n"
        f"и не передаются третьим лицам.\n\n"
        f"<b>Ваши права:</b>\n"
        f"Вы вправе запросить удаление данных,\n"
        f"написав в поддержку.\n\n"
        f"🌐 [Сайт]"
    )


def _unknown_text_msg() -> str:
    """Shown when user sends unrecognized text outside dialogs."""
    return (
        f"Воспользуйтесь кнопками меню ниже 👇\n\n"
        f"Или нажмите <b>💬 Консультация</b>,\n"
        f"чтобы задать вопрос нашему ИИ-консультанту."
    )


def _admin_new_booking_msg(client_name: str, phone: str, service_name: str, time_str: str) -> str:
    """Notification to admin about new booking."""
    return (
        f"🆕 <b>Новая запись!</b>\n\n"
        f"👤 {html.quote(client_name)}\n"
        f"📞 <code>{phone}</code>\n"
        f"🔧 {html.quote(service_name)}\n"
        f"🕐 {time_str}"
    )


def _admin_cancelled_msg(appt_id: int, client_name: str, service_name: str) -> str:
    """Notification to admin about cancelled booking."""
    return (
        f"❌ <b>Запись #{appt_id} отменена клиентом</b>\n\n"
        f"👤 {html.quote(client_name)}\n"
        f"🔧 {html.quote(service_name)}"
    )
