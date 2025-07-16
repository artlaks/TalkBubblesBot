import os
import logging
import asyncio
import requests

from aiogram import Bot, Dispatcher, Router, types
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")  # Hugging Face API token

if not BOT_TOKEN or not HF_TOKEN:
    raise RuntimeError("❌ Переменные окружения BOT_TOKEN и HF_TOKEN должны быть заданы")

# Настройка бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Deepseek model на HuggingFace
MODEL_URL = "https://api-inference.huggingface.co/models/deepseek-ai/deepseek-chat"

headers = {
    "Authorization": f"Bearer {HF_TOKEN}"
}

def query_deepseek(prompt: str) -> str:
    payload = {
        "inputs": f"<|system|>\nYou are a helpful assistant.\n<|user|>\n{prompt}\n<|assistant|>",
        "parameters": {"max_new_tokens": 200}
    }
    response = requests.post(MODEL_URL, headers=headers, json=payload)
    if response.status_code == 200:
        result = response.json()
        return result[0]["generated_text"].split("<|assistant|>")[-1].strip()
    else:
        logging.error(f"❌ Ошибка HuggingFace API: {response.status_code} - {response.text}")
        return "⚠️ Не удалось получить ответ от Deepseek."

@router.message()
async def handle_message(message: types.Message):
    logging.info(f"📩 Получено сообщение: {message.text}")
    await message.answer("💭 Думаю...")
    loop = asyncio.get_event_loop()
    reply = await loop.run_in_executor(None, query_deepseek, message.text)
    await message.answer(f"🤖 {reply}")

async def main():
    logging.info("🤖 Deepseek бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
