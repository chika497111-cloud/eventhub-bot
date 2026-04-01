import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from config import ADMIN_IDS
from keyboards.reply import main_menu_kb, admin_menu_kb

router = Router()
logger = logging.getLogger(__name__)


def _get_menu(user_id: int):
    return admin_menu_kb() if user_id in ADMIN_IDS else main_menu_kb()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 <b>Добро пожаловать в EventHub!</b>\n\n"
        "Я помогу вам находить интересные события и регистрироваться на них.\n\n"
        "Используйте меню ниже для навигации.",
        reply_markup=_get_menu(message.from_user.id),  # type: ignore[union-attr]
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message) -> None:
    text = (
        "ℹ️ <b>Справка по EventHub Bot</b>\n\n"
        "📋 <b>События</b> — просмотр предстоящих мероприятий\n"
        "🎟 <b>Мои регистрации</b> — ваши текущие регистрации\n\n"
        "<b>Как это работает:</b>\n"
        "1. Откройте список событий\n"
        "2. Выберите интересное мероприятие\n"
        "3. Нажмите кнопку регистрации\n"
        "4. Готово! Вы зарегистрированы\n\n"
        "Если мест нет — можно встать в лист ожидания. "
        "Вы автоматически займёте место, если кто-то отменит регистрацию."
    )
    await message.answer(text, reply_markup=_get_menu(message.from_user.id))  # type: ignore[union-attr]
