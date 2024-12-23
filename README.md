# pqopen-device

**pqopen-device** is a cost-effective, open-source measurement device for monitoring voltage and current within electrical distribution panels. It includes power quality (PQ) functionalities compliant with **IEC 61000-4-30** and is designed for tech enthusiasts and educational institutions. It bases on the [daqopen-lib](https://github.com/DaqOpen/daqopen-lib) for  data acquisition and [pqopen-lib](https://github.com/DaqOpen/pqopen-lib) for the power quality processing part.

> [!WARNING] 
> The actual hardware design is not tested so far. Please wait until an official release.

## Key Features

- **Voltage Measurement**: Measure and analyze 3-phase mains voltage up to 330 VAC
- **Current Measurement**: Use clamps like SCT13-0000 for current measurement
- **Power Quality**: Analysis of RMS, Harmonics, Interharmonics, Flicker and more according to IEC 61000-4-30
- **Data Aggregation**: Use different storage intervals for logging selected parameters to CSV or MQTT
- **Cost-Effective**: Built using open-source hardware like the **Arduino Due** and **Raspberry Pi**.


## Target Audience

- **Tech Enthusiasts**: People interested in measurement technology and electrical energy supply.
- **Educational Institutions**: For training and research purposes.

## Hardware Overview

The device comprises:

- A custom **mainboard** with connectors, power supplies, and signal conditioning for voltage and current.
- **Arduino Due** for data acquisition (running with 55 kS/s per channel)
- **Raspberry Pi 3A+** as the edge device.
- A **standard DIN-rail enclosure** (9 module width).

![](hardware/pics/housing_assembly.gif)

The main pcb is dual layer with components on both sides. It uses typically SMT components with down to size of 0805 to be soldered by hand.

![](hardware/pics/pcb_rendering_top.png)

![](hardware/pics/pcb_rendering_bottom.png)


## Software Overview

The software is split into two components:

1. **Firmware (C++)**: Runs on the Arduino Due for ADC data acquisition (see https://github.com/DaqOpen/daqopen-lib)
2. **Edge Device Software (Python)**: Runs on the Raspberry Pi for:
   - Data processing (calculating parameters at adjustable intervals).
   - Data storage.
   - Communication with an MQTT broker.



## Platform Compatibility

- **Core Library**: Runs on ARM64, AMD64, Linux, and Windows (Mac compatibility untested).
- **Main Application**: Designed specifically for the Raspberry Pi.



## Installation

An **initial setup guide** will be provided to assist with assembling the hardware and installing the software soon.



## Documentation

Documentation for the overarching project is available at [docs.daqopen.com](https://docs.daqopen.com). This documentation will be expanded to include specifics for pqopen-device.



## Contribution

Contributions are welcome, provided they align with the project's vision. Feel free to open issues, submit pull requests, or engage in discussions.



## License

This project is licensed under the **MIT License**.
