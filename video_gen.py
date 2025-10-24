import cv2
import numpy as np
import logging
from PIL import Image, ImageDraw, ImageFont

class ImprovedVideoGenerator:
    def __init__(self, width=480, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        logging.basicConfig(level=logging.INFO)

         def generate_video(self, text, audio_path, output_path):
             try:
                 # Создание видео
                 fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                 out = cv2.VideoWriter(output_path, fourcc, self.fps, (self.width, self.height))

                 # Генерация градиента (пример)
                 for frame_num in range(int(self.fps * 5)):  # 5 секунд
                     frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                     # Градиент от чёрного к белому (0-255)
                     r = min(255, int(255 * frame_num / (self.fps * 5)))  # Ограничение до 255
                     frame[:, :] = (r, r, r)  # Серый градиент
                     # Добавление текста
                     font = cv2.FONT_HERSHEY_SIMPLEX
                     cv2.putText(frame, text[:20], (50, self.height // 2), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
                     out.write(frame)
                     logging.debug(f"Frame {frame_num} generated with color {r}")

                 out.release()
                 logging.info(f"Video saved to {output_path}")
             except Exception as e:
                 logging.error(f"Video generation failed: {str(e)}")
                 raise

     if __name__ == "__main__":
         generator = ImprovedVideoGenerator()
         generator.generate_video("Test text", "audio.mp3", "output.mp4")

