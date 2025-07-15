import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if BOT_TOKEN is None or OPENAI_API_KEY is None:
    raise ValueError("Environment variables BOT_TOKEN or OPENAI_API_KEY are not set")
