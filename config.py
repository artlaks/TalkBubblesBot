import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")



