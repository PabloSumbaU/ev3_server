"""Comportamientos sociales del robot.

Cada comportamiento es una funcion sin argumentos que se ejecuta en el hilo
del Runner (movement.runner). Todos revisan movement.cancelled() entre pasos,
asi el joystick o el boton "Parar" los interrumpen al instante.

Letras del protocolo (se envian como "text:<letra>" desde la app):
    g saludar      n bailar       e respirar     c celebrar
    j chiste       x piedra, papel o tijera
    z dormir       w despertar    m-<emocion> cambiar la cara
Compatible con Python 3.5.
"""
import random
import threading

import config
import movement as mv
import personality as p
from personality import _font, text_size, draw_text_safe


class _State:
    sleeping = False


state = _State()

SPEED = config.BEHAVIOR_SPEED


def _wake_if_sleeping():
    if state.sleeping:
        state.sleeping = False
        p.emote("neutral")


# ====================================================================== saludar
def greet():
    _wake_if_sleeping()
    p.emote("happy")
    p.say("¡Hola! Soy " + config.ROBOT_NAME + ", tu amigo robot. ¡Qué bueno verte!", wait=False)
    # movimiento de "contento": se mueve de lado a lado
    for deg in (-20, 40, -40, 20):
        if not mv.turn(deg, SPEED):
            break
    _wait_voice()
    p.emote("neutral", leds=True)


def greet_short():
    '''Saludo autonomo cuando alguien se acerca.'''
    p.emote("surprised")
    p.say(random.choice([
        "¡Hola! ¿Quieres jugar conmigo?",
        "¡Oh! ¡Hola! Me encontraste.",
        "¡Hola, amigo! Qué gusto verte.",
    ]))
    p.emote("happy", seconds=3)


# ====================================================================== bailar
_DANCE_SONG = [(523, 150), (659, 150), (784, 150), (659, 150), (523, 150), (0, 100),
               (587, 150), (698, 150), (880, 150), (698, 150), (587, 150), (0, 100),
               (659, 150), (784, 150), (988, 150), (784, 300), (1047, 400)]


def dance():
    _wake_if_sleeping()
    p.emote("happy")
    p.lights.alternate("GREEN", "RED", 0.3)
    p.say("¡Hora de bailar!")
    if mv.cancelled():
        return _end()
    music = threading.Thread(target=p.voice.tone, args=(_DANCE_SONG,))
    music.daemon = True
    music.start()
    steps = [
        lambda: mv.turn(-30, 60), lambda: mv.turn(60, 60), lambda: mv.turn(-30, 60),
        lambda: mv.drive_cm(5, 50), lambda: mv.drive_cm(-5, 50),
        lambda: mv.turn(360, 70),
        lambda: mv.turn(-30, 60), lambda: mv.turn(30, 60),
    ]
    for i, step in enumerate(steps):
        p.face.set("love" if i % 2 else "happy")
        if not step():
            break
    music.join(4)
    if not mv.cancelled():
        p.say("¡Me encanta bailar contigo!", expression="happy")
    _end()


# ====================================================================== respirar
def breathe(cycles=3, seconds=4.0):
    '''Ejercicio de respiracion guiada: la luz crece al inhalar y baja al exhalar.'''
    _wake_if_sleeping()
    p.emote("calm")
    p.say("Vamos a respirar juntos. Mira mis luces.")
    if mv.cancelled():
        return _end()
    p.lights.pulse("GREEN", period=seconds * 2, restart=True)
    for i in range(cycles):
        p.say("Inhala", wait=False)
        p.face.show_text("Inhala...  (" + str(i + 1) + "/" + str(cycles) + ")")
        if not mv.wait(seconds):
            return _end()
        p.say("Exhala", wait=False)
        p.face.show_text("Exhala...  (" + str(i + 1) + "/" + str(cycles) + ")")
        if not mv.wait(seconds):
            return _end()
    p.face.clear_text()
    p.emote("happy")
    p.say("¡Muy bien! Lo hiciste genial. ¿Te sientes más tranquilo?")
    _end()


# ====================================================================== celebrar
_FANFARE = [(523, 120), (659, 120), (784, 120), (1047, 300), (0, 80), (784, 120), (1047, 450)]

ENCOURAGEMENTS = [
    "¡Lo lograste! Eres muy valiente.",
    "¡Increíble! Estoy muy orgulloso de ti.",
    "¡Bravo! ¡Eres un campeón!",
    "¡Súper! Lo hiciste muy bien.",
    "¡Wow! ¡Eres una estrella!",
]


def celebrate():
    _wake_if_sleeping()
    p.emote("love")
    p.lights.alternate("GREEN", "ORANGE", 0.25)
    p.voice.tone(_FANFARE)
    if mv.cancelled():
        return _end()
    p.say(random.choice(ENCOURAGEMENTS), wait=False)
    mv.turn(360, 60)
    _wait_voice()
    p.emote("happy")
    _end()


