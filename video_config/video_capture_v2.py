import subprocess
import numpy as np
import queue
import threading
import time
import os
from dotenv import load_dotenv

load_dotenv()

class VideoCapture:
    def __init__(self, rtsp_url, frame_callback=None, ffmpeg_path=None):
        self.rtsp_url = rtsp_url
        self.frame_callback = frame_callback
        self.ffmpeg_path = ffmpeg_path or os.getenv('FFMPEG_PATH')
        self.frame_queue = queue.Queue(maxsize=100)  # Buffer maior
        self.capture_thread = None
        self.running = False
        self.last_frame_time = 0
        self.frame_size = None

    def start_capture(self, frame_width=640, frame_height=640):
        """Inicia a captura com proteção contra falhas"""
        self.frame_size = frame_width * frame_height * 3
        self.running = True
        
        # Thread de captura com restart automático
        def _capture_worker():
            while self.running:
                try:
                    self._capture_frames(frame_width, frame_height)
                except Exception as e:
                    print(f"[CAPTURE CRASH] Reiniciando em 3s... Erro: {str(e)}")
                    time.sleep(3)

        self.capture_thread = threading.Thread(
            target=_capture_worker,
            daemon=True
        )
        self.capture_thread.start()

        # Consumidor principal
        while self.running:
            try:
                frame = self.frame_queue.get(timeout=2.0)
                if self.frame_callback:
                    self.frame_callback(frame)
                    
                # Monitoramento de saúde
                if time.time() - self.last_frame_time > 5.0:
                    print("[WARN] No frames received for 5 seconds!")
                    
            except queue.Empty:
                if not self.capture_thread.is_alive():
                    print("[ERROR] Capture thread died!")
                    break

    def _capture_frames(self, frame_width, frame_height):
        """Implementação robusta da captura"""
        command = [
            self.ffmpeg_path,
            '-rtsp_transport', 'tcp',
            '-i', self.rtsp_url,
            '-f', 'image2pipe',
            '-pix_fmt', 'bgr24',
            '-vcodec', 'rawvideo',
            '-flags', 'low_delay',
            '-avioflags', 'direct',
            '-fflags', 'nobuffer',
            '-s', f'{frame_width}x{frame_height}',
            '-'
        ]

        # Configuração especial para Windows/Docker
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NO_WINDOW

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=self.frame_size * 5,
            creationflags=creationflags
        )

        # Thread para ler stderr (evita deadlocks)
        def _read_stderr():
            while self.running:
                line = self.process.stderr.readline()
                # if line:
                #     print(f"[FFMPEG] {line.decode().strip()}")

        threading.Thread(target=_read_stderr, daemon=True).start()

        # Leitura principal de frames
        while self.running:
            try:
                raw_frame = self._read_with_timeout(self.process.stdout, self.frame_size, timeout=5.0)
                if not raw_frame or len(raw_frame) != self.frame_size:
                    print("[ERROR] Invalid frame size")
                    break

                frame = np.frombuffer(raw_frame, dtype=np.uint8)
                frame = frame.reshape((frame_height, frame_width, 3))
                
                self.last_frame_time = time.time()
                try:
                    self.frame_queue.put(frame, timeout=0.1)
                    print(f"[Frame Captured] Queue: {self.frame_queue.qsize()}\n")
                except queue.Full:
                    print("[WARN] Frame queue full - dropping frame")
                    continue

            except Exception as e:
                print(f"[Frame Read Error] {str(e)}")
                break

        self._cleanup()

    def _read_with_timeout(self, pipe, size, timeout):
        """Leitura com timeout para evitar bloqueios"""
        from functools import partial
        import select
        
        # Linux/Mac
        if hasattr(select, 'poll'):
            poller = select.poll()
            poller.register(pipe, select.POLLIN)
            
            if not poller.poll(timeout * 1000):
                raise TimeoutError("FFmpeg read timeout")
                
            return pipe.read(size)
        
        # Windows
        else:
            import win32file
            handle = win32file._get_osfhandle(pipe.fileno())
            while True:
                res = win32file.ReadFile(handle, size)
                if res[0] == 0:
                    return res[1]
                time.sleep(0.1)

    def _cleanup(self):
        """Limpeza garantida"""
        if self.process:
            try:
                self.process.kill()
            except:
                pass
            finally:
                self.process = None

    def stop_capture(self):
        """Parada segura"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        self._cleanup()
        