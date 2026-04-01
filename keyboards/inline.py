from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def events_list_kb(events: list[dict], page: int, total_pages: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ev in events:
        status_icon = "✅" if ev["status"] == "active" else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {ev['title']} — {ev['date']}",
                callback_data=f"event:{ev['id']}",
            )
        )
    nav_buttons: list[InlineKeyboardButton] = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"events_page:{page - 1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"events_page:{page + 1}"))
    if nav_buttons:
        builder.row(*nav_buttons)
    return builder.as_markup()


def event_detail_kb(event_id: int, is_registered: bool, is_waitlisted: bool, is_full: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_registered:
        builder.row(
            InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data=f"unreg:{event_id}")
        )
    elif is_waitlisted:
        builder.row(
            InlineKeyboardButton(text="❌ Покинуть лист ожидания", callback_data=f"unreg:{event_id}")
        )
    else:
        if is_full:
            builder.row(
                InlineKeyboardButton(text="📝 Встать в лист ожидания", callback_data=f"reg:{event_id}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="✅ Зарегистрироваться", callback_data=f"reg:{event_id}")
            )
    builder.row(InlineKeyboardButton(text="🔙 К списку событий", callback_data="events_page:0"))
    return builder.as_markup()


def my_events_kb(registrations: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for reg in registrations:
        status_icon = "✅" if reg["reg_status"] == "registered" else "⏳"
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon} {reg['title']} — {reg['date']}",
                callback_data=f"myevent:{reg['event_id']}",
            )
        )
    return builder.as_markup()


def my_event_detail_kb(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отменить регистрацию", callback_data=f"unreg:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Мои регистрации", callback_data="my_events")
    )
    return builder.as_markup()


# ── Admin keyboards ─────────────────────────────────────────────────

def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать событие", callback_data="admin:create"))
    builder.row(InlineKeyboardButton(text="📋 Все события", callback_data="admin:events"))
    return builder.as_markup()


def admin_events_kb(events: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ev in events:
        icons = {"active": "✅", "cancelled": "❌", "completed": "✔️"}
        icon = icons.get(ev["status"], "")
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {ev['title']} [{ev['status']}]",
                callback_data=f"admin_event:{ev['id']}",
            )
        )
    return builder.as_markup()


def admin_event_detail_kb(event_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == "active":
        builder.row(
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_edit:{event_id}"),
            InlineKeyboardButton(text="🚫 Отменить", callback_data=f"admin_cancel:{event_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="👥 Участники", callback_data=f"admin_participants:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Рассылка", callback_data=f"admin_broadcast:{event_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin:events"))
    return builder.as_markup()


def admin_edit_event_kb(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    fields = [
        ("Название", "title"),
        ("Описание", "description"),
        ("Дата", "date"),
        ("Время", "time"),
        ("Место", "location"),
        ("Макс. участников", "max_participants"),
    ]
    for label, field in fields:
        builder.row(
            InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"edit_field:{event_id}:{field}")
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_event:{event_id}"))
    return builder.as_markup()


def confirm_cancel_event_kb(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"confirm_cancel:{event_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"admin_event:{event_id}"),
    )
    return builder.as_markup()
