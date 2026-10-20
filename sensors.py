"""Telemetria (sensor IR + posicion) y reacciones autonomas al entorno.

- Envia a la app, TELEMETRY_HZ veces por segundo:
    socket sensor:   "ir:<0-100>;st:<emocion>;ac:<accion actual>"
    socket posicion: "<x>;<y>;<theta>"
  (antes se enviaba en un bucle sin pausa que saturaba el procesador del EV3)
- Freno de seguridad: si el robot avanza y hay algo muy cerca, se detiene.
- Saludo autonomo: si el robot esta quieto y alguien se acerca, saluda.
Compatible con Python 3.5.
"""
import threading
import time

from ev3dev2.sensor import INPUT_4
from ev3dev2.sensor.lego import InfraredSensor

import config
import sockets
import movement as mv
import personality as p
import behaviors
from utils import debug_print

try:
    ir_sensor = InfraredSensor(INPUT_4)
except Exception as e:
    debug_print("Sensor IR no encontrado en el puerto 4: " + str(e))
    ir_sensor = None


class _Reactions:
    enabled = True              # se puede apagar desde la app ("a-0" / "a-1")
    last_greet = 0.0
    was_far = True
    last_proximity = 100


reactions = _Reactions()


def read_proximity():
    if ir_sensor is None:
        return -1
    try:
        return int(ir_sensor.proximity)
    except Exception:
        return -1


def _safety(prox):
    if not config.SAFETY_STOP_ENABLED or prox < 0:
        mv.state.forward_blocked = False
        return
    blocked = prox <= config.SAFETY_STOP_PROXIMITY
    if blocked and not mv.state.forward_blocked and mv.moving_forward():
        mv.state.forward_blocked = True
        if mv.runner.busy:
            mv.runner.cancel_all(stop_motors=True)
        mv.stop_wheels()
        p.emote("alert", seconds=2.5)
        p.say("¡Uy! Hay algo enfrente.", wait=False)
    # se libera con un margen para no quedar en el limite
    if mv.state.forward_blocked and prox > config.SAFETY_STOP_PROXIMITY + 6:
        mv.state.forward_blocked = False
    elif blocked:
        mv.state.forward_blocked = True


def _greet_on_approach(prox):
    if not (config.GREET_ON_APPROACH_ENABLED and reactions.enabled) or prox < 0:
        return
    if prox >= config.GREET_FAR_PROXIMITY:
        reactions.was_far = True
        return
    if prox > config.GREET_NEAR_PROXIMITY or not reactions.was_far:
        return
    now = time.time()
    if (behaviors.state.sleeping or p.voice.speaking or mv.runner.busy
            or mv.idle_seconds() < config.IDLE_BEFORE_GREET_S
            or now - reactions.last_greet < config.GREET_COOLDOWN_S
            or sockets.current is None):
        return
    reactions.was_far = False
    reactions.last_greet = now
    mv.runner.submit(behaviors.greet_short, "saludo automatico", replace=False)


def _loop():
    period = 1.0 / config.TELEMETRY_HZ
    while True:
        t0 = time.time()
        try:
            prox = read_proximity()
            reactions.last_proximity = prox
            mv.odometer.update()
            _safety(prox)
            _greet_on_approach(prox)

            conn = sockets.current
            if conn is not None and conn.alive:
                parts = []
                if prox >= 0:
                    parts.append("ir:" + str(prox))
                parts.append("st:" + p.current_label())
                parts.append("ac:" + (mv.runner.current_name or "-"))
                conn.send_sensor(";".join(parts))
                conn.send_position(mv.odometer.as_message())
        except Exception as e:
            debug_print("Error en telemetria: " + str(e))
        time.sleep(max(0.01, period - (time.time() - t0)))


def start():
    t = threading.Thread(target=_loop)
    t.daemon = True
    t.start()
