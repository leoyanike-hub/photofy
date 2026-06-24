import logging
import os
import json
from datetime import datetime, timedelta
from aiogram import Router, F, types, Bot
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, BufferedInputFile, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

import database as db
from image_generator import generate_image
from keyboards import (
    main_menu_keyboard,
    subscription_keyboard,
    back_keyboard,
    generate_confirm_keyboard,
    buy_menu_keyboard,
    tariffs_keyboard,
    choose_model_keyboard,
    agreement_keyboard,
    subscription_tariffs_keyboard
)
from config import (
    FREE_CREDITS, SUBSCRIBE_BONUS,
    COST_GEMINI_25, COST_GEMINI_31,
    MODEL_GEMINI_25, MODEL_GEMINI_31,
    BONUS_TASK, ADMIN_IDS, CHANNEL_ID,
    PAYMENT_TOKEN, TARIFFS,
    SUBSCRIPTION_TARIFFS,
    PRO_DAILY_BONUS,
    PRO_SUBSCRIPTION_DURATION,
    BOT_TOKEN
)
from yookassa_integration import create_payment

router = Router()
logger = logging.getLogger(__name__)

# === FSM ===
class ModelSelection(StatesGroup):
    choosing_model = State()

class GenerateStates(StatesGroup):
    waiting_for_photo_and_prompt = State()

class TaskStates(StatesGroup):
    waiting_for_first_link = State()
    waiting_for_second_link = State()
    waiting_for_third_link = State()

# === Вспомогательная функция проверки подписки ===
async def check_subscription(bot, user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ["member", "creator", "administrator"]
    except TelegramBadRequest as e:
        logger.warning(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

# === /start с проверкой оферты ===
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"

    if not db.has_agreed(user_id):
        await message.answer(
            "📋 *Добро пожаловать в AvatarGen AI!*\n\n"
            "Перед началом работы пожалуйста ознакомьтесь с условиями:\n\n"
            "• Генерация изображений происходит с помощью нейросетей.\n"
            "• Результат не гарантирует точное исполнение запроса.\n"
            "• Ответственность за коммерческое использование лежит на вас.\n"
            "• Оплата является окончательной, возврат не осуществляется.\n\n"
            "📄 Полный текст оферты доступен по ссылке.\n\n"
            "✅ Нажимая «Принимаю», вы соглашаетесь с условиями.",
            parse_mode="Markdown",
            reply_markup=agreement_keyboard()
        )
        return

    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id, username)

    is_member = await check_subscription(message.bot, user_id)
    if is_member:
        await show_main_menu(message, state)
    else:
        await message.answer(
            "🔐 *Для доступа к боту подпишитесь на наш канал!*",
            parse_mode="Markdown",
            reply_markup=subscription_keyboard()
        )
    await state.clear()

# === Обработчик принятия оферты ===
@router.callback_query(F.data == "accept_offer")
async def cb_accept_offer(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    db.set_agreed(user_id)
    user = db.get_user(user_id)
    if not user:
        db.create_user(user_id, callback.from_user.username or "без username")

    await callback.message.edit_text(
        "✅ *Спасибо!* Вы приняли условия оферты.\n\n"
        "Теперь подпишитесь на наш канал, чтобы начать пользоваться ботом.",
        parse_mode="Markdown",
        reply_markup=subscription_keyboard()
    )
    await callback.answer()

# === Команда /restart ===
@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext):
    await state.clear()
    await cmd_start(message, state)

# === Вспомогательная функция для показа главного меню ===
async def show_main_menu(target, state: FSMContext):
    user_id = target.from_user.id
    credits = db.get_credits(user_id)
    sub = db.get_subscription(user_id)
    pro_active = sub and sub["is_active"]
    text = (
        f"👤 *{target.from_user.first_name}*\n"
        f"└ Баланс: `{credits}` AI Coin\n"
        f"└ Статус: {'🌟 PRO' if pro_active else 'Бесплатный'}\n\n"
        f"Выберите действие:"
    )
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        await target.answer()
    else:
        await target.answer(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    await state.clear()

# === Проверка подписки ===
@router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    bot = callback.bot

    is_member = await check_subscription(bot, user_id)

    if is_member:
        if not db.is_subscribed(user_id):
            db.set_subscribed(user_id)
        credits = db.get_credits(user_id)
        await callback.message.edit_text(
            f"✅ *Подписка подтверждена!*\n"
            f"Доступ к боту открыт.\n"
            f"Ваш баланс: `{credits}` AI Coin.",
            parse_mode="Markdown"
        )
        await show_main_menu(callback, state)
    else:
        await callback.answer(
            "❌ Вы ещё не подписались или бот не является администратором канала.\n"
            "Пожалуйста, подпишитесь и нажмите снова.",
            show_alert=True
        )
    await callback.answer()

# === Кнопка "Назад" ===
@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery, state: FSMContext):
    await show_main_menu(callback, state)

# === Кнопка "Сгенерировать" ===
@router.callback_query(F.data == "generate")
async def cb_generate(callback: CallbackQuery, state: FSMContext):
    text = (
        "🎨 *Выберите модель для генерации*\n\n"
        "Мы предлагаем две мощные нейросети:\n\n"
        "1️⃣ *Gemini 2.5 Nano Banana* — отличное качество, быстрая генерация.\n"
        f"   Стоимость: `{COST_GEMINI_25} AI Coin`\n\n"
        "2️⃣ *Gemini 3.1 Nano Banana 2* — улучшенная версия, лучше детализация, "
        "более точное следование промпту, более яркие и реалистичные изображения.\n"
        f"   Стоимость: `{COST_GEMINI_31} AI Coin`\n\n"
        "Выберите подходящую модель:"
    )
    await callback.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=choose_model_keyboard()
    )
    await state.update_data(bot_message_id=callback.message.message_id, chat_id=callback.message.chat.id)
    await state.set_state(ModelSelection.choosing_model)
    await callback.answer()

