import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

import database as db
from keyboards.inline import search_results_kb, search_type_kb
from keyboards.reply import cancel_kb, main_menu_kb

router = Router()
logger = logging.getLogger(__name__)


class SearchState(StatesGroup):
    waiting_text = State()
    waiting_date_from = State()
    waiting_date_to = State()


@router.message(F.text == "🔍 Поиск")
@router.message(Command("search"))
async def search_menu(message: Message) -> None:
    kb = search_type_kb()
    await message.answer("🔍 <b>Поиск событий</b>\n\nВыберите способ поиска:", reply_markup=kb)


@router.callback_query(F.data == "search:text")
async def search_text_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchState.waiting_text)
    await callback.message.answer(  # type: ignore[union-attr]
        "🔍 Введите текст для поиска (название или описание):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(SearchState.waiting_text)
async def search_text_execute(message: Message, state: FSMContext) -> None:
    query = message.text.strip()  # type: ignore[union-attr]
    await state.clear()

    events = await db.search_events(query, limit=15)
    if not events:
        await message.answer(
            f"😔 По запросу «{query}» ничего не найдено.",
            reply_markup=main_menu_kb(),
        )
        return

    kb = search_results_kb(events)
    await message.answer(
        f"🔍 Найдено <b>{len(events)}</b> событий по запросу «{query}»:",
        reply_markup=kb,
    )


@router.callback_query(F.data == "search:dates")
async def search_dates_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SearchState.waiting_date_from)
    await callback.message.answer(  # type: ignore[union-attr]
        "📅 Введите начальную дату (формат: <b>ГГГГ-ММ-ДД</b>):",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(SearchState.waiting_date_from)
async def search_date_from(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте <b>ГГГГ-ММ-ДД</b>:")
        return
    await state.update_data(date_from=text)
    await state.set_state(SearchState.waiting_date_to)
    await message.answer("📅 Введите конечную дату (формат: <b>ГГГГ-ММ-ДД</b>):")


@router.message(SearchState.waiting_date_to)
async def search_date_to(message: Message, state: FSMContext) -> None:
    text = message.text.strip()  # type: ignore[union-attr]
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте <b>ГГГГ-ММ-ДД</b>:")
        return

    data = await state.get_data()
    date_from = data["date_from"]
    date_to = text
    await state.clear()

    events = await db.search_events_by_date_range(date_from, date_to, limit=20)
    if not events:
        await message.answer(
            f"😔 Нет событий с {date_from} по {date_to}.",
            reply_markup=main_menu_kb(),
        )
        return

    kb = search_results_kb(events)
    await message.answer(
        f"📅 Найдено <b>{len(events)}</b> событий с {date_from} по {date_to}:",
        reply_markup=kb,
    )
