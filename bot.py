import os
import tempfile
import subprocess
from dotenv import load_dotenv
from gtts import gTTS
from pydub import AudioSegment
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from aiogram.filters import Command

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if not all([TELEGRAM_TOKEN, OPENROUTER_API_KEY, RENDER_EXTERNAL_HOSTNAME]):
    raise EnvironmentError("Не заданы необходимые переменные окружения.")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Функция конвертации MP3 в MP4 с анимированным фоном
def mp3_to_mp4(mp3_path: str) -> str:
    audio = AudioSegment.from_file(mp3_path)
    duration_sec = audio.duration_seconds

    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_file.close()
    mp4_path = tmp_file.name

    # Анимированный фон с плавным движением
    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", f"color=c=blue@0.3:s=320x320:d={duration_sec}",
        "-f", "lavfi",
        "-i", f"geq='r=255*sin(2*PI*X/W+2*PI*t/5)':g=128:b=255:a=255:s=320x320:d={duration_sec}",
        "-i", mp3_path,
        "-filter_complex", "[0][1]overlay=format=auto",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        mp4_path
    ]
    subprocess.run(cmd, check=True)
    return mp4_path

# Функция для генерации аудио из текста
def text_to_speech(text: str) -> str:
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_file.close()
    tts = gTTS(text=text, lang='ru')
    tts.save(tmp_file.name)
    return tmp_file.name

# Обработчик команды /start
@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Отправь мне текст, и я верну видео с озвучкой.")

# Обработчик текста
@dp.message()
async def handle_text(message: types.Message):
    text = message.text
    await message.answer("Генерирую аудио и видео...")
    
    # Генерация аудио
    mp3_path = text_to_speech(text)
    
    # Конвертация в видео
    try:
        mp4_path = mp3_to_mp4(mp3_path)
    except subprocess.CalledProcessError as e:
        await message.answer(f"Ошибка при создании видео: {e}")
        return
    
    # Отправка видео пользователю
    await message.answer_video(video=InputFile(mp4_path))
    
    # Удаляем временные файлы
    os.remove(mp3_path)
    os.remove(mp4_path)

# Настройка webhook (для Render)
async def on_startup():
    webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/webhook"
    await bot.set_webhook(webhook_url)
    print(f"Webhook установлен: {webhook_url}")

if __name__ == "__main__":
    import asyncio
    from aiogram import F
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, get_new_configured_app

    app = get_new_configured_app(dispatcher=dp, path="/webhook")
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(on_startup())
    import aiohttp.web
    aiohttp.web.run_app(app, port=int(os.getenv("PORT", 10000)))
