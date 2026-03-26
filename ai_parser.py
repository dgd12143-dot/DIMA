import anthropic
import json
from datetime import datetime
import pytz

from config import ANTHROPIC_API_KEY, TIMEZONE

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def parse_events_from_text(text: str) -> list:
    """
    Отправляет текст в Claude и получает список событий в формате JSON.
    Возвращает список словарей: [{"date": "YYYY-MM-DD", "time": "HH:MM", "description": "..."}]
    """
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz)
    today_str = today.strftime("%Y-%m-%d")
    weekday_names = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

    prompt = f"""Сегодня {today_str} ({weekday_names[today.weekday()]}).

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
- description: краткое, ёмкое описание на русском
- Если дата не указана явно — используй ближайший подходящий день
- Верни пустой массив [] если событий не найдено"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()

    # Очищаем от markdown-блоков если есть
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]

    events = json.loads(response_text)
    return events
