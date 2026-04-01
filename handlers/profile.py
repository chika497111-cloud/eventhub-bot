import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

import database as db
from keyboards.reply import main_menu_kb

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text == "👤 Профиль")
@router.message(Command("profile"))
async def show_profile(message: Message) -> None:
    user_id = message.from_user.id  # type: ignore[union-attr]
    full_name = message.from_user.full_name  # type: ignore[union-attr]
    username = message.from_user.username  # type: ignore[union-attr]

    stats = await db.get_user_profile_stats(user_id)

    lines = [f"👤 <b>Профиль</b>\n"]

    if username:
        lines.append(f"Имя: {full_name} (@{username})")
    else:
        lines.append(f"Имя: {full_name}")

    lines.append(f"\n📊 <b>Статистика:</b>")
    lines.append(f"📋 Всего регистраций: {stats['total_registrations']}")
    lines.append(f"🎉 Посещено событий: {stats['attended']}")
    lines.append(f"📅 Предстоящих событий: {stats['upcoming']}")

    if stats["avg_rating"]:
        lines.append(f"⭐ Средняя оценка в отзывах: {stats['avg_rating']}/5 ({stats['reviews_count']} отзывов)")

    if stats["favorite_category"]:
        lines.append(f"❤️ Любимая категория: {stats['favorite_category']}")

    # Upcoming events
    upcoming = await db.get_user_upcoming_events(user_id)
    if upcoming:
        lines.append(f"\n📅 <b>Ближайшие события:</b>")
        for ev in upcoming[:5]:
            code_text = f" | Код: <code>{ev['checkin_code']}</code>" if ev.get("checkin_code") else ""
            lines.append(f"  • {ev['title']} — {ev['date']} {ev['time']}{code_text}")

    # Recently attended
    attended = await db.get_user_attended_events(user_id, limit=5)
    if attended:
        lines.append(f"\n🎉 <b>Посещённые:</b>")
        for ev in attended:
            review = await db.get_user_review(ev["id"], user_id)
            review_text = f" ⭐{review['rating']}" if review else " (нет отзыва)"
            lines.append(f"  • {ev['title']} — {ev['date']}{review_text}")

    await message.answer("\n".join(lines), reply_markup=main_menu_kb())
