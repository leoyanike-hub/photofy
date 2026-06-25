from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import SUBSCRIPTION_TARIFFS

def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✨ Сгенерировать", callback_data="generate"))
    builder.row(InlineKeyboardButton(text="💰 Пополнить", callback_data="buy"), InlineKeyboardButton(text="📋 Задания", callback_data="tasks"))
    return builder.as_markup()

def subscription_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📢 Подписаться на канал", url="https://t.me/PhotofyAi"))
    builder.row(InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription"))
    return builder.as_markup()

def back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    return builder.as_markup()

def generate_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎨 Сгенерировать", callback_data="confirm_generate"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    return builder.as_markup()

def buy_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🪙 Купить токены AI Coin", callback_data="buy_tokens"))
    builder.row(InlineKeyboardButton(text="🌟 Купить PRO подписку", callback_data="buy_pro_subscription"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    return builder.as_markup()

def tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="50 AI Coin | 99 ₽", callback_data="buy_50"))
    builder.row(InlineKeyboardButton(text="120 AI Coin | 237 ₽", callback_data="buy_120"))
    builder.row(InlineKeyboardButton(text="240 AI Coin | 403 ₽ (-15%)", callback_data="buy_240"))
    builder.row(InlineKeyboardButton(text="480 AI Coin | 712 ₽ (-25%)", callback_data="buy_480"))
    builder.row(InlineKeyboardButton(text="960 AI Coin | 1259 ₽ (-35%)", callback_data="buy_960"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_buy"))
    return builder.as_markup()

def choose_model_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Gemini 2.5 Nano Banana | 10 AI Coin", callback_data="model_gemini_25"))
    builder.row(InlineKeyboardButton(text="Gemini 3.1 Nano Banana 2 | 15 AI Coin", callback_data="model_gemini_31"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"))
    return builder.as_markup()

def agreement_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Принимаю условия оферты", callback_data="accept_offer"))
    builder.row(InlineKeyboardButton(text="📄 Читать полный текст оферты", url="https://telegra.ph/OFERTA-06-22-3"))
    return builder.as_markup()

def subscription_tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, tariff in SUBSCRIPTION_TARIFFS.items():
        days = tariff["days"]
        price = tariff["price"] // 100
        label = f"{days} дней — {price} ₽"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"select_pro_{key}"))
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_buy"))
    return builder.as_markup()

# tasks_menu_keyboard УДАЛЕНА – больше не нужна