# ====================================================================== chistes
JOKES = [
    ("¿Qué le dice un semáforo a otro?", "¡No me mires, que me estoy cambiando!"),
    ("¿Qué le dijo un pez a otro pez?", "¡Nada, nada!"),
    ("¿Qué hace una abeja en el gimnasio?", "¡Zum-ba!"),
    ("¿Por qué el libro de matemáticas estaba triste?", "¡Porque tenía muchos problemas!"),
    ("¿Qué le dice una iguana a su hermana gemela?", "¡Somos iguanitas!"),
    ("¿Por qué los robots nunca tienen miedo?", "¡Porque tienen nervios de acero!"),
    ("¿Cuál es el animal más antiguo?", "¡La cebra, porque está en blanco y negro!"),
]
_last_joke = [-1]


def joke():
    _wake_if_sleeping()
    idx = random.randrange(len(JOKES))
    if idx == _last_joke[0]:
        idx = (idx + 1) % len(JOKES)
    _last_joke[0] = idx
    question, answer = JOKES[idx]
    p.emote("thinking")
    p.say(question)
    if not mv.wait(1.2):
        return _end()
    p.emote("happy")
    p.say(answer)
    p.say("¡Ja, ja, ja!", wait=False)
    for deg in (-15, 30, -15):
        if not mv.turn(deg, 50):
            break
    _wait_voice()
    _end()


# ====================================================================== piedra papel tijera
def _draw_choice(choice):
    def draw_fn(draw, w, h):
        cx, cy = w // 2, 48
        if choice == "piedra":
            draw.ellipse((cx - 30, cy - 26, cx + 30, cy + 26), fill="black")
        elif choice == "papel":
            draw.rectangle((cx - 24, cy - 32, cx + 24, cy + 32), outline="black", fill="white")
            for k in range(-20, 24, 9):
                draw.line((cx - 16, cy + k, cx + 16, cy + k), fill="black")
        else:  # tijera
            draw.line((cx - 26, cy - 30, cx + 18, cy + 18), fill="black", width=5)
            draw.line((cx + 26, cy - 30, cx - 18, cy + 18), fill="black", width=5)
            draw.ellipse((cx - 30, cy + 12, cx - 12, cy + 30), outline="black", fill="white")
            draw.ellipse((cx + 12, cy + 12, cx + 30, cy + 30), outline="black", fill="white")
        f = _font(18)
        word = choice.upper()
        tw = text_size(draw, word, f)[0]
        draw_text_safe(draw, ((w - tw) // 2, 92), word, f)
    return draw_fn


def _draw_big(text):
    def draw_fn(draw, w, h):
        f = _font(24)
        tw, th = text_size(draw, text, f)
        draw_text_safe(draw, ((w - tw) // 2, (h - th) // 2 - 4), text, f)
    return draw_fn


def rock_paper_scissors():
    _wake_if_sleeping()
    p.emote("happy")
    p.say("¡Juguemos piedra, papel o tijera! A la cuenta de tres.")
    for word in ("Uno", "Dos", "Tres"):
        if mv.cancelled():
            p.face.clear_custom()
            return _end()
        p.face.show_custom(_draw_big(word.upper()))
        p.say(word, wait=True)
        mv.wait(0.15)
    choice = random.choice(["piedra", "papel", "tijera"])
    p.face.show_custom(_draw_choice(choice))
    p.lights.steady("ORANGE")
    p.say("¡Yo saqué " + choice + "!", wait=True)
    mv.wait(2.5)
    p.face.clear_custom()
    p.emote("thinking")
    p.say("¿Quién ganó?")
    p.emote("happy", seconds=3)
    _end()


# ====================================================================== dormir / despertar
def sleep():
    p.emote("happy")
    p.say("Tengo un poco de sueño. ¡Buenas noches!")
    p.emote("sleep")
    state.sleeping = True


def wake():
    state.sleeping = False
    p.emote("surprised")
    p.say("¡Ya desperté!")
    p.emote("happy")
    p.say("¿Jugamos?")
    p.emote("neutral")


# ====================================================================== utilidades
def _wait_voice():
    import time
    t0 = time.time()
    time.sleep(0.1)
    while p.voice.speaking and time.time() - t0 < 15:
        time.sleep(0.05)


def _end():
    '''Deja luces y cara en un estado normal al terminar.'''
    if not state.sleeping:
        p.lights.for_emotion(p.face.expression)


# letra -> (funcion, nombre legible)
BEHAVIORS = {
    "g": (greet, "saludar"),
    "n": (dance, "bailar"),
    "e": (breathe, "respirar"),
    "c": (celebrate, "celebrar"),
    "j": (joke, "chiste"),
    "x": (rock_paper_scissors, "piedra papel o tijera"),
    "z": (sleep, "dormir"),
    "w": (wake, "despertar"),
}
