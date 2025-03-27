import cv2

class VideoCapture:
    def __init__(self, video_path, frame_callback=None):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(self.video_path)
        self.frame_callback = frame_callback

        if not self.cap.isOpened():
            raise ValueError(f"Erro ao abrir o vídeo: {self.video_path}")

    def start_capture(self):
        """
        Starts capturing frames from the video and emits them using the callback.
        """
        while self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                break

            if self.frame_callback:
                self.frame_callback(frame)

        self.cap.release()
        cv2.destroyAllWindows()

    def stop_capture(self):
        self.cap.release()