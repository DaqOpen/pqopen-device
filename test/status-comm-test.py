import unittest
import sys
import os
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from modules.statuscomm import StatusSender, StatusReceiver

class TestSingleSender(unittest.TestCase):

    def test_1s_interval(self):
        sender = StatusSender("test-service", port=50002, send_interval=1)
        receiver = StatusReceiver(["test-service"], port=50002)
        sender.update("OK")
        for i in range(5):
            time.sleep(1)
            sender.update("OK" if i % 2 else "NOK")
            receiver.recv_message()
            self.assertEqual(receiver.status_reg["test-service"]["status"], "OK" if i % 2 else "NOK")

if __name__ == '__main__':
    unittest.main()