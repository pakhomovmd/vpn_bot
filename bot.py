"""
Точка входа — запускай этот файл командой: python bot.py
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN
from database.db import init_db
from handlers import start, cabinet, payment, admin, subscription
from services.scheduler import setup_scheduler
from middlewares import SubscriptionCheckMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    # Инициализация бота
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    # Регистрируем middleware для проверки подписки
    dp.message.middleware(SubscriptionCheckMiddleware())
    dp.callback_query.middleware(SubscriptionCheckMiddleware())

    # Регистрируем хэндлеры (порядок важен!)
    dp.include_router(subscription.router)  # Проверка подписки должна быть первой
    dp.include_router(start.router)
    dp.include_router(cabinet.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)

    # Создаём таблицы в БД (если их ещё нет)
    await init_db()
    logger.info("База данных инициализирована")

    # Запускаем планировщик задач
    setup_scheduler(bot)

    # Удаляем старые вебхуки и стартуем polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен. Жду сообщений...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
