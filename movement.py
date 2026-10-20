"""Motores: joystick, secuencias de instrucciones, garra y odometria.

Cambios importantes respecto a la version original:
- La garra solo se mueve cuando CAMBIA su estado. Antes, cada mensaje del
  joystick (varios por segundo) mandaba a la garra a girar -90 grados y
  bloqueaba el programa ~0.5 s: esa era la causa de que el joystick
  respondiera lento (el famoso "0.6 s y no se por que" del codigo anterior).
- Las instrucciones de voz y los comportamientos corren en un hilo aparte
  (Runner) y se pueden cancelar: mover el joystick o el comando "s" (parar)
  detiene cualquier secuencia al instante.
- La odometria se calcula con los encoders de los motores, asi funciona igual
  con joystick, voz o comportamientos.
- Freno de seguridad: si el sensor IR detecta algo muy cerca, no deja avanzar.
Compatible con Python 3.5.
"""
import math
import threading
import time

from ev3dev2.motor import (LargeMotor, MediumMotor, MoveJoystick, MoveTank,
                           SpeedPercent, OUTPUT_A, OUTPUT_B, OUTPUT_C)

import config
from utils import debug_print

# Las orugas estan montadas al reves: velocidad NEGATIVA = avanzar.
FORWARD = -1

_left_port = OUTPUT_B
_right_port = OUTPUT_A
_claw_port = OUTPUT_C

_tank = MoveTank(_left_port, _right_port)
_joy = MoveJoystick(_left_port, _right_port)
_left = LargeMotor(_left_port)
_right = LargeMotor(_right_port)
_claw = MediumMotor(_claw_port)

_motor_lock = threading.RLock()


# ====================================================================== estado
class _State:
    def __init__(self):
        self.claw_closed = False
        self.last_activity = time.time()
        self.forward_blocked = False   # lo activa el freno de seguridad
        self.joystick_active = False


state = _State()


def touch():
    '''Marca que el robot hizo algo (para saber cuanto tiempo lleva quieto).'''
    state.last_activity = time.time()


def idle_seconds():
    if runner.busy or state.joystick_active:
        return 0.0
    return time.time() - state.last_activity


# ====================================================================== runner
class Runner:
    '''Ejecuta trabajos (secuencias de instrucciones o comportamientos) en un
    hilo aparte para no bloquear la recepcion de mensajes.'''

    def __init__(self):
        self._cancel = threading.Event()
        self._jobs = []
        self._cond = threading.Condition()
        self.busy = False
        self.current_name = ""
        self.stop_on_cancel = True

    def start(self):
        t = threading.Thread(target=self._loop)
        t.daemon = True
        t.start()

    def submit(self, fn, name="", replace=True):
        '''Agrega un trabajo. replace=True cancela lo que se este ejecutando.'''
        if replace:
            self.cancel_all(stop_motors=True)
        with self._cond:
            self._jobs.append((fn, name))
            self._cond.notify()

    def cancel_all(self, stop_motors=True):
        with self._cond:
            del self._jobs[:]
        self.stop_on_cancel = stop_motors
        if self.busy:
            self._cancel.set()
        if stop_motors:
            stop_wheels()

    def cancelled(self):
        return self._cancel.is_set()

    def _loop(self):
        while True:
            with self._cond:
                while not self._jobs:
                    self._cond.wait()
                fn, name = self._jobs.pop(0)
                self._cancel.clear()
                self.busy = True
                self.current_name = name
            try:
                fn()
            except Exception as e:
                debug_print("Error ejecutando '" + name + "': " + str(e))
            finally:
                self.busy = False
                self.current_name = ""
                touch()


runner = Runner()


def cancelled():
    return runner.cancelled()


def wait(seconds):
    '''Espera cancelable. Devuelve False si se cancelo.'''
    end = time.time() + seconds
    while time.time() < end:
        if runner.cancelled():
            return False
        time.sleep(0.03)
    return True


# ====================================================================== motores
def stop_wheels():
    with _motor_lock:
        try:
            _tank.off(brake=True)
        except Exception as e:
            debug_print("Error al detener: " + str(e))


def _motors_running():
    try:
        return _left.is_running or _right.is_running
    except Exception:
        return False


def _wait_motion(max_seconds):
    '''Espera a que terminen los motores, cancelable y con limite de tiempo.'''
    time.sleep(0.05)
    end = time.time() + max_seconds
    while _motors_running() and time.time() < end:
        if runner.cancelled():
            if runner.stop_on_cancel:
                stop_wheels()
            return False
        if state.forward_blocked and _moving_forward():
            stop_wheels()
            return False
        time.sleep(0.03)
    return not runner.cancelled()


def _moving_forward():
    try:
        return _left.speed * FORWARD > 50 and _right.speed * FORWARD > 50
    except Exception:
        return False


def tank_degrees(left_pct, right_pct, motor_degrees):
    '''Mueve cada oruga motor_degrees grados (cancelable).'''
    if runner.cancelled() or motor_degrees <= 0:
        return False
    if state.forward_blocked and left_pct * FORWARD > 0 and right_pct * FORWARD > 0:
        return False
    touch()
    with _motor_lock:
        if runner.cancelled():
            return False
        _tank.on_for_degrees(SpeedPercent(left_pct), SpeedPercent(right_pct), motor_degrees,
                             brake=True, block=False)
    pct = max(abs(left_pct), abs(right_pct), 1)
    expected = motor_degrees / (pct / 100.0 * 1000.0)   # ~1000 grados/s al 100%
    return _wait_motion(expected * 2 + 2)


