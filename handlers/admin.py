import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from config import ADMIN_IDS
import database as db
from utils.csv_export import export_participants_csv
from keyboards.inline import (
    admin_panel_kb,
    admin_events_kb,
    admin_event_detail_kb,
    admin_edit_event_kb,
    confirm_cancel_event_kb,
    admin_categories_kb,
    category_select_kb,
    recurrence_select_kb,
    admin_ticket_types_kb,
    admin_photos_kb,
    category_select_for_create_kb,
)
from keyboards.reply import admin_menu_kb, cancel_kb, skip_kb

router = Router()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# FSM States
# ══════════════════════════════════════════════════════════════════════

class CreateEvent(StatesGroup):
    title = State()
    description = State()
    date = State()
    time = State()
    location = State()
    max_participants = State()
    category = State()
    recurrence = State()
    photo = State()


class EditField(StatesGroup):
    waiting_value = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


class AddCategory(StatesGroup):
    name = State()
    emoji = State()


class AddTicketType(StatesGroup):
    name = State()
    price = State()
    max_count = State()


class AddPhoto(StatesGroup):
    waiting_photo = State()


# ══════════════════════════════════════════════════════════════════════
# Admin check
# ══════════════════════════════════════════════════════════════════════

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ══════════════════════════════════════════════════════════════════════
# Admin panel entry
# ══════════════════════════════════════════════════════════════════════

@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore[union-attr]
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin:panel")
async def admin_panel_cb(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_panel_kb())  # type: ignore[union-attr]
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Cancel FSM (universal)
# ══════════════════════════════════════════════════════════════════════

@router.message(F.text == "❌ Отмена", StateFilter("*"))
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=admin_menu_kb())


# ══════════════════════════════════════════════════════════════════════
# Create Event FSM
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:create")
async def create_event_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    await state.set_state(CreateEvent.title)
    await callback.message.answer(  # type: ignore[union-attr]
        "📝 <b>Создание события</b>\n\nВведите название:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(CreateEvent.title)
async def create_event_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text)
    await state.set_state(CreateEvent.description)
    await message.answer("📝 Введите описание события:")


@router.message(CreateEvent.description)
async def create_event_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text)
    await state.set_state(CreateEvent.date)
    await message.answer("📅 Введите дату (формат: <b>ГГГГ-ММ-ДД</b>):")


