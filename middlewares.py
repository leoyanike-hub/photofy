from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from config import CHANNEL_ID
import database as db
from keyboards import subscription_keyboard

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

        # Проверяем подписку
        try:
            chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            is_member = chat_member.status in ["member", "creator", "administrator"]
        except TelegramBadRequest:
            is_member = False

        if is_member:
            # Если пользователь ещё не отмечен как подписанный – отмечаем (без начисления монет)
            if not db.is_subscribed(user_id):
                db.set_subscribed(user_id)
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
