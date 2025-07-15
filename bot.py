import logging
import asyncio
import openai
from aiogram import Bot, Dispatcher, types, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OPENAI_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Конфигурация OpenAI
openai.api_key = OPENAI_API_KEY

# Инициализация бота и диспетчера
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Обработка входящих сообщений
@router.message()
async def handle_message(message: types.Message):
    await message.answer("💭 Думаю...")
    reply = await get_gpt_response(message.text)
    await message.answer(f"🤖 {reply}")

# Запрос к OpenAI GPT
async def get_gpt_response(prompt: str) -> str:
    completion = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return completion.choices[0].message.content.strip()

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
