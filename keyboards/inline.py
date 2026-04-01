from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ══════════════════════════════════════════════════════════════════════
# User: Events list
# ══════════════════════════════════════════════════════════════════════

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

    # Filter buttons
    builder.row(
        InlineKeyboardButton(text="📂 По категориям", callback_data="filter:categories"),
        InlineKeyboardButton(text="🔥 Популярные", callback_data="filter:popular"),
    )
    return builder.as_markup()


def event_detail_kb(
    event_id: int,
    is_registered: bool,
    is_waitlisted: bool,
    is_full: bool,
    has_ticket_types: bool = False,
    has_photos: bool = False,
    avg_rating: float | None = None,
) -> InlineKeyboardMarkup:
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
        if has_ticket_types:
            builder.row(
                InlineKeyboardButton(text="🎫 Выбрать билет", callback_data=f"tickets:{event_id}")
            )
        elif is_full:
            builder.row(
                InlineKeyboardButton(text="📝 Встать в лист ожидания", callback_data=f"reg:{event_id}")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="✅ Зарегистрироваться", callback_data=f"reg:{event_id}")
            )

    if has_photos:
        builder.row(
            InlineKeyboardButton(text="📷 Фотогалерея", callback_data=f"photos:{event_id}")
        )

    if avg_rating is not None:
        stars = "⭐" * round(avg_rating)
        builder.row(
            InlineKeyboardButton(
                text=f"{stars} Отзывы ({avg_rating})",
                callback_data=f"reviews:{event_id}",
            )
        )

    builder.row(InlineKeyboardButton(text="🔙 К списку событий", callback_data="events_page:0"))
    return builder.as_markup()


def ticket_types_kb(event_id: int, ticket_types: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tt in ticket_types:
        remaining = tt["max_count"] - tt["sold_count"]
        price_text = f"{tt['price']}₽" if tt["price"] > 0 else "Бесплатно"
        status = f"({remaining} мест)" if remaining > 0 else "(Распродано)"
        builder.row(
            InlineKeyboardButton(
                text=f"🎫 {tt['name']} — {price_text} {status}",
                callback_data=f"buy_ticket:{event_id}:{tt['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"event:{event_id}"))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════
# User: Categories filter
# ══════════════════════════════════════════════════════════════════════

def categories_filter_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"{cat['emoji']} {cat['name']}",
                callback_data=f"cat_filter:{cat['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Все события", callback_data="events_page:0"))
    return builder.as_markup()


def category_events_kb(events: list[dict], category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ev in events:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ {ev['title']} — {ev['date']}",
                callback_data=f"event:{ev['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Категории", callback_data="filter:categories"),
        InlineKeyboardButton(text="🔙 Все события", callback_data="events_page:0"),
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════
# User: My events
# ══════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════
# User: Reviews
# ══════════════════════════════════════════════════════════════════════

def review_rating_kb(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(1, 6):
        builder.add(
            InlineKeyboardButton(text=f"{'⭐' * i}", callback_data=f"rate:{event_id}:{i}")
        )
    builder.adjust(5)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=f"event:{event_id}"))
    return builder.as_markup()


def reviews_list_kb(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data=f"write_review:{event_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 К событию", callback_data=f"event:{event_id}"))
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════
# User: Search
# ══════════════════════════════════════════════════════════════════════

def search_results_kb(events: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ev in events:
        builder.row(
            InlineKeyboardButton(
                text=f"📌 {ev['title']} — {ev['date']}",
                callback_data=f"event:{ev['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Главное меню", callback_data="events_page:0"))
    return builder.as_markup()


def search_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📝 По тексту", callback_data="search:text"),
        InlineKeyboardButton(text="📅 По датам", callback_data="search:dates"),
    )
    builder.row(
        InlineKeyboardButton(text="📂 По категории", callback_data="filter:categories"),
        InlineKeyboardButton(text="🔥 Популярные", callback_data="filter:popular"),
    )
    return builder.as_markup()


# ══════════════════════════════════════════════════════════════════════
# Admin keyboards
# ══════════════════════════════════════════════════════════════════════

def admin_panel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать событие", callback_data="admin:create"))
    builder.row(InlineKeyboardButton(text="📋 Все события", callback_data="admin:events"))
    builder.row(InlineKeyboardButton(text="📂 Категории", callback_data="admin:categories"))
    builder.row(InlineKeyboardButton(text="📊 Аналитика", callback_data="admin:analytics"))
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
    builder.row(InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin:panel"))
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
        InlineKeyboardButton(text="📢 Рассылка", callback_data=f"admin_broadcast:{event_id}"),
        InlineKeyboardButton(text="📊 Статистика", callback_data=f"admin_event_stats:{event_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🎫 Типы билетов", callback_data=f"admin_tickets:{event_id}"),
        InlineKeyboardButton(text="📷 Фото", callback_data=f"admin_photos:{event_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="📥 Экспорт CSV", callback_data=f"admin_export:{event_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✅ Чекин", callback_data=f"admin_checkin_stats:{event_id}")
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
        ("Категория", "category_id"),
        ("Повторение", "recurrence_type"),
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


# ── Admin: Categories ──────────────────────────────────────────────

def admin_categories_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"{cat['emoji']} {cat['name']}",
                callback_data=f"admin_cat:{cat['id']}",
            ),
            InlineKeyboardButton(
                text="🗑",
                callback_data=f"admin_del_cat:{cat['id']}",
            ),
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin:add_category")
    )
    builder.row(InlineKeyboardButton(text="🔙 Админ-панель", callback_data="admin:panel"))
    return builder.as_markup()


def category_select_kb(categories: list[dict], event_id: int) -> InlineKeyboardMarkup:
    """Select category when editing event category."""
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"{cat['emoji']} {cat['name']}",
                callback_data=f"set_cat:{event_id}:{cat['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🚫 Без категории", callback_data=f"set_cat:{event_id}:0")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_edit:{event_id}"))
    return builder.as_markup()


def recurrence_select_kb(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    options = [
        ("Еженедельно", "weekly"),
        ("Раз в 2 недели", "biweekly"),
        ("Ежемесячно", "monthly"),
        ("Без повторения", "none"),
    ]
    for label, value in options:
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"set_recurrence:{event_id}:{value}")
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_edit:{event_id}"))
    return builder.as_markup()


# ── Admin: Ticket types management ──────────────────────────────────

def admin_ticket_types_kb(event_id: int, ticket_types: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for tt in ticket_types:
        price_text = f"{tt['price']}₽" if tt["price"] > 0 else "Бесплатно"
        builder.row(
            InlineKeyboardButton(
                text=f"🎫 {tt['name']} — {price_text} ({tt['sold_count']}/{tt['max_count']})",
                callback_data=f"admin_tt_info:{tt['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить тип билета", callback_data=f"admin_add_tt:{event_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_event:{event_id}"))
    return builder.as_markup()


# ── Admin: Photo management ─────────────────────────────────────────

def admin_photos_kb(event_id: int, photo_count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if photo_count < 5:
        builder.row(
            InlineKeyboardButton(
                text=f"📷 Добавить фото ({photo_count}/5)",
                callback_data=f"admin_add_photo:{event_id}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_event:{event_id}"))
    return builder.as_markup()


# ── Category select for event creation FSM ──────────────────────────

def category_select_for_create_kb(categories: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cat in categories:
        builder.row(
            InlineKeyboardButton(
                text=f"{cat['emoji']} {cat['name']}",
                callback_data=f"create_cat:{cat['id']}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="🚫 Без категории", callback_data="create_cat:0")
    )
    return builder.as_markup()
