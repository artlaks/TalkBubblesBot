import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os
import math

class ImprovedVideoGenerator:
    def __init__(self, width=480, height=480, fps=30):
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
        lines = self.split_text_into_lines(text)
        img = Image.new('RGBA', (frame_width, frame_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(self.font_path, font_size)
        except:
            font = ImageFont.load_default()
        
        total_height = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_height = bbox[3] - bbox[1]
            line_heights.append(line_height)
            total_height += line_height
        total_height += (len(lines) - 1) * 15
        
        start_y = frame_height - total_height - 50  # Нижняя часть
        current_y = start_y
        
        for i, line in enumerate(lines[:2]):  # Ограничиваем 2 строки
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x_position = (frame_width - text_width) // 2
            padding = 15
            rect_coords = [
                x_position - padding,
                current_y - padding,
                x_position + text_width + padding,
                current_y + (bbox[3] - bbox[1]) + padding
            ]
            draw.rectangle(rect_coords, fill=(0, 0, 0, 160))
            draw.text((x_position + 2, current_y + 2), line, font=font, fill=(0, 0, 0, 200))
            draw.text((x_position, current_y), line, font=font, fill=(255, 255, 255, 255))
            current_y += (bbox[3] - bbox[1]) + 15
        
        return img
    
    def create_animated_text(self, text, frame_number, total_frames):
        """Создает анимированный текст с эффектом появления"""
        font_size = self.get_optimal_font_size(text)
        text_img = self.create_text_with_effects(text, font_size, self.width, self.height)
        fade_frames = int(self.fps * 0.5)
        if frame_number < fade_frames:
            alpha = int(255 * (frame_number / fade_frames))
            data = np.array(text_img)
            data[:, :, 3] = data[:, :, 3] * alpha // 255
            return Image.fromarray(data)
        return text_img
    
    def create_gradient_background(self, frame_number, total_frames):
        """Создает анимированный градиентный фон"""
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        for y in range(self.height):
            ratio = y / self.height
            time_offset = (frame_number / total_frames) * 2 * math.pi
            animated_ratio = ratio + 0.1 * math.sin(time_offset + ratio * 2 * math.pi)
            r = int(50 + 100 * animated_ratio)
            g = int(100 + 50 * animated_ratio)
            b = int(200 + 55 * (1 - animated_ratio))
            frame[y, :] = [b, g, r]
        return frame
    
    def composite_layers(self, background, text_overlay):
        """Накладывает текст на фон"""
        background_pil = Image.fromarray(cv2.cvtColor(background, cv2.COLOR_BGR2RGB))
        result = background_pil.copy()
        result.paste(text_overlay, (0, 0), text_overlay)
        return cv2.cvtColor(np.array(result), cv2.COLOR_RGB2BGR)
    
    def generate_video(self, text, audio_path, output_path):
        """Генерирует улучшенное видео с текстом и аудио"""
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        duration = self.get_audio_duration(audio_path)
        total_frames = int(self.fps * duration)
        out = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))
        
        for i in range(total_frames):
            frame = self.create_gradient_background(i, total_frames)
            text_overlay = self.create_animated_text(text, i, total_frames)
            frame = self.composite_layers(frame, text_overlay)
            out.write(frame)
        
        out.release()
        return output_path
    
    def get_audio_duration(self, audio_path):
        """Получает длительность аудиофайла"""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            return len(audio) / 1000.0
        except Exception as e:
            logging.error(f"Ошибка при получении длительности аудио: {e}")
            return 4.0
