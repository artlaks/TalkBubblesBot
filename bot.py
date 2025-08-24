import os
import logging
import aiohttp
import io
import numpy as np
import tempfile
import warnings
import re
from aiogram import Bot, Dispatcher
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from moviepy.editor import ImageSequenceClip, AudioFileClip

# Подавление предупреждений о синтаксисе в moviepy
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME', 'talkbubblesbot.onrender.com')

if not TELEGRAM_TOKEN:
    logging.error("TELEGRAM_TOKEN not set")
    raise ValueError("TELEGRAM_TOKEN not set")
if not OPENROUTER_API_KEY:
    logging.error("OPENROUTER_API_KEY not set")
    raise ValueError("OPENROUTER_API_KEY not set")
if not RENDER_EXTERNAL_HOSTNAME:
    logging.error("RENDER_EXTERNAL_HOSTNAME not set")
    raise ValueError("RENDER_EXTERNAL_HOSTNAME not set")
logging.info(f"Environment variables loaded: TOKEN={TELEGRAM_TOKEN[:5]}..., API_KEY={OPENROUTER_API_KEY[:5]}..., HOST={RENDER_EXTERNAL_HOSTNAME}")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# Глобальный объект app для aiohttp
app = web.Application()

# Кэширование шрифта
FONT = None
def load_font(size=16):
    global FONT
    if FONT is None or FONT.size != size:
        try:
            FONT = ImageFont.truetype("fonts/arial.ttf", size)
            logging.info(f"Шрифт arial.ttf успешно загружен, размер {size}")
        except Exception as e:
            logging.warning(f"Шрифт arial.ttf не найден: {str(e)}, используется дефолтный")
            FONT = ImageFont.load_default()
    return FONT

# Удаление смайликов из текста
def remove_emojis(text: str) -> str:
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # Эмодзи (улыбки, лица)
        u"\U0001F300-\U0001F5FF"  # Символы и пиктограммы
        u"\U0001F680-\U0001F6FF"  # Транспорт и карты
        u"\U0001F700-\U0001F77F"  # Алхимические символы
        u"\U0001F780-\U0001F7FF"  # Геометрические фигуры
        u"\U0001F800-\U0001F8FF"  # Стрелки
        u"\U0001F900-\U0001F9FF"  # Дополнительные эмодзи
        u"\U0001FA00-\U0001FA6F"  # Шахматы и др.
        u"\U0001FA70-\U0001FAFF"  # Новые эмодзи
        u"\U00002700-\U000027BF"  # Декоративные символы
        u"\U00002600-\U000026FF"  # Разные символы
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub(r'', text)

# Разбиение текста на фразы
def split_into_phrases(text: str) -> list:
    return re.split('[.!?]+', text.strip())

# Команда /start
@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу видеосообщением!")

# Команда /setwebhook (для ручной настройки)
@dp.message(Command(commands=['setwebhook']))
async def set_webhook_manual(message: Message):
    webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/webhook"
    try:
        await bot.delete_webhook()
        await bot.set_webhook(webhook_url, allowed_updates=["message"])
        await message.reply(f"Webhook установлен: {webhook_url}")
        logging.info(f"Webhook вручную установлен: {webhook_url}")
    except Exception as e:
        logging.error(f"Ошибка установки webhook вручную: {str(e)}")
        await message.reply(f"Не удалось установить webhook: {str(e)}")

# Генерация аудио и оценка длительности
def text_to_speech(text: str, lang: str = 'ru') -> tuple[bytes, float, str]:
    try:
        tts = gTTS(text=text, lang=lang)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        audio_bytes.seek(0)
        word_count = len(text.split())
        duration = max(3.0, word_count * 0.5)  # Минимум 3 секунды
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
            temp_audio.write(audio_bytes.read())
            temp_audio_path = temp_audio.name
        audio_bytes.seek(0)
        logging.info(f"Аудио создано, длительность: {duration} сек, путь: {temp_audio_path}")
        return audio_bytes.read(), duration, temp_audio_path
    except Exception as e:
        logging.error(f"Ошибка генерации аудио: {str(e)}")
        raise

