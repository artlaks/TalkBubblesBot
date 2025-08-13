# bot.py

# ===== Патч для Python 3.13 =====
import sys, types
sys.modules['audioop'] = types.ModuleType('audioop')

# ===== Стандартные импорты =====
import os
import logging
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
from pydub import AudioSegment
import openai
import tempfile

# ===== Переменные окружения =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

# ===== Настройка логирования =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== Настройка OpenAI / OpenRouter =====
openai.api_key = OPENROUTER_API_KEY

# ===== Команды Telegram =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Я голосовой Telegram-бот. Пришли мне голосовое сообщение.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отправь голосовое сообщение, и я дам тебе ответ с текстом и переводом.")

# ===== Обработка голосовых сообщений =====
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    if not voice:
        await update.message.reply_text("Не удалось получить голосовое сообщение.")
        return

    # Скачиваем голосовое сообщение
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        voice_file = f.name
        await voice.get_file().download_to_drive(voice_file)

    # Конвертируем OGG → WAV с помощью pydub
    wav_file = voice_file.replace(".ogg", ".wav")
    AudioSegment.from_ogg(voice_file).export(wav_file, format="wav")

    # Открываем WAV и отправляем в OpenRouter / OpenAI
    with open(wav_file, "rb") as audio:
        transcript = openai.Audio.transcriptions.create(
            model="whisper-1",
            file=audio
        )

    text = transcript.text
    await update.message.reply_text(f"Ты сказал:\n{text}")

# ===== Основная функция =====
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    logger.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
