import g4f
from telethon import TelegramClient, events
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
import requests
import datetime
import logging

API_ID = 
API_HASH = ''
TELEGRAM_SESSION = 'session_name'
BOT_TOKEN = ""
AUTHORIZED_USER_ID = 
BANNED_USERS_FILE = "banned_users.json"
CODES_FILE = "codes_storage.json"
BLOCKED_USERS_FILE = "blocked_users.json"
AUTOREPLY_STATE_FILE = "autoreply_state.json"

logging.basicConfig(level=logging.DEBUG)

if os.path.exists(f'{TELEGRAM_SESSION}.session'):
    os.remove(f'{TELEGRAM_SESSION}.session')
    logging.info("Старая сессия удалена.")

# Настройки прокси (если нужно)
proxy = None  # Пример: ("socks5", "proxy_address", 1080, True, "username", "password")

client = TelegramClient(TELEGRAM_SESSION, API_ID, API_HASH, proxy=proxy)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

ai_enabled = True
response_delay = 0
banned_users = set()
user_requests = {}
codes_storage = {}
autoreply_enabled = False
autoreply_text = "Это текст автоответа."
blocked_users = set()

def load_banned_users():
    try:
        with open(BANNED_USERS_FILE, "r") as file:
            return set(json.load(file))
    except FileNotFoundError:
        return set()

def save_banned_users():
    with open(BANNED_USERS_FILE, "w") as file:
        json.dump(list(banned_users), file)

def load_codes():
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, "r") as file:
            return json.load(file)
    return {}

def save_codes():
    with open(CODES_FILE, "w") as file:
        json.dump(codes_storage, file)

def load_blocked_users():
    try:
        with open(BLOCKED_USERS_FILE, "r") as file:
            return set(json.load(file))
    except FileNotFoundError:
        return set()

def save_blocked_users():
    with open(BLOCKED_USERS_FILE, "w") as file:
        json.dump(list(blocked_users), file)

def load_autoreply_state():
    try:
        with open(AUTOREPLY_STATE_FILE, "r") as file:
            state = json.load(file)
            return state.get("autoreply_enabled", False), state.get("autoreply_text", "Это текст автоответа.")
    except FileNotFoundError:
        return False, "Это текст автоответа."

def save_autoreply_state():
    with open(AUTOREPLY_STATE_FILE, "w") as file:
        json.dump({"autoreply_enabled": autoreply_enabled, "autoreply_text": autoreply_text}, file)

banned_users = load_banned_users()
codes_storage = load_codes()
blocked_users = load_blocked_users()
autoreply_enabled, autoreply_text = load_autoreply_state()

def is_user_banned(user_id: int) -> bool:
    return user_id in banned_users

async def generate_gpt_response(user_input: str) -> str:
    try:
        response = g4f.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": user_input}],
        )
        if isinstance(response, str):
            return response
        elif isinstance(response, dict) and 'choices' in response:
            return response['choices'][0]['message']['content']
        else:
            return "❌ Не удалось получить корректный ответ от модели."
    except Exception as e:
        logging.error(f"Ошибка при запросе к GPT: {e}")
        return f"⚠️ Произошла ошибка: {str(e)}"

# Обработчики Telethon
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def handle_private_message(event):
    global ai_enabled, response_delay, autoreply_enabled, autoreply_text

    if event.sender_id in banned_users:
        await event.reply("⛔️ Вы заблокированы и не можете использовать этого бота.")
        return

    if not ai_enabled:
        return

    if event.sender_id in blocked_users:
        return

    if response_delay > 0:
        await asyncio.sleep(response_delay)

    if autoreply_enabled:
        await event.reply(autoreply_text)
        return

    user_input = event.message.message
    response = await generate_gpt_response(user_input)
    await event.reply(response)

