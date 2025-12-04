import tomllib
import time
import zmq
import uuid
import logging
import os
import sys
import argparse
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"

from daqopen.channelbuffer import AcqBufferPool
from daqopen.daqzmq import DaqSubscriber
from daqopen.helper import GracefulKiller
from pqopen.powersystem import PowerSystem
from pqopen.storagecontroller import StorageController
from pqopen.eventdetector import EventController, EventDetectorLevelLow, EventDetectorLevelHigh

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from modules.statuscomm import StatusSender

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
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
    device_id = device_id_file.read_text().strip()
else:
    device_id = "00000000-0000-0000-0000-000000000000"

# Init Status sender
status_sender = StatusSender("pqopen-app")

# Initialize App Killer
app_terminator = GracefulKiller()

# Generate measurement id
measurement_id = str(uuid.uuid4())

# Subscribe to DaqOpen Zmq Server
daq_sub = DaqSubscriber(config["zmq_server"]["host"], config["zmq_server"]["port"])
daq_sub.sock.setsockopt(zmq.RCVTIMEO, 5000) # set Socket Timeout to 5000ms
print("Daq Connected")

# Create DAQ Buffer Object
daq_buffer = AcqBufferPool(daq_info=daq_sub.daq_info, 
                           data_columns=daq_sub.data_columns,
                           start_timestamp_us=int(daq_sub.timestamp*1e6),
                           size=200_000)
input_wiring = config["powersystem"].get("input_wiring", "3P4W")    


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
power_system.enable_fluctuation_calculation(nominal_voltage=config["powersystem"].get("nominal_voltage", 230.0))
power_system.enable_mains_signaling_calculation(frequency=config["powersystem"].get("msv_frequency", 383.3))
power_system.enable_under_over_deviation_calculation(u_din=config["powersystem"].get("nominal_voltage", 230.0))
power_system.enable_energy_channels(Path(config["powersystem"].get("energy_file_path", "/tmp/energy.json")))
if config["powersystem"].get("enable_one_period_fundamental", False):
    power_system.enable_one_period_fundamental()
if config["powersystem"].get("enable_rms_trapz_rule", False):
    power_system.enable_rms_trapz_rule()
if config["powersystem"].get("enable_mains_signaling_tracer", False):
    power_system.enable_mains_signaling_tracer()
#power_system.enable_pmu_calculation()
power_system._update_calc_channels()

# Initialize Storage Controller
storage_controller = StorageController(time_channel=daq_buffer.time, sample_rate=daq_sub.daq_info.board.samplerate)
storage_controller.setup_endpoints_and_storageplans(endpoints=config["endpoint"],
                                                    storage_plans=config["storageplan"],
                                                    available_channels=power_system.output_channels,
                                                    measurement_id=measurement_id,
                                                    device_id=device_id,
                                                    start_timestamp_us=int(daq_sub.timestamp*1e6))

# Initialize Event Controller
event_controller = EventController(time_channel=daq_buffer.time, sample_rate=daq_sub.daq_info.board.samplerate)
if "eventdetector" in config:
    for ch_name in [f"U{idx+1:d}_1p_hp_rms" for idx in range(len(power_system._phases))]:
        level_low_voltage = config["eventdetector"].get("level_low_voltage", 208.0)
        level_high_voltage = config["eventdetector"].get("level_high_voltage", 253.0)
        threshold_voltage = config["eventdetector"].get("hysteresis_voltage", 2.0)
        event_controller.add_event_detector(EventDetectorLevelLow(level_low_voltage, threshold_voltage, power_system.output_channels[ch_name]))
        event_controller.add_event_detector(EventDetectorLevelHigh(level_high_voltage, threshold_voltage, power_system.output_channels[ch_name]))
    
# Initialize Acq variables
print_values_timestamp = time.time()
last_packet_number = None

# Application Loop
while not app_terminator.kill_now:
    try:
        m_data = daq_sub.recv_data()
    except zmq.Again:
        logger.error("Timeout of ZMQ socket ocurred - stopping")
        break
    if last_packet_number is None:
        last_packet_number = daq_sub.packet_num
    elif last_packet_number + 1 != daq_sub.packet_num:
        logger.error(f"DAQ packet gap detected {last_packet_number:d}+1 != {daq_sub.packet_num:d} - stopping")
        break
    else:
        last_packet_number = daq_sub.packet_num
    if input_wiring == "3P3W":
        m_data_conv = m_data.copy()
        u1_column = daq_sub.data_columns[daq_sub.daq_info.channel["U1"].ai_pin]
        u2_column = daq_sub.data_columns[daq_sub.daq_info.channel["U2"].ai_pin]
        u3_column = daq_sub.data_columns[daq_sub.daq_info.channel["U3"].ai_pin]
        m_data_conv[:,u1_column] = 1/3*(m_data[:,u2_column] - m_data[:,u3_column])
        m_data_conv[:,u2_column] = 1/3*(-2*m_data[:,u2_column] - m_data[:,u3_column])
        m_data_conv[:,u3_column] = 1/3*(2*m_data[:,u3_column] + m_data[:,u2_column])
        daq_buffer.put_data_with_timestamp(m_data_conv, int(daq_sub.timestamp*1e6))
    else:
        daq_buffer.put_data_with_timestamp(m_data, int(daq_sub.timestamp*1e6))
    power_system.process()
    events = event_controller.process()
    storage_controller.process()
    storage_controller.process_events(events)

    # Publish actual state
    status_sender.update("RUNNING")

print("Application Stopped")
status_sender.update("STOPPED")