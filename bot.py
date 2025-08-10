import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('TELEGRAM_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set in environment variables")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Логирование для отладки
logging.basicConfig(level=logging.INFO)

# Команда /start
@dp.message(commands=['start'])
async def send_welcome(message: Message):
    await message.reply("Привет! Я виртуальный собеседник TalkBubblesBot. Расскажи что-нибудь, и я отвечу.")

# Обработка текстовых сообщений (простой собеседник: эхо с "пузырем")
@dp.message()
async def echo_message(message: Message):
    text = message.text
    response = f"🗨️ Ты сказал: {text}. Интересно! 🗨️"
    await message.reply(response)

# Webhook setup
async def on_startup(bot: Bot) -> None:
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"  # Render предоставит hostname; подставьте ваш URL
    await bot.set_webhook(webhook_url)

if __name__ == '__main__':
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    # Запуск сервера на $PORT
    port = int(os.environ.get('PORT', 8080))
    web.run_app(app, host='0.0.0.0', port=port)
