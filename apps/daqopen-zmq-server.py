"""
App: daqopen-zmq-server.py
Description: app for reading the data from daq and providing it via zmq

Author: Michael Oberhofer
Created on: 2024-03-13
Last Updated: 2025-01-06

License: MIT

Notes: 

Version: 0.03
Github: https://github.com/DaqOpen/pqopen-device/apps
"""

import tomllib
import time
import threading
import logging
import argparse
import os
import sys

os.environ["OPENBLAS_NUM_THREADS"] = "1"

# Import PQopen Specific Modules
from daqopen.daqinfo import DaqInfo
from daqopen.duedaq import DueDaq, AcqNotRunningException, DAQErrorException
from daqopen.helper import GracefulKiller
from daqopen.daqzmq import DaqPublisher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from modules.timesync import is_time_synchronized

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
#start_time = time.time()
last_system_time = 0.0
acq_timestamp = 0.0
sample_count = 0
sync_interval_sec = 10
acq_time_correction_factor = 1.0
acq_time_correction_integral = 0.0
last_log_timestamp = 0.0

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
    if last_system_time == 0:
        last_system_time = actual_timestamp
        acq_timestamp = actual_timestamp
        start_time = actual_timestamp
    else:
        acq_time_correction = (acq_time_correction_factor+acq_time_correction_integral) 
        acq_timestamp += data.shape[0] / myDaq.samplerate * acq_time_correction
        sample_count += data.shape[0]
    
    # Send data with ZMQ
    daq_pub.send_data(data, sent_packet_num, acq_timestamp - daq_info.board.adc_delay_seconds, True)
    sent_packet_num += 1

    # Log Status
    if actual_timestamp > last_log_timestamp + 60:
        logger.info(f"Packet Number: {sent_packet_num:d}")
        last_log_timestamp = actual_timestamp

    # Sync Time
    if actual_timestamp > (last_system_time + sync_interval_sec):
        time_diff = actual_timestamp - acq_timestamp
        total_time_diff_uncorrected = (actual_timestamp - start_time) - sample_count / myDaq.samplerate
        if abs(time_diff) > 10.0:
            logger.error(f"Time Jump detected ({time_diff:f}s): Shutting down Service")
            break
        acq_time_correction_factor = 1.0 + total_time_diff_uncorrected / (actual_timestamp - start_time)
        acq_time_correction_integral += 0.001*time_diff - 0.05*acq_time_correction_integral
        logger.info(f"Time Diff: {time_diff*1000:.1f} ms, Corr Factor: {acq_time_correction_factor:.8f}, Corr Int: {acq_time_correction_integral:.8f}")
        last_system_time = actual_timestamp

myDaq.stop_acquisition()
daq_pub.terminate()