# Разбиение текста на части для отображения
def split_text_for_display(text: str, max_width: int, font: ImageFont.ImageFont) -> list:
    words = text.split()
    lines = []
    current_line = []
    current_width = 0
    for word in words:
        word_width = font.getlength(word + " ")
        if current_width + word_width <= max_width:
            current_line.append(word)
            current_width += word_width
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_width = word_width
    if current_line:
        lines.append(" ".join(current_line))
    return lines

# Генерация анимации с статичным текстом
def create_animation(text: str, duration: float, audio_path: str) -> bytes:
    frames = []
    width, height = 480, 480
    num_frames = int(duration * 30)  # 30 fps
    phrases = [p.strip() for p in split_into_phrases(text) if p.strip()]
    words = text.split()
    word_duration = duration / max(1, len(words))  # Длительность одного слова
    frames_per_word = max(1, int(word_duration * 30 * 0.9))

    font_size = 16
    font = load_font(font_size)
    max_text_width = 400  # Ограничение ширины для круга
    current_lines = split_text_for_display(" ".join(words[:4]), max_text_width, font)
    while len(current_lines) > 2 and font_size > 10:
        font_size -= 2
        font = load_font(font_size)
        current_lines = split_text_for_display(" ".join(words[:4]), max_text_width, font)

    future_font_size = int(font_size * 0.7)
    future_font = load_font(future_font_size)

    text_y_current = height - 120  # Текущий текст
    text_y_future = height - 60   # Будущий текст, ближе к текущему

    current_phrase_idx = 0
    current_word_idx = 0
    phrase_start_frame = 0

    for i in range(num_frames):
        img = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(img)
        scale = 1.0 + 0.2 * np.sin(2 * np.pi * i / 30)
        radius = int(100 * scale)
        draw.ellipse(
            (width//2 - radius, height//2 - radius, width//2 + radius, height//2 + radius),
            fill='blue'
        )

        total_words = len(words)
        if current_word_idx < total_words:
            current_frame_idx = i - phrase_start_frame
            words_so_far = len(" ".join(words[:current_word_idx + 1]).split())
            phrase_words = len(phrases[current_phrase_idx].split()) if current_phrase_idx < len(phrases) else 0
            if current_frame_idx >= phrase_words * frames_per_word and current_phrase_idx + 1 < len(phrases):
                current_phrase_idx += 1
                phrase_start_frame = i
                current_word_idx = sum(len(p.split()) for p in phrases[:current_phrase_idx])
                logging.info(f"Смена фразы: текущая={current_phrase_idx}, слово={current_word_idx}")

            if current_phrase_idx < len(phrases):
                current_text = phrases[current_phrase_idx]
                current_lines = split_text_for_display(current_text, max_text_width, font)
                y_offset = text_y_current
                for j, line in enumerate(current_lines[:2]):
                    text_width = font.getlength(line)
                    x_offset = (width - text_width) / 2
                    draw.text((x_offset, y_offset + j * (font_size + 5)), line, fill='white', font=font)

            if current_phrase_idx + 1 < len(phrases):
                future_text = phrases[current_phrase_idx + 1]
                future_lines = split_text_for_display(future_text, max_text_width, future_font)
                y_offset = text_y_future
                for j, line in enumerate(future_lines[:2]):
                    text_width = future_font.getlength(line)
                    x_offset = (width - text_width) / 2
                    draw.text((x_offset, y_offset + j * (future_font_size + 5)), line, fill='white', font=future_font)

        frames.append(np.array(img))

    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        temp_video_path = temp_video.name
        clip = ImageSequenceClip(frames, fps=30)
        try:
            audio_clip = AudioFileClip(audio_path)
            clip = clip.set_audio(audio_clip)
            logging.info(f"Аудио прикреплено к видео: {audio_path}")
        except Exception as e:
            logging.error(f"Ошибка прикрепления аудио: {str(e)}")
            clip = clip
        clip.write_videofile(temp_video_path, codec='libx264', audio_codec='aac', fps=30)
        clip.close()
        if clip.audio:
            clip.audio.close()

    # Проверка размера файла
    video_size = os.path.getsize(temp_video_path) / (1024 * 1024)  # Размер в МБ
    logging.info(f"Размер видео (после записи): {video_size:.2f} МБ")

    video_bytes = io.BytesIO()
    with open(temp_video_path, 'rb') as f:
        video_bytes.write(f.read())
    video_bytes