def tank_seconds(left_pct, right_pct, seconds):
    if runner.cancelled() or seconds <= 0:
        return False
    if state.forward_blocked and left_pct * FORWARD > 0 and right_pct * FORWARD > 0:
        return False
    touch()
    with _motor_lock:
        if runner.cancelled():
            return False
        _tank.on_for_seconds(SpeedPercent(left_pct), SpeedPercent(right_pct), seconds,
                             brake=True, block=False)
    return _wait_motion(seconds + 2)


def cm_to_motor_deg(cm):
    return abs(cm) / config.CM_PER_MOTOR_DEG


def robot_deg_to_motor_deg(robot_degrees):
    '''Grados que debe girar cada motor para que el robot gire robot_degrees en el sitio.'''
    arc_cm = math.pi * config.TRACK_WIDTH_CM * abs(robot_degrees) / 360.0
    return cm_to_motor_deg(arc_cm) * config.TURN_CALIBRATION


def drive_cm(cm, speed=None):
    '''cm > 0 avanza, cm < 0 retrocede.'''
    speed = speed or config.COMMAND_SPEED
    sign = FORWARD if cm >= 0 else -FORWARD
    return tank_degrees(sign * speed, sign * speed, cm_to_motor_deg(cm))


def drive_seconds(seconds, forward=True, speed=None):
    speed = speed or config.COMMAND_SPEED
    sign = FORWARD if forward else -FORWARD
    return tank_seconds(sign * speed, sign * speed, seconds)


def turn(robot_degrees, speed=None):
    '''robot_degrees > 0 gira a la derecha, < 0 a la izquierda.'''
    speed = speed or config.COMMAND_SPEED
    if robot_degrees >= 0:   # derecha: oruga izq. avanza, der. retrocede
        l, r = FORWARD * speed, -FORWARD * speed
    else:
        l, r = -FORWARD * speed, FORWARD * speed
    return tank_degrees(l, r, robot_deg_to_motor_deg(robot_degrees))


def turn_seconds(seconds, right=True, speed=None):
    speed = speed or config.COMMAND_SPEED
    if right:
        l, r = FORWARD * speed, -FORWARD * speed
    else:
        l, r = -FORWARD * speed, FORWARD * speed
    return tank_seconds(l, r, seconds)


# ====================================================================== garra
def set_claw(closed):
    '''Cierra (True) o abre (False) la garra. Solo actua si cambia el estado.'''
    if closed == state.claw_closed:
        return
    state.claw_closed = closed
    touch()
    try:
        if closed:
            _claw.on(SpeedPercent(config.CLAW_SPEED))   # aprieta y mantiene
        else:
            _claw.off(brake=False)
            _claw.on_for_degrees(SpeedPercent(config.CLAW_SPEED), -config.CLAW_RELEASE_DEG, block=False)
    except Exception as e:
        debug_print("Error garra: " + str(e))


# ====================================================================== joystick
def joystick(x, y, radius=1.0):
    '''x, y en [-1, 1] tal como los envia la app.'''
    x = -x
    if x == 0 and y == 0:
        joystick_stop()
        return

    if runner.busy:          # el operador siempre tiene prioridad
        runner.cancel_all(stop_motors=False)

    length = min(math.sqrt(x * x + y * y), radius)
    angle = math.degrees(math.atan2(y, x))
    if angle < 0:
        angle += 360
    l0, r0 = MoveJoystick.angle_to_speed_percentage(angle)
    l = l0 * length / radius
    r = r0 * length / radius

    if state.forward_blocked and l * FORWARD > 5 and r * FORWARD > 5:
        joystick_stop()
        return

    state.joystick_active = True
    touch()
    with _motor_lock:
        _tank.on(SpeedPercent(l), SpeedPercent(r))


def joystick_stop():
    state.joystick_active = False
    touch()
    stop_wheels()


def stop_all():
    runner.cancel_all(stop_motors=True)
    state.joystick_active = False


# ====================================================================== odometria
class Odometer:
    '''Posicion estimada con los encoders. Unidades de salida: 1 = 30 cm
    (igual que antes, para que el mapa de la app siga funcionando).'''
    unit = 30.0

    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self._last = None

    def update(self):
        try:
            lp, rp = _left.position, _right.position
        except Exception:
            return
        if self._last is None:
            self._last = (lp, rp)
            return
        dl = (lp - self._last[0]) * FORWARD * config.CM_PER_MOTOR_DEG
        dr = (rp - self._last[1]) * FORWARD * config.CM_PER_MOTOR_DEG
        self._last = (lp, rp)
        d = (dl + dr) / 2.0
        dtheta = (dr - dl) / config.TRACK_WIDTH_CM
        self.x += d * math.cos(self.theta + dtheta / 2.0) / self.unit
        self.y += d * math.sin(self.theta + dtheta / 2.0) / self.unit
        self.theta += dtheta

    def as_message(self):
        return "{:.4f};{:.4f};{:.4f}".format(self.x, self.y, self.theta)


odometer = Odometer()


def moving_forward():
    return _moving_forward()


def start():
    runner.start()