# Обработчики aiogram
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if is_user_banned(message.from_user.id):
        await message.answer("⛔️ Вы заблокированы и не можете использовать этого бота.")
        return
    await message.answer("йоу, /about для инфы/справки о боте")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "Доступные команды:\n"
        "/ai_on — включить ИИ.\n"
        "/ai_off — отключить ИИ.\n"
        "/set_delay <секунды> — установить задержку перед ответом.\n"
        "/ban <user_id> — заблокировать пользователя.\n"
        "/unban <user_id> — разблокировать пользователя.\n"
        "/banned — список забаненных пользователей.\n"
        "/upload_code — загрузить код.\n"
        "/get_code <название> — получить код.\n"
        "/code_list — список всех кодов.\n"
        "/delete_code <название> — удалить код.\n"
        "/log <user_id> — логи пользователя.\n"
        "/logs — логи всех пользователей.\n"
        "/autoreply_on — включить автоответчик.\n"
        "/autoreply_off — выключить автоответчик.\n"
        "/set_autoreply <текст> — установить текст автоответа.\n"
        "/about — информация о боте.\n"
        "/block_user <user_id> — заблокировать пользователя (ИИ не будет отвечать).\n"
        "/unblock_user <user_id> — разблокировать пользователя."
    )
    await message.answer(help_text)

@dp.message(Command("ai_on"))
async def cmd_ai_on(message: types.Message):
    global ai_enabled
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    ai_enabled = True
    await message.answer("✅ ИИ включен и готов к работе.")

@dp.message(Command("ai_off"))
async def cmd_ai_off(message: types.Message):
    global ai_enabled
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    ai_enabled = False
    await message.answer("❌ ИИ отключен и не будет отвечать на сообщения.")

@dp.message(Command("set_delay"))
async def cmd_set_delay(message: types.Message):
    global response_delay
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        delay = int(message.text.split(" ", 1)[1].strip())
        if delay >= 0:
            response_delay = delay
            await message.answer(f"✅ Задержка перед ответом установлена на {delay} секунд.")
        else:
            await message.answer("❌ Задержка не может быть отрицательной.")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите задержку в секундах. Пример: /set_delay 5")

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        user_id = int(message.text.split(" ", 1)[1].strip())
        banned_users.add(user_id)
        save_banned_users()
        await message.answer(f"🔴 Пользователь с ID {user_id} заблокирован.")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите ID пользователя. Пример: /ban 123456789")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        user_id = int(message.text.split(" ", 1)[1].strip())
        banned_users.discard(user_id)
        save_banned_users()
        await message.answer(f"🟢 Пользователь с ID {user_id} разблокирован.")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите ID пользователя. Пример: /unban 123456789")

