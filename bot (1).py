import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import pytz

from config import BOT_TOKEN, TIMEZONE
from database import (init_db, save_event, get_today_events, get_week_events,
                      get_tomorrow_events, mark_done, delete_event, update_event,
                      get_event_by_id, get_setting, save_setting, get_all_chat_ids,
                      get_events_by_date)
from ai_parser import parse_events_from_text, analyze_schedule, detect_intent, parse_edit_from_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# Состояния для редактирования
edit_states = {}  # chat_id -> event_id


def get_tz():
    return pytz.timezone(TIMEZONE)


def today():
    return datetime.now(get_tz()).date()


def format_event(event: dict, show_id=True) -> str:
    status = "✅" if event["done"] else "•"
    time_str = f" {event['time']}" if event.get("time") else ""
    id_str = f" [#{event['id']}]" if show_id else ""
    return f"{status}{time_str} {event['description']}{id_str}"


def format_date(date_str: str) -> str:
    tz = get_tz()
    weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    return f"{d.strftime('%d.%m')} ({weekday_names[d.weekday()]})"


def events_keyboard(events: list, action: str):
    builder = InlineKeyboardBuilder()
    for e in events:
        label = f"{'✅ ' if e['done'] else ''}{e['description'][:30]}"
        builder.button(text=label, callback_data=f"{action}:{e['id']}")
    builder.adjust(1)
    return builder.as_markup()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    setting = get_setting(message.chat.id)
    await message.answer(
        f"👋 Добрый день! Я Jarvis, ваш личный секретарь.\n\n"
        f"Просто пишите мне задачи в свободной форме:\n"
        f"• «В пятницу встреча с клиентом в 14:00»\n"
        f"• «Завтра поход к врачу в 10:30»\n\n"
        f"Или задавайте вопросы:\n"
        f"• «Что у меня на этой неделе?»\n"
        f"• «Завтра утром я свободен?»\n\n"
        f"Утренняя сводка приходит в {setting['hour']}:{setting['minute']:02d} 📋\n\n"
        f"Команды:\n"
        f"/today — план на сегодня\n"
        f"/week — план на неделю\n"
        f"/done — отметить выполненное\n"
        f"/delete — удалить событие\n"
        f"/edit — изменить событие\n"
        f"/time — изменить время сводки"
    )


@dp.message(Command("today"))
async def cmd_today(message: Message):
    events = get_today_events(message.chat.id, today())
    await send_day_summary(message.chat.id, today(), events, reply=message)


@dp.message(Command("week"))
async def cmd_week(message: Message):
    await send_week_summary(message.chat.id, reply=message)


@dp.message(Command("done"))
async def cmd_done(message: Message):
    events = [e for e in get_today_events(message.chat.id, today()) if not e["done"]]
    if not events:
        await message.answer("На сегодня нет невыполненных задач.")
        return
    await message.answer("Что выполнено?", reply_markup=events_keyboard(events, "done"))


@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    tz = get_tz()
    start = today()
    end = start + timedelta(days=30)
    events = get_week_events(message.chat.id, start, end)
    if not events:
        await message.answer("Нет предстоящих событий.")
        return
    await message.answer("Какое событие удалить?", reply_markup=events_keyboard(events, "delete"))


@dp.message(Command("edit"))
async def cmd_edit(message: Message):
    start = today()
    end = start + timedelta(days=30)
    events = get_week_events(message.chat.id, start, end)
    if not events:
        await message.answer("Нет предстоящих событий.")
        return
    await message.answer("Какое событие изменить?", reply_markup=events_keyboard(events, "edit"))


@dp.message(Command("time"))
async def cmd_time(message: Message):
    setting = get_setting(message.chat.id)
    await message.answer(
        f"Текущее время сводки: {setting['hour']}:{setting['minute']:02d}\n\n"
        f"Напишите новое время в формате ЧЧ:ММ\nНапример: 7:30 или 09:00"
    )
    edit_states[message.chat.id] = "set_time"


