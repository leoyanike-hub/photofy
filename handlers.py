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
    subscription_tariffs_keyboard,
    tasks_menu_keyboard
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

router = Router()
logger = logging.getLogger(__name__)

# === FSM ===
class ModelSelection(StatesGroup):
    choosing_model = State()

class GenerateStates(StatesGroup):
    waiting_for_photo_and_prompt = State()

class ScreenshotTaskStates(StatesGroup):
    waiting_for_screenshot_1 = State()
    waiting_for_screenshot_2 = State()
    waiting_for_screenshot_3 = State()

# === Вспомогательная функция проверки подписки ===
async def check_subscription(bot, user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ["member", "creator", "administrator"]
    except TelegramBadRequest as e:
        logger.warning(f"Ошибка проверки подписки для {user_id}: {e}")
        return False

# === /start с проверкой оферты и реферальной ссылки ===
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "без username"
    args = message.text.split()
    ref_id = None
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            ref_id = int(args[1].replace("ref_", ""))
        except ValueError:
            pass

    # Проверяем оферту
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

    # Обработка реферальной ссылки
    if ref_id and ref_id != user_id:
        # Проверяем, не зарегистрирован ли уже пользователь
        user = db.get_user(user_id)
        if not user:
            # Создаём пользователя и записываем реферала
            db.create_user(user_id, username)
            # Добавляем реферальную связь
            if db.add_referral(ref_id, user_id):
                # Начисляем бонус пригласившему
                db.add_credits(ref_id, BONUS_TASK)
                await message.answer(
                    f"🎉 *Вы перешли по реферальной ссылке!*\n"
                    f"Ваш друг получил бонус {BONUS_TASK} AI Coin.\n"
                    f"Вам тоже начислено {FREE_CREDITS} AI Coin за регистрацию.",
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    f"👋 *Добро пожаловать!*\n"
                    f"Вы получили {FREE_CREDITS} AI Coin.",
                    parse_mode="Markdown"
                )
        else:
            # Пользователь уже существует
            await message.answer(
                "👋 *Вы уже зарегистрированы!*",
                parse_mode="Markdown"
            )
    else:
        # Обычная регистрация
        user = db.get_user(user_id)
        if not user:
            db.create_user(user_id, username)
            await message.answer(
                f"👋 *Добро пожаловать!*\n"
                f"Вы получили {FREE_CREDITS} AI Coin.",
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                "👋 *С возвращением!*",
                parse_mode="Markdown"
            )

    # Проверяем подписку на канал
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

# === Подтверждение генерации ===
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

    if not db.spend_credits(user_id, cost):
        await callback.answer(f"Недостаточно средств! Нужно {cost} AI Coin.", show_alert=True)
        return

    await callback.message.edit_text("⏳ *Генерация началась...*", parse_mode="Markdown")
    await callback.answer()

    try:
        file = await callback.bot.get_file(photo_file_id)
        file_bytes_io = await callback.bot.download_file(file.file_path)
        image_bytes = file_bytes_io.read()
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

# === PRO подписка ===
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

@router.callback_query(F.data.startswith("select_pro_"))
async def cb_select_pro_tariff(callback: CallbackQuery):
    tariff_key = callback.data.split("_")[2]
    tariff = SUBSCRIPTION_TARIFFS.get(tariff_key)
    if not tariff:
        await callback.answer("Неверный тариф", show_alert=True)
        return

    user_id = callback.from_user.id
    sub = db.get_subscription(user_id)
    if sub and sub["is_active"]:
        await callback.answer("У вас уже есть активная PRO подписка!", show_alert=True)
        return

    days = tariff["days"]
    price = tariff["price"]
    title = f"PRO подписка на {days} дней"
    description = f"Ежедневное начисление {PRO_DAILY_BONUS} AI Coin в течение {days} дней."
    payload = f"sub_{days}d_{price}"

    provider_data = {
        "receipt": {
            "items": [
                {
                    "description": title,
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{price/100:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ]
        }
    }

    try:
        await callback.bot.send_invoice(
            chat_id=user_id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PAYMENT_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=title, amount=price)],
            start_parameter=f"sub_{tariff_key}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            provider_data=json.dumps(provider_data)
        )
        await callback.answer("💳 Открываю платёжное окно...")
    except Exception as e:
        logger.error(f"Ошибка отправки инвойса для подписки: {e}")
        await callback.message.answer("❌ Ошибка при создании платежа. Попробуйте позже.")
        await callback.answer()

# === Разовые платежи ===
async def send_invoice(callback: CallbackQuery, tariff_key: str):
    coins, price, label = TARIFFS[tariff_key]
    title = label
    description = f"Пополнение баланса на {coins} AI Coin."
    payload = f"pay_{tariff_key}_{coins}"

    provider_data = {
        "receipt": {
            "items": [
                {
                    "description": title,
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{price/100:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_mode": "full_payment",
                    "payment_subject": "service"
                }
            ]
        }
    }

    try:
        await callback.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=title,
            description=description,
            payload=payload,
            provider_token=PAYMENT_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=title, amount=price)],
            start_parameter=f"pay_{tariff_key}",
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            is_flexible=False,
            provider_data=json.dumps(provider_data)
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
    user_id = message.from_user.id

    if payload.startswith("pay_"):
        parts = payload.split("_")
        if len(parts) >= 3:
            try:
                coins = int(parts[2])
                db.add_credits(user_id, coins)
                new_balance = db.get_credits(user_id)
                await message.answer(
                    f"✅ *Оплата прошла успешно!*\n"
                    f"Вам начислено *{coins}* AI Coin.\n"
                    f"Текущий баланс: `{new_balance}` AI Coin.",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
                return
            except ValueError:
                pass
        await message.answer("⚠️ Ошибка при начислении монет. Обратитесь к администратору.")
    elif payload.startswith("sub_"):
        parts = payload.split("_")
        if len(parts) >= 3:
            try:
                days = int(parts[1])
                start_date = datetime.now()
                end_date = start_date + timedelta(days=days)
                db.create_or_update_subscription(
                    user_id,
                    "pro",
                    start_date.isoformat(),
                    end_date.isoformat(),
                    auto_renew=False,
                    payment_id=f"sub_{user_id}_{int(datetime.now().timestamp())}"
                )
                db.add_credits(user_id, PRO_DAILY_BONUS)
                db.update_last_daily_bonus(user_id, start_date.isoformat())
                await message.answer(
                    f"🌟 *PRO подписка активирована!*\n\n"
                    f"Длительность: {days} дней\n"
                    f"Действует до: {end_date.strftime('%d.%m.%Y')}\n"
                    f"Ежедневное начисление: {PRO_DAILY_BONUS} AI Coin.\n"
                    f"Первый бонус уже начислен!",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
                return
            except Exception as e:
                logger.error(f"Ошибка активации подписки: {e}")
        await message.answer("⚠️ Ошибка при активации подписки. Обратитесь к администратору.")
    else:
        await message.answer("⚠️ Неизвестный тип платежа.")

# ============================================================
# === НОВЫЕ ЗАДАНИЯ ===
# ============================================================

# --- Меню заданий ---
@router.callback_query(F.data == "tasks")
async def cb_tasks(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📋 *Задания*\n\n"
        "Выберите задание, которое хотите выполнить:\n\n"
        "📝 *Задание 1: Скриншоты комментариев*\n"
        "   Сделайте скриншоты 3 ваших комментариев в TikTok под видео с нейросетями.\n"
        "   Награда: 5 AI Coin\n\n"
        "👥 *Задание 2: Приглашения*\n"
        "   Приглашайте друзей и получайте бонусы.\n"
        "   Награда: 5 AI Coin за каждого приглашённого.",
        parse_mode="Markdown",
        reply_markup=tasks_menu_keyboard()
    )
    await callback.answer()

# --- Задание 1: Скриншоты ---
@router.callback_query(F.data == "task_screenshots")
async def cb_task_screenshots(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if db.task_completed(user_id, "screenshots_task"):
        await callback.message.edit_text(
            "📋 *Вы уже выполнили это задание.*\nОно доступно только один раз.",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📝 *Задание: отправьте 3 скриншота комментариев*\n\n"
        "1. Введите в поиске TikTok «фото нейросетью».\n"
        "2. Зайдите на **три любых видео** с тематикой обработки фотографий.\n"
        "3. Под каждым из них оставьте комментарий:\n"
        "   `сделал/сделала такое фото в этом боте @Trendavatar_bot`\n"
        "4. Сделайте **скриншот** каждого комментария и отправьте их по очереди.\n\n"
        "После третьего скриншота вы получите бонус 5 AI Coin.",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )
    await callback.message.answer(
        "📎 *Отправьте первый скриншот.*",
        parse_mode="Markdown"
    )
    await state.set_state(ScreenshotTaskStates.waiting_for_screenshot_1)
    await callback.answer()

@router.message(ScreenshotTaskStates.waiting_for_screenshot_1, F.photo)
async def handle_screenshot_1(message: Message, state: FSMContext):
    await state.update_data(screenshot_1=message.photo[-1].file_id)
    await message.answer("✅ Скриншот 1/3 получен. Отправьте второй.")
    await state.set_state(ScreenshotTaskStates.waiting_for_screenshot_2)

@router.message(ScreenshotTaskStates.waiting_for_screenshot_2, F.photo)
async def handle_screenshot_2(message: Message, state: FSMContext):
    await state.update_data(screenshot_2=message.photo[-1].file_id)
    await message.answer("✅ Скриншот 2/3 получен. Отправьте третий.")
    await state.set_state(ScreenshotTaskStates.waiting_for_screenshot_3)

@router.message(ScreenshotTaskStates.waiting_for_screenshot_3, F.photo)
async def handle_screenshot_3(message: Message, state: FSMContext):
    await state.update_data(screenshot_3=message.photo[-1].file_id)
    user_id = message.from_user.id

    # Все три скриншота получены – начисляем бонус
    db.add_credits(user_id, BONUS_TASK)
    db.mark_task_done(user_id, "screenshots_task")

    # Очищаем данные состояния
    await state.clear()

    await message.answer(
        f"🎉 *Поздравляем!*\n\n"
        f"Задание выполнено. Вам начислено {BONUS_TASK} AI Coin.\n"
        f"Текущий баланс: `{db.get_credits(user_id)}` AI Coin.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

# --- Задание 2: Рефералы ---
@router.callback_query(F.data == "task_referral")
async def cb_task_referral(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    bot_username = (await callback.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    referral_count = db.get_referral_count(user_id)

    await callback.message.edit_text(
        "👥 *Задание: приглашайте друзей!*\n\n"
        "Получите 5 AI Coin за каждого друга, который перейдёт по вашей ссылке и зарегистрируется.\n\n"
        f"📊 *Вы пригласили:* {referral_count} человек\n\n"
        "Ваша реферальная ссылка:\n"
        f"`{referral_link}`\n\n"
        "Поделитесь ссылкой с друзьями, опубликуйте её в соцсетях, делайте видео с нашим ботом и прикрепляйте ссылку.\n\n"
        "Бонус начисляется после регистрации нового пользователя.",
        parse_mode="Markdown",
        reply_markup=back_keyboard()
    )
    await callback.answer()

# ============================================================
# === ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ===
# ============================================================

# === Обработка некорректного ввода в состоянии генерации ===
@router.message(GenerateStates.waiting_for_photo_and_prompt)
async def handle_invalid_input(message: Message, state: FSMContext):
    await message.answer(
        "❌ Пожалуйста, отправьте **фото** с **текстовым промптом** в подписи.\n"
        "Или нажмите кнопку «Назад».",
        reply_markup=back_keyboard()
    )

# === Обработка некорректного ввода для скриншотов ===
@router.message(ScreenshotTaskStates.waiting_for_screenshot_1, ~F.photo)
@router.message(ScreenshotTaskStates.waiting_for_screenshot_2, ~F.photo)
@router.message(ScreenshotTaskStates.waiting_for_screenshot_3, ~F.photo)
async def handle_invalid_screenshot(message: Message, state: FSMContext):
    await message.answer(
        "❌ Пожалуйста, отправьте **фото** (скриншот).\n"
        "Текст не принимается.",
        reply_markup=back_keyboard()
    )

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
