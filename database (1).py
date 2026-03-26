import sqlite3
from datetime import date, datetime
from typing import Optional

DB_PATH = "secretary.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            description TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            chat_id INTEGER PRIMARY KEY,
            morning_hour INTEGER DEFAULT 8,
            morning_minute INTEGER DEFAULT 30
        )
    """)
    conn.commit()
    conn.close()


def save_event(chat_id: int, date: str, time: Optional[str], description: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "INSERT INTO events (chat_id, date, time, description) VALUES (?, ?, ?, ?)",
        (chat_id, date, time, description)
    )
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return event_id


def get_today_events(chat_id: int, today: date) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, date, time, description, done FROM events WHERE chat_id = ? AND date = ? ORDER BY time",
        (chat_id, today.strftime("%Y-%m-%d"))
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "date": r[1], "time": r[2], "description": r[3], "done": r[4]} for r in rows]


def get_week_events(chat_id: int, start: date, end: date) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, date, time, description, done FROM events WHERE chat_id = ? AND date BETWEEN ? AND ? ORDER BY date, time",
        (chat_id, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "date": r[1], "time": r[2], "description": r[3], "done": r[4]} for r in rows]


def get_events_by_date(chat_id: int, target_date: date) -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, date, time, description, done FROM events WHERE chat_id = ? AND date = ? ORDER BY time",
        (chat_id, target_date.strftime("%Y-%m-%d"))
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "date": r[1], "time": r[2], "description": r[3], "done": r[4]} for r in rows]


def get_tomorrow_events(chat_id: int, tomorrow: date) -> list:
    return get_events_by_date(chat_id, tomorrow)


def mark_done(event_id: int, chat_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "UPDATE events SET done = 1 WHERE id = ? AND chat_id = ?",
        (event_id, chat_id)
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def delete_event(event_id: int, chat_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "DELETE FROM events WHERE id = ? AND chat_id = ?",
        (event_id, chat_id)
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def update_event(event_id: int, chat_id: int, description: str = None, date: str = None, time: str = None) -> bool:
    conn = sqlite3.connect(DB_PATH)
    fields = []
    values = []
    if description:
        fields.append("description = ?")
        values.append(description)
    if date:
        fields.append("date = ?")
        values.append(date)
    if time is not None:
        fields.append("time = ?")
        values.append(time)
    if not fields:
        return False
    values.extend([event_id, chat_id])
    cursor = conn.execute(
        f"UPDATE events SET {', '.join(fields)} WHERE id = ? AND chat_id = ?",
        values
    )
    changed = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return changed


def get_event_by_id(event_id: int, chat_id: int) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT id, date, time, description, done FROM events WHERE id = ? AND chat_id = ?",
        (event_id, chat_id)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "date": row[1], "time": row[2], "description": row[3], "done": row[4]}
    return None


def get_setting(chat_id: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        "SELECT morning_hour, morning_minute FROM settings WHERE chat_id = ?",
        (chat_id,)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"hour": row[0], "minute": row[1]}
    return {"hour": 8, "minute": 30}


def save_setting(chat_id: int, hour: int, minute: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO settings (chat_id, morning_hour, morning_minute) VALUES (?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET morning_hour=?, morning_minute=?",
        (chat_id, hour, minute, hour, minute)
    )
    conn.commit()
    conn.close()


def get_all_chat_ids() -> list:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute("SELECT DISTINCT chat_id FROM events")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]
