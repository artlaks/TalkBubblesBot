import tempfile
import textwrap
import moviepy.editor as mp

# 📌 Создание кружка с субтитрами
def create_video_with_subtitles(audio_path: str, text: str) -> str:
    # Читаем аудио
    audio = mp.AudioFileClip(audio_path)

    # Настройки видео
    size = (480, 480)  # Квадрат под кружок
    bg = mp.ColorClip(size, color=(0, 0, 0)).set_duration(audio.duration)

    # 🔹 Перенос строк
    wrapped_text = textwrap.fill(text, width=30)  # <= регулируй ширину

    # Субтитры
    txt_clip = mp.TextClip(
        wrapped_text,
        fontsize=32,
        color="white",
        font="Arial-Bold",
        size=(440, None),
        method="caption",  # авто-перенос по ширине
        align="center"
    ).set_position(("center", "bottom")).set_duration(audio.duration)

    # Собираем видео
    video = mp.CompositeVideoClip([bg, txt_clip]).set_audio(audio)

    # Экспорт как кружок
    output_path = tempfile.mktemp(suffix=".mp4")
    video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", verbose=False, logger=None)

    return output_path
