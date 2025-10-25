import cv2
     import numpy as np
     import logging
     import subprocess
     import os

     class ImprovedVideoGenerator:
         def __init__(self, width=480, height=480, fps=30):
             self.width = width
             self.height = height
             self.fps = fps
             logging.basicConfig(level=logging.INFO)

         def generate_video(self, text, audio_path, output_path):
             try:
                 # Ограничение длины текста
                 text = text[:100] if len(text) > 100 else text
                 # Создание видео
                 fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                 out = cv2.VideoWriter('temp_video.mp4', fourcc, self.fps, (self.width, self.height))

                 # Генерация градиента
                 for frame_num in range(int(self.fps * 5)):  # 5 секунд
                     frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                     r = min(255, int(255 * frame_num / (self.fps * 5)))
                     frame[:, :] = (r, r, r)
                     font = cv2.FONT_HERSHEY_SIMPLEX
                     cv2.putText(frame, text, (50, self.height // 2), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
                     out.write(frame)

                 out.release()
                 logging.info(f"Video frame generated to temp_video.mp4")

                 # Синхронизация аудио и видео с ffmpeg
                 subprocess.run([
                     'ffmpeg', '-i', 'temp_video.mp4', '-i', audio_path, '-c:v', 'copy', '-c:a', 'aac',
                     '-map', '0:v', '-map', '1:a', '-shortest', output_path
                 ], check=True, capture_output=True, text=True)
                 logging.info(f"Video with audio saved to {output_path}")

                 # Удаление временного файла
                 os.remove('temp_video.mp4')
             except subprocess.CalledProcessError as e:
                 logging.error(f"FFmpeg error: {e.stderr}")
                 raise
             except Exception as e:
                 logging.error(f"Video generation failed: {str(e)}")
                 raise

     if __name__ == "__main__":
         generator = ImprovedVideoGenerator()
         generator.generate_video("Test text", "audio.mp3", "output.mp4")
