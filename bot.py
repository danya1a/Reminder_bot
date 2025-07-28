from aiogram import Bot, Dispatcher, F, types
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import TOKEN
from db import create_table, add_reminder, get_reminders, delete_reminder
from timezone import detect_timezone
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator
import asyncio
import pytz

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

LANGS = {
    "en": "English",
    "ru": "Русский",
    "uk": "Українська"
}

user_lang = {}
job_mapping = {}


@dp.message(F.text == "/start")
async def cmd_start(message: Message):
    keyboard = InlineKeyboardBuilder()
    for code, name in LANGS.items():
        keyboard.add(InlineKeyboardButton(text=name, callback_data=f"lang:{code}"))
    await message.answer("🌐 Choose your language / Выберите язык / Оберіть мову", reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split(":")[1]
    user_lang[callback.from_user.id] = lang
    msg = {
        "en": "✅ Language set. Send your reminder like:\n- Buy milk at 18:30\n- Buy milk 28.07.2025 at 18:30",
        "ru": "✅ Язык установлен. Отправьте напоминание как:\n- Купить молоко в 18:30\n- Купить молоко 28.07.2025 в 18:30",
        "uk": "✅ Мову встановлено. Надішліть нагадування як:\n- Купити молоко о 18:30\n- Купити молоко 28.07.2025 о 18:30"
    }
    await callback.message.answer(msg.get(lang, msg["en"]))


@dp.message(F.text == "/reminders")
async def show_reminders(message: Message):
    lang = user_lang.get(message.from_user.id, "en")
    reminders = get_reminders(message.from_user.id)
    if not reminders:
        await message.answer(translate("ℹ️ No reminders found.", lang))
        return
    for r in reminders:
        time_local = datetime.fromisoformat(r[3]).strftime("%H:%M")
        text = f"⏰ <b>{r[2]}</b> — <code>{time_local}</code>"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=translate("❌ Delete", lang), callback_data=f"del:{r[0]}")]
        ])
        await message.answer(text, reply_markup=keyboard)


@dp.message(F.text.startswith("/"))
async def unknown_command(message: Message):
    lang = user_lang.get(message.from_user.id, "en")
    msg = {
        "en": "❌ Invalid format. Use:\n1. /start\n2. /reminders",
        "ru": "❌ Неверный формат. Использовать:\n1. /start\n2. /reminders",
        "uk": "❌ Невірний формат. Використовуйте:\n1. /start\n2. /reminders"
    }
    await message.answer(msg.get(lang, msg["en"]))


@dp.message()
async def handle_reminder(message: Message):
    lang = user_lang.get(message.from_user.id, "en")
    text_input = message.text.strip()

    if " at " in text_input:
        parts = text_input.rsplit(" at ", 1)
    elif " в " in text_input:
        parts = text_input.rsplit(" в ", 1)
    elif " о " in text_input:
        parts = text_input.rsplit(" о ", 1)
    else:
        await message.answer(translate("❌ Invalid format. Use:\n1. Buy milk at 18:30\n2. Buy milk 28.07.2025 at 18:30", lang))
        return

    if len(parts) != 2:
        await message.answer(translate("❌ Invalid format. Use:\n1. Buy milk at 18:30\n2. Buy milk 28.07.2025 at 18:30", lang))
        return

    text_part, time_part = parts
    time_part = time_part.strip()
    text_part = text_part.strip()

    now = datetime.now()

    try:
        words = text_part.split()
        last_word = words[-1]

        if "." in last_word and len(last_word) == 10:
            date_str = last_word
            text = " ".join(words[:-1])
            dt = datetime.strptime(f"{date_str} {time_part}", "%d.%m.%Y %H:%M")
        else:
            t = datetime.strptime(time_part, "%H:%M")
            dt = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
            if dt < now:
                dt += timedelta(days=1)
            text = text_part
    except:
        await message.answer(translate("❌ Invalid date/time format. Example:\nBuy milk 28.07.2025 at 18:30", lang))
        return

    tz = detect_timezone(message.from_user.language_code)
    user_id = message.from_user.id
    reminder_id = add_reminder(user_id, text.strip(), dt.astimezone(pytz.utc), tz)

    job = scheduler.add_job(send_reminder, "date", run_date=dt.astimezone(pytz.utc), args=[user_id, text.strip()])
    job_mapping.setdefault(user_id, {})[reminder_id] = job

    success_msg = {
        "en": "✅ Reminder set!",
        "ru": "✅ Напоминание сохранено!",
        "uk": "✅ Нагадування збережено!"
    }
    await message.answer(success_msg.get(lang, success_msg["en"]))


@dp.callback_query(F.data.startswith("del:"))
async def delete_reminder_cb(callback: CallbackQuery):
    reminder_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    delete_reminder(reminder_id)

    job = job_mapping.get(user_id, {}).pop(reminder_id, None)
    if job:
        job.remove()

    lang = user_lang.get(user_id, "en")
    await callback.message.edit_text(translate("🗑️ Reminder deleted.", lang))


async def send_reminder(user_id, text):
    await bot.send_message(user_id, f"🔔 <b>Reminder:</b> {text}")


def translate(text, lang):
    if lang == "en":
        return text
    return GoogleTranslator(source="en", target=lang).translate(text)


async def run_bot():
    create_table()
    scheduler.start()
    await dp.start_polling(bot)
