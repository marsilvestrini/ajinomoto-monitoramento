import subprocess
import numpy as np
import cv2
from dotenv import load_dotenv
import os
load_dotenv()

FFMPEG_PATH = os.getenv('FFMPEG_PATH')

class VideoCapture:
    def __init__(self, rtsp_url, frame_callback=None, ffmpeg_path="ffmpeg"):
        """
        Initialize the VideoCapture object.

        Args:
            rtsp_url (str): The RTSP URL of the video stream.
            frame_callback (callable, optional): A callback function to process each frame.
            ffmpeg_path (str): Path to the ffmpeg executable. Defaults to "ffmpeg" (assumes it's in PATH).
        """
        self.rtsp_url = rtsp_url
        self.frame_callback = frame_callback
        self.ffmpeg_path = ffmpeg_path
        self.process = None

    def start_capture(self, frame_width=640, frame_height=640):
        """
        Start capturing frames from the RTSP stream using ffmpeg.

        Args:
            frame_width (int): Width of the output frame.
            frame_height (int): Height of the output frame.
        """
        # FFmpeg command to capture the RTSP stream and output raw RGB frames
        command = [
            self.ffmpeg_path,  # Use the specified ffmpeg path
            '-rtsp_transport', 'tcp',  # Use TCP for RTSP transport
            '-i', self.rtsp_url,      # Input RTSP URL
            '-f', 'image2pipe',        # Output to pipe
            '-pix_fmt', 'bgr24',       # Pixel format (OpenCV uses BGR)
            '-vcodec', 'rawvideo',     # Raw video codec
            '-s', f'{frame_width}x{frame_height}',  # Resize frames
            '-'                       # Output to stdout
        ]

        # Start the FFmpeg process
        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)

        # Frame buffer size (width * height * 3 channels for BGR)
        frame_size = frame_width * frame_height * 3

        while True:
            # Read raw frame data from stdout
            raw_frame = self.process.stdout.read(frame_size)
            if not raw_frame:
                print("Failed to grab frame. Exiting...")
                break

            # Convert raw frame data to a numpy array
            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((frame_height, frame_width, 3))

            rotated_image = cv2.rotate(frame, cv2.ROTATE_180)


            # Pass the frame to the callback function
            if self.frame_callback:
                if not self.frame_callback(rotated_image):  # Stop if callback returns False
                    break

        # Clean up
        self.stop_capture()

    def stop_capture(self):
        """
        Stop capturing frames and terminate the FFmpeg process.
        """
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
            print("FFmpeg process terminated.")


def process_frame(frame):
    """
    Example callback function to process each frame.
    """
    # Display the frame
    cv2.imshow("Frame", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):  # Press 'q' to exit
        return False
    return True

# RTSP URL of the stream
rtsp_url = "rtsp://admin:@jinomoto01@192.168.10.100:554/cam/realmonitor?channel=1&subtype=0"

# Path to the ffmpeg executable
FFMPEG_PATH = r"C:\Users\monitoramento_desvio\Documents\sv\ajinomoto-monitoramento\ffmpeg\bin\ffmpeg.exe"

# Create VideoCapture object
video_capture = VideoCapture(rtsp_url, frame_callback=process_frame, ffmpeg_path=FFMPEG_PATH)

# Start capturing frames
video_capture.start_capture(frame_width=1280, frame_height=720)