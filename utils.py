import sys
import os
import subprocess

import config

_sound = None


def _get_sound():
    global _sound
    if _sound is None:
        from ev3dev2.sound import Sound
        _sound = Sound()
    return _sound


class _ErrorPrinter:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        # El EV3 a veces corre sin locale UTF-8 (Python 3.5 usa ASCII): un texto
        # con tildes o "¡" lanzaba UnicodeEncodeError y trababa al robot.
        for f in self.files:
            try:
                f.write(obj)
            except UnicodeEncodeError:
                f.write(obj.encode("ascii", "replace").decode("ascii"))
            except Exception:
                pass
            try:
                f.flush()
            except Exception:
                pass

    def flush(self):
        for f in self.files:
            f.flush()


# El log anterior se guarda como log_anterior.txt (antes se borraba al reiniciar
# y se perdia el error que habia cerrado el programa).
try:
    if os.path.exists("log.txt"):
        os.replace("log.txt", "log_anterior.txt")
except OSError:
    pass
_log_file = open("log.txt", 'w', encoding="utf-8", errors="replace")
_printer = _ErrorPrinter(sys.stderr, _log_file)
sys.stderr = _printer


def debug_print(*args, **kwargs):
    '''Imprime mensajes de depuracion en stderr y en log.txt.

    En VS Code aparece en el panel de salida.
    '''
    import time
    print(time.strftime("%H:%M:%S"), *args, file=sys.stderr, **kwargs)


def reset_console():
    '''Resets the console to the default state'''
    print('\x1Bc', end='')


def set_cursor(visible):
    '''Turn the cursor on or off'''
    if visible:
        print('\x1B[?25h', end='')
    else:
        print('\x1B[?25l', end='')


def set_font(name):
    '''Sets the console font

    A full list of fonts can be found with `ls /usr/share/consolefonts`
    '''
    os.system('setfont ' + name)


def get_ip_addresses():
    '''Devuelve las IP del robot (excepto localhost) como lista de strings.'''
    try:
        out = subprocess.check_output(["hostname", "-I"]).decode().split()
        ips = [ip for ip in out if not ip.startswith("127.") and ":" not in ip]
        if ips:
            return ips
    except Exception as e:
        debug_print("hostname -I fallo: " + str(e))

    try:
        import socket
        return [socket.gethostbyname(socket.gethostname())]
    except Exception:
        return ["?"]


def speak_es(text: str) -> None:
    '''Compatibilidad con el codigo anterior. Mejor usar personality.say().'''
    _get_sound().speak(text, espeak_opts=config.VOICE_OPTS)


def beep() -> None:
    _get_sound().beep()
