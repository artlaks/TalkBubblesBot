import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
import math

class ImprovedVideoGenerator:
    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.font_path = "fonts/arial.ttf"
        self.base_font_size = 32
        self.max_chars_per_line = 40
        
    def get_optimal_font_size(self, text):
        """Определяет оптимальный размер шрифта в зависимости от длины текста"""
        if len(text) <= 20:
            return self.base_font_size
        elif len(text) <= 40:
            return self.base_font_size - 4
        elif len(text) <= 60:
            return self.base_font_size - 8
        else:
            return self.base_font_size - 12
    
    def split_text_into_lines(self, text, max_chars=None):
        """Разбивает текст на строки с учетом максимальной длины"""
        if max_chars is None:
            max_chars = self.max_chars_per_line
            
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if len(test_line) <= max_chars:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line.strip())
                current_line = word
        
        if current_line:
            lines.append(current_line.strip())
            
        return lines
    
    def create_text_with_effects(self, text, font_size, frame_width, frame_height):
        """Создает текст с визуальными эффектами"""
        # Разбиваем текст на строки
        lines = self.split_text_into_lines(text)
        
        # Создаем изображение для текста
        img = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except:
            font = ImageFont.load_default()
        
        # Вычисляем общую высоту текста
        total_height = 0
        line_heights = []
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            line_heights.append(line_height)
            total_height += line_height
        
        # Добавляем отступы между строками
        total_height += (len(lines) - 1) * 15
        
        # Начальная позиция Y (центрируем по вертикали)
        start_y = (frame_height - total_height) // 2
        
        # Рисуем каждую строку
        current_y = start_y
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Центрируем по горизонтали
            x_position = (frame_width - text_width) // 2
            
            # Создаем фон для текста с закругленными углами
            padding = 15
            rect_coords = [
                x_position - padding,
                current_y - padding,
                x_position + text_width + padding,
                current_y + text_height + padding
            ]
            
            # Рисуем полупрозрачный фон
            draw.rectangle(rect_coords, fill=(0, 0, 0, 160))
            
            # Рисуем обводку текста (тень)
            shadow_offset = 2
            draw.text((x_position + shadow_offset, current_y + shadow_offset), 
                     line, font=font, fill=(0, 0, 0, 200))
            
            # Рисуем основной текст
            draw.text((x_position, current_y), line, font=font, fill=(255, 255, 255, 255))
            
            current_y += text_height + 15
        
        return img
    
    def create_animated_text(self, text, frame_number, total_frames):
        """Создает анимированный текст с эффектом появления"""
        font_size = self.get_optimal_font_size(text)
        
        # Создаем базовый текст
        text_img = self.create_text_with_effects(text, font_size, self.width, self.height)
        
        # Анимация появления (первые 0.5 секунды)
        fade_frames = int(self.fps * 0.5)
        
        if frame_number < fade_frames:
            # Эффект появления
            alpha = int(255 * (frame_number / fade_frames))
            # Создаем новое изображение с измененной прозрачностью
            result = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
            result.paste(text_img, (0, 0), text_img)
            
            # Применяем прозрачность
            data = np.array(result)
            data[:, :, 3] = data[:, :, 3] * alpha // 255
            return Image.fromarray(data)
        
        return text_img
    
    def generate_video(self, text, output_path="improved_output.mp4", duration=4):
        """Генерирует улучшенное видео с текстом"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))
        
        total_frames = int(self.fps * duration)
        
        for i in range(total_frames):
            # Создаем градиентный фон
            frame = self.create_gradient_background(i, total_frames)
            
            # Добавляем анимированный текст
            text_overlay = self.create_animated_text(text, i, total_frames)
            
            # Накладываем текст на фон
            frame = self.composite_layers(frame, text_overlay)
            
            out.write(frame)
        
        out.release()
        return output_path
    
    def generate_video_with_audio(self, text, audio_path, output_path="video_with_audio.mp4", duration=None):
        """Генерирует видео с текстом и аудио"""
        # Если длительность не указана, определяем по аудио
        if duration is None:
            duration = self.get_audio_duration(audio_path)
        
        # Создаем видео без аудио
        temp_video_path = f"temp_{output_path}"
        self.generate_video(text, temp_video_path, duration)
        
        # Добавляем аудио к видео
        self.add_audio_to_video(temp_video_path, audio_path, output_path)
        
        # Удаляем временный файл
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        
        return output_path
    
    def get_audio_duration(self, audio_path):
        """Получает длительность аудиофайла"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0  # Конвертируем в секунды
        except Exception as e:
            print(f"Ошибка при получении длительности аудио: {e}")
            return 4.0  # Возвращаем стандартную длительность
    
    def add_audio_to_video(self, video_path, audio_path, output_path):
        """Добавляет аудио к видео"""
        try:
            from moviepy.editor import VideoFileClip, AudioFileClip
            
            # Загружаем видео и аудио
            video = VideoFileClip(video_path)
            audio = AudioFileClip(audio_path)
            
            # Обрезаем аудио до длительности видео
            if audio.duration > video.duration:
                audio = audio.subclip(0, video.duration)
            
            # Добавляем аудио к видео
            final_video = video.set_audio(audio)
            
            # Сохраняем результат
            final_video.write_videofile(output_path, codec='libx264', audio_codec='aac')
            
            # Закрываем файлы
            video.close()
            audio.close()
            final_video.close()
            
        except Exception as e:
            print(f"Ошибка при добавлении аудио к видео: {e}")
            # Если не удалось добавить аудио, просто копируем видео
            import shutil
            shutil.copy2(video_path, output_path)
    
    def create_gradient_background(self, frame_number, total_frames):
        """Создает анимированный градиентный фон"""
        # Создаем градиент от синего к фиолетовому
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        for y in range(self.height):
            # Градиент по вертикали
            ratio = y / self.height
            
            # Анимация градиента
            time_offset = (frame_number / total_frames) * 2 * math.pi
            animated_ratio = ratio + 0.1 * math.sin(time_offset + ratio * 2 * math.pi)
            
            # Цвета градиента
            r = int(50 + 100 * animated_ratio)
            g = int(100 + 50 * animated_ratio)
            b = int(200 + 55 * (1 - animated_ratio))
            
            frame[y, :] = [b, g, r]  # BGR для OpenCV
        
        return frame
    
    def composite_layers(self, background, text_overlay):
        """Накладывает текст на фон"""
        # Конвертируем фон в PIL Image
        background_pil = Image.fromarray(background)
        
        # Накладываем текст
        result = background_pil.copy()
        result.paste(text_overlay, (0, 0), text_overlay)
        
        # Конвертируем обратно в numpy array
        result_array = np.array(result)
        
        # Конвертируем RGB в BGR для OpenCV
        result_bgr = cv2.cvtColor(result_array, cv2.COLOR_RGB2BGR)
        
        return result_bgr

# Пример использования
if __name__ == "__main__":
    generator = ImprovedVideoGenerator()
    
    # Тестовые сообщения разной длины
    test_messages = [
        "Привет!",
        "Как дела?",
        "Это тестовое сообщение для проверки отображения текста в видео.",
        "Очень длинное сообщение для проверки того, как система обрабатывает большие объемы текста и разбивает их на строки для лучшей читаемости."
    ]
    
    for i, message in enumerate(test_messages):
        output_file = f"test_video_{i+1}.mp4"
        generator.generate_video(message, output_file)
        print(f"Создано видео: {output_file}")
