import os
import sqlite3
from datetime import datetime
from config import FREE_CREDITS, SUBSCRIBE_BONUS

# Постоянная папка для данных (на Bothost это /app/data)
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'users.db')

def get_db_connection():
    """Возвращает соединение с БД и устанавливает row_factory для удобной работы с результатами."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создаёт все таблицы, если их нет."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            credits INTEGER DEFAULT 0,
            subscribed BOOLEAN DEFAULT 0,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица выполненных заданий (одноразовые)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            user_id INTEGER PRIMARY KEY,
            task_type TEXT,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица для сохранения ссылок (оставлена для совместимости)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_links (
            user_id INTEGER,
            link TEXT,
            order_num INTEGER,
            PRIMARY KEY (user_id, order_num)
        )
    """)

    # Таблица согласий с офертой
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agreements (
            user_id INTEGER PRIMARY KEY,
            agreed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Таблица подписок (PRO)
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

    # Таблица платежей (история)
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

    # Реферальная таблица – удалена, но оставляем таблицу пустой, если была
    # (Никаких рефералов)

    conn.commit()
    conn.close()

# ============================================================
# ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
# ============================================================

def get_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(user_id: int, username: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (user_id, username, credits) VALUES (?, ?, ?)",
            (user_id, username, FREE_CREDITS)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def get_credits(user_id: int) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def add_credits(user_id: int, amount: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def spend_credits(user_id: int, amount: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if not result or result[0] < amount:
        conn.close()
        return False
    cursor.execute("UPDATE users SET credits = credits - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return True

def spend_credit(user_id: int) -> bool:
    return spend_credits(user_id, 1)

def set_subscribed(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET subscribed = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def is_subscribed(user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT subscribed FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return bool(result[0]) if result else False

# ============================================================
# ФУНКЦИИ ДЛЯ ЗАДАНИЙ (одноразовые)
# ============================================================

def task_completed(user_id: int, task_type: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM completed_tasks WHERE user_id = ? AND task_type = ?", (user_id, task_type))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def mark_task_done(user_id: int, task_type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO completed_tasks (user_id, task_type) VALUES (?, ?)", (user_id, task_type))
    conn.commit()
    conn.close()

# Функции для работы со ссылками (оставлены для обратной совместимости)
def save_task_link(user_id: int, link: str, order: int) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO task_links (user_id, link, order_num) VALUES (?, ?, ?)",
        (user_id, link, order)
    )
    conn.commit()
    conn.close()

def get_task_links(user_id: int) -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT link FROM task_links WHERE user_id = ? ORDER BY order_num", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def clear_task_links(user_id: int) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM task_links WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ============================================================
# ФУНКЦИИ ДЛЯ ОФЕРТЫ
# ============================================================

def has_agreed(user_id: int) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM agreements WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return bool(result)

def set_agreed(user_id: int) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO agreements (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# ============================================================
# ФУНКЦИИ ДЛЯ ПОДПИСОК (PRO)
# ============================================================

def get_subscription(user_id: int) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_or_update_subscription(user_id: int, sub_type: str, start_date, end_date, auto_renew=False, payment_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO subscriptions
        (user_id, subscription_type, start_date, end_date, is_active, auto_renew, payment_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, sub_type, start_date, end_date, 1, auto_renew, payment_id))
    conn.commit()
    conn.close()

def deactivate_subscription(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET is_active = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_last_daily_bonus(user_id: int, date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE subscriptions SET last_daily_bonus_date = ? WHERE user_id = ?", (date, user_id))
    conn.commit()
    conn.close()

def get_all_active_subscriptions() -> list:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE is_active = 1 AND subscription_type = 'pro'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============================================================
# ФУНКЦИИ ДЛЯ ПЛАТЕЖЕЙ
# ============================================================

def save_payment(payment_id: str, user_id: int, amount: int, status: str, description: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO payments (id, user_id, amount, status, description)
        VALUES (?, ?, ?, ?, ?)
    """, (payment_id, user_id, amount, status, description))
    conn.commit()
    conn.close()

def update_payment_status(payment_id: str, status: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payments SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, payment_id))
    conn.commit()
    conn.close()

def get_payment(payment_id: str) -> dict:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None
