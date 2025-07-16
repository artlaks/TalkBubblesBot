from aiohttp import web

app = web.Application()

# ✅ Настраиваем обработку Webhook
async def on_startup_app(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"✅ Webhook установлен: {WEBHOOK_URL}")

async def on_shutdown_app(app: web.Application):
    await bot.delete_webhook()
    logging.info("❌ Webhook удалён")

# Подключаем события
app.on_startup.append(on_startup_app)
app.on_shutdown.append(on_shutdown_app)

# Подключаем Telegram к aiohttp через Aiogram
setup_application(app, dp, bot=bot, handle_in_background=True)
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

# ✅ Стартуем без asyncio.run()
if __name__ == "__main__":
    logging.info("🚀 Webhook бот запущен через aiohttp")
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
