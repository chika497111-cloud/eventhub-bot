import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from handlers import start, events, my_events, admin
from handlers.search import router as search_router
from handlers.profile import router as profile_router
from handlers.reviews import router as reviews_router
from utils.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    dp.include_routers(
        start.router,
        admin.router,
        search_router,
        reviews_router,
        profile_router,
        events.router,
        my_events.router,
    )

    # Start the scheduler for reminders, recurring events, auto-completion
    sched = setup_scheduler(bot)

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        sched.shutdown(wait=False)
        logger.info("Scheduler shut down")


if __name__ == "__main__":
    asyncio.run(main())
