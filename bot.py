import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import io

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')  # Для Render, не используется
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу в пузыре!")

# Обработка текстовых сообщений (AI через Puter.js)
@dp.message()
async def handle_message(message: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://js.puter.com/v2/openrouter/v1/chat/completions",
                json={
                    "model": "google/gemma-2-9b-it:free",
                    "messages": [
                        {"role": "system", "content": "Ты дружелюбный виртуальный собеседник, отвечай на русском с юмором."},
                        {"role": "user", "content": message.text}
                    ],
                    "max_tokens": 150
                }
            ) as response:
                if response.status != 200:
                    raise Exception(f"API error: {response.status}")
                data = await response.json()
                ai_text = data['choices'][0]['message']['content']

        # Создание "пузыря" с текстом
        img = Image.new('RGB', (400, 100), color='white')
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("fonts/arial.ttf", 20)  # Загрузите шрифт в репозиторий
        except:
            font = ImageFont.load_default()
        d.text((10, 10), ai_text[:50], fill='black', font=font)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        # Отправка текста и изображения
        await message.reply(ai_text)
        await message.reply_photo(img_byte_arr)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await message.reply(f"Ой, что-то пошло не так: {str(e)}")

# Webhook setup
async def on_startup(bot: Bot) -> None:
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set to {webhook_url}")

if __name__ == '__main__':
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get('PORT', 8080))
    web.run_app(app, host='0.0.0.0', port=port)
