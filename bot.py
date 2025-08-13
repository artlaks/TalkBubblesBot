import os
import tempfile
import subprocess
from aiogram import Bot, Dispatcher, types
from aiogram.utils.executor import start_webhook
from gtts import gTTS
from pydub import AudioSegment

# ==== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ====
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

# ==== WEBHOOK ====
WEBHOOK_PATH = f"/webhook"
WEBHOOK_URL = f"https://{RENDER_EXTERNAL_HOSTNAME}{WEBHOOK_PATH}" if RENDER_EXTERNAL_HOSTNAME else None
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# ==== Функции ====
def split_text(text: str, max_chars: int = 300):
    """Разделяем текст на части до max_chars символов, стараясь не разрывать слова."""
    words = text.split()
    chunks = []
    chunk = ""
    for word in words:
        if len(chunk) + len(word) + 1 > max_chars:
            chunks.append(chunk.strip())
            chunk = word
        else:
            chunk += " " + word
    if chunk:
        chunks.append(chunk.strip())
    return chunks

def mp3_to_mp4(mp3_path: str) -> str:
    audio = AudioSegment.from_file(mp3_path)
    duration_sec = audio.duration_seconds

    tmp_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_file.close()
    mp4_path = tmp_file.name

    cmd = [
        "ffmpeg",
        "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=240x240",
        "-i", mp3_path,
        "-vf", "format=yuv420p,scale=240:240",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-shortest",
        "-t", str(duration_sec),
        mp4_path
    ]
    subprocess.run(cmd, check=True)
    return mp4_path

# ==== Хэндлеры ====
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.reply("Привет! Отправь мне текст, и я верну видео с озвучкой.")

@dp.message_handler()
async def text_to_video(message: types.Message):
    try:
        chunks = split_text(message.text, max_chars=300)
        for idx, chunk in enumerate(chunks):
            # Генерация MP3
            tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_mp3.close()
            tts = gTTS(text=chunk, lang="ru")
            tts.save(tmp_mp3.name)

            # Конвертация в MP4
            mp4_file = mp3_to_mp4(tmp_mp3.name)

            # Отправка видео
            with open(mp4_file, "rb") as video:
                caption = f"Часть {idx+1}/{len(chunks)}"
                await message.reply_video(video, caption=caption)

            # Очистка
            os.remove(tmp_mp3.name)
            os.remove(mp4_file)

    except Exception as e:
        await message.reply(f"Ошибка: {e}")

# ==== Старт бота ====
if __name__ == "__main__":
    if WEBHOOK_URL:
        import asyncio
        from aiohttp import web

        async def handle(request):
            update = types.Update(**await request.json())
            await dp.process_update(update)
            return web.Response()

        async def on_startup(app):
            await bot.set_webhook(WEBHOOK_URL)

        async def on_shutdown(app):
            await bot.delete_webhook()

        app = web.Application()
        app.router.add_post(WEBHOOK_PATH, handle)
        app.on_startup.append(on_startup)
        app.on_shutdown.append(on_shutdown)

        web.run_app(app, host=WEBAPP_HOST, port=WEBAPP_PORT)
    else:
        from aiogram import executor
        executor.start_polling(dp, skip_updates=True)