@dp.callback_query(F.data.startswith("done:"))
async def cb_done(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = get_event_by_id(event_id, callback.message.chat.id)
    if event and mark_done(event_id, callback.message.chat.id):
        await callback.message.edit_text(f"✅ Выполнено: {event['description']}")
    await callback.answer()


@dp.callback_query(F.data.startswith("delete:"))
async def cb_delete(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = get_event_by_id(event_id, callback.message.chat.id)
    if event and delete_event(event_id, callback.message.chat.id):
        await callback.message.edit_text(f"🗑 Удалено: {event['description']}")
    await callback.answer()


@dp.callback_query(F.data.startswith("edit:"))
async def cb_edit(callback: CallbackQuery):
    event_id = int(callback.data.split(":")[1])
    event = get_event_by_id(event_id, callback.message.chat.id)
    if event:
        edit_states[callback.message.chat.id] = event_id
        time_str = event['time'] or 'не указано'
        await callback.message.edit_text(
            f"Редактируем: {event['description']}\n"
            f"Дата: {event['date']}, время: {time_str}\n\n"
            f"Напишите что изменить, например:\n"
            f"«Перенеси на пятницу в 15:00» или «Измени название на Встреча с Иваном»"
        )
    await callback.answer()


@dp.message()
async def handle_message(message: Message):
    chat_id = message.chat.id
    text = message.text.strip()

    # Режим редактирования
    if chat_id in edit_states:
        state = edit_states.pop(chat_id)

        if state == "set_time":
            try:
                parts = text.replace(".", ":").split(":")
                hour, minute = int(parts[0]), int(parts[1])
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    save_setting(chat_id, hour, minute)
                    reschedule_jobs()
                    await message.answer(f"✅ Утренняя сводка теперь приходит в {hour}:{minute:02d}")
                else:
                    await message.answer("Неверный формат. Попробуйте ещё раз: /time")
            except:
                await message.answer("Не понял время. Попробуйте ещё раз: /time")
            return

        # Редактирование события
        event = get_event_by_id(state, chat_id)
        if event:
            changes = await parse_edit_from_text(text, event)
            update_event(state, chat_id,
                         description=changes.get("description"),
                         date=changes.get("date"),
                         time=changes.get("time"))
            await message.answer(f"✅ Событие обновлено: {changes.get('description', event['description'])}")
        return

    # Определяем намерение
    intent = await detect_intent(text)

    if intent == "list_today":
        events = get_today_events(chat_id, today())
        await send_day_summary(chat_id, today(), events, reply=message)

    elif intent == "list_week":
        await send_week_summary(chat_id, reply=message)

    elif intent == "done":
        events = [e for e in get_today_events(chat_id, today()) if not e["done"]]
        if events:
            await message.answer("Что выполнено?", reply_markup=events_keyboard(events, "done"))
        else:
            await message.answer("На сегодня нет невыполненных задач.")

    elif intent == "delete":
        start = today()
        end = start + timedelta(days=30)
        events = get_week_events(chat_id, start, end)
        if events:
            await message.answer("Какое событие удалить?", reply_markup=events_keyboard(events, "delete"))
        else:
            await message.answer("Нет предстоящих событий.")

    elif intent == "edit":
        start = today()
        end = start + timedelta(days=30)
        events = get_week_events(chat_id, start, end)
        if events:
            await message.answer("Какое событие изменить?", reply_markup=events_keyboard(events, "edit"))
        else:
            await message.answer("Нет предстоящих событий.")

    elif intent == "set_time":
        await cmd_time(message)

    elif intent == "analyze":
        start = today()
        end = start + timedelta(days=7)
        events = get_week_events(chat_id, start, end)
        answer = await analyze_schedule(text, events)
        await message.answer(f"🎩 {answer}")

    elif intent == "add":
        await message.answer("⏳ Записываю...")
        events = await parse_events_from_text(text)
        if not events:
            await message.answer("🤔 Не смог распознать событие. Попробуйте иначе.")
            return
        saved = []
        for event in events:
            save_event(chat_id, event["date"], event.get("time"), event["description"])
            time_str = f" в {event['time']}" if event.get("time") else ""
            saved.append(f"• {event['description']}{time_str} — {format_date(event['date'])}")
        await message.answer("✅ Записано:\n" + "\n".join(saved))

    else:
        await message.answer("⏳ Обрабатываю...")
        events = await parse_events_from_text(text)
        if events:
            saved = []
            for event in events:
                save_event(chat_id, event["date"], event.get("time"), event["description"])
                time_str = f" в {event['time']}" if event.get("time") else ""
                saved.append(f"• {event['description']}{time_str} — {format_date(event['date'])}")
            await message.answer("✅ Записано:\n" + "\n".join(saved))
        else:
            await message.answer(
                "🎩 Я ваш секретарь, Jarvis. Скажите мне о задаче или задайте вопрос о расписании."
            )


async def send_day_summary(chat_id: int, day, events: list, reply: Message = None):
    tz = get_tz()
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    day_name = weekday_names[day.weekday()]
    date_str = day.strftime("%d.%m.%Y")

    if not events:
        text = f"📋 {day_name}, {date_str} — задач нет."
    else:
        lines = [f"📋 {day_name}, {date_str}:\n"]
        for e in sorted(events, key=lambda x: x["time"] or "00:00"):
            lines.append(format_event(e))
        text = "\n".join(lines)

    if reply:
        await reply.answer(text)
    else:
        await bot.send_message(chat_id, text)


async def send_week_summary(chat_id: int, reply: Message = None):
    start = today()
    end = start + timedelta(days=6)
    events = get_week_events(chat_id, start, end)

    if not events:
        text = "📅 На этой неделе задач нет."
    else:
        by_date = {}
        for e in events:
            by_date.setdefault(e["date"], []).append(e)

        lines = ["📅 Неделя:\n"]
        for date_str in sorted(by_date.keys()):
            lines.append(f"\n{format_date(date_str)}")
            for e in sorted(by_date[date_str], key=lambda x: x["time"] or "00:00"):
                lines.append(format_event(e, show_id=False))
        text = "\n".join(lines)

    if reply:
        await reply.answer(text)
    else:
        await bot.send_message(chat_id, text)


async def send_morning_summary():
    for chat_id in get_all_chat_ids():
        events = get_today_events(chat_id, today())
        if not events:
            await bot.send_message(chat_id, f"☀️ Доброе утро! На сегодня задач нет.\n\nХорошего дня! 😊")
        else:
            lines = [f"☀️ Доброе утро! Ваш план на сегодня:\n"]
            for e in sorted(events, key=lambda x: x["time"] or "00:00"):
                lines.append(format_event(e, show_id=False))
            await bot.send_message(chat_id, "\n".join(lines))


async def send_tomorrow_reminders():
    tz = get_tz()
    tomorrow = today() + timedelta(days=1)
    for chat_id in get_all_chat_ids():
        events = get_tomorrow_events(chat_id, tomorrow)
        if events:
            lines = [f"🔔 Напоминание! Завтра ({format_date(str(tomorrow))}):\n"]
            for e in sorted(events, key=lambda x: x["time"] or "00:00"):
                lines.append(format_event(e, show_id=False))
            await bot.send_message(chat_id, "\n".join(lines))


def reschedule_jobs():
    scheduler.remove_all_jobs()
    scheduler.add_job(send_morning_summary, "cron", hour=8, minute=30, id="morning")
    scheduler.add_job(send_tomorrow_reminders, "cron", hour=20, minute=0, id="tomorrow")


async def main():
    init_db()
    reschedule_jobs()
    scheduler.start()
    logger.info("Jarvis запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
