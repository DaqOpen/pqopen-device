import tomllib
import time
import zmq
import uuid
import logging
import os
import argparse
from pathlib import Path

from daqopen.channelbuffer import AcqBufferPool
from daqopen.daqzmq import DaqSubscriber
from daqopen.helper import GracefulKiller
from pqopen.powersystem import PowerSystem
from pqopen.storagecontroller import StorageController
from pqopen.eventdetector import EventController, EventDetectorLevelLow, EventDetectorLevelHigh

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Argparser
parser = argparse.ArgumentParser(description="Configure App Paths")
parser.add_argument(
        "-c", "--config",
        type=str,
        default="/etc/pqopen/pqopen-conf.toml",
        help="Path to pqopen-conf.toml Config File"
    )
args = parser.parse_args()

# Read Config
with open(args.config, "rb") as f:
    config = tomllib.load(f)

# Read Device ID
device_id_file = Path("/etc/pqopen/device-id")
if device_id_file.exists():
    device_id = device_id_file.read_text()
else:
    device_id = "00000000-0000-0000-0000-000000000000"

# Initialize App Killer
app_terminator = GracefulKiller()

# Generate measurement id
measurement_id = str(uuid.uuid4())

# Subscribe to DaqOpen Zmq Server
daq_sub = DaqSubscriber(config["zmq_server"]["host"], config["zmq_server"]["port"])
print("Daq Connected")

# Create DAQ Buffer Object
daq_buffer = AcqBufferPool(daq_info=daq_sub.daq_info, 
                                data_columns=daq_sub.data_columns,
                                start_timestamp_us=int(daq_sub.timestamp*1e6))

# Create Powersystem Object
power_system = PowerSystem(zcd_channel = daq_buffer.channel[config["powersystem"]["zcd_channel"]],
                           input_samplerate = daq_sub.daq_info.board.samplerate,
                           zcd_threshold = 1)

# Add Phases
for phase_name, phase in config["powersystem"]["phase"].items():
    power_system.add_phase(u_channel=daq_buffer.channel[phase["u_channel"]],
                           i_channel=daq_buffer.channel[phase["i_channel"]])
power_system.enable_harmonic_calculation()
power_system.enable_nper_abs_time_sync(daq_buffer.time, interval_sec=10)
power_system.enable_fluctuation_calculation(nominal_voltage=230)
power_system.enable_mains_signaling_calculation(frequency=383)
power_system.enable_under_over_deviation_calculation(u_din=230)

# Initialize Storage Controller
storage_controller = StorageController(time_channel=daq_buffer.time, sample_rate=daq_sub.daq_info.board.samplerate)
storage_controller.setup_endpoints_and_storageplans(endpoints=config["endpoint"],
                                                    storage_plans=config["storageplan"],
                                                    available_channels=power_system.output_channels,
                                                    measurement_id=measurement_id,
                                                    device_id=device_id,
                                                    client_id="pqopen-app",
                                                    start_timestamp_us=int(daq_sub.timestamp*1e6))

# Initialize Event Controller
event_controller = EventController(time_channel=daq_buffer.time, sample_rate=daq_sub.daq_info.board.samplerate)
for ch_name in [f"U{idx+1:d}_1p_hp_rms" for idx in range(len(power_system._phases))]:
    event_controller.add_event_detector(EventDetectorLevelLow(208, 2, power_system.output_channels[ch_name]))
    event_controller.add_event_detector(EventDetectorLevelHigh(253, 2, power_system.output_channels[ch_name]))
    
# Initialize Acq variables
print_values_timestamp = time.time()
last_packet_number = None

# Initialize ZMQ Publisher
context = zmq.Context()
socket = context.socket(zmq.PUB)
socket.bind("tcp://*:5555")  # An Port 5555 binden

# Application Loop
while not app_terminator.kill_now:
    m_data = daq_sub.recv_data()
    if last_packet_number is None:
        last_packet_number = daq_sub.packet_num
    elif last_packet_number + 1 != daq_sub.packet_num:
        logger.error(f"DAQ packet gap detected {last_packet_number:d}+1 != {daq_sub.packet_num:d} - stopping")
        break
    else:
        last_packet_number = daq_sub.packet_num
    daq_buffer.put_data_with_timestamp(m_data, int(daq_sub.timestamp*1e6))
    power_system.process()
    events = event_controller.process()
    storage_controller.process()
    storage_controller.process_events(events)

print("Application Stopped")