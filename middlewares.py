from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from config import CHANNEL_ID
from keyboards import subscription_keyboard
import sqlite3
import os

# Путь к БД (если не определён в database, определяем здесь)
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
DB_PATH = os.path.join(DATA_DIR, 'users.db')

class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        # Проверяем подписку через Telegram API
        try:
            chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            is_member = chat_member.status in ["member", "creator", "administrator"]
        except TelegramBadRequest:
            is_member = False

        # Если подписан – проверяем и обновляем статус в БД
        if is_member:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            if not result or not result[0]:
                cursor.execute("UPDATE users SET subscribed = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
            conn.close()
            return await handler(event, data)

        # Не подписан – просим
        if isinstance(event, Message):
            await event.answer(
                "❗ Чтобы пользоваться ботом, подпишитесь на наш канал!\n\n"
                "После подписки нажмите «✅ Я подписался».",
                reply_markup=subscription_keyboard()
            )
        elif isinstance(event, CallbackQuery):
            await event.message.edit_text(
                "❗ Чтобы пользоваться ботом, подпишитесь на наш канал!\n\n"
                "После подписки нажмите «✅ Я подписался».",
                reply_markup=subscription_keyboard()
            )
            await event.answer()
        return
