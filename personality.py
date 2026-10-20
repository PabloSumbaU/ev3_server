"""Personalidad del robot: cara animada en la pantalla, LEDs y voz.

Uso desde otros modulos:
    import personality as p
    p.emote("happy")                 # cara + LEDs
    p.emote("surprised", seconds=2)  # vuelve a neutral despues de 2 s
    p.say("Hola")                    # habla y muestra el texto en pantalla
    p.say("Hola", wait=False)        # habla sin bloquear

Las caras se dibujan una sola vez al arrancar y despues solo se pegan en la
pantalla, porque dibujar con PIL en el EV3 es lento.
Compatible con Python 3.5.
"""
import random
import threading
import time
import unicodedata

from PIL import Image, ImageDraw, ImageFont

import config
from utils import debug_print

# Nombres en espanol (los que llegan desde la app/voz) -> nombre interno
EMOTION_ALIASES = {
    "feliz": "happy", "contento": "happy", "alegre": "happy",
    "triste": "sad",
    "sorprendido": "surprised", "sorpresa": "surprised",
    "amor": "love", "enamorado": "love", "carino": "love",
    "pensando": "thinking", "pensar": "thinking",
    "dormido": "sleep", "dormir": "sleep", "sueno": "sleep",
    "neutral": "neutral", "normal": "neutral",
    "calma": "calm", "tranquilo": "calm", "relajado": "calm",
    "asustado": "alert", "susto": "alert", "alerta": "alert",
}

# Nombre interno -> nombre para mostrar en la app
EMOTION_LABELS = {
    "neutral": "neutral", "happy": "feliz", "sad": "triste",
    "surprised": "sorprendido", "love": "carinoso", "thinking": "pensando",
    "sleep": "dormido", "calm": "tranquilo", "alert": "alerta",
}

# expresion -> (ojos, boca)
EXPRESSIONS = {
    "neutral":   ("open", "smile"),
    "happy":     ("happy", "bigsmile"),
    "sad":       ("sad", "frown"),
    "surprised": ("big", "o"),
    "love":      ("heart", "bigsmile"),
    "thinking":  ("lookup", "flat"),
    "sleep":     ("closed", "flat"),
    "calm":      ("relaxed", "smile"),
    "alert":     ("sad", "o"),
}

# Expresiones que parpadean solas de vez en cuando
BLINKING = ("neutral", "sad", "surprised", "thinking", "alert")

# Color de LEDs por expresion: (color, modo) modo = steady | pulse | off
EMOTION_LEDS = {
    "neutral":   ("GREEN", "steady"),
    "happy":     ("GREEN", "steady"),
    "sad":       ("AMBER", "steady"),
    "surprised": ("YELLOW", "steady"),
    "love":      ("RED", "pulse"),
    "thinking":  ("AMBER", "pulse"),
    "sleep":     ("BLACK", "off"),
    "calm":      ("GREEN", "pulse"),
    "alert":     ("RED", "steady"),
}


def normalize_emotion(name):
    if not name:
        return "neutral"
    key = _strip_accents(name.strip().lower())
    if key in EXPRESSIONS:
        return key
    return EMOTION_ALIASES.get(key, "neutral")


def _strip_accents(text):
    text = text.replace("ñ", "n").replace("Ñ", "N")
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


# ====================================================================== dibujo
def _ellipse(draw, cx, cy, w, h, fill):
    draw.ellipse((cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0), fill=fill)


