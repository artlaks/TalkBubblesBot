import os
import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import io

logging.basicConfig(level=logging.INFO)
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
if not TELEGRAM_TOKEN or not OPENROUTER_API_KEY:
    raise ValueError("TELEGRAM_TOKEN or OPENROUTER_API_KEY not set")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

@dp.message(commands=['start'])
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot. Напиши, и я отвечу в пузыре!")

@dp.message()
async def handle_message(message: Message):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemma-2-9b-it:free",
                    "messages": [
                        {"role": "system", "content": "Ты дружелюбный собеседник, отвечай на русском с юмором."},
                        {"role": "user", "content": message.text}
                    ],
                    "max_tokens": 150
                }
            ) as response:
                if response.status != 200:
                    raise Exception(f"API error: {response.status}")
                data = await response.json()
                ai_text = data['choices'][0]['message']['content']

        img = Image.new('RGB', (400, 100), color='white')
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("fonts/arial.ttf", 20)
        except:
            font = ImageFont.load_default()
        d.text((10, 10), ai_text[:50], fill='black', font=font)
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)

        await message.reply(ai_text)
        await message.reply_photo(img_byte_arr)
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        await message.reply(f"Ой, что-то пошло не так: {str(e)}")

async def on_startup(bot: Bot) -> None:
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await bot.set_webhook(webhook_url)
    logging.info(f"Webhook set to {webhook_url}")

if __name__ == '__main__':
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)

    port = int(os.environ.get('PORT', 8080))
    web.run_app(app, host='0.0.0.0', port=port)
