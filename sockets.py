"""Comunicacion TCP con la app.

Cambios respecto a la version original:
- Se escucha en todas las interfaces ("") y con SO_REUSEADDR, asi al reiniciar
  el programa no aparece el error "Address already in use".
- Los sockets de escucha se crean una sola vez y se pueden aceptar varias
  conexiones seguidas: si la app se desconecta, el robot vuelve a esperar y no
  hace falta reiniciar main.py.
- MessageReader arma los mensajes completos aunque lleguen partidos o juntos
  en un mismo recv() (antes eso podia lanzar IndexError y cerrar el programa).
"""
import socket
import threading

import config
from utils import debug_print

message_end = config.MESSAGE_END


class Connection:
    '''Los 4 sockets de una sesion con la app.'''

    def __init__(self, client, sensor, speech, position, address):
        self.client = client        # app -> robot: movimiento y comandos
        self.sensor = sensor        # robot -> app: datos del sensor
        self.speech = speech        # app -> robot: texto a decir
        self.position = position    # robot -> app: odometria
        self.address = address
        self.alive = True
        self._send_lock = threading.Lock()

    def send_sensor(self, text):
        self._send(self.sensor, text)

    def send_position(self, text):
        self._send(self.position, text)

    def _send(self, sock, text):
        if not self.alive:
            return
        try:
            with self._send_lock:
                sock.sendall((text + message_end).encode())
        except (OSError, ConnectionError) as e:
            debug_print("Error enviando: " + str(e))
            self.alive = False

    def close(self):
        self.alive = False
        for s in (self.client, self.sensor, self.speech, self.position):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass


# Conexion activa (None si no hay app conectada). Los hilos la consultan.
current = None

_listeners = []


def _listener(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", port))
    s.listen(1)
    return s


def initialize():
    '''Crea los sockets de escucha (una sola vez).'''
    if _listeners:
        return
    for port in (config.PORT_MAIN, config.PORT_SENSOR, config.PORT_SPEECH, config.PORT_POSITION):
        _listeners.append(_listener(port))
    debug_print("Servidor escuchando en puertos " + str(config.PORT_MAIN) + "-" + str(config.PORT_POSITION))


def wait_for_client():
    '''Bloquea hasta que la app se conecta a los 4 puertos. Devuelve Connection.'''
    global current
    main_l, sensor_l, speech_l, position_l = _listeners

    client, addr = main_l.accept()
    sensor, _ = sensor_l.accept()
    speech, _ = speech_l.accept()
    position, _ = position_l.accept()

    for s in (client, sensor, speech, position):
        try:
            s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

    debug_print("Conexion aceptada desde " + str(addr[0]) + ":" + str(addr[1]))
    current = Connection(client, sensor, speech, position, addr)
    return current


def drop_current():
    global current
    if current is not None:
        current.close()
    current = None


def clear():
    '''Cierra todo (al salir del programa).'''
    drop_current()
    for s in _listeners:
        try:
            s.close()
        except Exception:
            pass
    del _listeners[:]


class MessageReader:
    '''Lee de un socket y entrega mensajes completos separados por "|".'''

    def __init__(self, sock):
        self.sock = sock
        self._buffer = ""

    def read(self):
        '''Devuelve una lista de mensajes completos, o None si se cerro la conexion.'''
        data = self.sock.recv(1024)
        if not data:
            return None
        self._buffer += data.decode("utf-8", "ignore")
        parts = self._buffer.split(message_end)
        self._buffer = parts[-1]
        return [p for p in parts[:-1] if p.strip() != ""]
