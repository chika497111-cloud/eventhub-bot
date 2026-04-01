import logging

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards.inline import my_events_kb, my_event_detail_kb

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "🎟 Мои регистрации")
async def show_my_events(message: Message) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    regs = await db.get_user_registrations(user_id)

    if not regs:
        await message.answer("У вас пока нет регистраций.")
        return

    text = "🎟 <b>Ваши регистрации:</b>"
    kb = my_events_kb(regs)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "my_events")
async def show_my_events_cb(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id  # type: ignore[union-attr]
    regs = await db.get_user_registrations(user_id)

    if not regs:
        await callback.message.edit_text("У вас пока нет регистраций.")  # type: ignore[union-attr]
        await callback.answer()
        return

    text = "🎟 <b>Ваши регистрации:</b>"
    kb = my_events_kb(regs)
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


@router.callback_query(F.data.startswith("myevent:"))
async def show_my_event_detail(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    user_id = callback.from_user.id  # type: ignore[union-attr]

    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    reg = await db.get_user_registration(event_id, user_id)
    reg_status = ""
    if reg:
        if reg["status"] == "registered":
            reg_status = "\n\n✅ <i>Вы зарегистрированы</i>"
        elif reg["status"] == "waitlist":
            reg_status = "\n\n⏳ <i>Вы в листе ожидания</i>"

    reg_count = await db.get_registration_count(event_id)
    text = (
        f"📌 <b>{event['title']}</b>\n\n"
        f"📅 {event['date']}  🕐 {event['time']}\n"
        f"📍 {event['location']}\n"
        f"👥 {reg_count}/{event['max_participants']}"
        f"{reg_status}"
    )

    kb = my_event_detail_kb(event_id)
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()
