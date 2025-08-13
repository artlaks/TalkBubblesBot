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
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')  # Для Render, не используется с Puter.js
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'talkbubblesbot.onrender.com')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")
if not RENDER_EXTERNAL_HOSTNAME:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Команда /start
@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу в пузыре!")

# Команда /setwebhook (для ручной настройки)
@dp.message(Command(commands=['setwebhook']))
async def set_webhook_manual(message: Message):
    webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/webhook"
    try:
        await bot.delete_webhook()
        await bot.set_webhook(webhook_url, allowed_updates=["message"])
        await message.reply(f"Webhook установлен: {webhook_url}")
        logging.info(f"Webhook вручную установлен: {webhook_url}")
    except Exception as e:
        logging.error(f"Ошибка установки webhook вручную: {str(e)}")
        await message.reply(f"Не удалось установить webhook: {str(e)}")

# Обработка текстовых сообщений
@dp.message()
async def handle_message(message: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://js.puter.com/v2/openrouter/v1/chat/completions",
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Referer": f"https://{RENDER_EXTERNAL_HOSTNAME}",
                    "Origin": f"https://{RENDER_EXTERNAL_HOSTNAME}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
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
                    response_text = await response.text()
                    logging.error(f"Ошибка API: {response.status}, Ответ: {response_text}")
                    raise Exception(f"Ошибка API: {response.status}: {response_text}")
                data = await response.json()
                ai_text = data['choices'][0]['message']['content']

        # Создание "пузыря" с текстом
        img = Image.new('RGB', (400, 100), color='white')
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("fonts/arial.ttf", 20)  # Загрузите шрифт в папку fonts/
        except:
            font = ImageFont.load_default()
            logging.warning("Шрифт arial.ttf не найден, используется дефолтный")
        d.text((10, 10), ai_text[:50], fill='black', font=font)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        # Отправка текста и изображения
        await message.reply(ai_text)
        await message.reply_photo(img_byte_arr)
    except Exception as e:
        logging.error(f"Ошибка: {str(e)}")
        await message.reply(f"Ой, что-то пошло не так: {str(e)}")

# Webhook setup
async def on_startup() -> None:
    webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/webhook"
    logging.info(f"Попытка установить webhook: {webhook_url}")
    try:
        await bot.delete_webhook()
        await bot.set_webhook(webhook_url, allowed_updates=["message"])
        logging.info(f"Webhook успешно установлен: {webhook_url}")
    except Exception as e:
        logging.error(f"Ошибка установки webhook: {str(e)}")
        raise

if __name__ == '__main__':
    dp.startup.register(on_startup)
    
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get('PORT', 8080))
    logging.info(f"Запуск сервера на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
