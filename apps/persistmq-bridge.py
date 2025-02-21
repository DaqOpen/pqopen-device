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

from paho.mqtt import client as mqtt
from persistmq.client import PersistClient

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
   

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

# Callback function for connection handling
def on_connect(client, userdata, flags, reason_code, properties):
    logger.info(f"Connected with result code {reason_code}")
    for topic in config["source"]["topics"]:
        client.subscribe(topic, qos=0)
    
# Callback function for reading the local message and publishing to remote
def handle_message(client, userdata, msg):
    logger.debug("New Message")
    write_client.publish(msg.topic, msg.payload)

if __name__ == "__main__":
    # Configure persistmq-client for sending
    write_client = PersistClient(client_id="persistmq-bridge", cache_path=Path(config["cache"].get("path", "/tmp/")))
    write_client.connect_async(mqtt_host=config["destination"]["mqtt_host"])
    
    # Configure Source/Reading MQTT Client
    read_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="persistmq-bridge", clean_session=False)
    read_client.on_message = handle_message
    read_client.on_connect = on_connect
    read_client.connect_async(config["source"].get("mqtt_host", "localhost"), 
                              config["source"].get("mqtt_port", 1883))
    read_client.loop_start()

    # Loop
    while True:
        time.sleep(1)
