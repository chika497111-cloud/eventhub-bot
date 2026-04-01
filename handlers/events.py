import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards.inline import events_list_kb, event_detail_kb

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 5


def _format_event_card(event: dict, reg_count: int, waitlist_count: int) -> str:
    spots = f"{reg_count}/{event['max_participants']}"
    remaining = event["max_participants"] - reg_count
    status_line = f"✅ Свободно мест: {remaining}" if remaining > 0 else f"🔴 Мест нет (в очереди: {waitlist_count})"
    return (
        f"📌 <b>{event['title']}</b>\n\n"
        f"{event['description']}\n\n"
        f"📅 Дата: {event['date']}\n"
        f"🕐 Время: {event['time']}\n"
        f"📍 Место: {event['location']}\n"
        f"👥 Занято мест: {spots}\n"
        f"{status_line}"
    )


@router.message(F.text == "📋 События")
async def show_events(message: Message) -> None:
    await _send_events_page(message, page=0)


@router.callback_query(F.data.startswith("events_page:"))
async def on_events_page(callback: CallbackQuery) -> None:
    page = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    await _send_events_page(callback, page=page)


async def _send_events_page(target: Message | CallbackQuery, page: int) -> None:
    # Auto-complete past events
    await db.mark_completed_events()

    total = await db.count_active_events()
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    events = await db.get_active_events(offset=page * PAGE_SIZE, limit=PAGE_SIZE)

    if not events:
        text = "😔 Пока нет предстоящих событий."
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text)  # type: ignore[union-attr]
            await target.answer()
        else:
            await target.answer(text)
        return

    text = f"📋 <b>Предстоящие события</b> (стр. {page + 1}/{total_pages}):"
    kb = events_list_kb(events, page, total_pages)

    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("event:"))
async def show_event_detail(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    user_id = callback.from_user.id  # type: ignore[union-attr]
    reg_count = await db.get_registration_count(event_id)
    waitlist_count = await db.get_waitlist_count(event_id)
    user_reg = await db.get_user_registration(event_id, user_id)

    is_registered = user_reg is not None and user_reg["status"] == "registered"
    is_waitlisted = user_reg is not None and user_reg["status"] == "waitlist"
    is_full = reg_count >= event["max_participants"]

    text = _format_event_card(event, reg_count, waitlist_count)
    if is_registered:
        text += "\n\n✅ <i>Вы зарегистрированы</i>"
    elif is_waitlisted:
        text += "\n\n⏳ <i>Вы в листе ожидания</i>"

    kb = event_detail_kb(event_id, is_registered, is_waitlisted, is_full)

    if event.get("photo_id"):
        await callback.message.delete()  # type: ignore[union-attr]
        await callback.message.answer_photo(  # type: ignore[union-attr]
            photo=event["photo_id"],
            caption=text,
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("reg:"))
async def register_for_event(callback: CallbackQuery, bot: Bot) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    user_id = callback.from_user.id  # type: ignore[union-attr]
    username = callback.from_user.username  # type: ignore[union-attr]

    result = await db.register_user(event_id, user_id, username)

    if result == "registered":
        await callback.answer("✅ Вы успешно зарегистрированы!", show_alert=True)
    elif result == "waitlist":
        await callback.answer("⏳ Мест нет, вы добавлены в лист ожидания.", show_alert=True)
    elif result == "already":
        await callback.answer("Вы уже зарегистрированы на это событие.", show_alert=True)
        return
    elif result == "event_not_found":
        await callback.answer("Событие не найдено или отменено.", show_alert=True)
        return

    # Refresh event card
    await show_event_detail(callback)


@router.callback_query(F.data.startswith("unreg:"))
async def unregister_from_event(callback: CallbackQuery, bot: Bot) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    user_id = callback.from_user.id  # type: ignore[union-attr]

    promoted = await db.cancel_registration(event_id, user_id)
    await callback.answer("❌ Регистрация отменена.", show_alert=True)

    # Notify promoted user
    if promoted:
        event = await db.get_event(event_id)
        try:
            await bot.send_message(
                promoted["user_id"],
                f"🎉 Освободилось место!\n\n"
                f"Вы перемещены из листа ожидания в участники события "
                f"<b>{event['title']}</b> ({event['date']} {event['time']})",
            )
        except Exception:
            logger.warning("Failed to notify promoted user %s", promoted["user_id"])

    # Refresh event card
    await show_event_detail(callback)
