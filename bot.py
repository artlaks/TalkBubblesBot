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
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

class Conversation(StatesGroup):
    chatting = State()

# Подавление предупреждений о синтаксисе в moviepy
warnings.filterwarnings("ignore", category=SyntaxWarning)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', 'https://talkbubblesbot-production.up.railway.app')

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
# Обработка текстовых сообщений
@dp.message()
async def handle_message(message: Message, state: FSMContext):
    try:
        logging.info(f"Получено сообщение: {message.text}")
        # Получение контекста из FSM
        data = await state.get_data()
        conversation = data.get('conversation', [])

        # Добавляем сообщение пользователя в контекст
        conversation.append({"role": "user", "content": message.text})

        # Получение ответа от OpenRouter с контекстом
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
                        {"role": "system", "content": "Ты дружелюбный виртуальный собеседник, ведешь беседу, помнишь контекст, даешь советы, отвечай на языке, на котором к тебе обращаются."}
                    ] + conversation,  # Добавляем весь контекст
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

        # Добавляем ответ бота в контекст
        conversation.append({"role": "assistant", "content": ai_text})
        await state.update_data(conversation=conversation)  # Сохраняем контекст

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
        # Оценка длительности: ~150 слов в минуту (0.5 сек/слово)
        word_count = len(text.split())
        duration = max(3.0, word_count * 0.5)  # Минимум 3 секунды
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

# Генерация анимации с пользовательской GIF (замедленная)
def create_animation(text: str, duration: float, audio_path: str) -> bytes:
    frames = []
    width, height = 480, 480  # Убедитесь, что размер соответствует вашей GIF
    num_frames = int(duration * 15)  # Уменьшаем FPS до 15 для замедления
    words = text.split()
    word_duration = duration / max(1, len(words))  # Длительность одного слова

    # Загрузка GIF
    try:
        gif = Image.open("assets/girl_gif.gif")
        gif_frames = []
        try:
            while True:
                gif_frame = gif.copy()
                gif_frame = gif_frame.convert("RGB")
                if gif_frame.size != (width, height):
                    gif_frame = gif_frame.resize((width, height), Image.Resampling.LANCZOS)
                gif_frames.append(np.array(gif_frame))
                gif.seek(gif.tell() + 1)
        except EOFError:
            pass
        gif.close()
    except FileNotFoundError:
        logging.error("Файл assets/girl_gif.gif не найден. Использую чёрный фон.")
        gif_frames = [np.array(Image.new("RGB", (width, height), color=(0, 0, 0))) for _ in range(15)]
    except Exception as e:
        logging.error(f"Ошибка загрузки GIF: {str(e)}")
        gif_frames = [np.array(Image.new("RGB", (width, height), color=(0, 0, 0))) for _ in range(15)]

    # Повторяем каждый кадр GIF для замедления (например, 2 раза)
    slowed_gif_frames = []
    for frame in gif_frames:
        slowed_gif_frames.extend([frame] * 2)  # Повторяем каждый кадр дважды
    gif_frames = slowed_gif_frames

    # Повторяем GIF для соответствия длительности
    gif_duration = len(gif_frames) / 15  # Длительность GIF в секундах (при 15 fps)
    if gif_duration > 0:
        repeat_count = max(1, int(duration / gif_duration))
        full_frames = gif_frames * repeat_count
        # Обрезаем или дополняем до нужной длительности
        if len(full_frames) < num_frames:
            full_frames.extend(gif_frames[:num_frames - len(full_frames)])
        elif len(full_frames) > num_frames:
            full_frames = full_frames[:num_frames]
        frames = full_frames
    else:
        frames = [np.array(Image.new("RGB", (width, height), color=(0, 0, 0))) for _ in range(num_frames)]

    # Создание видео с moviepy
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        temp_video_path = temp_video.name
        clip = ImageSequenceClip(frames, fps=15)  # Уменьшаем FPS до 15
        try:
            audio_clip = AudioFileClip(audio_path)
            clip = clip.set_audio(audio_clip)
            if clip.duration < duration:
                clip = clip.set_duration(duration)  # Убедимся, что видео не короче аудио
            logging.info(f"Аудио прикреплено к видео: {audio_path}")
        except Exception as e:
            logging.error(f"Ошибка прикрепления аудио: {str(e)}")
            clip = clip.set_duration(duration)  # Используем длительность текста
        clip.write_videofile(temp_video_path, codec='libx264', audio_codec='aac', fps=15)
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

    # Создание видео с moviepy
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
        temp_video_path = temp_video.name
        clip = ImageSequenceClip(frames, fps=30)
        try:
            audio_clip = AudioFileClip(audio_path)
            clip = clip.set_audio(audio_clip)
            if clip.duration < duration:
                clip = clip.set_duration(duration)  # Убедимся, что видео не короче аудио
            logging.info(f"Аудио прикреплено к видео: {audio_path}")
        except Exception as e:
            logging.error(f"Ошибка прикрепления аудио: {str(e)}")
            clip = clip.set_duration(duration)  # Используем длительность текста
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
