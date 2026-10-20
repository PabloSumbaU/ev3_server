"""Configuracion central del robot.

Todo lo que se quiera ajustar sin tocar la logica esta aqui:
nombre, voz, velocidades, puertos y umbrales del sensor.
Compatible con Python 3.5 (ev3dev stretch): no usar f-strings.
"""

# ---------------------------------------------------------------- Identidad
ROBOT_NAME = "Lumi"

# ---------------------------------------------------------------- Voz (espeak)
# -v es   -> espanol
# -p 0-99 -> tono (mas alto = voz mas aguda y amigable)
# -s      -> palabras por minuto
# -a 0-200 -> amplitud (volumen de espeak)
# -b1     -> texto en UTF-8 (tildes y enie)
# Si quieres probar una voz femenina cambia "-v es" por "-v es+f3".
# Si con eso el robot queda mudo, vuelve a "-v es".
VOICE_OPTS = "-v es -p 70 -s 145 -a 200 -b1"

# ---------------------------------------------------------------- Red
PORT_MAIN = 8000
PORT_SENSOR = 8001
PORT_SPEECH = 8002
PORT_POSITION = 8003
MESSAGE_END = "|"

# Veces por segundo que se envian sensor y posicion a la app.
# Antes se enviaban en un bucle sin pausa y eso saturaba el EV3.
TELEMETRY_HZ = 10

# ---------------------------------------------------------------- Movimiento
# Velocidad (%) para comandos de voz y botones. 100 es demasiado brusco
# cerca de ninos y ademas patina mas (menos precision).
COMMAND_SPEED = 60

# Velocidad (%) usada en los comportamientos sociales (bailar, saludar...)
BEHAVIOR_SPEED = 40

# cm que avanza el robot por cada grado de giro del motor
CM_PER_MOTOR_DEG = 0.02618

# Distancia entre las orugas (cm). Se usa para girar N grados y la odometria.
TRACK_WIDTH_CM = 15.5

# Factor de correccion para giros (las orugas patinan). Si al pedir
# "gira 90 grados" gira de menos, sube este valor; si gira de mas, bajalo.
TURN_CALIBRATION = 1.0

# Giro corto por defecto cuando solo se dice "izquierda" o "derecha" (grados)
DEFAULT_TURN_DEG = 90

# Velocidad de la garra (%) y grados para soltar
CLAW_SPEED = 25
CLAW_RELEASE_DEG = 90

# ---------------------------------------------------------------- Sensor IR
# El sensor de proximidad devuelve 0 (muy cerca) a 100 (lejos, ~70 cm).

# Freno de seguridad: si el robot avanza y algo esta mas cerca que esto, se detiene.
SAFETY_STOP_ENABLED = True
SAFETY_STOP_PROXIMITY = 12

# Saludo autonomo: si el robot esta quieto y alguien se acerca a menos de esto.
GREET_ON_APPROACH_ENABLED = True
GREET_NEAR_PROXIMITY = 25
GREET_FAR_PROXIMITY = 45   # tiene que haber estado "lejos" antes (evita repetir)
GREET_COOLDOWN_S = 25      # segundos minimos entre saludos automaticos
IDLE_BEFORE_GREET_S = 4    # segundos quieto antes de poder saludar solo

# ---------------------------------------------------------------- Cara
BLINK_MIN_S = 2.5
BLINK_MAX_S = 6.0
