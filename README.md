# ev3_server

> **Novedades:** cara animada, LEDs, comportamientos sociales, freno de seguridad y reconexión automática. Ver [CAMBIOS.md](CAMBIOS.md).
These scripts serve the purpose of interpreting instructions received from the [ev3_client](https://github.com/MaxASamaniego/ev3_client) mobile app and executing them on an EV3 robot.

Each module serves a different purpose.

- `main.py`: This is the main module. It is responsible for initializing the server and starting the threads for the other modules.
- `sockets.py`: This module handles the communication between the server (robot) and the client (mobile app) via TCP sockets.
- `sensors.py`: This module handles the sensor information on the EV3 robot.
- `speech.py`: This module handles the speech function of the robot.
- `movement.py`: This module handles the communication between the client and the motors on the EV3 robot.
- `config.py`, `personality.py`, `behaviors.py`, `commands.py`: configuración, cara/LEDs/voz, comportamientos sociales e intérprete de instrucciones (ver CAMBIOS.md).

## Running the server
In order to run the server, simply download all `.py` files into the robot and run the `main.py` file.
