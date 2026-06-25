import os
import sqlite3
from datetime import datetime
from config import FREE_CREDITS, SUBSCRIBE_BONUS

DATA_DIR = os.getenv('DATA_DIR', '/app/data')
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, 'users.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            credits INTEGER DEFAULT 0,
            subscribed BOOLEAN DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            user_id INTEGER PRIMARY KEY,
            task_type TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_links (
            user_id INTEGER,
            link TEXT,
            order_num INTEGER,
            PRIMARY KEY (user_id, order_num)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agreements (
            user_id INTEGER PRIMARY KEY,
            agreed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            user_id INTEGER PRIMARY KEY,
            subscription_type TEXT DEFAULT 'free',
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            last_daily_bonus_date TIMESTAMP,
            is_active BOOLEAN DEFAULT 0,
            auto_renew BOOLEAN DEFAULT 0,
            payment_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount INTEGER,
            currency TEXT DEFAULT 'RUB',
            status TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Таблица рефералов УДАЛЕНА

    conn.commit()
    conn.close()

# ... все остальные функции без изменений (пользователи, задания, оферта, подписки, платежи)
# Удалены функции: add_referral, get_referral_count, get_referrer

# Функции для пользователей, заданий, оферты, подписок, платежей остаются без изменений.
# Для краткости я не копирую их полностью, но они идентичны предыдущей версии, кроме удалённых реферальных функций.
