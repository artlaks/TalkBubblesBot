import os
     import logging
     import aiohttp
     import io
     import tempfile
     import re
     from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
     from telegram import Update
     from dotenv import load_dotenv
     from video_gen import ImprovedVideoGenerator
     from gtts import gTTS
     import asyncio

     # Настройка логирования
     logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

     # Загрузка переменных окружения
     load_dotenv()
     TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
     OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
     WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'talkbubblesbot-production.up.railway.app')

     if not TELEGRAM_TOKEN:
         raise ValueError("TELEGRAM_TOKEN not set")
     if not OPENROUTER_API_KEY:
         raise ValueError("OPENROUTER_API_KEY not set")

     # Инициализация
     application = Application.builder().token(TELEGRAM_TOKEN).build()

     # Обработчики
     async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
         await update.message.reply_text("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь!")

     async def set_webhook(update: Update, context: ContextTypes.DEFAULT_TYPE):
         webhook_url = f"https://{WEBHOOK_HOST}/webhook"
         try:
             await application.bot.set_webhook(url=webhook_url)
             await update.message.reply_text(f"Webhook установлен: {webhook_url}")
             logging.info(f"Webhook set to {webhook_url}")
         except Exception as e:
             await update.message.reply_text(f"Ошибка установки webhook: {str(e)}")
             logging.error(f"Webhook set failed: {str(e)}")

     async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
         try:
             logging.info(f"Получено сообщение: {update.message.text}")
             ai_text = await get_openrouter_response(update.message.text)
             logging.info(f"Ответ от OpenRouter: {ai_text}")

             if not ai_text or not ai_text.strip():
                 ai_text = "Hello! I couldn't process your request. Please try again!"
             clean_text = re.sub(r'[^\w\s!?]', '', ai_text).strip()
             logging.info(f"Текст для видео/аудио: {clean_text}")

             tts = gTTS(text=clean_text, lang='en')
             audio_bytes = io.BytesIO()
             tts.write_to_fp(audio_bytes)
             audio_bytes.seek(0)
             logging.debug(f"Audio generated, size: {audio_bytes.getbuffer().nbytes} bytes")
             with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
                 temp_audio.write(audio_bytes.read())
                 audio_path = temp_audio.name
                 logging.debug(f"Audio saved to {audio_path}")

             logging.debug("Starting video generation")
             generator = ImprovedVideoGenerator(width=480, height=480, fps=30)
             with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
                 temp_video_path = temp_video.name
                 generator.generate_video(clean_text, audio_path, temp_video_path)
             logging.debug("Video generation completed")

             with open(temp_video_path, 'rb') as video_file:
                 await update.message.reply_video_note(video_file, duration=5, length=480)
             logging.info("Видеосообщение отправлено")
             await update.message.reply_text(ai_text)
             logging.info("Текстовый ответ отправлен")

             os.remove(temp_video_path)
             os.remove(audio_path)
         except Exception as e:
             logging.error(f"Ошибка в handle_message: {str(e)}")
             await update.message.reply_text(f"Ошибка: {str(e)}")

     async def get_openrouter_response(text):
         max_retries = 3
         for attempt in range(max_retries):
             try:
                 async with aiohttp.ClientSession() as session:
                     async with session.post(
                         "https://openrouter.ai/api/v1/chat/completions",
                         headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                         json={
                             "model": "google/gemma-2-9b-it:free",
                             "messages": [{"role": "system", "content": "Ты дружелюбный виртуальный собеседник, отвечай на том языке, на котором тебе пишут."},
                                         {"role": "user", "content": text}],
                             "max_tokens": 150
                         }
                     ) as response:
                         if response.status == 200:
                             data = await response.json()
                             return data['choices'][0]['message']['content']
                         elif response.status == 429:
                             if attempt < max_retries - 1:
                                 await asyncio.sleep(2 ** attempt)
                                 continue
                         raise Exception(f"Ошибка API: {response.status}")
             except Exception as e:
                 if attempt < max_retries - 1:
                     await asyncio.sleep(2 ** attempt)
                     continue
                 raise
         raise Exception("Превышено максимальное количество попыток")

     # Регистрация обработчиков
     application.add_handler(CommandHandler("start", start))
     application.add_handler(CommandHandler("setwebhook", set_webhook))
     application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

     # Запуск
     if __name__ == '__main__':
         if WEBHOOK_HOST == 'localhost':
             logging.info("Запуск бота в режиме polling...")
             application.run_polling()
         else:
             logging.info(f"Запуск бота с вебхуком: https://{WEBHOOK_HOST}/webhook")
             application.run_webhook(
                 listen="0.0.0.0",
                 port=10000,
                 url_path="/webhook",
                 webhook_url=f"https://{WEBHOOK_HOST}/webhook"
             )
