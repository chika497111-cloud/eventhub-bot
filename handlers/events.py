import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

import database as db
from keyboards.inline import (
    events_list_kb, event_detail_kb, ticket_types_kb,
    categories_filter_kb, category_events_kb, reviews_list_kb,
)

router = Router()
logger = logging.getLogger(__name__)

PAGE_SIZE = 5


def _format_event_card(event: dict, reg_count: int, waitlist_count: int, category: dict | None = None) -> str:
    spots = f"{reg_count}/{event['max_participants']}"
    remaining = event["max_participants"] - reg_count
    status_line = f"✅ Свободно мест: {remaining}" if remaining > 0 else f"🔴 Мест нет (в очереди: {waitlist_count})"

    cat_line = ""
    if category:
        cat_line = f"📂 Категория: {category['emoji']} {category['name']}\n"

    recurrence_line = ""
    rec = event.get("recurrence_type")
    if rec:
        labels = {"weekly": "Еженедельно", "biweekly": "Раз в 2 недели", "monthly": "Ежемесячно"}
        recurrence_line = f"🔄 Повторение: {labels.get(rec, rec)}\n"

    return (
        f"📌 <b>{event['title']}</b>\n\n"
        f"{event['description']}\n\n"
        f"📅 Дата: {event['date']}\n"
        f"🕐 Время: {event['time']}\n"
        f"📍 Место: {event['location']}\n"
        f"{cat_line}"
        f"{recurrence_line}"
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


# ── Event detail ──────────────────────────────────────────────────

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

    is_registered = user_reg is not None and user_reg["status"] in ("registered", "attended")
    is_waitlisted = user_reg is not None and user_reg["status"] == "waitlist"
    is_full = reg_count >= event["max_participants"]

    # Get category
    category = None
    if event.get("category_id"):
        category = await db.get_category(event["category_id"])

    # Check for ticket types
    ticket_types = await db.get_ticket_types(event_id)
    has_ticket_types = len(ticket_types) > 0

    # Check for photos
    photo_count = await db.count_event_photos(event_id)
    has_photos = photo_count > 0

    # Average rating
    avg_rating = await db.get_event_avg_rating(event_id)

    text = _format_event_card(event, reg_count, waitlist_count, category)

    # Ticket types info
    if ticket_types:
        text += "\n\n🎫 <b>Типы билетов:</b>"
        for tt in ticket_types:
            remaining = tt["max_count"] - tt["sold_count"]
            price_text = f"{tt['price']}₽" if tt["price"] > 0 else "Бесплатно"
            text += f"\n  • {tt['name']} — {price_text} (осталось: {remaining})"

    if is_registered:
        text += "\n\n✅ <i>Вы зарегистрированы</i>"
        if user_reg and user_reg.get("checkin_code"):
            text += f"\n🔑 Код для чекина: <code>{user_reg['checkin_code']}</code>"
    elif is_waitlisted:
        text += "\n\n⏳ <i>Вы в листе ожидания</i>"

    kb = event_detail_kb(
        event_id, is_registered, is_waitlisted, is_full,
        has_ticket_types=has_ticket_types and not is_registered and not is_waitlisted,
        has_photos=has_photos,
        avg_rating=avg_rating,
    )

    # Try to edit, handle photo case
    try:
        if event.get("photo_id"):
            await callback.message.delete()  # type: ignore[union-attr]
            await callback.message.answer_photo(  # type: ignore[union-attr]
                photo=event["photo_id"],
                caption=text,
                reply_markup=kb,
            )
        else:
            await callback.message.edit_text(text, reply_markup=kb)  # type: ignore[union-attr]
    except Exception:
        await callback.message.answer(text, reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()


# ── Ticket selection ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("tickets:"))
async def show_ticket_types(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    ticket_types = await db.get_ticket_types(event_id)
    if not ticket_types:
        await callback.answer("Нет доступных типов билетов", show_alert=True)
        return
    kb = ticket_types_kb(event_id, ticket_types)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🎫 <b>Выберите тип билета:</b>", reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("buy_ticket:"))
async def buy_ticket(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")  # type: ignore[union-attr]
    event_id = int(parts[1])
    ticket_type_id = int(parts[2])

    tt = await db.get_ticket_type(ticket_type_id)
    if not tt or tt["sold_count"] >= tt["max_count"]:
        await callback.answer("😔 Этот тип билета распродан", show_alert=True)
        return

    user_id = callback.from_user.id  # type: ignore[union-attr]
    username = callback.from_user.username  # type: ignore[union-attr]
    full_name = callback.from_user.full_name  # type: ignore[union-attr]

    result = await db.register_user(event_id, user_id, username, full_name, ticket_type_id)

    if result == "registered":
        price_text = f" ({tt['price']}₽)" if tt["price"] > 0 else ""
        await callback.answer(
            f"✅ Вы зарегистрированы! Билет: {tt['name']}{price_text}",
            show_alert=True,
        )
    elif result == "waitlist":
        await callback.answer("⏳ Мест нет, вы добавлены в лист ожидания.", show_alert=True)
    elif result == "already":
        await callback.answer("Вы уже зарегистрированы на это событие.", show_alert=True)
        return
    elif result == "ticket_sold_out":
        await callback.answer("😔 Этот тип билета распродан", show_alert=True)
        return
    elif result == "event_not_found":
        await callback.answer("Событие не найдено или отменено.", show_alert=True)
        return

    # Refresh event card
    callback.data = f"event:{event_id}"  # type: ignore[assignment]
    await show_event_detail(callback)


# ── Registration (simple, without ticket types) ──────────────────

@router.callback_query(F.data.startswith("reg:"))
async def register_for_event(callback: CallbackQuery, bot: Bot) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    user_id = callback.from_user.id  # type: ignore[union-attr]
    username = callback.from_user.username  # type: ignore[union-attr]
    full_name = callback.from_user.full_name  # type: ignore[union-attr]

    result = await db.register_user(event_id, user_id, username, full_name)

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
    callback.data = f"event:{event_id}"  # type: ignore[assignment]
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
    callback.data = f"event:{event_id}"  # type: ignore[assignment]
    await show_event_detail(callback)


# ── Categories filter ─────────────────────────────────────────────

@router.callback_query(F.data == "filter:categories")
async def show_categories_filter(callback: CallbackQuery) -> None:
    categories = await db.get_categories()
    if not categories:
        await callback.answer("Категории ещё не созданы", show_alert=True)
        return
    kb = categories_filter_kb(categories)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📂 <b>Выберите категорию:</b>", reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_filter:"))
async def show_events_by_category(callback: CallbackQuery) -> None:
    category_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    category = await db.get_category(category_id)
    events = await db.get_active_events_by_category(category_id, limit=20)

    if not events:
        await callback.answer("В этой категории нет событий", show_alert=True)
        return

    cat_name = f"{category['emoji']} {category['name']}" if category else "Категория"
    kb = category_events_kb(events, category_id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"📂 <b>{cat_name}</b> — {len(events)} событий:", reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "filter:popular")
async def show_popular_events(callback: CallbackQuery) -> None:
    events = await db.get_popular_events(limit=10)
    if not events:
        await callback.answer("Пока нет событий", show_alert=True)
        return

    from keyboards.inline import search_results_kb
    kb = search_results_kb(events)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔥 <b>Популярные события:</b>", reply_markup=kb,
    )
    await callback.answer()


# ── Photos gallery ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("photos:"))
async def show_event_photos(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    photos = await db.get_event_photos(event_id)

    if not photos:
        await callback.answer("Нет фотографий", show_alert=True)
        return

    event = await db.get_event(event_id)
    title = event["title"] if event else "Событие"

    if len(photos) == 1:
        await callback.message.answer_photo(  # type: ignore[union-attr]
            photo=photos[0]["photo_id"],
            caption=f"📷 Фото — <b>{title}</b>",
        )
    else:
        media = []
        for i, photo in enumerate(photos):
            caption = f"📷 Фото — <b>{title}</b> ({i+1}/{len(photos)})" if i == 0 else ""
            media.append(InputMediaPhoto(media=photo["photo_id"], caption=caption))
        await callback.message.answer_media_group(media=media)  # type: ignore[union-attr]

    await callback.answer()


# ── Reviews ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reviews:"))
async def show_event_reviews(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    reviews = await db.get_event_reviews(event_id)
    avg_rating = await db.get_event_avg_rating(event_id)
    event = await db.get_event(event_id)
    title = event["title"] if event else "Событие"

    lines = [f"⭐ <b>Отзывы — {title}</b>"]
    if avg_rating:
        lines.append(f"Средняя оценка: {'⭐' * round(avg_rating)} ({avg_rating}/5)")
    lines.append(f"Всего отзывов: {len(reviews)}\n")

    for rev in reviews[:10]:
        stars = "⭐" * rev["rating"]
        comment = rev.get("comment") or "Без комментария"
        lines.append(f"{stars}\n{comment}\n")

    kb = reviews_list_kb(event_id)
    await callback.message.edit_text("\n".join(lines), reply_markup=kb)  # type: ignore[union-attr]
    await callback.answer()
