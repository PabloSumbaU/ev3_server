#!/usr/bin/env python3
"""Programa principal del robot social EV3.

1. Muestra la cara y la IP en la pantalla mientras espera la app.
2. Cuando la app se conecta, saluda y procesa los mensajes:
     "stick:<x>;<y>;<garra>"   joystick (garra = 1 cerrada / 0 abierta)
     "stick:*;<garra>"         se solto el joystick
     "text:<instrucciones>"    comandos de voz y botones (ver commands.py)
3. Si la app se desconecta, el robot vuelve a esperar (ya no hace falta
   reiniciar main.py para volver a conectar).
Compatible con Python 3.5 (ev3dev stretch).
"""
import time
import traceback

import config
import sockets
import personality as p
import movement as mv
import commands
import sensors
import speech
import behaviors
from utils import debug_print, get_ip_addresses, set_cursor


def handle_stick(payload):
    parts = payload.split(";")
    if not parts:
        return
    if parts[0].strip() == "*":
        # "*" llega al soltar el joystick y tambien al tocar el boton de la garra:
        # solo detenemos las ruedas si el joystick las estaba moviendo.
        if mv.state.joystick_active:
            mv.joystick_stop()
        claw = parts[1] if len(parts) > 1 else None
    else:
        try:
            x = float(parts[0])
            y = float(parts[1])
        except (ValueError, IndexError):
            debug_print("Joystick invalido: " + payload)
            return
        if behaviors.state.sleeping and (x or y):
            behaviors.state.sleeping = False
            p.emote("neutral")
        mv.joystick(x, y)
        claw = parts[2] if len(parts) > 2 else None
    if claw is not None and claw.strip() in ("0", "1"):
        mv.set_claw(claw.strip() == "1")


def process(messages):
    # Del joystick solo importa el ultimo mensaje de cada lote.
    last_stick = None
    for i, msg in enumerate(messages):
        if msg.startswith("stick:"):
            last_stick = i
    for i, msg in enumerate(messages):
        if ":" not in msg:
            continue
        mode, payload = msg.split(":", 1)
        mode = mode.strip()
        # Un error en un mensaje nunca debe cerrar el servidor: se registra y se sigue.
        try:
            if mode == "stick":
                if i == last_stick:
                    handle_stick(payload)
            elif mode == "text":
                debug_print("Comando: " + payload)
                commands.handle_text(payload)
            else:
                debug_print("Modo desconocido: " + mode)
        except Exception:
            debug_print("ERROR procesando '" + msg + "':")
            debug_print(traceback.format_exc())


def session(conn):
    p.face.clear_custom()
    p.emote("happy")
    p.say("¡Hola! Soy " + config.ROBOT_NAME + ". ¡Estoy listo para jugar!", wait=False)
    reader = sockets.MessageReader(conn.client)
    while conn.alive:
        messages = reader.read()
        if messages is None:
            break
        process(messages)


def main():
    set_cursor(False)
    p.start()
    while True:
        try:
            sockets.initialize()
            break
        except OSError as e:
            # Casi siempre: otro main.py sigue corriendo y ocupa los puertos.
            debug_print("No se pudieron abrir los puertos: " + str(e))
            p.show_message("Puertos ocupados", "¿Hay otro main.py abierto? Reintentando...")
            time.sleep(3)
    mv.start()
    sensors.start()
    speech.start()

    while True:
        p.show_waiting_screen(get_ip_addresses())
        p.voice.beep()
        conn = sockets.wait_for_client()
        try:
            session(conn)
        except (OSError, ConnectionError) as e:
            debug_print("Conexion perdida: " + str(e))
        except Exception:
            debug_print("ERROR en la sesion:")
            debug_print(traceback.format_exc())
        finally:
            try:
                mv.stop_all()
                mv.set_claw(False)
            except Exception:
                debug_print(traceback.format_exc())
            sockets.drop_current()
            behaviors.state.sleeping = False
            try:
                p.emote("sad")
                p.say("Me desconecté. Te espero.", wait=True)
            except Exception:
                debug_print(traceback.format_exc())
            time.sleep(0.5)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        debug_print("ERROR FATAL:")
        debug_print(traceback.format_exc())
        try:
            p.show_message("Error", "Revisa log.txt")
            time.sleep(5)
        except Exception:
            pass
    finally:
        try:
            mv.stop_all()
        except Exception:
            pass
        sockets.clear()
