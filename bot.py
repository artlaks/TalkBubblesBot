import os
import logging
import asyncio
import requests

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import setup_application, SimpleRequestHandler

from aiohttp import web

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # e.g., https://your-app-name.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

if not BOT_TOKEN or not HF_TOKEN or not WEBHOOK_HOST:
    raise RuntimeError("❌ Не заданы переменные BOT_TOKEN, HF_TOKEN или WEBHOOK_HOST")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

MODEL_URL = "https://api-inference.huggingface.co/models/deepseek-ai/deepseek-chat"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

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

@router.message()
async def handle_message(message: types.Message):
    logging.info(f"📩 Получено сообщение: {message.text}")
    await message.answer("💭 Думаю...")
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, query_deepseek, message.text)
    await message.answer(f"🤖 {reply}")

async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.info("❌ Webhook удалён")

async def main():
    app = web.Application()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    setup_application(app, dp, bot=bot, handle_in_background=True)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    logging.info("🚀 Запуск Webhook-сервера")
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Приложение остановлено")

