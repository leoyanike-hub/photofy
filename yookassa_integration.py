import uuid
import logging
import requests
from datetime import datetime, timedelta
from config import YKASSA_SHOP_ID, YKASSA_SECRET_KEY, YKASSA_RETURN_URL

logger = logging.getLogger(__name__)
API_URL = "https://api.yookassa.ru/v3"

def create_payment(amount: int, description: str, user_id: int, payment_type="subscription", duration_days=None):
    """
    Создаёт платёж в ЮKassa.
    amount – сумма в рублях (целое число, копейки).
    description – описание.
    user_id – Telegram ID.
    payment_type – 'subscription' или 'one_time'.
    duration_days – количество дней подписки (для metadata).
    Возвращает: (payment_id, confirmation_url) или (None, None).
    """
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {
            "value": f"{amount/100:.2f}",  # переводим копейки в рубли
            "currency": "RUB"
        },
        "payment_method_data": {
            "type": "bank_card"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": YKASSA_RETURN_URL
        },
        "description": description,
        "metadata": {
            "user_id": str(user_id),
            "type": payment_type,
            "duration_days": str(duration_days) if duration_days else ""
        }
    }

    auth = (YKASSA_SHOP_ID, YKASSA_SECRET_KEY)
    headers = {
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(f"{API_URL}/payments", json=payload, auth=auth, headers=headers)
        response.raise_for_status()
        data = response.json()
        payment_id = data["id"]
        confirmation_url = data["confirmation"]["confirmation_url"]
        return payment_id, confirmation_url
    except Exception as e:
        logger.error(f"Ошибка создания платежа: {e}")
        return None, None

def get_payment_info(payment_id: str) -> dict:
    auth = (YKASSA_SHOP_ID, YKASSA_SECRET_KEY)
    try:
        response = requests.get(f"{API_URL}/payments/{payment_id}", auth=auth)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Ошибка получения платежа {payment_id}: {e}")
        return None