@router.message(CreateEvent.date)
async def create_event_date(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте <b>ГГГГ-ММ-ДД</b>:")
        return
    await state.update_data(date=text)
    await state.set_state(CreateEvent.time)
    await message.answer("🕐 Введите время (формат: <b>ЧЧ:ММ</b>):")


@router.message(CreateEvent.time)
async def create_event_time(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте <b>ЧЧ:ММ</b>:")
        return
    await state.update_data(time=text)
    await state.set_state(CreateEvent.location)
    await message.answer("📍 Введите место проведения:")


@router.message(CreateEvent.location)
async def create_event_location(message: Message, state: FSMContext) -> None:
    await state.update_data(location=message.text)
    await state.set_state(CreateEvent.max_participants)
    await message.answer("👥 Введите максимальное количество участников:")


@router.message(CreateEvent.max_participants)
async def create_event_max_participants(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введите положительное целое число:")
        return
    await state.update_data(max_participants=int(text))
    await state.set_state(CreateEvent.category)

    # Show category selection
    categories = await db.get_categories()
    if categories:
        kb = category_select_for_create_kb(categories)
        await message.answer("📂 Выберите категорию:", reply_markup=kb)
    else:
        await state.update_data(category_id=None)
        await state.set_state(CreateEvent.recurrence)
        await message.answer(
            "🔄 Повторение события?\n\n"
            "Отправьте: <b>weekly</b>, <b>biweekly</b>, <b>monthly</b>\n"
            "Или /skip чтобы пропустить:",
            reply_markup=skip_kb(),
        )


@router.callback_query(F.data.startswith("create_cat:"), CreateEvent.category)
async def create_event_category(callback: CallbackQuery, state: FSMContext) -> None:
    cat_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await state.update_data(category_id=cat_id if cat_id > 0 else None)
    await state.set_state(CreateEvent.recurrence)
    await callback.message.answer(  # type: ignore[union-attr]
        "🔄 Повторение события?\n\n"
        "Отправьте: <b>weekly</b>, <b>biweekly</b>, <b>monthly</b>\n"
        "Или /skip чтобы пропустить:",
        reply_markup=skip_kb(),
    )
    await callback.answer()


@router.message(CreateEvent.recurrence, F.text.casefold().in_({"weekly", "biweekly", "monthly"}))
async def create_event_recurrence(message: Message, state: FSMContext) -> None:
    await state.update_data(recurrence_type=message.text.strip().lower())
    await state.set_state(CreateEvent.photo)
    await message.answer("📷 Отправьте фото для события или /skip чтобы пропустить:")


@router.message(CreateEvent.recurrence)
async def create_event_recurrence_skip(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().lower()
    if text in ("/skip", "⏩ пропустить"):
        await state.update_data(recurrence_type=None)
        await state.set_state(CreateEvent.photo)
        await message.answer("📷 Отправьте фото для события или /skip чтобы пропустить:")
    else:
        await message.answer(
            "❌ Неверное значение. Отправьте: <b>weekly</b>, <b>biweekly</b>, <b>monthly</b> или /skip:"
        )


@router.message(CreateEvent.photo, F.photo)
async def create_event_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id  # type: ignore[index]
    await state.update_data(photo_id=photo_id)
    await _save_event(message, state)


@router.message(CreateEvent.photo)
async def create_event_skip_photo(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().lower()
    if text in ("/skip", "⏩ пропустить"):
        await state.update_data(photo_id=None)
        await _save_event(message, state)
    else:
        await message.answer("📷 Отправьте фото или /skip:")


async def _save_event(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = await db.create_event(
        title=data["title"],
        description=data["description"],
        event_date=data["date"],
        event_time=data["time"],
        location=data["location"],
        max_participants=data["max_participants"],
        photo_id=data.get("photo_id"),
        category_id=data.get("category_id"),
        recurrence_type=data.get("recurrence_type"),
    )
    await state.clear()

    rec_text = ""
    if data.get("recurrence_type"):
        labels = {"weekly": "еженедельно", "biweekly": "раз в 2 недели", "monthly": "ежемесячно"}
        rec_text = f"\n🔄 Повторение: {labels.get(data['recurrence_type'], data['recurrence_type'])}"

    await message.answer(
        f"✅ Событие <b>{data['title']}</b> создано! (ID: {event_id}){rec_text}\n\n"
        f"Теперь вы можете добавить типы билетов и фотографии через админ-панель.",
        reply_markup=admin_menu_kb(),
    )
    logger.info("Event created: id=%s title=%s", event_id, data["title"])


# ══════════════════════════════════════════════════════════════════════
# Admin: list events
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:events")
async def admin_events_list(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔", show_alert=True)
        return
    events = await db.get_all_events(limit=20)
    if not events:
        await callback.message.edit_text("Событий пока нет.")  # type: ignore[union-attr]
        await callback.answer()
        return
    kb = admin_events_kb(events)
    await callback.message.edit_text("📋 <b>Все события:</b>", reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: event detail
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_event:"))
async def admin_event_detail(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    reg_count = await db.get_registration_count(event_id)
    waitlist_count = await db.get_waitlist_count(event_id)

    # Category
    cat_line = ""
    if event.get("category_id"):
        cat = await db.get_category(event["category_id"])
        if cat:
            cat_line = f"\n📂 Категория: {cat['emoji']} {cat['name']}"

    # Recurrence
    rec_line = ""
    if event.get("recurrence_type"):
        labels = {"weekly": "Еженедельно", "biweekly": "Раз в 2 недели", "monthly": "Ежемесячно"}
        rec_line = f"\n🔄 Повторение: {labels.get(event['recurrence_type'], event['recurrence_type'])}"

    # Rating
    avg_rating = await db.get_event_avg_rating(event_id)
    rating_line = f"\n⭐ Рейтинг: {avg_rating}/5" if avg_rating else ""

    text = (
        f"📌 <b>{event['title']}</b>\n\n"
        f"{event['description']}\n\n"
        f"📅 {event['date']}  🕐 {event['time']}\n"
        f"📍 {event['location']}\n"
        f"👥 {reg_count}/{event['max_participants']} (в очереди: {waitlist_count})\n"
        f"Статус: <b>{event['status']}</b>"
        f"{cat_line}{rec_line}{rating_line}"
    )

    kb = admin_event_detail_kb(event_id, event["status"])
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: edit event
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_edit:"))
async def admin_edit_menu(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    kb = admin_edit_event_kb(event_id)
    await callback.message.edit_text("✏️ Выберите поле для редактирования:", reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def admin_edit_field_start(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")  # type: ignore[union-attr]
    event_id = int(parts[1])
    field = parts[2]

    # Special handling for category_id
    if field == "category_id":
        categories = await db.get_categories()
        kb = category_select_kb(categories, event_id)
        await callback.message.edit_text("📂 Выберите категорию:", reply_markup=kb)  # type: ignore[union-attr]
        await callback.answer()
        return

    # Special handling for recurrence_type
    if field == "recurrence_type":
        kb = recurrence_select_kb(event_id)
        await callback.message.edit_text("🔄 Выберите тип повторения:", reply_markup=kb)  # type: ignore[union-attr]
        await callback.answer()
        return

    field_labels = {
        "title": "название",
        "description": "описание",
        "date": "дату (ГГГГ-ММ-ДД)",
        "time": "время (ЧЧ:ММ)",
        "location": "место",
        "max_participants": "макс. участников",
    }
    label = field_labels.get(field, field)

    await state.set_state(EditField.waiting_value)
    await state.update_data(edit_event_id=event_id, edit_field=field)
    await callback.message.answer(  # type: ignore[union-attr]
        f"Введите новое значение для <b>{label}</b>:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_cat:"))
async def admin_set_category(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")  # type: ignore[union-attr]
    event_id = int(parts[1])
    cat_id = int(parts[2])
    await db.update_event_field(event_id, "category_id", cat_id if cat_id > 0 else None)
    await callback.answer("✅ Категория обновлена", show_alert=True)

    # Return to event detail
    callback.data = f"admin_event:{event_id}"  # type: ignore[assignment]
    await admin_event_detail(callback)


@router.callback_query(F.data.startswith("set_recurrence:"))
async def admin_set_recurrence(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")  # type: ignore[union-attr]
    event_id = int(parts[1])
    value = parts[2]
    await db.update_event_field(
        event_id, "recurrence_type", value if value != "none" else None,
    )
    await callback.answer("✅ Повторение обновлено", show_alert=True)

    callback.data = f"admin_event:{event_id}"  # type: ignore[assignment]
    await admin_event_detail(callback)


@router.message(EditField.waiting_value)
async def admin_edit_field_save(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data["edit_event_id"]
    field = data["edit_field"]
    value = message.text.strip()  # type: ignore[union-attr]

    # Validate
    if field == "date":
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            await message.answer("❌ Формат: ГГГГ-ММ-ДД")
            return
    elif field == "time":
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError:
            await message.answer("❌ Формат: ЧЧ:ММ")
            return
    elif field == "max_participants":
        if not value.isdigit() or int(value) <= 0:
            await message.answer("❌ Введите положительное число")
            return
        value = int(value)  # type: ignore[assignment]

    await db.update_event_field(event_id, field, value)
    await state.clear()
    await message.answer("✅ Поле обновлено.", reply_markup=admin_menu_kb())


# ══════════════════════════════════════════════════════════════════════
# Admin: cancel event
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_cancel:"))
async def admin_cancel_confirm(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    kb = confirm_cancel_event_kb(event_id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "⚠️ <b>Вы уверены, что хотите отменить это событие?</b>\n\n"
        "Все зарегистрированные участники получат уведомление.",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel:"))
async def admin_cancel_event(callback: CallbackQuery, bot: Bot) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    await db.cancel_event(event_id)

    # Notify all registered users
    user_ids = await db.get_event_registered_user_ids(event_id)
    notified = 0
    for uid in user_ids:
        try:
            await bot.send_message(
                uid,
                f"🚫 <b>Событие отменено</b>\n\n"
                f"К сожалению, событие <b>{event['title']}</b> "
                f"({event['date']} {event['time']}) было отменено.",
            )
            notified += 1
        except Exception:
            logger.warning("Failed to notify user %s about cancellation", uid)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Событие <b>{event['title']}</b> отменено.\n"
        f"Уведомлено участников: {notified}/{len(user_ids)}"
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: participants
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_participants:"))
async def admin_participants(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    participants = await db.get_event_participants(event_id)
    waitlist = await db.get_event_waitlist(event_id)

    lines = [f"👥 <b>Участники — {event['title']}</b>\n"]

    if participants:
        lines.append("<b>Зарегистрированы:</b>")
        for i, p in enumerate(participants, 1):
            name = f"@{p['username']}" if p.get("username") else f"ID: {p['user_id']}"
            ticket_info = f" [{p.get('ticket_name', '')}]" if p.get("ticket_name") else ""
            status_icon = "🎉" if p["status"] == "attended" else "✅"
            lines.append(f"  {i}. {status_icon} {name}{ticket_info}")
    else:
        lines.append("Пока никто не зарегистрирован.")

    if waitlist:
        lines.append(f"\n<b>Лист ожидания ({len(waitlist)}):</b>")
        for i, w in enumerate(waitlist, 1):
            name = f"@{w['username']}" if w.get("username") else f"ID: {w['user_id']}"
            lines.append(f"  {i}. ⏳ {name}")

    kb = admin_event_detail_kb(event_id, event["status"])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: broadcast
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_broadcast:"))
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔", show_alert=True)
        return

    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_message)
    await state.update_data(broadcast_event_id=event_id)
    await callback.message.answer(  # type: ignore[union-attr]
        f"📢 Введите сообщение для рассылки участникам события "
        f"<b>{event['title']}</b>:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(BroadcastState.waiting_message)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    event_id = data["broadcast_event_id"]
    broadcast_text = message.text  # type: ignore[union-attr]

    event = await db.get_event(event_id)
    if not event:
        await state.clear()
        await message.answer("Событие не найдено.", reply_markup=admin_menu_kb())
        return

    user_ids = await db.get_event_registered_user_ids(event_id)
    await db.save_broadcast(event_id, broadcast_text)

    sent = 0
    for uid in user_ids:
        try:
            await bot.send_message(
                uid,
                f"📢 <b>Сообщение от организаторов</b>\n"
                f"Событие: <b>{event['title']}</b>\n\n"
                f"{broadcast_text}",
            )
            sent += 1
        except Exception:
            logger.warning("Failed to send broadcast to user %s", uid)

    await state.clear()
    await message.answer(
        f"✅ Рассылка отправлена: {sent}/{len(user_ids)} участников.",
        reply_markup=admin_menu_kb(),
    )
    logger.info("Broadcast sent for event %s: %s/%s", event_id, sent, len(user_ids))


# ══════════════════════════════════════════════════════════════════════
# Admin: Categories management
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:categories")
async def admin_categories_list(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔", show_alert=True)
        return
    categories = await db.get_categories()
    kb = admin_categories_kb(categories)
    await callback.message.edit_text("📂 <b>Категории событий:</b>", reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data == "admin:add_category")
async def admin_add_category_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(AddCategory.name)
    await callback.message.answer(  # type: ignore[union-attr]
        "📂 Введите название категории:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AddCategory.name)
async def admin_add_category_name(message: Message, state: FSMContext) -> None:
    await state.update_data(cat_name=message.text)
    await state.set_state(AddCategory.emoji)
    await message.answer("Введите эмодзи для категории (один символ):")


@router.message(AddCategory.emoji)
async def admin_add_category_emoji(message: Message, state: FSMContext) -> None:
    emoji = message.text.strip()  # type: ignore[union-attr]
    data = await state.get_data()
    try:
        await db.create_category(name=data["cat_name"], emoji=emoji)
        await state.clear()
        await message.answer(
            f"✅ Категория <b>{emoji} {data['cat_name']}</b> создана!",
            reply_markup=admin_menu_kb(),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            f"❌ Ошибка: категория с таким именем уже существует.",
            reply_markup=admin_menu_kb(),
        )


@router.callback_query(F.data.startswith("admin_del_cat:"))
async def admin_delete_category(callback: CallbackQuery) -> None:
    cat_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    cat = await db.get_category(cat_id)
    if not cat:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    await db.delete_category(cat_id)
    await callback.answer(f"🗑 Категория '{cat['name']}' удалена", show_alert=True)

    # Refresh list
    categories = await db.get_categories()
    kb = admin_categories_kb(categories)
    await callback.message.edit_text("📂 <b>Категории событий:</b>", reply_markup=kb)  # type: ignore[union-attr]


# ══════════════════════════════════════════════════════════════════════
# Admin: Ticket types management
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_tickets:"))
async def admin_ticket_types(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    ticket_types = await db.get_ticket_types(event_id)
    kb = admin_ticket_types_kb(event_id, ticket_types)
    event = await db.get_event(event_id)
    title = event["title"] if event else "Событие"
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"🎫 <b>Типы билетов — {title}</b>", reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_add_tt:"))
async def admin_add_ticket_type_start(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await state.set_state(AddTicketType.name)
    await state.update_data(tt_event_id=event_id)
    await callback.message.answer(  # type: ignore[union-attr]
        "🎫 Введите название типа билета (напр. Обычный, VIP, Бесплатный):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AddTicketType.name)
async def admin_add_tt_name(message: Message, state: FSMContext) -> None:
    await state.update_data(tt_name=message.text)
    await state.set_state(AddTicketType.price)
    await message.answer("💰 Введите цену билета (0 для бесплатного):")


@router.message(AddTicketType.price)
async def admin_add_tt_price(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    try:
        price = float(text)
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число >= 0:")
        return
    await state.update_data(tt_price=price)
    await state.set_state(AddTicketType.max_count)
    await message.answer("👥 Введите максимальное количество билетов этого типа:")


@router.message(AddTicketType.max_count)
async def admin_add_tt_max_count(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❌ Введите положительное целое число:")
        return

    data = await state.get_data()
    event_id = data["tt_event_id"]
    tt_id = await db.create_ticket_type(
        event_id=event_id,
        name=data["tt_name"],
        price=data["tt_price"],
        max_count=int(text),
    )
    await state.clear()

    price_text = f"{data['tt_price']}₽" if data["tt_price"] > 0 else "Бесплатно"
    await message.answer(
        f"✅ Тип билета <b>{data['tt_name']}</b> ({price_text}, {text} шт.) создан!",
        reply_markup=admin_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════
# Admin: Photo management
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_photos:"))
async def admin_photos(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    photo_count = await db.count_event_photos(event_id)
    event = await db.get_event(event_id)
    title = event["title"] if event else "Событие"

    kb = admin_photos_kb(event_id, photo_count)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"📷 <b>Фотогалерея — {title}</b>\n\n"
        f"Загружено фото: {photo_count}/5",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_add_photo:"))
async def admin_add_photo_start(callback: CallbackQuery, state: FSMContext) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await state.set_state(AddPhoto.waiting_photo)
    await state.update_data(photo_event_id=event_id)
    await callback.message.answer(  # type: ignore[union-attr]
        "📷 Отправьте фотографию для события:",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AddPhoto.waiting_photo, F.photo)
async def admin_add_photo_receive(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data["photo_event_id"]
    photo_id = message.photo[-1].file_id  # type: ignore[index]

    count = await db.count_event_photos(event_id)
    if count >= 5:
        await state.clear()
        await message.answer(
            "❌ Максимум 5 фото на событие.",
            reply_markup=admin_menu_kb(),
        )
        return

    await db.add_event_photo(event_id, photo_id, sort_order=count)
    await state.clear()
    await message.answer(
        f"✅ Фото добавлено ({count + 1}/5).",
        reply_markup=admin_menu_kb(),
    )


@router.message(AddPhoto.waiting_photo)
async def admin_add_photo_invalid(message: Message, state: FSMContext) -> None:
    await message.answer("📷 Отправьте фото или нажмите ❌ Отмена:")


# ══════════════════════════════════════════════════════════════════════
# Admin: Check-in
# ══════════════════════════════════════════════════════════════════════

@router.message(Command("checkin"))
async def cmd_checkin(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore[union-attr]
        await message.answer("⛔ Только для администраторов.")
        return

    parts = message.text.split()  # type: ignore[union-attr]
    if len(parts) < 2:
        await message.answer(
            "Использование: <code>/checkin КОД</code>\n"
            "Пример: <code>/checkin ABC123</code>"
        )
        return

    code = parts[1].strip().upper()
    result = await db.checkin_by_code(code)

    if not result:
        await message.answer(
            f"❌ Код <code>{code}</code> не найден или участник уже отмечен."
        )
        return

    name = f"@{result['username']}" if result.get("username") else f"ID: {result['user_id']}"
    await message.answer(
        f"✅ <b>Чекин успешен!</b>\n\n"
        f"Участник: {name}\n"
        f"Событие: <b>{result['event_title']}</b>"
    )


@router.callback_query(F.data.startswith("admin_checkin_stats:"))
async def admin_checkin_stats(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    stats = await db.get_checkin_stats(event_id)
    text = (
        f"✅ <b>Чекин — {event['title']}</b>\n\n"
        f"Пришли: <b>{stats['attended']}/{stats['total']}</b>\n"
        f"Ожидается: {stats['registered']}\n\n"
        f"Для чекина используйте:\n"
        f"<code>/checkin КОД</code>"
    )

    kb = admin_event_detail_kb(event_id, event["status"])
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: CSV Export
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_export:"))
async def admin_export_csv(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    csv_buffer = await export_participants_csv(event_id)
    filename = f"participants_{event_id}_{event['date']}.csv"

    await callback.message.answer_document(  # type: ignore[union-attr]
        document=BufferedInputFile(csv_buffer.read(), filename=filename),
        caption=f"📥 Список участников — <b>{event['title']}</b>",
    )
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: Event Analytics
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("admin_event_stats:"))
async def admin_event_stats(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    stats = await db.get_event_analytics(event_id)

    text = (
        f"📊 <b>Статистика — {event['title']}</b>\n\n"
        f"✅ Зарегистрировано: {stats['registered']}\n"
        f"🎉 Посетили: {stats['attended']}\n"
        f"❌ Отменили: {stats['cancelled']}\n"
        f"⏳ В очереди: {stats['waitlist']}\n"
    )

    if stats["registered"] + stats["attended"] > 0:
        total = stats["registered"] + stats["attended"]
        rate = round(stats["attended"] / total * 100, 1) if total > 0 else 0
        text += f"\n📈 Посещаемость: {rate}%"

    if stats["avg_rating"]:
        text += f"\n⭐ Рейтинг: {stats['avg_rating']}/5 ({stats['reviews_count']} отзывов)"

    if stats["revenue"] > 0:
        text += f"\n💰 Выручка: {stats['revenue']}₽"

    kb = admin_event_detail_kb(event_id, event["status"])
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ══════════════════════════════════════════════════════════════════════
# Admin: Overall Analytics (/analytics)
# ══════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "admin:analytics")
async def admin_analytics_cb(callback: CallbackQuery) -> None:
    if not _is_admin(callback.from_user.id):  # type: ignore[union-attr]
        await callback.answer("⛔", show_alert=True)
        return
    text = await _format_analytics()
    await callback.message.edit_text(text, reply_markup=admin_panel_kb())  # type: ignore[union-attr]
    await callback.answer()


@router.message(Command("analytics"))
async def cmd_analytics(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore[union-attr]
        await message.answer("⛔ Только для администраторов.")
        return
    text = await _format_analytics()
    await message.answer(text)


async def _format_analytics() -> str:
    data = await db.get_analytics()

    lines = ["📊 <b>Аналитика EventHub</b>\n"]

    # Events stats
    lines.append(f"📋 Всего событий: <b>{data['total_events']}</b>")
    for status, count in data["events_by_status"].items():
        icons = {"active": "✅", "cancelled": "❌", "completed": "✔️"}
        icon = icons.get(status, "")
        lines.append(f"  {icon} {status}: {count}")

    lines.append(f"\n👥 Всего регистраций: <b>{data['total_registrations']}</b>")
    lines.append(f"🎉 Посетили: <b>{data['total_attended']}</b>")
    lines.append(f"📈 Посещаемость: <b>{data['attendance_rate']}%</b>")

    # Popular categories
    if data["popular_categories"]:
        lines.append("\n📂 <b>Популярные категории:</b>")
        for cat in data["popular_categories"]:
            lines.append(f"  {cat['emoji']} {cat['name']}: {cat['count']} регистраций")

    # Revenue by ticket type
    if data["revenue_by_type"]:
        lines.append("\n💰 <b>Выручка по типам билетов:</b>")
        total_revenue = 0
        for rt in data["revenue_by_type"]:
            lines.append(f"  🎫 {rt['name']}: {rt['revenue']}₽ ({rt['sold']} шт.)")
            total_revenue += rt["revenue"]
        lines.append(f"  <b>Итого: {total_revenue}₽</b>")

    return "\n".join(lines)
