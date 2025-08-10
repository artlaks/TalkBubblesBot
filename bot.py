# bot.py
import os
import logging
from aiohttp import web
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

from openai import AsyncOpenAI

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")  # https://your-app.onrender.com

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")
if not OPENROUTER_API_KEY:
    raise RuntimeError("OPENROUTER_API_KEY not set")
if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL not set")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# OpenRouter client via OpenAI-compatible SDK
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

MODEL = "deepseek-chat"

async def get_response(prompt: str) -> str:
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful English-speaking assistant for language learners."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenRouter error")
        return "⚠️ Ошибка при обращении к языковой модели."

@dp.message()
async def handle_message(message: types.Message):
    text = message.text or ""
    logger.info(f"Received from {message.from_user.id}: {text}")
    await message.answer("🔍 Думаю…")
    reply = await get_response(text)
    await message.answer(reply)

# webhook
WEBHOOK_PATH = "/webhook"
app = web.Application()

async def webhook_handler(request):
    update = await request.json()
    await dp.feed_webhook_update(bot, update)
    return web.Response(status=200)

app.router.add_post(WEBHOOK_PATH, webhook_handler)

async def on_startup(app):
    webhook_url = RENDER_EXTERNAL_URL.rstrip("/") + WEBHOOK_PATH
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")

app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting aiohttp app on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)
