
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import json
import time
from datetime import datetime, timedelta
import re

API_TOKEN = 'YOUR_BOT_TOKEN'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

users_file = 'users.json'

def load_users():
    try:
        with open(users_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users(data):
    with open(users_file, 'w') as f:
        json.dump(data, f)

users = load_users()

main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("Клик 👆"))
main_kb.add(KeyboardButton("Пригласить друзей"), KeyboardButton("Рейтинг участников"))
main_kb.add(KeyboardButton("Донат"))

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user_id = str(message.from_user.id)
    referrer = message.get_args()
    
    if user_id not in users:
        if not message.from_user.username:
            await message.answer("Для игры необходимо разрешить доступ к своему аккаунту (имя пользователя).")
            return
        
        await message.answer("Добро пожаловать! Придумай никнейм (не длиннее 7 символов, без эмодзи):")
        await bot.send_message(user_id, "Отправь свой никнейм в ответ на это сообщение.")
        users[user_id] = {"clicks": 0, "nickname": "", "referrer": referrer, "last_notified": 0}
        save_users(users)
    else:
        await message.answer("Ты уже зарегистрирован!", reply_markup=main_kb)

@dp.message_handler(lambda message: message.text and message.from_user.id in map(int, users.keys()) and users[str(message.from_user.id)]["nickname"] == "")
async def nickname_handler(message: types.Message):
    nickname = message.text.strip()
    if len(nickname) > 7 or re.search(r'[^\w\d_]', nickname):
        await message.answer("Некорректный никнейм. Максимум 7 символов, только буквы и цифры, без эмодзи.")
        return
    user_id = str(message.from_user.id)
    users[user_id]["nickname"] = nickname
    referrer = users[user_id]["referrer"]
    if referrer in users:
        users[referrer]["clicks"] += 500
    save_users(users)
    await message.answer(f"Ты успешно зарегистрирован как {nickname}!", reply_markup=main_kb)

@dp.message_handler(lambda message: message.text == "Клик 👆")
async def click_handler(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id not in users or users[user_id]["nickname"] == "":
        await message.answer("Сначала зарегистрируйся через /start.")
        return
    users[user_id]["clicks"] += 1
    save_users(users)
    await message.answer(f"Ты кликнул! Всего кликов: {users[user_id]['clicks']}")

@dp.message_handler(lambda message: message.text == "Пригласить друзей")
async def invite_handler(message: types.Message):
    link = f"https://t.me/{(await bot.get_me()).username}?start={message.from_user.id}"
    await message.answer(f"Пригласи друзей по этой ссылке и получай +500 за каждого: {link}")

@dp.message_handler(lambda message: message.text == "Рейтинг участников")
async def rating_handler(message: types.Message):
    rating = sorted(users.items(), key=lambda x: x[1]['clicks'], reverse=True)
    top = "
".join([f"{i+1}. {v['nickname']} — {v['clicks']}" for i, (k, v) in enumerate(rating[:10])])
    await message.answer(f"🏆 Топ-10 участников:

{top}")

@dp.message_handler(lambda message: message.text == "Донат")
async def donate_handler(message: types.Message):
    await message.answer("Поддержи проект донатом 💸
Скоро здесь появится кнопка оплаты.")

async def auto_notify():
    while True:
        now = datetime.utcnow() + timedelta(hours=3)  # МСК
        if now.minute == 0:
            rating = sorted(users.items(), key=lambda x: x[1]['clicks'], reverse=True)
            top = "
".join([f"{i+1}. {v['nickname']} — {v['clicks']}" for i, (k, v) in enumerate(rating[:10])])
            for uid in users:
                try:
                    await bot.send_message(uid, f"🏆 Обновлённый рейтинг:

{top}")
                except:
                    continue
            await asyncio.sleep(60)
        await asyncio.sleep(10)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(auto_notify())
    executor.start_polling(dp, skip_updates=True)
