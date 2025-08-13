import os
import logging
import aiohttp
import subprocess
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from gtts import gTTS

# Логирование
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')

if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("TELEGRAM_TOKEN or OPENROUTER_API_KEY not set")
if not RENDER_EXTERNAL_HOSTNAME:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME not set")

# Инициализация бота
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# /start
@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу кружком 🎤")

# Обработка сообщений
@dp.message()
async def handle_message(message: Message):
    try:
        # Получаем ответ от ИИ
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
                    logging.error(f"API error: {response.status}, Response: {response_text}")
                    raise Exception(f"API error: {response.status}: {response_text}")
                data = await response.json()
                ai_text = data['choices'][0]['message']['content']

        # Сохраняем MP3
        tts = gTTS(ai_text, lang="ru")
        mp3_path = "voice.mp3"
        tts.save(mp3_path)

        # Конвертируем MP3 в WebM (кружок)
        webm_path = "circle.webm"
        subprocess.run([
            "ffmpeg", "-i", mp3_path, 
            "-vf", "scale=240:240,format=yuv420p",
            "-c:v", "libvpx-vp9", 
            "-c:a", "libopus", 
            "-b:v", "256k", 
            "-y", webm_path
        ], check=True)

        # Отправляем текст и кружок
        await message.reply(ai_text)
        with open(webm_path, "rb") as video:
            await bot.send_video_note(chat_id=message.chat.id, video_note=video)

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await message.reply(f"Ой, что-то пошло не так: {str(e)}")

# Автоматическая установка вебхука при старте
async def on_startup(app) -> None:
    webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/webhook"
    try:
        current_webhook = await bot.get_webhook_info()
        if current_webhook.url != webhook_url:
            await bot.delete_webhook()
            await bot.set_webhook(webhook_url, allowed_updates=["message"])
            logging.info(f"Webhook установлен: {webhook_url}")
        else:
            logging.info(f"Webhook уже установлен: {webhook_url}")
    except Exception as e:
        logging.error(f"Ошибка при установке webhook: {str(e)}")
        raise

if __name__ == '__main__':
    app = web.Application()
    app.on_startup.append(on_startup)

    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get('PORT', 8080))
    logging.info(f"Запуск на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
