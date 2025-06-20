import time
import sys
import os

import logging
import gpiod
from gpiod.line import Direction, Value

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from modules.statuscomm import StatusReceiver
from daqopen.helper import GracefulKiller

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize App Killer
app_terminator = GracefulKiller()

# Status Receiver
status_receiver = StatusReceiver(services=["persistmq-bridge", "pqopen-app"])
status_receiver._sock.settimeout(0.1)
last_time = time.time()

#Status LED 1 Init
LED_GREEN = 27
led_green_blink_duration = 0.0
LED_YELLOW = 17
led_yellow_last_state = False

gpio_request = gpiod.request_lines(
    path="/dev/gpiochip0",
    consumer="status-monitor-app",
    config={
        LED_GREEN: gpiod.LineSettings(
            direction=Direction.OUTPUT, output_value=Value.ACTIVE
        ),
        LED_YELLOW: gpiod.LineSettings(
            direction=Direction.OUTPUT, output_value=Value.ACTIVE
        )
    })

while not app_terminator.kill_now:
    ret = status_receiver.recv_message()
    logger.debug(str(status_receiver.status_reg))
    time_diff = time.time() - last_time
    last_time = time.time()
    
    # PQopen Status LED
    if status_receiver.status_reg["pqopen-app"]["status"] == "RUNNING":
        gpio_request.set_value(LED_GREEN, Value.ACTIVE)
    else:
        if led_green_blink_duration > 0.5:
            gpio_request.set_value(LED_GREEN, Value.INACTIVE)
            led_green_blink_duration = -0.1
        elif led_green_blink_duration < -0.5:
            gpio_request.set_value(LED_GREEN, Value.ACTIVE)
            led_green_blink_duration = 0.1
        elif led_green_blink_duration > 0:
            led_green_blink_duration += time_diff
        elif led_green_blink_duration < 0:
            led_green_blink_duration -= time_diff

    # Persistmq-Status-LED
    if status_receiver.status_reg["persistmq-bridge"]["status"] == "RUNNING":
        gpio_request.set_value(LED_YELLOW, Value.INACTIVE)
    elif status_receiver.status_reg["persistmq-bridge"]["status"] == "IDLE":
        if led_yellow_last_state:
            gpio_request.set_value(LED_YELLOW, Value.INACTIVE)
            led_yellow_last_state = False
        else:
            gpio_request.set_value(LED_YELLOW, Value.ACTIVE)
            led_yellow_last_state = True
    else:
        gpio_request.set_value(LED_YELLOW, Value.ACTIVE) # OFF

    