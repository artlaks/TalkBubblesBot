import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor
import openai
import os
from config import BOT_TOKEN, OPENAI_API_KEY

# Настройки
openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Ответ от GPT
async def get_gpt_response(prompt: str) -> str:
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message["content"]

# Обработка сообщений
@dp.message_handler()
async def handle_message(message: Message):
    user_text = message.text
    await message.answer("💭 Думаю...")
    gpt_reply = await get_gpt_response(user_text)
    await message.answer(f"🤖 {gpt_reply}")

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)