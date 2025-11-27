"""
App: daqopen-zmq-server.py
Description: app for reading the data from daq and providing it via zmq

Author: Michael Oberhofer
Created on: 2024-03-13
Last Updated: 2025-11-27

License: MIT

Notes: 

Version: 0.6
Github: https://github.com/DaqOpen/pqopen-device/apps
"""

import tomllib
import time
import logging
import argparse
import os
import sys
import numpy as np

os.environ["OPENBLAS_NUM_THREADS"] = "1"

# Import PQopen Specific Modules
from daqopen.daqinfo import DaqInfo
from daqopen.duedaq import DueDaq, AcqNotRunningException, DAQErrorException
from daqopen.helper import GracefulKiller
from daqopen.daqzmq import DaqPublisher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from modules.timesync import is_time_synchronized

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Argparser
parser = argparse.ArgumentParser(description="Configure App Paths")
parser.add_argument(
        "-c", "--config",
        type=str,
        default="/etc/pqopen/daqinfo.toml",
        help="Path to daqinfo.toml Config File"
    )
args = parser.parse_args()

# Read Config
with open(args.config, "rb") as f:
    daq_config = tomllib.load(f)
daq_info = DaqInfo.from_dict(daq_config)

# Check time sync
check_time_sync = daq_config["app"].get("check_timesync", False)
if check_time_sync:
    if not is_time_synchronized():
        logger.error("System time is not synchronized")
        sys.exit(-1)

# Init terminator
terminator = GracefulKiller()

# Initialize the duedaq
myDaq = DueDaq(channels=daq_info.ai_pin_name.values(),
               samplerate=daq_info.board.samplerate,
               differential=daq_info.board.differential,
               gain=daq_info.board.gain,
               serial_port_name=daq_config["app"]["zmq_server"]["daq_port"])
daq_info.board.samplerate = myDaq.samplerate * daq_info.board.adc_clock_gain

# Initialize the daqzmq publisher
daq_pub = DaqPublisher(daq_info=daq_info,
                       data_columns=myDaq.data_columns,
                       host=daq_config["app"]["zmq_server"]["bind_addr"], 
                       port=daq_config["app"]["zmq_server"]["tcp_port"])

# Local Time Sync
last_log_timestamp = 0.0
ts_agg_window = 51
ts_array = np.zeros(ts_agg_window)
diff_agg_window = 1000
diff_array = np.zeros(diff_agg_window)
daq_ts_seconds = 0.0

# Prepare for acquisition
sent_packet_num = 0

# Start acquisition
myDaq.start_acquisition()

while not terminator.kill_now:
    # Read Data from DAQ
    try:
        data = myDaq.read_data()
    except AcqNotRunningException:
        time.sleep(0.1)
    except DAQErrorException:
        logger.error("DAQErrorException occured - stopping")
        break # Exit Application

    # Generate Timestamp
    actual_timestamp = time.time()
    ts_array = np.roll(ts_array, -1)
    ts_array[-1] = actual_timestamp
    diff_array = np.roll(diff_array, -1)
    diff_array[-1] = ts_array[-1] - ts_array[-2]

    if myDaq._num_frames_read > 10:
        packet_ts_diff_mean = diff_array[-sent_packet_num-1:].mean()
        packet_ts_diff_med = np.median(diff_array[-sent_packet_num-1:])
        packet_ts_diff_min = diff_array[-sent_packet_num-1:].min()
        packet_ts_diff_max = diff_array[-sent_packet_num-1:].max()
        ts_mean = ts_array[-sent_packet_num-1:].mean()
        daq_ts_seconds = ts_mean + packet_ts_diff_mean*(0.5*min(sent_packet_num+1, ts_agg_window) - 0.5)
        if (packet_ts_diff_min < packet_ts_diff_med/2) or (packet_ts_diff_max > packet_ts_diff_med*2):
            logger.error("High packet jitter - quit")
            sys.exit(1)
        # Send data with ZMQ
        daq_pub.send_data(data, sent_packet_num, daq_ts_seconds - daq_info.board.adc_delay_seconds, True)
        sent_packet_num += 1

    # Log Status
    if actual_timestamp > last_log_timestamp + 60:
        logger.info(f"Packet Number: {sent_packet_num:d}, samplerate: {data.shape[0]/diff_array[-sent_packet_num-1:].mean():f}")
        last_log_timestamp = actual_timestamp

myDaq.stop_acquisition()
daq_pub.terminate()
