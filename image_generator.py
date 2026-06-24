import io
import base64
import logging
import requests
from PIL import Image, ImageDraw, ImageFont

POLZA_API_KEY = "pza_QlLrxFuKPHtuQu0qiOhDKzsB4f9fNfYw"  # или из config
logger = logging.getLogger(__name__)

async def generate_image(prompt: str, model: str = "google/gemini-2.5-flash-image", image_data: bytes = None) -> bytes | None:
    """
    Генерирует изображение через Polza AI.
    Если передано image_data, используется как исходное изображение (img2img).
    Поддерживает модели: google/gemini-2.5-flash-image, google/gemini-3.1-flash-image-preview
    """
    url = "https://polza.ai/api/v1/media"
    headers = {
        "Authorization": f"Bearer {POLZA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
            "aspect_ratio": "1:1",
            "max_images": 1
        }
    }

    # Если есть фото, добавляем его в массив images (требование Polza AI для Gemini)
    if image_data:
        base64_image = base64.b64encode(image_data).decode('utf-8')
        payload["input"]["images"] = [
            {
                "type": "base64",
                "data": base64_image
            }
        ]

    proxies = {"http": None, "https": None}  # отключаем прокси

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60, proxies=proxies)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Ответ от Polza AI: {data}")

        # Извлечение URL изображения из ответа (поддерживаем разные форматы)
        image_url = None
        if "output" in data and isinstance(data["output"], list) and len(data["output"]) > 0:
            if isinstance(data["output"][0], dict) and "url" in data["output"][0]:
                image_url = data["output"][0]["url"]
            elif isinstance(data["output"][0], str):
                image_url = data["output"][0]
        elif "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            if isinstance(data["data"][0], dict) and "url" in data["data"][0]:
                image_url = data["data"][0]["url"]

        if image_url:
            img_response = requests.get(image_url, timeout=30, proxies=proxies)
            img_response.raise_for_status()
            return img_response.content
        else:
            logger.error(f"Не удалось найти изображение в ответе: {data}")
            return None

    except requests.exceptions.Timeout:
        logger.error("Таймаут при запросе к Polza AI")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса к Polza AI: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка: {e}")
        return None
