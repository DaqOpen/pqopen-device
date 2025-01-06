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

# Import PQopen Specific Modules
from daqopen.daqinfo import DaqInfo
from daqopen.duedaq import DueDaq, AcqNotRunningException, DAQErrorException
from daqopen.helper import GracefulKiller, check_time_sync
from daqopen.daqzmq import DaqPublisher

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

# Sync Status
actual_time_sync_state = [False]
last_sync_status_checked = 0
sync_check_thread = threading.Thread(target=check_time_sync, args=(actual_time_sync_state,))
sync_check_thread.start()

# Local Time Sync
last_system_time = 0.0
acq_timestamp = 0.0
sync_interval_sec = 10
acq_time_correction_factor = 1.0
time_diff_sum = 0.0
last_log_timestamp = 0.0

# Prepare for acquisition
sent_packet_num = 0

myDaq.start_acquisition()

while not terminator.kill_now:
    # Check status of system time sync every 10s
    if ((last_sync_status_checked + 10) < time.time()) and (not sync_check_thread.is_alive()):
        sync_check_thread.join()
        sync_check_thread = threading.Thread(target=check_time_sync, args=(actual_time_sync_state,))
        sync_check_thread.start()
        last_sync_status_checked = time.time()

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
    acq_timestamp += data.shape[0] / myDaq.samplerate * acq_time_correction_factor
    
    # Send data with ZMQ
    daq_pub.send_data(data, sent_packet_num, acq_timestamp, actual_time_sync_state[0])
    sent_packet_num += 1

    # Log Status
    if actual_timestamp > last_log_timestamp + 60:
        logger.info(f"Packet Number: {sent_packet_num:d}, Sync: {actual_time_sync_state[0]}")
        last_log_timestamp = actual_timestamp

    # Sync Time
    if actual_timestamp > (last_system_time + sync_interval_sec):
        time_diff = actual_timestamp - acq_timestamp
        time_diff_sum += time_diff
        if abs(time_diff) > 10.0:
            logger.error(f"Time Jump detected ({time_diff:f}s): Shutting down Service")
            break
        acq_time_correction_factor = 1.0 + time_diff/(actual_timestamp - last_system_time) + time_diff_sum/sync_interval_sec
        logger.info(f"Actual Time Difference: {time_diff*1000:.1f} ms, Actual Correction Factor: {acq_time_correction_factor:.4f}, Actual Diff Sum: {time_diff_sum:.3f} s")
        last_system_time = actual_timestamp

myDaq.stop_acquisition()
daq_pub.terminate()
