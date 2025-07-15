import logging
import asyncio
import openai
from aiogram import Bot, Dispatcher, types, Router
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, OPENAI_API_KEY

logging.basicConfig(level=logging.INFO)

openai.api_key = OPENAI_API_KEY

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

async def get_gpt_response(prompt: str) -> str:
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    ))
    return response.choices[0].message["content"].strip()

@router.message()
async def handle_message(message: types.Message):
    await message.answer("💭 Думаю...")
    try:
        reply = await get_gpt_response(message.text)
        await message.answer(f"🤖 {reply}")
    except Exception as e:
        await message.answer("⚠️ Произошла ошибка при обработке запроса.")
        logging.exception("❌ Ошибка при вызове OpenAI:")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
