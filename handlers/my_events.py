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
    checkin_line = ""
    if reg:
        if reg["status"] == "registered":
            reg_status = "\n\n✅ <i>Вы зарегистрированы</i>"
        elif reg["status"] == "waitlist":
            reg_status = "\n\n⏳ <i>Вы в листе ожидания</i>"
        elif reg["status"] == "attended":
            reg_status = "\n\n🎉 <i>Вы посетили это событие</i>"

        if reg.get("checkin_code") and reg["status"] in ("registered",):
            checkin_line = f"\n🔑 Код для чекина: <code>{reg['checkin_code']}</code>"

    # Ticket type info
    ticket_line = ""
    if reg and reg.get("ticket_type_id"):
        tt = await db.get_ticket_type(reg["ticket_type_id"])
        if tt:
            price_text = f"{tt['price']}₽" if tt["price"] > 0 else "Бесплатно"
            ticket_line = f"\n🎫 Билет: {tt['name']} ({price_text})"

    reg_count = await db.get_registration_count(event_id)
    text = (
        f"📌 <b>{event['title']}</b>\n\n"
        f"📅 {event['date']}  🕐 {event['time']}\n"
        f"📍 {event['location']}\n"
        f"👥 {reg_count}/{event['max_participants']}"
        f"{ticket_line}"
        f"{reg_status}"
        f"{checkin_line}"
    )

    kb = my_event_detail_kb(event_id)
    await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()
