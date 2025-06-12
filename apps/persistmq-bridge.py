"""
App: persistmq-bridge.py
Description: app for collecting the data from local mqtt broker and sending it to the remote broker

Author: Michael Oberhofer
Created on: 2025-02-21
Last Updated: 2025-02-21

License: MIT

Notes: 

Version: 0.01
Github: https://github.com/DaqOpen/pqopen-device/apps
"""

import tomllib
import logging
import argparse
from pathlib import Path
import time
import socket
import random
import string
import os
import sys

from paho.mqtt import client as mqtt
from persistmq.client import PersistClient
from daqopen.helper import GracefulKiller
import importlib.metadata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from modules.statuscomm import StatusSender

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_unique_client_id(prefix: str, number_char: int):
    chars = string.ascii_lowercase + string.digits  # a-z, 0-9
    random_str = ''.join(random.choices(chars, k=number_char))
    return prefix+"-"+random_str

# Configure Argparser
parser = argparse.ArgumentParser(description="Configure App Paths")
parser.add_argument(
        "-c", "--config",
        type=str,
        default="/etc/pqopen/persistmq-conf.toml",
        help="Path to persistmq-conf.toml Config File"
    )
args = parser.parse_args()

# Read Config
with open(args.config, "rb") as f:
    config = tomllib.load(f)
print(config)

# Init Status sender
status_sender = StatusSender("persistmq-bridge")

# Callback function for connection handling
def on_connect(client, userdata, flags, reason_code, properties):
    logger.info(f"Connected with result code {reason_code}")
    for topic in config["source"]["topics"]:
        client.subscribe(topic, qos=0)
    
# Callback function for reading the local message and publishing to remote
def handle_message(client, userdata, msg):
    logger.debug("New Message")
    write_client.publish(msg.topic, msg.payload)

app_terminator = GracefulKiller()

# Configure persistmq-client for sending
client_id = config["destination"].get("client_id", socket.gethostname())
if importlib.metadata.version("persistmq") >= '0.1.0':
    write_client = PersistClient(client_id=client_id, 
                                    cache_path=Path(config["cache"].get("path", "/tmp/")), 
                                    bulk_msg_count=config["bulk_messages"].get("bulk_msg_count", 100),
                                    bulk_topic_rewrite=config["bulk_messages"].get("bulk_topic_rewrite", "mixed/cbor"))
else:
    write_client = PersistClient(client_id=client_id, cache_path=Path(config["cache"].get("path", "/tmp/")))
write_client.mqtt_client.username_pw_set(username=config["destination"].get("username", ""), 
                                            password=config["destination"].get("password", ""))
if config["destination"].get("use_tls", False):
    write_client.mqtt_client.tls_set()
write_client.connect_async(mqtt_host=config["destination"]["mqtt_host"],
                            mqtt_port=config["destination"]["mqtt_port"])

# Configure Source/Reading MQTT Client
read_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, 
                            client_id=generate_unique_client_id("persistmq-bridge", 4), 
                            clean_session=False)
read_client.on_message = handle_message
read_client.on_connect = on_connect
read_client.connect_async(config["source"].get("mqtt_host", "localhost"), 
                            config["source"].get("mqtt_port", 1883))
read_client.loop_start()

# Loop
while not app_terminator.kill_now:
    time.sleep(1)
    persist_client_state = write_client.get_status()
    if persist_client_state["connected"] is None:
        status_sender.update("IDLE")
    elif persist_client_state["connected"]:
        status_sender.update("RUNNING")

status_sender.update("STOPPED")

