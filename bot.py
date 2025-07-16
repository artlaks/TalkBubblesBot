import os
import logging
import requests
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

# Настройки логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Создание бота и диспетчера
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Hugging Face модель DeepSeek
HUGGINGFACE_MODEL = "deepseek-ai/deepseek-llm-7b-instruct"

def query_deepseek(prompt: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HUGGINGFACE_MODEL}"
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}"
    }
    data = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 200,
            "do_sample": True,
            "temperature": 0.7,
            "top_p": 0.9
        }
    }

    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        try:
            return response.json()[0]["generated_text"]
        except Exception as e:
            logger.error(f"Ошибка парсинга ответа: {e}")
            return "⚠️ Ошибка в ответе модели."
    else:
        logger.error(f"❌ Ошибка HuggingFace API: {response.status_code} - {response.text}")
        return "⚠️ Ошибка при обращении к языковой модели."

@dp.message()
async def handle_message(message: types.Message):
    user_input = message.text
    logger.info(f"📨 Сообщение от {message.from_user.id}: {user_input}")
    
    await message.answer("💬 Думаю...")

    reply = query_deepseek(user_input)
    await message.answer(reply)

# ---- Веб-сервер и webhook ----

WEBHOOK_PATH = "/webhook"
app = web.Application()
app.router.add_post(WEBHOOK_PATH, dp.handler)

async def on_startup_app(app: web.Application):
    webhook_url = os.getenv("RENDER_EXTERNAL_URL", "") + WEBHOOK_PATH
    await bot.set_webhook(webhook_url)
    logger.info(f"📡 Установлен webhook: {webhook_url}")

app.on_startup.append(on_startup_app)

if __name__ == '__main__':
    web.run_app(app, host='0.0.0.0', port=int(os.getenv("PORT", 3000)))
