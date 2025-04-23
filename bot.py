
import logging
import os
import re
import asyncio
import aiosqlite
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

API_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

DB_FILE = "clicker.db"
cooldowns = {}

LEAGUES = [
    ("Рядовой", 0, 501),
    ("Ефрейтор", 502, 999),
    ("Сержант", 1000, 2501),
    ("Ст. сержант", 2502, 5000),
    ("Лейтенант", 5001, 15001),
    ("Капитан", 15002, 25001),
    ("Майор", 25002, 39999),
    ("Полковник", 40000, float("inf")),
]

DAILY_MISSIONS = {100: 100, 250: 250, 1000: 1000}

def today_str():
    return (datetime.utcnow() + timedelta(hours=3)).strftime("%Y-%m-%d")

def is_night():
    return 0 <= (datetime.utcnow() + timedelta(hours=3)).hour < 10

async def get_league(clicks):
    for name, lo, hi in LEAGUES:
        if lo <= clicks <= hi:
            return name
    return "–"

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("🖱 Клик 👆"))
main_kb.add(KeyboardButton("👥 Пригласить друзей"), KeyboardButton("🏆 Рейтинг участников"))
main_kb.add(KeyboardButton("📋 Профиль"), KeyboardButton("💸 Донат"))
main_kb.add(KeyboardButton("🎯 Цели на сегодня"), KeyboardButton("❓ Помощь"))

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            nickname TEXT,
            clicks INTEGER DEFAULT 0,
            league TEXT,
            daily_clicks INTEGER DEFAULT 0,
            missions_done TEXT DEFAULT '',
            night_clicks INTEGER DEFAULT 0,
            night_hunter INTEGER DEFAULT 0,
            achievements TEXT DEFAULT '',
            date TEXT
        )
        """)
        await db.commit()

@dp.message_handler(commands=["start"])
async def cmd_start(m: types.Message):
    await init_db()
    uid = m.from_user.id
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT * FROM users WHERE id = ?", (uid,)) as cur:
            user = await cur.fetchone()
        if not user:
            await db.execute("INSERT INTO users (id, date, league) VALUES (?, ?, ?)",
                             (uid, today_str(), "Рядовой"))
            await db.commit()
            return await m.answer("Добро пожаловать! Придумай никнейм (до 7 символов, без эмодзи):")
        else:
            await m.answer("Ты уже зарегистрирован!", reply_markup=main_kb)

@dp.message_handler(lambda m: True)
async def all_messages(m: types.Message):
    uid = m.from_user.id
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT nickname FROM users WHERE id = ?", (uid,)) as cur:
            row = await cur.fetchone()
        if row and not row[0]:
            nick = m.text.strip()
            if len(nick) > 7 or re.search(r"[^\w\d_]", nick):
                return await m.answer("❌ Никнейм некорректен.")
            await db.execute("UPDATE users SET nickname = ? WHERE id = ?", (nick, uid))
            await db.commit()
            return await m.answer(f"✅ Никнейм установлен: {nick}", reply_markup=main_kb)

    if m.text == "🖱 Клик 👆":
        now_ts = datetime.utcnow().timestamp()
        if now_ts - cooldowns.get(uid, 0) < 3:
            return await m.answer("⏳ Подожди 3 сек.")
        cooldowns[uid] = now_ts

        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET date = ? WHERE id = ?", (today_str(), uid))
            await db.commit()

            async with db.execute("SELECT clicks, daily_clicks, night_clicks, night_hunter, achievements FROM users WHERE id = ?", (uid,)) as cur:
                row = await cur.fetchone()
                if row is None:
                    return await m.answer("Ошибка: ты не зарегистрирован. Напиши /start")
                clicks, daily, night, night_hunter, ach = row

            inc = 2 if is_night() else 1
            clicks += inc
            daily += 1
            night += inc if is_night() else 0
            ach_list = ach.split(",") if ach else []

            if night >= 1000 and not night_hunter:
                night_hunter = 1
                ach_list.append("Ночной охотник")

            league = await get_league(clicks)
            await db.execute("""
                UPDATE users SET clicks=?, daily_clicks=?, night_clicks=?, night_hunter=?, achievements=?, league=?
                WHERE id=?
            """, (clicks, daily, night, night_hunter, ",".join(ach_list), league, uid))
            await db.commit()

        await m.answer(f"🖱 Клики: {clicks} | Лига: {league}
🏅 Ачивки: {', '.join(ach_list) or '—'}", reply_markup=main_kb)

    elif m.text == "📋 Профиль":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT nickname, clicks, daily_clicks, night_clicks, league, achievements FROM users WHERE id = ?", (uid,)) as cur:
                row = await cur.fetchone()
                if row is None:
                    return await m.answer("Сначала напиши /start")
                nick, clicks, daily, night, league, ach = row
        await m.answer(f"👤 {nick}
🖱 {clicks} кликов
🎯 Сегодня: {daily}
🌙 Ночь: {night}
🎖 Лига: {league}
🏅 Ачивки: {ach or '—'}", reply_markup=main_kb)

    elif m.text == "🎯 Цели на сегодня":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT daily_clicks, missions_done FROM users WHERE id = ?", (uid,)) as cur:
                row = await cur.fetchone()
                if row is None:
                    return await m.answer("Сначала напиши /start")
                daily, done = row
        done_list = done.split(",") if done else []
        response = ["🎯 Цели на сегодня:
"]
        for goal, reward in DAILY_MISSIONS.items():
            mark = "✅" if str(goal) in done_list else "⏳"
            response.append(f"• Сделай {goal} кликов — +{reward} {mark}")
        await m.answer("
".join(response), reply_markup=main_kb)

    elif m.text == "🏆 Рейтинг участников":
        async with aiosqlite.connect(DB_FILE) as db:
            async with db.execute("SELECT nickname, clicks, league FROM users ORDER BY clicks DESC LIMIT 10") as cur:
                top = await cur.fetchall()
        msg = "🏆 Топ‑10:
" + "
".join(f"{i+1}. {row[0]} — {row[1]} [{row[2]}]" for i, row in enumerate(top))
        await m.answer(msg, reply_markup=main_kb)

    elif m.text == "💸 Донат":
        await m.answer("💸 Донат будет позже!", reply_markup=main_kb)

    elif m.text == "👥 Пригласить друзей":
        link = f"https://t.me/{(await bot.get_me()).username}?start={uid}"
        await m.answer(f"👥 Приглашай по ссылке:
{link}", reply_markup=main_kb)

    elif m.text == "❓ Помощь":
        await m.answer(
            "📖 Команды:
/start — регистрация
🖱 Клик — +1 (ночью ×2)
📋 Профиль
🏆 Рейтинг
🎯 Цели дня
👥 Пригласить друзей",
            reply_markup=main_kb
        )

if __name__ == '__main__':
    async def main():
        await init_db()
        await dp.start_polling()
    asyncio.run(main())
