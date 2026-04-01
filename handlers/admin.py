import logging
from datetime import datetime

from aiogram import Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
import database as db
from keyboards.inline import (
    admin_panel_kb,
    admin_events_kb,
    admin_event_detail_kb,
    admin_edit_event_kb,
    confirm_cancel_event_kb,
)
from keyboards.reply import admin_menu_kb, cancel_kb

router = Router()
logger = logging.getLogger(__name__)


# ── FSM States ──────────────────────────────────────────────────────

class CreateEvent(StatesGroup):
    title = State()
    description = State()
    date = State()
    time = State()
    location = State()
    max_participants = State()
    photo = State()


class EditField(StatesGroup):
    waiting_value = State()


class BroadcastState(StatesGroup):
    waiting_message = State()


# ── Middleware-like admin check ─────────────────────────────────────

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ── Admin panel entry ──────────────────────────────────────────────

@router.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: Message) -> None:
    if not _is_admin(message.from_user.id):  # type: ignore[union-attr]
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("⚙️ <b>Админ-панель</b>", reply_markup=admin_panel_kb())


# ── Create Event FSM ───────────────────────────────────────────────

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


@router.message(F.text == "❌ Отмена", StateFilter("*"))
async def cancel_fsm(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=admin_menu_kb())


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
    await state.set_state(CreateEvent.photo)
    await message.answer(
        "📷 Отправьте фото для события или нажмите /skip чтобы пропустить:"
    )


@router.message(CreateEvent.photo, F.photo)
async def create_event_photo(message: Message, state: FSMContext) -> None:
    photo_id = message.photo[-1].file_id  # type: ignore[index]
    await state.update_data(photo_id=photo_id)
    await _save_event(message, state)


@router.message(CreateEvent.photo, F.text.casefold() == "/skip")
async def create_event_skip_photo(message: Message, state: FSMContext) -> None:
    await state.update_data(photo_id=None)
    await _save_event(message, state)


@router.message(CreateEvent.photo)
async def create_event_photo_invalid(message: Message, state: FSMContext) -> None:
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
    )
    await state.clear()
    await message.answer(
        f"✅ Событие <b>{data['title']}</b> создано! (ID: {event_id})",
        reply_markup=admin_menu_kb(),
    )
    logger.info("Event created: id=%s title=%s", event_id, data["title"])


# ── Admin: list events ─────────────────────────────────────────────

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


# ── Admin: event detail ────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_event:"))
async def admin_event_detail(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    reg_count = await db.get_registration_count(event_id)
    waitlist_count = await db.get_waitlist_count(event_id)

    text = (
        f"📌 <b>{event['title']}</b>\n\n"
        f"{event['description']}\n\n"
        f"📅 {event['date']}  🕐 {event['time']}\n"
        f"📍 {event['location']}\n"
        f"👥 {reg_count}/{event['max_participants']} (в очереди: {waitlist_count})\n"
        f"Статус: <b>{event['status']}</b>"
    )

    kb = admin_event_detail_kb(event_id, event["status"])
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ── Admin: edit event ──────────────────────────────────────────────

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
    await message.answer(
        f"✅ Поле обновлено.",
        reply_markup=admin_menu_kb(),
    )


# ── Admin: cancel event ───────────────────────────────────────────

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


# ── Admin: participants ────────────────────────────────────────────

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
            name = f"@{p['username']}" if p["username"] else f"ID: {p['user_id']}"
            lines.append(f"  {i}. {name}")
    else:
        lines.append("Пока никто не зарегистрирован.")

    if waitlist:
        lines.append(f"\n<b>Лист ожидания ({len(waitlist)}):</b>")
        for i, w in enumerate(waitlist, 1):
            name = f"@{w['username']}" if w["username"] else f"ID: {w['user_id']}"
            lines.append(f"  {i}. {name}")

    from keyboards.inline import admin_event_detail_kb
    kb = admin_event_detail_kb(event_id, event["status"])
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ── Admin: broadcast ───────────────────────────────────────────────

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
