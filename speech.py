"""Canal de voz: la app envia texto y el robot lo dice y lo muestra en pantalla.

Funciona con la funcion "Repetir lo que digo" y con el cuadro de texto de la
app (escribir lo que dira el robot).
Compatible con Python 3.5.
"""
import threading
import time

import sockets
import personality as p
import behaviors
from utils import debug_print


def _loop():
    reader, conn = None, None
    while True:
        try:
            current = sockets.current
            if current is None or not current.alive:
                reader, conn = None, None
                time.sleep(0.3)
                continue
            if current is not conn:
                conn, reader = current, sockets.MessageReader(current.speech)

            messages = reader.read()
            if messages is None:          # la app cerro el socket
                reader = None
                time.sleep(0.3)
                continue
            for text in messages:
                text = text.strip()
                if not text:
                    continue
                if behaviors.state.sleeping:
                    behaviors.state.sleeping = False
                    p.emote("neutral")
                p.say(text)
        except Exception as e:
            debug_print("[Voz] Error recuperable: " + str(e))
            reader, conn = None, None
            time.sleep(0.5)


def start():
    t = threading.Thread(target=_loop)
    t.daemon = True
    t.start()
