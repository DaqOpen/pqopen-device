import socket
import time
import json
import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BUF_SIZE = 200

class StatusSender(object):
    def __init__(self, service_name: str, port: int = 50002, send_interval: float = 1.0):
        self.service_name = service_name
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._port = port
        self._send_interval = send_interval
        self._last_time_sent = time.time()
        self._status_reg = {"service": service_name, "status": None}

    def _send_status_message(self):
        self._sock.sendto(json.dumps(self._status_reg).encode(), ("localhost", self._port))

    def update(self, status: str):
        self._status_reg["status"] = status
        if self._last_time_sent + self._send_interval < time.time():
            self._send_status_message()
            self._last_time_sent = time.time()

    def __del__(self):
        self._sock.close()

class StatusReceiver(object):
    def __init__(self, services: list, port: int = 50002, inactive_timeout: float = 5):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.bind(("localhost", port))
        self._sock.settimeout(1)
        self._port = port
        self._inactive_timeout = inactive_timeout
        self.status_reg = {}
        for service in services:
            self.status_reg[service] = {"status": None, "last_timestamp": time.time()}
    
    def recv_message(self):
        try:
            raw_data = self._sock.recv(BUF_SIZE)
            data = json.loads(raw_data.decode())
            if data["service"] not in self.status_reg:
                logger.error(f"service name {data["service"]} not configured!")
            self.status_reg[data["service"]]["status"] = data["status"]
            self.status_reg[data["service"]]["last_timestamp"] = time.time()
        except TimeoutError:
            pass
        # Check inactive
        for service in self.status_reg:
            if self.status_reg[service]["last_timestamp"] + self._inactive_timeout < time.time():
                self.status_reg[service]["status"] = None

    def __del__(self):
        self._sock.close()