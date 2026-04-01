import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards.inline import review_rating_kb
from keyboards.reply import cancel_kb, main_menu_kb

router = Router()
logger = logging.getLogger(__name__)


class ReviewState(StatesGroup):
    waiting_comment = State()


@router.message(Command("review"))
async def cmd_review(message: Message) -> None:
    parts = message.text.split()  # type: ignore[union-attr]
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer(
            "Использование: <code>/review ID_СОБЫТИЯ</code>\n"
            "Пример: <code>/review 5</code>"
        )
        return

    event_id = int(parts[1])
    user_id = message.from_user.id  # type: ignore[union-attr]

    event = await db.get_event(event_id)
    if not event:
        await message.answer("❌ Событие не найдено.")
        return

    if event["status"] != "completed":
        await message.answer("⏳ Отзывы можно оставлять только для завершённых событий.")
        return

    # Check if user was registered
    reg = await db.get_user_registration(event_id, user_id)
    if not reg or reg["status"] not in ("registered", "attended"):
        await message.answer("❌ Вы не были зарегистрированы на это событие.")
        return

    # Check if already reviewed
    existing = await db.get_user_review(event_id, user_id)
    if existing:
        await message.answer(
            f"Вы уже оставили отзыв на это событие (⭐{existing['rating']})."
        )
        return

    kb = review_rating_kb(event_id)
    await message.answer(
        f"⭐ <b>Оценка — {event['title']}</b>\n\n"
        f"Выберите рейтинг от 1 до 5:",
        reply_markup=kb,
    )


@router.callback_query(F.data.startswith("write_review:"))
async def write_review_start(callback: CallbackQuery) -> None:
    event_id = int(callback.data.split(":")[1])  # type: ignore[union-attr]
    user_id = callback.from_user.id  # type: ignore[union-attr]

    event = await db.get_event(event_id)
    if not event:
        await callback.answer("Событие не найдено", show_alert=True)
        return

    if event["status"] != "completed":
        await callback.answer("Отзывы доступны только для завершённых событий", show_alert=True)
        return

    # Check existing review
    existing = await db.get_user_review(event_id, user_id)
    if existing:
        await callback.answer(f"Вы уже оставили отзыв (⭐{existing['rating']})", show_alert=True)
        return

    # Check registration
    reg = await db.get_user_registration(event_id, user_id)
    if not reg or reg["status"] not in ("registered", "attended"):
        await callback.answer("Вы не были на этом событии", show_alert=True)
        return

    kb = review_rating_kb(event_id)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"⭐ <b>Оценка — {event['title']}</b>\n\n"
        f"Выберите рейтинг от 1 до 5:",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rate:"))
async def on_rate(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")  # type: ignore[union-attr]
    event_id = int(parts[1])
    rating = int(parts[2])

    await state.set_state(ReviewState.waiting_comment)
    await state.update_data(review_event_id=event_id, review_rating=rating)

    stars = "⭐" * rating
    await callback.message.answer(  # type: ignore[union-attr]
        f"Ваша оценка: {stars}\n\n"
        f"Напишите комментарий к отзыву (или /skip чтобы оставить без комментария):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(ReviewState.waiting_comment)
async def review_comment(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data["review_event_id"]
    rating = data["review_rating"]
    user_id = message.from_user.id  # type: ignore[union-attr]

    text = (message.text or "").strip()
    comment = None if text.lower() in ("/skip", "⏩ пропустить", "") else text

    try:
        await db.create_review(event_id, user_id, rating, comment)
        await state.clear()

        stars = "⭐" * rating
        await message.answer(
            f"✅ Спасибо за отзыв!\n\n{stars}\n{comment or 'Без комментария'}",
            reply_markup=main_menu_kb(),
        )
    except Exception as e:
        await state.clear()
        await message.answer(
            "❌ Не удалось сохранить отзыв. Возможно, вы уже оставляли отзыв.",
            reply_markup=main_menu_kb(),
        )
