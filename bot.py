import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from gtts import gTTS
from moviepy.editor import ColorClip, AudioFileClip, CompositeVideoClip
import tempfile

logging.basicConfig(level=logging.INFO)
load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("TELEGRAM_TOKEN or OPENROUTER_API_KEY not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу в пузыре с голосом!")

@dp.message()
async def handle_message(message: Message):
    try:
        # Получаем ответ от OpenRouter
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

        # Генерируем TTS (голос) на русском
        tts = gTTS(text=ai_text, lang='ru')
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf_audio:
            tts.save(tf_audio.name)

        # Создаём видео-кружок с белым кругом (360x360)
        duration = AudioFileClip(tf_audio.name).duration
        circle_clip = ColorClip(size=(360, 360), color=(255, 255, 255), duration=duration)
        # Можно добавить анимацию, текст и пр. позже

        audio_clip = AudioFileClip(tf_audio.name)
        video = circle_clip.set_audio(audio_clip)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf_video:
            video.write_videofile(tf_video.name, codec='libx264', fps=24, audio_codec='aac', verbose=False, logger=None)
        
        # Отправляем видео-кружок
        with open(tf_video.name, 'rb') as video_file:
            await message.reply_video_note(video_file)

        # Чистим временные файлы
        os.unlink(tf_audio.name)
        os.unlink(tf_video.name)

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await message.reply(f"Ой, что-то пошло не так: {str(e)}")

async def on_startup(app) -> None:
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set to {webhook_url}")

if __name__ == '__main__':
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get('PORT', 8080))
    logging.info(f"Запуск на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
