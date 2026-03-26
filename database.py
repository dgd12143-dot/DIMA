import sqlite3
from datetime import date
from typing import Optional

DB_PATH = "secretary.db"


def init_db():
    """Создаёт таблицу событий, если её нет"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_event(chat_id: int, date: str, time: Optional[str], description: str):
    """Сохраняет событие в базу данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO events (chat_id, date, time, description) VALUES (?, ?, ?, ?)",
        (chat_id, date, time, description)
    )
    conn.commit()
    conn.close()


def get_today_events(chat_id: int, today: date) -> list:
    """Возвращает список событий на сегодня"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT date, time, description FROM events WHERE chat_id = ? AND date = ?",
        (chat_id, today.strftime("%Y-%m-%d"))
    )
    rows = cursor.fetchall()
    conn.close()

    return [{"date": row[0], "time": row[1], "description": row[2]} for row in rows]
