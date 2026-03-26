import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import pytz

from config import BOT_TOKEN, TIMEZONE
from database import init_db, save_event, get_today_events
from ai_parser import parse_events_from_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Хранилище chat_id для рассылки (простое решение для одного пользователя)
USER_CHAT_IDS = set()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    USER_CHAT_IDS.add(message.chat.id)
    await message.answer(
        "👋 Привет! Я твой личный секретарь.\n\n"
        "Просто напиши мне задачу или событие, например:\n"
        "• «В пятницу встреча с клиентом в 14:00»\n"
        "• «25 апреля день рождения мамы»\n"
        "• «Завтра поход к врачу в 10:30»\n\n"
        "Каждое утро в 8:30 я буду присылать тебе план на день 📋"
    )


@dp.message()
async def handle_message(message: Message):
    USER_CHAT_IDS.add(message.chat.id)
    text = message.text

    await message.answer("⏳ Обрабатываю...")

    events = await parse_events_from_text(text)

    if not events:
        await message.answer(
            "🤔 Не смог распознать события. Попробуй написать иначе, например:\n"
            "«В среду тренировка в 19:00»"
        )
        return

    saved = []
    for event in events:
        save_event(
            chat_id=message.chat.id,
            date=event["date"],
            time=event.get("time"),
            description=event["description"]
        )
        date_str = event["date"]
        time_str = f" в {event['time']}" if event.get("time") else ""
        saved.append(f"• {event['description']}{time_str} — {date_str}")

    saved_text = "\n".join(saved)
    await message.answer(f"✅ Сохранено:\n{saved_text}")


async def send_morning_summary():
    """Утренняя рассылка плана на день"""
    tz = pytz.timezone(TIMEZONE)
    today = datetime.now(tz).date()

    for chat_id in USER_CHAT_IDS:
        events = get_today_events(chat_id, today)

        if not events:
            await bot.send_message(
                chat_id,
                f"☀️ Доброе утро! На сегодня ({today.strftime('%d.%m.%Y')}) задач нет.\n\nХорошего дня! 😊"
            )
        else:
            lines = [f"☀️ Доброе утро! План на сегодня ({today.strftime('%d.%m.%Y, %A')}):\n"]
            for event in sorted(events, key=lambda x: x["time"] or "00:00"):
                time_str = f"🕐 {event['time']} — " if event["time"] else "• "
                lines.append(f"{time_str}{event['description']}")

            await bot.send_message(chat_id, "\n".join(lines))


async def main():
    init_db()

    # Запускаем утреннюю рассылку в 8:30 по заданному часовому поясу
    scheduler.add_job(send_morning_summary, "cron", hour=8, minute=30)
    scheduler.start()

    logger.info("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
