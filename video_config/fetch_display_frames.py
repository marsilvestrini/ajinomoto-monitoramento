import cv2
import requests
import numpy as np

def get_video_feed(url):
    """
    Faz a requisição para a rota video_feed e exibe os frames recebidos.
    """
    stream = requests.get(url, stream=True)
    
    if stream.status_code != 200:
        print(f"Erro ao conectar à URL: {url}")
        return
    
    byte_stream = b''
    for chunk in stream.iter_content(chunk_size=1024):
        byte_stream += chunk
        
        a = byte_stream.find(b'\xff\xd8')  # Início de um frame JPEG
        b = byte_stream.find(b'\xff\xd9')  # Fim de um frame JPEG
        
        if a != -1 and b != -1:
            jpg = byte_stream[a:b+2]
            byte_stream = byte_stream[b+2:]
            
            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            
            if frame is not None:
                cv2.imshow('Video Feed', frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    video_feed_url = "http://127.0.0.1:5000/video_feed"  # Ajuste conforme necessário
    get_video_feed(video_feed_url)