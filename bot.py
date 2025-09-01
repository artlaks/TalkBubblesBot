import os
import tempfile
import requests
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from gtts import gTTS
from video_gen import create_video_with_subtitles

# 🔑 Настройки окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

# 📌 Функция: запрос к LLM через OpenRouter
def ask_llm(prompt: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]

# 📌 Обработчик сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    await update.message.reply_chat_action("typing")

    # Получаем ответ от LLM
    bot_reply = ask_llm(user_text)

    # Озвучиваем в mp3
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
        tts = gTTS(bot_reply, lang="ru")
        tts.save(audio_file.name)
        audio_path = audio_file.name

    # Создаем кружок с субтитрами
    video_path = create_video_with_subtitles(audio_path, bot_reply)

    # Отправляем кружок
    with open(video_path, "rb") as video:
        await update.message.reply_video_note(video)

    # Убираем временные файлы
    os.remove(audio_path)
    os.remove(video_path)

# 📌 Основной запуск
def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
