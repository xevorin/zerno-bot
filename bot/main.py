"""Точка входа: python -m bot.main"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import load_settings
from bot.db import OrderStore
from bot.handlers import router
from bot.logic import load_menu


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    menu = load_menu(settings.menu_path)
    store = OrderStore(settings.db_path)
    await store.init()

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Меню и новый заказ"),
            BotCommand(command="cancel", description="Очистить корзину"),
        ]
    )
    logging.info("Бот «%s» запущен, позиций в меню: %d", menu.shop, sum(len(c.items) for c in menu.categories))
    await dp.start_polling(bot, menu=menu, store=store, settings=settings)


if __name__ == "__main__":
    asyncio.run(main())
