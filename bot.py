import os
import logging
import asyncio
import requests

from aiohttp import web
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import setup_application, SimpleRequestHandler

# 🔧 Логирование
logging.basicConfig(level=logging.INFO)

# 📦 Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://your-render-url.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# ❗ Проверка переменных
if not BOT_TOKEN or not HF_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("❌ Переменные BOT_TOKEN, HF_TOKEN или WEBHOOK_HOST не заданы!")

# 🤖 Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# 🔗 Модель DeepSeek на Hugging Face
MODEL_URL = "https://api-inference.huggingface.co/models/deepseek-ai/deepseek-chat"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# 🧠 Функция обращения к DeepSeek
def query_deepseek(prompt: str) -> str:
    payload = {
        "inputs": f"<|system|>\nYou are a helpful assistant.\n<|user|>\n{prompt}\n<|assistant|>",
        "parameters": {"max_new_tokens": 200}
    }
    response = requests.post(MODEL_URL, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        return result[0]["generated_text"].split("<|assistant|>")[-1].strip()
    else:
        logging.error(f"❌ Ошибка HuggingFace API: {response.status_code} - {response.text}")
        return "⚠️ Не удалось получить ответ от Deepseek."

# 📩 Обработка сообщений от пользователей
@router.message()
async def handle_message(message: types.Message):
    logging.info(f"📨 Сообщение от {message.from_user.id}: {message.text}")
    await message.answer("💭 Думаю...")
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, query_deepseek, message.text)
    await message.answer(f"🤖 {reply}")

# 🌐 Webhook-сервер aiohttp
app = web.Application()

# 🔄 Обработка запуска
async def on_startup_app(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")

# 🔁 Обработка остановки
async def on_shutdown_app(app: web.Application):
    await bot.delete_webhook()
    logging.info("🛑 Webhook удалён")

# 📡 Настройка Webhook и сервера
app.on_startup.append(on_startup_app)
app.on_shutdown.append(on_shutdown_app)

setup_application(app, dp, bot=bot, handle_in_background=True)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

# 🚀 Запуск приложения
if __name__ == "__main__":
    logging.info("🚀 Webhook бот запущен")
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
