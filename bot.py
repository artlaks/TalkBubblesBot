import os
import logging
import aiohttp
import asyncio
import tempfile
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
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу кружком!")

# Обработка сообщений
@dp.message()
async def handle_message(message: Message):
    try:
        # 1. Получаем ответ от AI
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

        await message.reply(ai_text)  # Текстовый ответ

        # 2. Генерация TTS
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
            tts = gTTS(ai_text, lang="ru")
            tts.save(audio_file.name)
            audio_path = audio_file.name

        # 3. Создание кружка через ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as video_file:
            video_path = video_file.name
            # Видео с чёрным фоном (кружок)
            subprocess.run([
                "ffmpeg", "-y",
                "-loop", "1",
                "-f", "lavfi", "-i", "color=c=black:s=240x240:d=5",
                "-i", audio_path,
                "-vf", "format=yuv420p,scale=240:240",
                "-c:v", "libx264", "-tune", "stillimage",
                "-c:a", "aac", "-shortest",
                video_path
            ], check=True)

        # 4. Отправляем кружок
        with open(video_path, "rb") as video:
            await message.answer_video_note(video)

        # Удаляем временные файлы
        os.remove(audio_path)
        os.remove(video_path)

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
