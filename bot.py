import os
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание клиента OpenRouter через OpenAI совместимый интерфейс
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Используем DeepSeek через OpenRouter
MODEL = "deepseek-chat"

async def get_response_from_openrouter(prompt: str) -> str:
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
        logger.error(f"\u274c Ошибка OpenRouter: {e}")
        return "\u26a0\ufe0f Ошибка при обращении к языковой модели."

@dp.message()
async def handle_message(message: types.Message):
    user_input = message.text
    logger.info(f"\ud83d\udce8 Сообщение от {message.from_user.id}: {user_input}")

    await message.answer("\ud83d\udd0d Думаю...")

    reply = await get_response_from_openrouter(user_input)
    await message.answer(reply)

# ---- Webhook-сервер ----
WEBHOOK_PATH = "/webhook"
app = web.Application()
app.router.add_post(WEBHOOK_PATH, dp.handler)

async def on_startup_app(app: web.Application):
    webhook_url = os.getenv("RENDER_EXTERNAL_URL", "") + WEBHOOK_PATH
    await bot.set_webhook(webhook_url)
    logger.info(f"\ud83d\udce1 Установлен webhook: {webhook_url}")

app.on_startup.append(on_startup_app)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.getenv("PORT", 3000)))
