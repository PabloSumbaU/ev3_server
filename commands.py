"""Interprete de instrucciones de texto que llegan desde la app.

Formato: "text:<instr>;<instr>;..."  donde cada instruccion es
    <letra>[-<valor>[-<unidad>]]

Movimiento:
    f  adelante      b  atras        (unidades: cm, m, s; por defecto 20 cm)
    l  izquierda     r  derecha      (unidades: g = grados del robot, s, d = grados de motor;
                                      por defecto DEFAULT_TURN_DEG grados)
    t  dar la vuelta (por defecto 360 g)
    p  agarrar       d  soltar
    s  parar todo (inmediato)
Social:
    g saludar, n bailar, e respirar, c celebrar, j chiste,
    x piedra-papel-tijera, z dormir, w despertar
    m-<emocion>   cambia la cara (feliz, triste, sorprendido, amor, pensando, calma...)
    h-<texto>     el robot dice el texto
    a-1 / a-0     activa / desactiva reacciones autonomas (saludo al acercarse)

Ejemplo: "text:f-20-cm;l;g;m-feliz"
Compatible con Python 3.5.
"""
import config
import movement as mv
import personality as p
import behaviors
import sensors
from utils import debug_print


def _to_float(value, default):
    try:
        return float(value.replace(",", "."))
    except (ValueError, AttributeError):
        return default


def _parse(instruction):
    parts = instruction.strip().split("-")
    order = parts[0].strip().lower()
    value = parts[1].strip() if len(parts) > 1 else None
    unit = parts[2].strip().lower() if len(parts) > 2 else None
    return order, value, unit, parts


def _movement_step(order, value, unit):
    '''Devuelve una funcion que ejecuta el paso de movimiento.'''
    if order in ("f", "b"):
        forward = order == "f"
        amount = _to_float(value, None)
        if amount is None:
            amount, unit = 20, "cm"
        unit = unit or "cm"
        if unit == "s":
            return lambda: mv.drive_seconds(amount, forward)
        if unit == "d":
            sign = mv.FORWARD if forward else -mv.FORWARD
            speed = config.COMMAND_SPEED
            return lambda: mv.tank_degrees(sign * speed, sign * speed, amount)
        cm = amount * 100 if unit == "m" else amount
        return lambda: mv.drive_cm(cm if forward else -cm)

    if order in ("l", "r", "t"):
        right = order != "l"
        default = 360 if order == "t" else config.DEFAULT_TURN_DEG
        amount = _to_float(value, None)
        if amount is None:
            amount, unit = default, "g"
        unit = unit or "g"
        if unit == "s":
            return lambda: mv.turn_seconds(amount, right)
        if unit == "d":
            speed = config.COMMAND_SPEED
            l, r = (mv.FORWARD * speed, -mv.FORWARD * speed) if right else (-mv.FORWARD * speed, mv.FORWARD * speed)
            return lambda: mv.tank_degrees(l, r, amount)
        return lambda: mv.turn(amount if right else -amount)

    if order == "p":
        return lambda: mv.set_claw(True) or mv.wait(0.6)
    if order == "d":
        return lambda: mv.set_claw(False) or mv.wait(0.6)
    return None


def handle_text(payload):
    '''payload: lo que viene despues de "text:".'''
    instructions = [i for i in payload.split(";") if i.strip()]
    steps = []
    names = []

    for instruction in instructions:
        order, value, unit, parts = _parse(instruction)

        if order == "s":                       # parar: inmediato
            mv.stop_all()
            p.emote("neutral")
            steps = []
            names = []
            continue

        if order == "m":                       # emocion: inmediata
            p.emote(value or "neutral")
            continue

        if order == "a":                       # reacciones autonomas on/off
            sensors.reactions.enabled = (value != "0")
            p.say("Modo automático " + ("activado" if sensors.reactions.enabled else "desactivado"), wait=False)
            continue

        if order == "h":                       # decir texto
            text = "-".join(parts[1:]).strip()
            if text:
                steps.append(lambda t=text: p.say(t))
                names.append("hablar")
            continue

        if order in behaviors.BEHAVIORS:
            fn, name = behaviors.BEHAVIORS[order]
            steps.append(fn)
            names.append(name)
            continue

        step = _movement_step(order, value, unit)
        if step is None:
            debug_print("Instruccion desconocida: " + instruction)
            continue
        steps.append(step)
        names.append("moverse")

    if not steps:
        return

    def sequence():
        if behaviors.state.sleeping and names and names[0] not in ("despertar", "dormir"):
            behaviors.state.sleeping = False
            p.emote("neutral")
        for step in steps:
            if mv.cancelled():
                break
            result = step()
            if result is False and mv.cancelled():
                break

    label = names[0] if len(set(names)) == 1 else "secuencia"
    mv.runner.submit(sequence, label, replace=True)
