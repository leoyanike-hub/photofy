import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, API_ROOT
from handlers import router, yookassa_webhook
from middlewares import SubscriptionMiddleware
from database import init_db
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Если используется BotGate – раскомментируйте следующую строку ===
# API_ROOT = "https://bot-gate.ru/"   # или укажите в .env

async def handle_webhook(request):
    return await yookassa_webhook(request)

async def start_web_server():
    app = web.Application()
    app.router.add_post('/webhook/yookassa', handle_webhook)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Webhook сервер запущен на порту 8080")

async def main():
    init_db()
    start_scheduler()

    # Создаём бота – если есть API_ROOT (BotGate), подставляем его, иначе direct
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        api_root=API_ROOT if API_ROOT and API_ROOT != "https://api.telegram.org" else None
    )
    dp = Dispatcher()
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    dp.include_router(router)

    # Запускаем webhook-сервер (для ЮKassa)
    web_task = asyncio.create_task(start_web_server())

    logger.info("Бот запущен и готов к работе!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
