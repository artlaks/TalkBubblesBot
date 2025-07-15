import logging
import asyncio
import openai
import os

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# Настройка логирования (подробное)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Импорт токенов из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Ошибка: переменные окружения BOT_TOKEN и OPENAI_API_KEY должны быть установлены")

openai.api_key = OPENAI_API_KEY

# Инициализация бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Функция для обращения к OpenAI (старый синтаксис openai==0.28)
async def get_gpt_response(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        ))
        return response.choices[0].message["content"].strip()
    except Exception as e:
        logging.exception("Ошибка при вызове OpenAI API:")
        raise

# Обработчик входящих сообщений
@router.message()
async def handle_message(message: types.Message):
    logging.info(f"Получено сообщение: {message.text}")
    await message.answer("💭 Думаю...")
    try:
        reply = await get_gpt_response(message.text)
        await message.answer(f"🤖 {reply}")
    except Exception:
        await message.answer("⚠️ Произошла ошибка при обработке запроса.")

# Точка входа
async def main():
    logging.info("Бот запускается...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
