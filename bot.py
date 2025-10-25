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
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'talkbubblesbot.onrender.com')

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not set")
if not WEBHOOK_HOST:
    raise ValueError("WEBHOOK_HOST not set")

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
        except:
            FONT = ImageFont.load_default()
            logging.warning("Шрифт arial.ttf не найден, используется дефолтный")
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

# Команда /start
@dp.message(Command(commands=['start']))
async def send_welcome(message: Message):
    await message.reply("Привет! Я TalkBubblesBot — твой виртуальный собеседник. Напиши что-нибудь, и я отвечу видеосообщением!")

# Команда /setwebhook (для ручной настройки)
@dp.message(Command(commands=['setwebhook']))
async def set_webhook_manual(message: Message):
    webhook_url = f"https://{WEBHOOK_HOST}/webhook"
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
        # Оценка длительности: ~150 слов в минуту (0.4 сек/слово)
        word_count = len(text.split())
        duration = max(3.0, word_count * 0.4)  # Минимум 3 секунды
        # Сохраняем аудио во временный файл
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
    words = text.split()
    word_duration = duration / max(1, len(words))  # Длительность одного слова
    frames_per_word = max(1, int(word_duration * 30 * 0.9))  # Уменьшено для точности
    max_text_width = 400  # Ограничение ширины для круга
    
    # Попробуем шрифт разного размера
    font_size = 16
    font = load_font(font_size)
    lines = split_text_for_display(" ".join(words[-4:]), max_text_width, font)
    while len(lines) > 2 and font_size > 10:  # Ограничим на 2 строки для текущего текста
        font_size -= 2
        font = load_font(font_size)
        lines = split_text_for_display(" ".join(words[-4:]), max_text_width, font)
    
    # Шрифт для будущего текста
    future_font_size = int(font_size * 0.8)
    future_font = load_font(future_font_size)
    
    # Координаты для текста в границах кружка
    text_y_current = height - 120  # Текущий текст
    text_y_future = height - 60   # Будущий текст, ближе к текущему

    for i in range(num_frames):
        img = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(img)
        # Пульсирующий круг
        scale = 1.0 + 0.2 * np.sin(2 * np.pi * i / 30)
        radius = int(100 * scale)
        draw.ellipse(
            (width//2 - radius, height//2 - radius, width//2 + radius, height//2 + radius),
            fill='blue'
        )
        # Текущий текст: 3–4 последних слова, выравнивание по центру
        current_word_idx = min(len(words) - 1, i // frames_per_word)
        start_idx = max(0, current_word_idx - 3)  # До 4 слов
        current_text = " ".join(words[start_idx:current_word_idx + 1])
        current_lines = split_text_for_display(current_text, max_text_width, font)
        y_offset = text_y_current
        for j, line in enumerate(current_lines[:2]):
            text_width = font.getlength(line)
            x_offset = (width - text_width) / 2
            draw.text((x_offset, y_offset + j * (font_size + 5)), line, fill='white', font=font)
        
        # Будущий текст: следующие 3–4 слова, выравнивание по центру
        future_start_idx = current_word_idx + 1
        future_end_idx = min(len(words), future_start_idx + 4)
        future_text = " ".join(words[future_start_idx:future_end_idx])
        if future_text:
            future_lines = split_text_for_display(future_text, max_text_width, future_font)
            y_offset = text_y_future
            for j, line in enumerate(future_lines[:2]):
                text_width = future_font.getlength(line)
                x_offset = (width - text_width) / 2
                draw.text((x_offset, y_offset + j * (future_font_size + 5)), line, fill='white', font=future_font)
        
        frames.append(np.array(img))
    
    # Создание видео с moviepy
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        temp_video_path = temp_video.name
        clip = ImageSequenceClip(frames, fps=30)
        try:
            audio_clip = AudioFileClip(audio_path)
            clip = clip.set_audio(audio_clip)
            logging.info(f"Аудио прикреплено к видео: {audio_path}")
        except Exception as e:
            logging.error(f"Ошибка прикрепления аудио: {str(e)}")
            clip = clip  # Продолжаем без аудио, если ошибка
        clip.write_videofile(temp_video_path, codec='libx264', audio_codec='aac', fps=30)
        clip.close()
        if clip.audio:
            clip.audio.close()
    
    # Чтение временного файла в BytesIO
    video_bytes = io.BytesIO()
    with open(temp_video_path, 'rb') as f:
        video_bytes.write(f.read())
    video_bytes.seek(0)
    
    # Проверка размера файла
    video_size = len(video_bytes.getvalue()) / (1024 * 1024)  # Размер в МБ
    logging.info(f"Размер видео: {video_size:.2f} МБ")
    
    # Удаление временных файлов
    os.remove(temp_video_path)
    os.remove(audio_path)
    logging.info(f"Видео создано: {temp_video_path}, аудио удалено: {audio_path}")
    
    return video_bytes.read()

# Обработка текстовых сообщений
@dp.message()
async def handle_message(message: Message):
    try:
        logging.info(f"Получено сообщение: {message.text}")
        # Получение ответа от OpenRouter
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
                        {"role": "system", "content": "Ты дружелюбный виртуальный собеседник, отвечай на русском с юмором."},
                        {"role": "user", "content": message.text}
                    ],
                    "max_tokens": 150
                }
            ) as response:
                if response.status != 200:
                    response_text = await response.text()
                    logging.error(f"Ошибка API: {response.status}, Ответ: {response_text}")
                    raise Exception(f"Ошибка API: {response.status}: {response_text}")
                data = await response.json()
                ai_text = data['choices'][0]['message']['content']
                logging.info(f"Ответ от OpenRouter: {ai_text}")

        # Удаляем смайлики для видео и аудио
        clean_text = remove_emojis(ai_text)
        logging.info(f"Текст без смайликов для видео/аудио: {clean_text}")

        # Генерация аудио и длительности
        audio_data, duration, audio_path = text_to_speech(clean_text)
        # Генерация видео
        video_data = create_animation(clean_text, duration, audio_path)

        # Отправка видеосообщения
        logging.info("Отправка видеосообщения...")
        await message.reply_video_note(
            BufferedInputFile(video_data, filename="video_note.mp4"),
            duration=int(duration),
            length=480,
            supports_streaming=True
        )
        logging.info("Видеосообщение отправлено")
        # Отправка оригинального текста с смайликами
        await message.reply(ai_text)
        logging.info("Текстовый ответ отправлен")
    except Exception as e:
        logging.error(f"Ошибка в handle_message: {str(e)}")
        await message.reply(f"Ой, что-то пошло не так: {str(e)}")

# Webhook setup
async def on_startup() -> None:
    webhook_url = f"https://{WEBHOOK_HOST}/webhook"
    logging.info(f"Попытка установить webhook: {webhook_url}")
    try:
        await bot.delete_webhook()
        await bot.set_webhook(webhook_url, allowed_updates=["message"])
        logging.info(f"Webhook успешно установлен: {webhook_url}")
    except Exception as e:
        logging.error(f"Ошибка установки webhook: {str(e)}")
        raise

# Настройка приложения
webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
webhook_requests_handler.register(app, path="/webhook")
setup_application(app, dp, bot=bot)
dp.startup.register(on_startup)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logging.info(f"Запуск сервера на порту {port}")
    web.run_app(app, host='0.0.0.0', port=port)
