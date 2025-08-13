import os
import tempfile
import subprocess
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import InputFile
from gtts import gTTS
from pydub import AudioSegment

# Загружаем переменные окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if not all([TELEGRAM_TOKEN, OPENROUTER_API_KEY, RENDER_EXTERNAL_HOSTNAME]):
    raise ValueError("TELEGRAM_TOKEN, OPENROUTER_API_KEY и RENDER_EXTERNAL_HOSTNAME должны быть заданы в .env")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

def text_to_speech(text: str) -> str:
    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_file.close()
    tts = gTTS(text=text, lang="en")
    tts.save(tmp_file.name)
    return tmp_file.name

def mp3_to_mp4(mp3_path: str) -> str:
    audio = AudioSegment.from_file(mp3_path)
    duration_sec = audio.duration_seconds

    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_file.close()
    mp4_path = tmp_file.name

    # Анимированный фон с несколькими пульсирующими кругами
    filter_complex = (
        f"color=c=black:s=480x480:d={duration_sec}[base];"
        f"[base]drawbox=x=0:y=0:w=iw:h=ih:color=black@0:t=fill[bg];"
        f"[bg]geq='r=255*sin(2*PI*sqrt((X-240)^2+(Y-240)^2)/50-t*2*PI/5)':"
        f"g=128: b=255: alpha=255:enable='between(t,0,{duration_sec})'[v];"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-i", mp3_path,
        "-f", "lavfi",
        "-i", f"color=c=black:s=480x480:d={duration_sec}",
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        mp4_path
    ]
    subprocess.run(cmd, check=True)
    return mp4_path

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    await message.answer("Привет! Отправь мне текст, и я верну видео с озвучкой.")

@dp.message_handler()
async def handle_text(message: types.Message):
    try:
        mp3_file = text_to_speech(message.text)
        mp4_file = mp3_to_mp4(mp3_file)
        await message.answer_video(InputFile(mp4_file))
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

if __name__ == "__main__":
    import logging
    from aiogram import executor

    logging.basicConfig(level=logging.INFO)
    logging.info(f"Запуск на порту 10000, webhook: https://{RENDER_EXTERNAL_HOSTNAME}/webhook")
    
    executor.start_polling(dp, skip_updates=True)