def _draw_eye(draw, cx, cy, w, h, kind, side):
    '''side = -1 ojo izquierdo, 1 ojo derecho (para cejas/parpados inclinados).'''
    B, W = "black", "white"

    if kind in ("open", "big", "lookup", "sad", "worried"):
        if kind == "big":
            w, h = w * 1.2, h * 1.15
        if kind == "lookup":
            cx, cy = cx + w * 0.12, cy - h * 0.12
            h = h * 0.9
        _ellipse(draw, cx, cy, w, h, B)
        # brillo
        r = w * (0.2 if kind == "big" else 0.16)
        hy = cy + h * 0.08 if kind in ("sad", "worried") else cy - h * 0.18
        _ellipse(draw, cx + w * 0.17 * (-side if kind == "sad" else 1), hy, r * 2, r * 2, W)

        top = cy - h / 2.0 - 2
        if kind == "sad":
            # parpado caido hacia afuera
            outer = cx + side * (w / 2.0 + 2)
            inner = cx - side * (w / 2.0 + 2)
            draw.polygon([(inner, top), (outer, top), (outer, cy + h * 0.05)], fill=W)
        elif kind == "worried":
            # ceja inclinada hacia adentro
            outer = cx + side * (w / 2.0 + 2)
            inner = cx - side * (w / 2.0 + 2)
            draw.polygon([(inner, top), (outer, top), (inner, cy - h * 0.02)], fill=W)

    elif kind == "happy":
        # media luna hacia arriba (ojos sonrientes ^ ^)
        _ellipse(draw, cx, cy, w, h * 0.8, B)
        _ellipse(draw, cx, cy + h * 0.28, w * 1.1, h * 0.8, W)

    elif kind == "relaxed":
        # ojos cerrados tranquilos (u u)
        _ellipse(draw, cx, cy, w, h * 0.55, B)
        _ellipse(draw, cx, cy - h * 0.12, w * 1.1, h * 0.5, W)

    elif kind == "closed":
        t = max(3, int(h * 0.1))
        draw.rectangle((cx - w / 2.0, cy - t / 2.0, cx + w / 2.0, cy + t / 2.0), fill=B)

    elif kind == "heart":
        s = w * 0.55
        _ellipse(draw, cx - s * 0.45, cy - s * 0.25, s, s, B)
        _ellipse(draw, cx + s * 0.45, cy - s * 0.25, s, s, B)
        draw.polygon([(cx - s * 0.95, cy - s * 0.1), (cx + s * 0.95, cy - s * 0.1), (cx, cy + s * 0.95)], fill=B)


def _draw_mouth(draw, cx, cy, w, kind):
    B, W = "black", "white"
    if kind == "smile":
        _ellipse(draw, cx, cy, w, w * 0.45, B)
        _ellipse(draw, cx, cy - w * 0.1, w * 1.05, w * 0.4, W)
    elif kind == "bigsmile":
        h = w * 0.55
        draw.chord((cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0), 0, 180, fill=B)
    elif kind == "frown":
        _ellipse(draw, cx, cy + w * 0.1, w * 0.8, w * 0.4, B)
        _ellipse(draw, cx, cy + w * 0.2, w * 0.9, w * 0.38, W)
    elif kind == "o":
        _ellipse(draw, cx, cy, w * 0.3, w * 0.36, B)
        _ellipse(draw, cx, cy, w * 0.16, w * 0.2, W)
    elif kind == "flat":
        draw.rectangle((cx - w * 0.25, cy - 1.5, cx + w * 0.25, cy + 1.5), fill=B)


def render_face(size, mode, expression, compact, blink=False):
    '''Dibuja una cara completa. compact=True deja espacio abajo para texto.'''
    W_, H_ = size
    img = Image.new(mode, (W_, H_), "white")
    draw = ImageDraw.Draw(img)
    eyes, mouth = EXPRESSIONS.get(expression, EXPRESSIONS["neutral"])
    if blink and eyes in ("open", "big", "lookup", "sad", "worried"):
        eyes = "closed"

    if compact:
        ey, ew, eh = 30, 30, 36
    else:
        ey, ew, eh = 46, 40, 50
    lx, rx = W_ * 0.31, W_ * 0.69

    _draw_eye(draw, lx, ey, ew, eh, eyes, -1)
    _draw_eye(draw, rx, ey, ew, eh, eyes, 1)

    if not compact:
        _draw_mouth(draw, W_ / 2.0, 100, 46, mouth)

    if expression == "sleep":
        f = _font(12)
        draw.text((W_ - 34, 6 if compact else 10), "z", font=f, fill="black")
        draw.text((W_ - 24, 0 if compact else 2), "Z", font=f, fill="black")
    return img


