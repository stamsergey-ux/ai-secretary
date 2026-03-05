"""AI Secretary for Board of Directors — Telegram Bot."""

import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.database import init_db
from app.handlers import onboarding, protocol, tasks, chat
from app.scheduler import run_scheduler


async def main():
    # Init database
    os.makedirs("data", exist_ok=True)
    await init_db()

    # Init bot
    bot = Bot(
        token=os.getenv("BOT_TOKEN"),
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()

    # Register handlers (order matters — chat is catch-all, must be last)
    dp.include_router(onboarding.router)
    dp.include_router(protocol.router)
    dp.include_router(tasks.router)
    dp.include_router(chat.router)  # Must be last — catches all text messages

    # Start scheduler in background
    asyncio.create_task(run_scheduler(bot))

    print("Bot started!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
