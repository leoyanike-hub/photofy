import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import database as db
from config import PRO_DAILY_BONUS

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def check_and_give_daily_bonuses():
    """Задача: проверить активные подписки и начислить бонусы, если прошли сутки и подписка не истекла."""
    subscriptions = db.get_all_active_subscriptions()
    now = datetime.now()
    for sub in subscriptions:
        user_id = sub["user_id"]
        end_date = datetime.fromisoformat(sub["end_date"]) if sub["end_date"] else None
        # Если подписка истекла – деактивируем
        if end_date and end_date < now:
            db.deactivate_subscription(user_id)
            logger.info(f"Подписка пользователя {user_id} истекла и деактивирована")
            continue
        # Начисляем бонус, если прошли сутки
        last_bonus = sub.get("last_daily_bonus_date")
        if last_bonus is None or (now - datetime.fromisoformat(last_bonus)) >= timedelta(days=1):
            db.add_credits(user_id, PRO_DAILY_BONUS)
            db.update_last_daily_bonus(user_id, now.isoformat())
            logger.info(f"Начислено {PRO_DAILY_BONUS} токенов пользователю {user_id} (PRO подписка)")

def start_scheduler():
    scheduler.add_job(check_and_give_daily_bonuses, IntervalTrigger(hours=1))
    scheduler.start()
    logger.info("Планировщик запущен")
