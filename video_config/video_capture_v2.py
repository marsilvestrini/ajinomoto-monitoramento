import subprocess
import numpy as np
import cv2
import queue
import threading
from dotenv import load_dotenv
import os
import time

load_dotenv()

FFMPEG_PATH = os.getenv('FFMPEG_PATH')

class VideoCapture:
    def __init__(self, rtsp_url, frame_callback=None, ffmpeg_path=FFMPEG_PATH):
        self.rtsp_url = rtsp_url
        self.frame_callback = frame_callback
        self.ffmpeg_path = ffmpeg_path
        self.process = None
        self.frame_queue = queue.Queue(maxsize=2)  # Buffer limitado
        self.capture_thread = None
        self.running = False

    def start_capture(self, frame_width=640, frame_height=640):
        """Inicia a captura em uma thread separada"""
        self.running = True
        self.capture_thread = threading.Thread(
            target=self._capture_frames,
            args=(frame_width, frame_height),
            daemon=True
        )
        self.capture_thread.start()
        
        # Thread de processamento
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=1.0)
                if self.frame_callback:
                    self.frame_callback(frame)
            except queue.Empty:
                continue

    def _capture_frames(self, frame_width, frame_height):
        """Thread dedicada para captura de frames"""
        command = [
            self.ffmpeg_path,
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-f', 'image2pipe',
            '-pix_fmt', 'bgr24',
            '-vcodec', 'rawvideo',
            '-s', f'{frame_width}x{frame_height}',
            '-'
        ]

        frame_size = frame_width * frame_height * 3
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=frame_size * 2  # Buffer otimizado
        )

        while self.running:
            try:
                raw_frame = self.process.stdout.read(frame_size)
                if not raw_frame:
                    break

                frame = np.frombuffer(raw_frame, dtype=np.uint8)
                frame = frame.reshape((frame_height, frame_width, 3))
                
                # Não bloqueia se a fila estiver cheia
                try:
                    self.frame_queue.put(frame, timeout=0.1)
                except queue.Full:
                    continue

            except Exception as e:
                print(f"[Capture Error] {str(e)}")
                break

        self._cleanup()

    def _cleanup(self):
        """Limpeza segura dos recursos"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2.0)
            except:
                self.process.kill()
            finally:
                self.process = None

    def stop_capture(self):
        """Para a captura de forma não bloqueante"""
        self.running = False
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=1.0)
        self._cleanup()