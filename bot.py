import os
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
PORT = int(os.getenv("PORT", 3000))

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenRouter клиент (интерфейс OpenAI)
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Telegram bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Модель DeepSeek
MODEL = "deepseek-chat"

async def get_response(prompt: str) -> str:
    """Запрос к модели через OpenRouter"""
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful English-speaking assistant for language learners."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Ошибка OpenRouter: {e}")
        return "⚠️ Ошибка при обращении к языковой модели."

@dp.message(F.text)
async def handle_message(message: types.Message):
    logger.info(f"Сообщение от {message.from_user.id}: {message.text}")
    await message.answer("🔍 Думаю...")
    reply = await get_response(message.text)
    await message.answer(reply)

# --- Webhook-сервер ---
WEBHOOK_PATH = "/webhook"
app = web.Application()

async def webhook_handler(request):
    update = await request.json()
    await dp.feed_webhook_update(bot, update)
    return web.Response()

app.router.add_post(WEBHOOK_PATH, webhook_handler)

async def on_startup(app):
    webhook_url = RENDER_EXTERNAL_URL + WEBHOOK_PATH
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook установлен: {webhook_url}")

app.on_startup.append(on_startup)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)
