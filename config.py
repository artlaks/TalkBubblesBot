import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")

if BOT_TOKEN is None or HF_TOKEN is None:
    raise ValueError("Environment variables BOT_TOKEN or HF_TOKEN are not set")
