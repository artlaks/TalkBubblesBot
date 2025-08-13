import os
import logging
import aiohttp
import io
import numpy as np
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
import imageio
from pydub import AudioSegment

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'talkbubblesbot.onrender.com')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set")
if not RENDER_EXTERNAL_HOSTNAME:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Глобальный объект app для aiohttp
app = web.Application()

# Кэширование шрифта
FONT = None
def load_font():
    global FONT
    if FONT is None:
        try:
            FONT = ImageFont.truetype("fonts/arial.ttf", 20)
        except:
            FONT = ImageFont.load_default()
            logging.warning("Шрифт arial.ttf не найден, используется дефолтный")
    return FONT

# Команда /start
@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу видеосообщением!")

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

# Генерация аудио и определение длительности
def text_to_speech(text: str, lang: str = 'ru') -> tuple[bytes, float]:
    try:
        tts = gTTS(text=text, lang=lang)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        audio = AudioSegment.from_file(audio_bytes, format="mp3")
        duration = len(audio) / 1000.0  # Длительность в секундах
        audio_bytes.seek(0)
        return audio_bytes.read(), duration
    except Exception as e:
        logging.error(f"Ошибка генерации аудио: {str(e)}")
        raise

# Генерация анимации
def create_animation(text: str, duration: float) -> bytes:
    frames = []
    width, height = 480, 480
    num_frames = int(duration * 30)  # 30 fps
    for i in range(num_frames):
        img = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(img)
        # Пульсирующий круг
        scale = 1.0 + 0.2 * np.sin(2 * np.pi * i / 30)
        radius = int(100 * scale)
        draw.ellipse(
            (width//2 - radius, height//2 - radius, width//2 + radius, height//2 + radius),
            fill='blue'
        )
        # Текст
        font = load_font()
        draw.text((10, 10), text[:50], fill='white', font=font)
        frames.append(np.array(img))
    
    # Создание видео
    video_bytes = io.BytesIO()
    with imageio.get_writer(video_bytes, format='mp4', mode='I', fps=30, extension='.mp4') as writer:
        for frame in frames:
            writer.append_data(frame)
    video_bytes.seek(0)
    return video_bytes.read()

# Обработка текстовых сообщений
@dp.message()
async def handle_message(message: Message):
    try:
        # Получение ответа от OpenRouter
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
                    logging.error(f"Ошибка API: {response.status}, Ответ: {response_text}")
                    raise Exception(f"Ошибка API: {response.status}: {response_text}")
                data = await response.json()
                ai_text = data['choices'][0]['message']['content']

        # Генерация аудио и длительности
        audio_data, duration = text_to_speech(ai_text)
        # Генерация видео
        video_data = create_animation(ai_text, duration)

        # Отправка видеосообщения
        await message.reply_video_note(
            BufferedInputFile(video_data, filename="video_note.mp4"),
            duration=int(duration),
            length=480,  # Ширина видео для кружка
            supports_streaming=True
        )
        await message.reply(ai_text)
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

# Настройка приложения
webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
webhook_requests_handler.register(app, path="/webhook")
setup_application(app, dp, bot=bot)
dp.startup.register(on_startup)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logging.info(f"Запуск сервера на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
