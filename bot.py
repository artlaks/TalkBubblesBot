# bot.py
import os
import logging
from aiohttp import web
from dotenv import load_dotenv

# aiogram
from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import setup_application, SimpleRequestHandler

# OpenRouter (OpenAI-compatible client)
from openai import AsyncOpenAI

# Загрузка переменных окружения (локально .env, в Render переменные окружения настроены отдельно)
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")  # https://your-app.onrender.com (без /)

# Валидация
if not BOT_TOKEN or not OPENROUTER_API_KEY or not RENDER_EXTERNAL_URL:
    raise RuntimeError("BOT_TOKEN, OPENROUTER_API_KEY и RENDER_EXTERNAL_URL должны быть заданы")

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация OpenRouter client (через OpenAI-compatible interface)
# Если OpenRouter требует другой base_url, поменяй на тот, что в их документации.
client = AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

# Telegram bot и dispatcher
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Модель (имя модели в OpenRouter). При проблемах проверь документацию OpenRouter
MODEL = "deepseek-chat"

# Запрос к OpenRouter (DeepSeek через OpenRouter)
async def get_response_from_openrouter(prompt: str) -> str:
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful English-speaking assistant for language learners."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        # В новом клиенте структура ответа: resp.choices[0].message.content
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("Ошибка OpenRouter:")
        return "⚠️ Ошибка при обращении к языковой модели."

# Обработчик сообщений
@router.message()
async def handle_message(message: types.Message):
    text = message.text or ""
    logger.info(f"Сообщение от {message.from_user.id}: {text}")
    await message.answer("🔍 Думаю...")
    reply = await get_response_from_openrouter(text)
    await message.answer(reply)

# ---- Webhook + aiohttp app ----
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{RENDER_EXTERNAL_URL.rstrip('/')}{WEBHOOK_PATH}"

app = web.Application()

# on_startup / on_shutdown
async def on_startup_app(app: web.Application):
    # установить webhook у телеграма
    await bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown_app(app: web.Application):
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    logger.info("Webhook удалён")

app.on_startup.append(on_startup_app)
app.on_shutdown.append(on_shutdown_app)

# Регистрируем aiogram в aiohttp через утилиты
setup_application(app, dp, bot=bot, handle_in_background=True)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

# Запуск приложения
if __name__ == "__main__":
    logger.info("Запуск webhook-сервера...")
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 3000)))