# === Выбор модели Gemini 2.5 ===
@router.callback_query(ModelSelection.choosing_model, F.data == "model_gemini_25")
async def cb_model_gemini_25(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    credits = db.get_credits(user_id)
    if credits < COST_GEMINI_25:
        await callback.message.edit_text(
            f"❌ *Недостаточно средств!*\n"
            f"Для генерации на модели *Gemini 2.5 Nano Banana* нужно {COST_GEMINI_25} AI Coin.\n"
            f"Ваш баланс: `{credits}` AI Coin.\n\n"
            f"Пополните баланс через раздел «💰 Пополнить» или выполните задания.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
        await callback.answer()
        return

    await state.update_data(model=MODEL_GEMINI_25, cost=COST_GEMINI_25)
    await state.set_state(GenerateStates.waiting_for_photo_and_prompt)
    await callback.message.edit_text(
        f"📸 *Отправьте фото и промпт в одном сообщении*\n\n"
        f"Вы выбрали модель *Gemini 2.5 Nano Banana* (стоимость {COST_GEMINI_25} AI Coin).\n\n"
        f"Пришлите **фото**, которое хотите обработать, и в подписи к нему напишите **текстовый промпт**.\n"
        f"Пример: фото вашего портрета + подпись *«сделай меня в стиле киберпанк»*.\n\n"
        f"💡 Готовые промпты ищите в нашем канале https://t.me/PhotofyAi.\n\n"
        f"После отправки нажмите кнопку «Сгенерировать».",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )
    await callback.answer()

# === Выбор модели Gemini 3.1 ===
@router.callback_query(ModelSelection.choosing_model, F.data == "model_gemini_31")
async def cb_model_gemini_31(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    credits = db.get_credits(user_id)
    if credits < COST_GEMINI_31:
        await callback.message.edit_text(
            f"❌ *Недостаточно средств!*\n"
            f"Для генерации на модели *Gemini 3.1 Nano Banana 2* нужно {COST_GEMINI_31} AI Coin.\n"
            f"Ваш баланс: `{credits}` AI Coin.\n\n"
            f"Пополните баланс через раздел «💰 Пополнить» или выполните задания.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
        await callback.answer()
        return

    await state.update_data(model=MODEL_GEMINI_31, cost=COST_GEMINI_31)
    await state.set_state(GenerateStates.waiting_for_photo_and_prompt)
    await callback.message.edit_text(
        f"📸 *Отправьте фото и промпт в одном сообщении*\n\n"
        f"Вы выбрали модель *Gemini 3.1 Nano Banana 2* (стоимость {COST_GEMINI_31} AI Coin).\n"
        f"Эта модель даёт более качественные и детализированные изображения.\n\n"
        f"Пришлите **фото**, которое хотите обработать, и в подписи к нему напишите **текстовый промпт**.\n"
        f"Пример: фото вашего портрета + подпись *«сделай меня в стиле киберпанк»*.\n\n"
        f"💡 Готовые промпты ищите в нашем канале https://t.me/PhotofyAi.\n\n"
        f"После отправки нажмите кнопку «Сгенерировать».",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )
    await callback.answer()

# === Получение фото и промпта ===
@router.message(GenerateStates.waiting_for_photo_and_prompt, F.photo)
async def handle_photo_and_prompt(message: Message, state: FSMContext):
    photo = message.photo[-1]
    prompt = message.caption or ""
    if not prompt.strip():
        await message.answer("❌ Вы не написали промпт. Пожалуйста, добавьте текстовое описание в подписи к фото.")
        return

    await state.update_data(photo_file_id=photo.file_id, prompt=prompt)

    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")
    chat_id = data.get("chat_id")

    if bot_message_id and chat_id:
        await message.bot.edit_message_text(
            chat_id=chat_id,
            message_id=bot_message_id,
            text=(
                f"✅ *Фото и промпт приняты!*\n\n"
                f"Промпт: `{prompt[:100]}{'...' if len(prompt)>100 else ''}`\n\n"
                f"Теперь нажмите кнопку «Сгенерировать»."
            ),
            parse_mode="Markdown",
            reply_markup=generate_confirm_keyboard()
        )
    else:
        await message.answer(
            f"✅ *Фото и промпт приняты!*\n\n"
            f"Теперь нажмите кнопку «Сгенерировать».",
            parse_mode="Markdown",
            reply_markup=generate_confirm_keyboard()
        )

# ========== ИСПРАВЛЕННАЯ ФУНКЦИЯ ПОДТВЕРЖДЕНИЯ ГЕНЕРАЦИИ ==========
@router.callback_query(F.data == "confirm_generate")
async def cb_confirm_generate(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    if "photo_file_id" not in data or "prompt" not in data or "model" not in data:
        await callback.answer("Сначала отправьте фото с промптом!", show_alert=True)
        return

    model = data["model"]
    cost = data["cost"]
    photo_file_id = data["photo_file_id"]
    prompt = data["prompt"]

    credits = db.get_credits(user_id)
    if credits < cost:
        await callback.answer(f"Недостаточно средств! Нужно {cost} AI Coin.", show_alert=True)
        return

    # Списываем монеты
    for _ in range(cost):
        db.spend_credit(user_id)

    await callback.message.edit_text("⏳ *Генерация началась...*", parse_mode="Markdown")
    await callback.answer()

    # Скачиваем фото пользователя и преобразуем в bytes
    try:
        file = await callback.bot.get_file(photo_file_id)
        file_bytes_io = await callback.bot.download_file(file.file_path)
        image_bytes = file_bytes_io.read()   # <-- преобразуем BytesIO в bytes
    except Exception as e:
        logger.error(f"Ошибка скачивания фото: {e}")
        db.add_credits(user_id, cost)
        await callback.message.edit_text(
            "❌ *Ошибка загрузки фото.*\nМонеты возвращены на баланс.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
        await state.clear()
        return

    try:
        # Передаём image_bytes (тип bytes) в generate_image
        result_bytes = await generate_image(prompt, model, image_data=image_bytes)
        if result_bytes:
            photo = BufferedInputFile(result_bytes, filename="result.png")
            await callback.message.answer_photo(
                photo,
                caption=f"🎉 *Готово!*\n\nВаша аватарка создана.\nОстаток баланса: `{db.get_credits(user_id)}` AI Coin.",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
            await callback.message.delete()
        else:
            db.add_credits(user_id, cost)
            await callback.message.edit_text(
                "❌ *Ошибка генерации.*\nМонеты возвращены на баланс.",
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
    except Exception as e:
        logger.error(e)
        db.add_credits(user_id, cost)
        await callback.message.edit_text(
            "❌ *Техническая ошибка.*\nМонеты возвращены.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
    finally:
        await state.clear()

# === Кнопка "Пополнение" ===
@router.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    await callback.message.edit_text(
        "💳 *Пополнение баланса*\n\n"
        "Вы можете приобрести AI Coin для генерации изображений.\n"
        "Чем больше покупаете, тем выгоднее цена!\n\n"
        "Или оформите PRO подписку для ежедневных бонусов.",
        parse_mode="Markdown",
        reply_markup=buy_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "buy_tokens")
async def cb_buy_tokens(callback: CallbackQuery):
    await callback.message.edit_text(
        "🪙 *Выберите пакет*\n\n"
        "Выберите количество AI Coin, которое хотите приобрести:\n\n"
        "• 50 Coin — 99 ₽\n"
        "• 120 Coin — 237 ₽\n"
        "• 240 Coin — 403 ₽ (скидка 15%, было ~475 ₽)\n"
        "• 480 Coin — 712 ₽ (скидка 25%, было ~950 ₽)\n"
        "• 960 Coin — 1259 ₽ (скидка 35%, было ~1900 ₽)\n\n"
        "💰 Нажмите на нужный пакет для оплаты.",
        parse_mode="Markdown",
        reply_markup=tariffs_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_buy")
async def cb_back_to_buy(callback: CallbackQuery):
    await cb_buy(callback)

# === PRO подписка (выбор тарифа) ===
@router.callback_query(F.data == "buy_pro_subscription")
async def cb_buy_pro(callback: CallbackQuery):
    text = (
        "🌟 *PRO подписка*\n\n"
        "Выберите длительность подписки:\n\n"
        f"• Ежедневное начисление: {PRO_DAILY_BONUS} AI Coin\n"
        "• Приоритетная очередь генерации\n"
        "• Доступ к эксклюзивным моделям\n\n"
        "Выберите тариф:"
    )
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=subscription_tariffs_keyboard())
    await callback.answer()

# === Обработчик выбора тарифа подписки ===
@router.callback_query(F.data.startswith("select_pro_"))
async def cb_select_pro_tariff(callback: CallbackQuery):
    tariff_key = callback.data.split("_")[2]  # например "7d"
    tariff = SUBSCRIPTION_TARIFFS.get(tariff_key)
    if not tariff:
        await callback.answer("Неверный тариф", show_alert=True)
        return
    days = tariff["days"]
    price = tariff["price"]  # в копейках
    price_rub = price // 100

    user_id = callback.from_user.id
    sub = db.get_subscription(user_id)
    if sub and sub["is_active"]:
        await callback.answer("У вас уже есть активная PRO подписка!", show_alert=True)
        return

    # Создаём платёж с передачей длительности в metadata
    payment_id, conf_url = create_payment(
        amount=price,
        description=f"PRO подписка на {days} дней",
        user_id=user_id,
        payment_type="subscription",
        duration_days=days
    )
    if not payment_id:
        await callback.message.edit_text("❌ Ошибка при создании платежа. Попробуйте позже.")
        await callback.answer()
        return

    db.save_payment(payment_id, user_id, price, "pending", f"PRO подписка {days}дн")

    await callback.message.edit_text(
        f"💳 *Оплата подписки на {days} дней*\n\n"
        f"Стоимость: {price_rub} ₽\n"
        f"Перейдите по ссылке для оплаты:\n{conf_url}\n\n"
        "После оплаты подписка активируется автоматически в течение 1-2 минут.",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )
    await callback.answer()

# === Разовые платежи через Telegram Payments ===
async def send_invoice(callback: CallbackQuery, tariff_key: str):
    coins, price_kopecks = TARIFFS[tariff_key]
    title = f"{coins} AI Coin"
    description = f"Пополнение баланса на {coins} монет."
    payload = f"pay_{tariff_key}_{coins}"
    provider_token = PAYMENT_TOKEN
    currency = "RUB"
    prices = [LabeledPrice(label=title, amount=price_kopecks)]

    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=title,
            description=description,
            payload=payload,
            provider_token=provider_token,
            currency=currency,
            prices=prices,
            start_parameter="test-payment",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
        )
        await callback.answer("💳 Открываю платёжное окно...")
    except Exception as e:
        logger.error(f"Ошибка отправки инвойса: {e}")
        await callback.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        await callback.answer()

@router.callback_query(F.data == "buy_50")
async def cb_buy_50(callback: CallbackQuery):
    await send_invoice(callback, "buy_50")

@router.callback_query(F.data == "buy_120")
async def cb_buy_120(callback: CallbackQuery):
    await send_invoice(callback, "buy_120")

@router.callback_query(F.data == "buy_240")
async def cb_buy_240(callback: CallbackQuery):
    await send_invoice(callback, "buy_240")

@router.callback_query(F.data == "buy_480")
async def cb_buy_480(callback: CallbackQuery):
    await send_invoice(callback, "buy_480")

@router.callback_query(F.data == "buy_960")
async def cb_buy_960(callback: CallbackQuery):
    await send_invoice(callback, "buy_960")

@router.pre_checkout_query()
async def pre_checkout_query_handler(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment = message.successful_payment
    payload = payment.invoice_payload
    parts = payload.split("_")
    if len(parts) >= 3:
        try:
            coins = int(parts[2])
        except ValueError:
            coins = 0
    else:
        coins = 0

    if coins > 0:
        user_id = message.from_user.id
        db.add_credits(user_id, coins)
        new_balance = db.get_credits(user_id)
        await message.answer(
            f"✅ *Оплата прошла успешно!*\n"
            f"Вам начислено *{coins}* AI Coin.\n"
            f"Текущий баланс: `{new_balance}` AI Coin.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await message.answer(
            "⚠️ Произошла ошибка при начислении монет. Обратитесь к администратору.",
            reply_markup=main_menu_keyboard()
        )

# === Кнопка "Задания" ===
@router.callback_query(F.data == "tasks")
async def cb_tasks(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.task_completed(user_id, "tiktok_task"):
        await callback.message.edit_text(
            "📋 *Вы уже выполнили это задание.*\nОно доступно только один раз.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
        await callback.answer()
        return

    guide_text = (
        "📋 *Задание: получи 5 AI Coin бесплатно!*\n\n"
        "1. Введите в поиске TikTok «фото нейросетью».\n"
        "2. Зайдите на **три любых видео** с тематикой обработки фотографий.\n"
        "3. Под каждым из них оставьте комментарий:\n"
        "   `сделал/сделала такое фото в этом боте @Trendavatar_bot`\n"
        "4. Отправьте сюда **ссылки на ваши комментарии** (по одной).\n\n"
        "После третьей ссылки вы получите бонус 5 AI Coin."
    )
    await callback.message.edit_text(guide_text, parse_mode="Markdown", reply_markup=back_keyboard())

    await callback.message.answer(
        "📎 *Отправьте 3 ссылки на комментарии поочередно.*\n"
        "Начните с первой.",
        parse_mode="Markdown"
    )
    await state.set_state(TaskStates.waiting_for_first_link)
    await callback.answer()

@router.message(TaskStates.waiting_for_first_link, F.text)
async def handle_task_link_1(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("❌ Это не похоже на ссылку. Пожалуйста, отправьте корректную ссылку на комментарий.")
        return
    user_id = message.from_user.id
    db.save_task_link(user_id, link, 1)
    await message.answer("✅ Ссылка 1/3 получена. Отправьте вторую.")
    await state.set_state(TaskStates.waiting_for_second_link)

@router.message(TaskStates.waiting_for_second_link, F.text)
async def handle_task_link_2(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("❌ Это не ссылка. Попробуйте ещё раз.")
        return
    user_id = message.from_user.id
    db.save_task_link(user_id, link, 2)
    await message.answer("✅ Ссылка 2/3 получена. Отправьте третью.")
    await state.set_state(TaskStates.waiting_for_third_link)

@router.message(TaskStates.waiting_for_third_link, F.text)
async def handle_task_link_3(message: Message, state: FSMContext):
    link = message.text.strip()
    if not link.startswith("http"):
        await message.answer("❌ Это не ссылка. Попробуйте ещё раз.")
        return
    user_id = message.from_user.id
    db.save_task_link(user_id, link, 3)

    db.add_credits(user_id, BONUS_TASK)
    db.mark_task_done(user_id, "tiktok_task")
    db.clear_task_links(user_id)

    await message.answer(
        f"🎉 *Поздравляем!*\n\n"
        f"Задание выполнено. Вам начислено {BONUS_TASK} AI Coin.\n"
        f"Текущий баланс: `{db.get_credits(user_id)}` AI Coin.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    await state.clear()

# === Обработка некорректного ввода ===
@router.message(GenerateStates.waiting_for_photo_and_prompt)
async def handle_invalid_input(message: Message, state: FSMContext):
    await message.answer(
        "❌ Пожалуйста, отправьте **фото** с **текстовым промптом** в подписи.\n"
        "Или нажмите кнопку «Назад».",
        reply_markup=back_keyboard()
    )

# ============================================================
# === WEBHOOK ОБРАБОТЧИК ДЛЯ ЮKASSA ===
# ============================================================

async def yookassa_webhook(request):
    """
    Обработка webhook от ЮKassa.
    Ожидается POST с JSON.
    """
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"Ошибка парсинга webhook: {e}")
        return {"status": "error", "message": "Invalid JSON"}

    event = data.get("event")
    payment_data = data.get("object", {})
    payment_id = payment_data.get("id")
    status = payment_data.get("status")
    metadata = payment_data.get("metadata", {})
    user_id = int(metadata.get("user_id", 0))
    payment_type = metadata.get("type", "one_time")
    duration_days = int(metadata.get("duration_days", 30))

    if not user_id or not payment_id:
        logger.warning("Webhook: отсутствуют user_id или payment_id")
        return {"status": "error", "message": "Missing data"}

    db.update_payment_status(payment_id, status)

    if status == "succeeded" and payment_type == "subscription":
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)
        db.create_or_update_subscription(
            user_id,
            "pro",
            start_date.isoformat(),
            end_date.isoformat(),
            auto_renew=True,
            payment_id=payment_id
        )
        # Начисляем первый бонус
        db.add_credits(user_id, PRO_DAILY_BONUS)
        db.update_last_daily_bonus(user_id, start_date.isoformat())
        await notify_user_about_subscription(user_id, "activated")
        logger.info(f"Активирована PRO подписка для пользователя {user_id} на {duration_days} дней (платёж {payment_id})")
        return {"status": "ok"}

    return {"status": "ok"}

async def notify_user_about_subscription(user_id: int, action: str):
    try:
        bot = Bot(token=BOT_TOKEN)
        if action == "activated":
            sub = db.get_subscription(user_id)
            end_date = sub["end_date"] if sub else "неизвестно"
            await bot.send_message(
                user_id,
                f"🌟 *PRO подписка активирована!*\n\n"
                f"Теперь вы получаете {PRO_DAILY_BONUS} AI Coin каждый день.\n"
                f"Действует до: {end_date[:10] if end_date else 'неизвестно'}.\n"
                f"Ваш баланс: {db.get_credits(user_id)} AI Coin.",
                parse_mode="Markdown"
            )
        elif action == "expired":
            await bot.send_message(
                user_id,
                "⏰ *Ваша PRO подписка истекла.*\n"
                "Чтобы продлить, нажмите «Купить PRO подписку» в разделе «Пополнение».",
                parse_mode="Markdown"
            )
        elif action == "renewed":
            await bot.send_message(
                user_id,
                f"🔄 *PRO подписка продлена!*\n"
                f"Следующее списание через {PRO_SUBSCRIPTION_DURATION} дней.",
                parse_mode="Markdown"
            )
        await bot.session.close()
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

# ============================================================
# === АДМИН-КОМАНДЫ ===
# ============================================================

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    import sqlite3
    conn = sqlite3.connect(db.DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(credits) FROM users")
    total_credits = cursor.fetchone()[0] or 0
    conn.close()
    await message.answer(f"👥 Пользователей: {total_users}\n💰 Кредитов: {total_credits}")

@router.message(Command("add_credits"))
async def cmd_add_credits(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    args = message.text.split()
    if len(args) != 3:
        await message.answer("Использование: /add_credits <user_id> <количество>")
        return
    try:
        user_id = int(args[1])
        amount = int(args[2])
        db.add_credits(user_id, amount)
        await message.answer(f"✅ Добавлено {amount} кредитов пользователю {user_id}")
    except ValueError:
        await message.answer("❌ Неверный формат.")
