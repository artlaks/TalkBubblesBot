import logging
import asyncio
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router
import openai

from config import BOT_TOKEN, OPENAI_API_KEY

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

openai.api_key = OPENAI_API_KEY

# Ответ от GPT
async def get_gpt_response(prompt: str) -> str:
    completion = await openai.ChatCompletion.acreate(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    return completion.choices[0].message.content

# Обработка входящих сообщений
@router.message()
async def handle_message(message: types.Message):
    await message.answer("💭 Думаю...")
    reply = await get_gpt_response(message.text)
    await message.answer(f"🤖 {reply}")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
