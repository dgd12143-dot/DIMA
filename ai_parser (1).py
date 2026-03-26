import anthropic
import json
from datetime import datetime
import pytz

from config import ANTHROPIC_API_KEY, TIMEZONE

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _today_context() -> tuple:
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    weekday_names = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    return now, now.strftime("%Y-%m-%d"), weekday_names[now.weekday()]


async def parse_events_from_text(text: str) -> list:
    now, today_str, weekday = _today_context()

    prompt = f"""Сегодня {today_str} ({weekday}).

Пользователь написал: "{text}"

Извлеки все события/задачи из этого текста и верни их в формате JSON.
Только JSON, без пояснений. Пример:
[
  {{"date": "2024-03-15", "time": "14:00", "description": "Встреча с клиентом"}},
  {{"date": "2024-03-20", "time": null, "description": "День рождения мамы"}}
]

Правила:
- date: всегда YYYY-MM-DD, вычисляй относительно сегодня ({today_str})
- time: HH:MM или null если время не указано
- description: краткое описание на русском
- Верни пустой массив [] если событий не найдено"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    return json.loads(response_text)


async def parse_edit_from_text(text: str, event: dict) -> dict:
    now, today_str, weekday = _today_context()

    prompt = f"""Сегодня {today_str} ({weekday}).

Текущее событие:
- Описание: {event['description']}
- Дата: {event['date']}
- Время: {event.get('time', 'не указано')}

Пользователь хочет изменить: "{text}"

Верни JSON с изменёнными полями. Только поля которые нужно изменить:
{{"description": "...", "date": "YYYY-MM-DD", "time": "HH:MM"}}

Если поле не меняется — не включай его в ответ. Только JSON."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    return json.loads(response_text)


async def analyze_schedule(text: str, events: list) -> str:
    now, today_str, weekday = _today_context()

    events_str = json.dumps(events, ensure_ascii=False, indent=2)

    prompt = f"""Сегодня {today_str} ({weekday}). Ты — личный секретарь Jarvis.

Расписание пользователя:
{events_str}

Вопрос пользователя: "{text}"

Ответь коротко и по делу, как умный секретарь. Используй русский язык.
Если спрашивают о свободном времени — проверь расписание и скажи конкретно.
Максимум 3-4 предложения."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip()


async def detect_intent(text: str) -> str:
    """Определяет намерение пользователя"""
    prompt = f"""Определи намерение пользователя по его сообщению.

Сообщение: "{text}"

Верни ОДНО слово:
- "add" — хочет добавить событие/задачу
- "list_today" — спрашивает что на сегодня
- "list_week" — спрашивает что на неделе
- "delete" — хочет удалить событие
- "done" — хочет отметить как выполненное
- "edit" — хочет изменить событие
- "analyze" — задаёт вопрос о расписании (свободно ли, когда, сколько)
- "set_time" — хочет изменить время утренней сводки
- "other" — всё остальное

Только одно слово, без объяснений."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text.strip().lower()
