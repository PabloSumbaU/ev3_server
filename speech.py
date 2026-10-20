import threading
import sockets
import time
from utils import speak_es

def speak():
    while True:
        try:
            # Comprobar que el socket existe antes de intentar recibir
            if not hasattr(sockets.receivers, 'speech') or sockets.receivers.speech is None:
                time.sleep(0.5)
                continue

            data = sockets.receivers.speech.recv(1024)
            if not data:
                time.sleep(0.1)
                continue
            
            text = data.decode('utf-8', errors='ignore').strip()
            
            if '|' in text:
                text = text.split('|')[0]
            
            if text:
                print("[Speech Socket] Hablando: '{}'".format(text))
                speak_es(text)

        except Exception as e:
            print("[Speech Socket] Error de lectura (recuperable): {}".format(e))
            time.sleep(0.5)

def start():
    speech_thread = threading.Thread(target=speak)
    speech_thread.daemon = True
    speech_thread.start()