@dp.message(Command("banned"))
async def cmd_banned(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    if not banned_users:
        await message.answer("🚫 Нет забаненных пользователей.")
    else:
        banned_list = "\n".join(str(user_id) for user_id in banned_users)
        await message.answer(f"🔴 Забаненные пользователи:\n{banned_list}")

@dp.message(Command("upload_code"))
async def cmd_upload_code(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        code_name, code_content = message.text.split("\n", 1)[1].split(":", 1)
        code_name = code_name.strip()
        code_content = code_content.strip()
        codes_storage[code_name] = code_content
        save_codes()
        await message.answer(f"✅ Код под названием '{code_name}' успешно загружен.")
    except ValueError:
        await message.answer("❌ Необходимо указать название кода и сам код в формате 'Название: Код'.")

@dp.message(Command("get_code"))
async def cmd_get_code(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        code_name = message.text.split(" ", 1)[1].strip()
        if code_name in codes_storage:
            code_content = codes_storage[code_name]
            await message.answer(f"Код '{code_name}':\n```python\n{code_content}\n```", parse_mode="Markdown")
        else:
            await message.answer(f"❌ Код с названием '{code_name}' не найден.")
    except IndexError:
        await message.answer("❌ Укажите название кода. Пример: /get_code MyCode")

@dp.message(Command("code_list"))
async def cmd_code_list(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    if not codes_storage:
        await message.answer("📝 Список кодов пуст.")
    else:
        code_list = "📝 Список кодов:\n" + "\n".join(f"- {name}" for name in codes_storage.keys())
        await message.answer(code_list)

@dp.message(Command("delete_code"))
async def cmd_delete_code(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        code_name = message.text.split(" ", 1)[1].strip()
        if code_name in codes_storage:
            del codes_storage[code_name]
            save_codes()
            await message.answer(f"✅ Код с названием '{code_name}' успешно удалён.")
        else:
            await message.answer(f"❌ Код с названием '{code_name}' не найден.")
    except IndexError:
        await message.answer("❌ Укажите название кода. Пример: /delete_code MyCode")

@dp.message(Command("log"))
async def cmd_log(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        user_id = int(message.text.split(" ", 1)[1].strip())
        if user_id in user_requests:
            logs = "\n".join(f"{log['time']}: {log['request']}" for log in user_requests[user_id])
            await message.answer(f"📜 Логи пользователя {user_id}:\n{logs}")
        else:
            await message.answer(f"❌ Логи для пользователя {user_id} не найдены.")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите ID пользователя. Пример: /log 123456789")

@dp.message(Command("logs"))
async def cmd_logs(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    if not user_requests:
        await message.answer("📜 Логи отсутствуют.")
    else:
        logs = []
        for user_id, requests in user_requests.items():
            logs.append(f"Пользователь {user_id}:\n" + "\n".join(f"{log['time']}: {log['request']}" for log in requests))
        await message.answer("📜 Логи всех пользователей:\n" + "\n\n".join(logs))

@dp.message(Command("autoreply_on"))
async def cmd_autoreply_on(message: types.Message):
    global autoreply_enabled
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    autoreply_enabled = True
    save_autoreply_state()
    await message.answer("✅ Автоответчик включен.")

@dp.message(Command("autoreply_off"))
async def cmd_autoreply_off(message: types.Message):
    global autoreply_enabled
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    autoreply_enabled = False
    save_autoreply_state()
    await message.answer("❌ Автоответчик отключен.")

@dp.message(Command("set_autoreply"))
async def cmd_set_autoreply(message: types.Message):
    global autoreply_text
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        autoreply_text = message.text.split(" ", 1)[1].strip()
        save_autoreply_state()
        await message.answer(f"✅ Текст автоответа установлен: {autoreply_text}")
    except IndexError:
        await message.answer("❌ Укажите текст автоответа. Пример: /set_autoreply Привет! Я бот.")

@dp.message(Command("about"))
async def cmd_about(message: types.Message):
    about_text = (
        "Привет, Я — бот для обработки сообщений в телеграмме"
    )
    await message.answer(about_text)

@dp.message(Command("block_user"))
async def cmd_block_user(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        user_id = int(message.text.split(" ", 1)[1].strip())
        blocked_users.add(user_id)
        save_blocked_users()
        await message.answer(f"✅ Пользователь с ID {user_id} добавлен в список заблокированных.")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите ID пользователя. Пример: /block_user 123456789")

@dp.message(Command("unblock_user"))
async def cmd_unblock_user(message: types.Message):
    if message.from_user.id != AUTHORIZED_USER_ID:
        await message.answer("🚫 У вас нет прав для выполнения этой команды.")
        return
    try:
        user_id = int(message.text.split(" ", 1)[1].strip())
        if user_id in blocked_users:
            blocked_users.discard(user_id)
            save_blocked_users()
            await message.answer(f"✅ Пользователь с ID {user_id} удалён из списка заблокированных.")
        else:
            await message.answer(f"❌ Пользователь с ID {user_id} не найден в списке заблокированных.")
    except (IndexError, ValueError):
        await message.answer("❌ Укажите ID пользователя. Пример: /unblock_user 123456789")

async def start_telethon():
    await client.start()
    logging.info("Telethon клиент запущен и слушает личные сообщения...")
    await client.run_until_disconnected()

async def start_bot():
    await dp.start_polling(bot)

async def main():
    await asyncio.gather(
        start_telethon(),
        start_bot()
    )

if __name__ == '__main__':
    asyncio.run(main())