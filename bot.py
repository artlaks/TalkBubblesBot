from telegram.ext import Updater, MessageHandler, Filters
from config import BOT_TOKEN
import logging

# Настройка логов
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def start(update, context):
    update.message.reply_text('Привет! Я работаю!')

def echo(update, context):
    update.message.reply_text(f'Вы написали: {update.message.text}')

def main():
    updater = Updater(BOT_TOKEN)
    dp = updater.dispatcher
    
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, echo))
    dp.add_handler(MessageHandler(Filters.command, start))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
