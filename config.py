import os
from dotenv import load_dotenv

load_dotenv()

POLZA_API_KEY = os.getenv("POLZA_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PAYMENT_TOKEN = os.getenv("PAYMENT_TOKEN")  # Токен для Telegram Payments (от ЮKassa)
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# === BotGate или другой шлюз ===
API_ROOT = os.getenv("API_ROOT", "https://api.telegram.org")

# === ЮKassa (для API-интеграции, если нужна) ===
YKASSA_SHOP_ID = os.getenv("YKASSA_SHOP_ID")
YKASSA_SECRET_KEY = os.getenv("YKASSA_SECRET_KEY")
YKASSA_RETURN_URL = os.getenv("YKASSA_RETURN_URL", "https://t.me/ваш_бот")

# === НАСТРОЙКИ БАЛАНСА ===
FREE_CREDITS = 5
SUBSCRIBE_BONUS = 0
BONUS_TASK = 5
PRO_DAILY_BONUS = 40
PRO_SUBSCRIPTION_DURATION = 30

# === ТАРИФЫ ПОДПИСКИ ===
SUBSCRIPTION_TARIFFS = {
    "7d":   {"days": 7,   "price": 24900,   "label": "PRO на 7 дней"},
    "30d":  {"days": 30,  "price": 59000,   "label": "PRO на 30 дней"},
    "90d":  {"days": 90,  "price": 159000,  "label": "PRO на 90 дней"},
    "180d": {"days": 180, "price": 299000,  "label": "PRO на 180 дней"},
}

# === СТОИМОСТЬ ГЕНЕРАЦИИ ===
COST_GEMINI_25 = 10
COST_GEMINI_31 = 15

# === МОДЕЛИ ДЛЯ API ===
MODEL_GEMINI_25 = "google/gemini-2.5-flash-image"
MODEL_GEMINI_31 = "google/gemini-3.1-flash-image-preview"

# === ТАРИФЫ ДЛЯ РАЗОВЫХ ПОКУПОК ===
TARIFFS = {
    "buy_50":  (50,  9900,  "50 AI Coin"),
    "buy_120": (120, 23700, "120 AI Coin"),
    "buy_240": (240, 40300, "240 AI Coin"),
    "buy_480": (480, 71200, "480 AI Coin"),
    "buy_960": (960, 125900, "960 AI Coin"),
}
