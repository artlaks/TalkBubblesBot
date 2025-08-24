import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from improved_video_gen import ImprovedVideoGenerator
import os
import asyncio
from config import BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TalkBubblesBot:
    def __init__(self):
        self.video_generator = ImprovedVideoGenerator(
            width=640, 
            height=480, 
            fps=30
        )
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        welcome_message = (
            "👋 Привет! Я TalkBubblesBot - бот, который создает видеосообщения.\n\n"
            "💬 Просто напиши мне любое сообщение, и я создам для тебя красивое видео с текстом!\n\n"
            "🎨 Особенности:\n"
            "• Адаптивный размер текста\n"
            "• Красивые визуальные эффекты\n"
            "• Анимированные переходы\n"
            "• Градиентный фон\n\n"
            "Попробуй написать что-нибудь! 😊"
        )
        await update.message.reply_text(welcome_message)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "🤖 **TalkBubblesBot - Помощь**\n\n"
            "**Команды:**\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать эту справку\n"
            "/settings - Настройки видео\n\n"
            "**Как использовать:**\n"
            "1. Просто напиши любое сообщение\n"
            "2. Бот создаст видео с твоим текстом\n"
            "3. Получи красивое видеосообщение!\n\n"
            "**Советы:**\n"
            "• Короткие сообщения (до 20 символов) отображаются крупнее\n"
            "• Длинные сообщения автоматически разбиваются на строки\n"
            "• Видео длится 4 секунды с анимацией появления\n\n"
            "Попробуй написать что-нибудь! 🎬"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /settings"""
        settings_text = (
            "⚙️ **Настройки видео**\n\n"
            f"**Текущие параметры:**\n"
            f"• Размер видео: {self.video_generator.width}x{self.video_generator.height}\n"
            f"• Частота кадров: {self.video_generator.fps} FPS\n"
            f"• Базовый размер шрифта: {self.video_generator.base_font_size}\n"
            f"• Максимум символов в строке: {self.video_generator.max_chars_per_line}\n\n"
            "**Возможности:**\n"
            "• Адаптивный размер шрифта\n"
            "• Автоматическая разбивка на строки\n"
            "• Визуальные эффекты и тени\n"
            "• Анимированный градиентный фон\n\n"
            "Настройки можно изменить в коде бота."
        )
        await update.message.reply_text(settings_text, parse_mode='Markdown')
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        user_message = update.message.text
        user_id = update.effective_user.id
        
        # Отправляем сообщение о начале обработки
        processing_msg = await update.message.reply_text(
            "🎬 Создаю видеосообщение...\n"
            "⏳ Это может занять несколько секунд."
        )
        
        try:
            # Генерируем уникальное имя файла
            video_filename = f"video_{user_id}_{update.message.message_id}.mp4"
            
            # Создаем видео
            await self.create_video_async(user_message, video_filename)
            
            # Отправляем видео
            with open(video_filename, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption=f"📹 Видеосообщение:\n{user_message}",
                    supports_streaming=True
                )
            
            # Удаляем временный файл
            os.remove(video_filename)
            
            # Удаляем сообщение о обработке
            await processing_msg.delete()
            
        except Exception as e:
            logger.error(f"Ошибка при создании видео: {e}")
            await processing_msg.edit_text(
                "❌ Произошла ошибка при создании видео.\n"
                "Попробуйте еще раз или обратитесь к администратору."
            )
    
    async def create_video_async(self, text: str, filename: str):
        """Асинхронное создание видео"""
        # Запускаем генерацию видео в отдельном потоке
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            self.video_generator.generate_video, 
            text, 
            filename
        )
    
    def run(self):
        """Запуск бота"""
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("settings", self.settings_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Запускаем бота
        logger.info("Бот запущен...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Главная функция"""
    try:
        bot = TalkBubblesBot()
        bot.run()
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")

if __name__ == '__main__':
    main()