# ====================================================================== fuentes
_font_cache = {}


def _font(size):
    if size in _font_cache:
        return _font_cache[size]
    names = {
        10: ["luBS10", "helvB10", "luBS12"],
        12: ["luBS12", "helvB12", "luBS14"],
        14: ["luBS14", "helvB14", "luBS12"],
        18: ["luBS18", "helvB18", "luBS19", "luBS14"],
        24: ["luBS24", "helvB24", "luBS19", "luBS18"],
    }.get(size, ["luBS12"])
    font = None
    try:
        from ev3dev2 import fonts
        for n in names:
            try:
                font = fonts.load(n)
                break
            except Exception:
                continue
    except Exception:
        pass
    if font is None:
        try:
            font = ImageFont.load_default(size=size)   # Pillow nuevo (pruebas en PC)
        except TypeError:
            font = ImageFont.load_default()
    _font_cache[size] = font
    return font


def text_size(draw, text, font):
    try:
        box = draw.textbbox((0, 0), text, font=font)
        return box[2] - box[0], box[3] - box[1]
    except AttributeError:
        return draw.textsize(text, font=font)   # Pillow viejo del EV3


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = w if not line else line + " " + w
        if text_size(draw, test, font)[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def draw_text_safe(draw, xy, text, font):
    try:
        draw.text(xy, text, font=font, fill="black")
    except Exception:
        draw.text(xy, _strip_accents(text), font=font, fill="black")


# ====================================================================== cara
class Face:
    def __init__(self):
        self.enabled = False
        self._lock = threading.RLock()
        self._expression = "neutral"
        self._expr_until = None
        self._text = ""
        self._text_until = None
        self._custom = None          # funcion(draw, w, h) que toma la pantalla
        self._custom_until = None
        self._blinking = False
        self._next_blink = time.time() + 3
        self._last_key = None
        self._cache = {}
        try:
            from ev3dev2.display import Display
            self.display = Display()
            img = self.display.image
            w = getattr(self.display, "xres", img.size[0])
            h = getattr(self.display, "yres", img.size[1])
            self.size = (min(w, img.size[0]), min(h, img.size[1]))
            self.mode = img.mode
            self.enabled = True
        except Exception as e:
            debug_print("Pantalla no disponible: " + str(e))
            self.display = None
            self.size = (178, 128)
            self.mode = "1"

    # ------------------------------------------------------------ API publica
    @property
    def expression(self):
        return self._expression

    def set(self, expression, seconds=None):
        with self._lock:
            self._expression = normalize_emotion(expression)
            self._expr_until = time.time() + seconds if seconds else None

    def show_text(self, text, seconds=None):
        with self._lock:
            self._text = text or ""
            self._text_until = time.time() + seconds if seconds else None

    def clear_text(self):
        with self._lock:
            self._text = ""
            self._text_until = None

    def show_custom(self, draw_fn, seconds=None):
        '''Toma la pantalla completa con un dibujo propio (draw_fn(draw, w, h)).'''
        with self._lock:
            self._custom = draw_fn
            self._custom_until = time.time() + seconds if seconds else None
            self._last_key = None

    def clear_custom(self):
        with self._lock:
            self._custom = None
            self._custom_until = None
            self._last_key = None

    def start(self):
        if not self.enabled:
            return
        for name in EXPRESSIONS:          # dibujar todo una vez al inicio
            for compact in (False, True):
                for blink in (False, True):
                    self._get(name, compact, blink)
        t = threading.Thread(target=self._loop)
        t.daemon = True
        t.start()

    # ------------------------------------------------------------ interno
    def _get(self, name, compact, blink):
        key = (name, compact, blink)
        if key not in self._cache:
            self._cache[key] = render_face(self.size, self.mode, name, compact, blink)
        return self._cache[key]

    def _loop(self):
        while True:
            try:
                self._tick()
            except Exception as e:
                debug_print("Error en cara: " + str(e))
            time.sleep(0.08)

    def _tick(self):
        now = time.time()
        with self._lock:
            if self._expr_until and now > self._expr_until:
                self._expression, self._expr_until = "neutral", None
            if self._text_until and now > self._text_until:
                self._text, self._text_until = "", None
            if self._custom_until and now > self._custom_until:
                self._custom, self._custom_until = None, None

            if self._expression in BLINKING and self._custom is None:
                if not self._blinking and now >= self._next_blink:
                    self._blinking = True
                    self._blink_end = now + 0.15
                elif self._blinking and now >= self._blink_end:
                    self._blinking = False
                    self._next_blink = now + random.uniform(config.BLINK_MIN_S, config.BLINK_MAX_S)
            else:
                self._blinking = False

            custom = self._custom
            key = ("custom", id(custom)) if custom else (self._expression, self._text, self._blinking)
            if key == self._last_key:
                return
            self._last_key = key
            expression, text, blink = self._expression, self._text, self._blinking

        self._render(custom, expression, text, blink)

    def _render(self, custom, expression, text, blink):
        img = self.display.image
        draw = self.display.draw
        w, h = self.size
        if custom is not None:
            draw.rectangle((0, 0, img.size[0], img.size[1]), fill="white")
            custom(draw, w, h)
        else:
            compact = bool(text)
            img.paste(self._get(expression, compact, blink), (0, 0))
            if compact:
                self._draw_bubble(draw, text, w, h)
        self.display.update()

    def _draw_bubble(self, draw, text, w, h):
        font = _font(12)
        lines = wrap_text(draw, text, font, w - 10)
        line_h = text_size(draw, "Ag", font)[1] + 2
        max_lines = max(1, (h - 66) // line_h)
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        draw.rectangle((1, 64, w - 2, h - 1), outline="black", fill="white")
        y = 67
        for line in lines:
            tw = text_size(draw, line, font)[0]
            draw_text_safe(draw, ((w - tw) // 2, y), line, font)
            y += line_h


# ====================================================================== LEDs
class Lights:
    def __init__(self):
        self._mode = "off"
        self._color = "BLACK"
        self._color2 = None
        self._period = 2.0
        self._t0 = time.time()
        self._lock = threading.Lock()
        try:
            from ev3dev2.led import Leds
            self.leds = Leds()
            self.enabled = True
        except Exception as e:
            debug_print("LEDs no disponibles: " + str(e))
            self.leds = None
            self.enabled = False

    def steady(self, color):
        self._set_mode("steady", color)

    def pulse(self, color, period=2.0, restart=False):
        '''Respira: sube y baja el brillo. restart=True empieza desde apagado
        (sirve para sincronizar con "inhala / exhala").'''
        self._set_mode("pulse", color, period=period, restart=restart)

    def alternate(self, color1, color2, period=0.5):
        self._set_mode("alternate", color1, color2, period)

    def off(self):
        self._set_mode("off", "BLACK")

    def for_emotion(self, expression):
        color, mode = EMOTION_LEDS.get(expression, ("GREEN", "steady"))
        if mode == "pulse":
            self.pulse(color)
        elif mode == "off":
            self.off()
        else:
            self.steady(color)

    def _set_mode(self, mode, color, color2=None, period=2.0, restart=False):
        with self._lock:
            if restart or mode != self._mode:
                self._t0 = time.time()
            self._mode, self._color, self._color2, self._period = mode, color, color2, period
        if mode in ("steady", "off"):
            self._apply(color, color, 1)

    def _apply(self, left, right, pct):
        if not self.enabled:
            return
        try:
            self.leds.set_color("LEFT", left, pct)
            self.leds.set_color("RIGHT", right, pct)
        except Exception as e:
            debug_print("Error LED: " + str(e))

    def start(self):
        if not self.enabled:
            return
        t = threading.Thread(target=self._loop)
        t.daemon = True
        t.start()

    def _loop(self):
        import math
        while True:
            with self._lock:
                mode, c1, c2, period, t0 = self._mode, self._color, self._color2, self._period, self._t0
            if mode == "pulse":
                phase = ((time.time() - t0) % period) / period
                pct = 0.15 + 0.85 * (0.5 - 0.5 * math.cos(2 * math.pi * phase))
                self._apply(c1, c1, pct)
                time.sleep(0.1)
            elif mode == "alternate":
                flip = int((time.time() - t0) / period) % 2 == 0
                self._apply(c1 if flip else c2, c2 if flip else c1, 1)
                time.sleep(0.1)
            else:
                time.sleep(0.2)


# ====================================================================== voz
class Voice:
    def __init__(self, face):
        self.face = face
        self._lock = threading.Lock()
        self.speaking = False
        self.muted = False
        try:
            from ev3dev2.sound import Sound
            self.sound = Sound()
        except Exception as e:
            debug_print("Sonido no disponible: " + str(e))
            self.sound = None

    def say(self, text, wait=True, show=True):
        # ev3dev2 pasa el texto a la shell entre comillas simples: un apostrofo lo rompe
        text = (text or "").replace(config.MESSAGE_END, " ").replace("'", " ").replace("\n", " ").strip()
        if not text:
            return
        if not wait:
            t = threading.Thread(target=self.say, args=(text, True, show))
            t.daemon = True
            t.start()
            return
        with self._lock:
            self.speaking = True
            if show:
                self.face.show_text(text)
            debug_print("[Voz] " + text)
            try:
                if self.sound is not None and not self.muted:
                    self.sound.speak(text, espeak_opts=config.VOICE_OPTS)
            except Exception as e:
                debug_print("Error al hablar: " + str(e))
            finally:
                self.speaking = False
                if show:
                    self.face.show_text(text, seconds=1.5)

    def tone(self, notes):
        '''notes: lista de (frecuencia_hz, duracion_ms). Bloquea mientras suena.'''
        if self.sound is None:
            return
        for freq, ms in notes:
            try:
                if freq <= 0:
                    time.sleep(ms / 1000.0)
                else:
                    self.sound.play_tone(freq, ms / 1000.0)
            except Exception as e:
                debug_print("Error tono: " + str(e))
                return

    def beep(self):
        if self.sound is not None:
            try:
                self.sound.beep()
            except Exception:
                pass


# ====================================================================== instancias
face = Face()
lights = Lights()
voice = Voice(face)


def start():
    face.start()
    lights.start()


def emote(expression, seconds=None, leds=True):
    expression = normalize_emotion(expression)
    face.set(expression, seconds)
    if leds:
        lights.for_emotion(expression)


def say(text, wait=True, expression=None):
    if expression:
        emote(expression)
    voice.say(text, wait=wait)


def current_label():
    return EMOTION_LABELS.get(face.expression, face.expression)


def show_waiting_screen(ips):
    '''Pantalla mientras se espera la app: nombre del robot e IP.'''
    def draw_fn(draw, w, h):
        big, small = _font(18), _font(12)
        title = config.ROBOT_NAME
        tw = text_size(draw, title, big)[0]
        draw_text_safe(draw, ((w - tw) // 2, 4), title, big)
        msg = "Esperando la app..."
        tw = text_size(draw, msg, small)[0]
        draw_text_safe(draw, ((w - tw) // 2, 34), msg, small)
        y = 60
        for ip in ips[:3]:
            tw = text_size(draw, ip, big)[0]
            draw_text_safe(draw, ((w - tw) // 2, y), ip, big)
            y += 24
    face.show_custom(draw_fn)
    lights.pulse("AMBER", 2.5)
