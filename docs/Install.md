# Installation and Software Setup

This document describes the software setup and installation for the embedded Raspberry Pi. 

## Step 1: Create RPi Image

Prepare a SD-Card with an Raspbian OS Lite Image. Follow instructions here: https://www.raspberrypi.com/software/

Use the rpi-imager and set at least the following parameters:

- Your WiFi AP Name and Key
- Username: daqopen with your password
- Hostname: eg. pqopen-1

I recommend setting an ssh-key for secure access without password.

Attach the pre-configured SD-Card to your Raspberry Pi and Power Up.

Connect via SSH to the Raspberry Pi

```bash
ssh daqopen@pqopen-1
```

## Step 2: Install essential packages

To clone the git-repository, git must be installed. Before that, we will do a system update.

```bash
sudo apt update
sudo apt upgrade
sudo apt install git vim
```



## Step 3: Clone Repo and run install script

Now we will clone the repository and run the install script, which takes care of creating a virtual python environment, creating directories and copying necessary files.

Make sure, that the user daqopen is in sudoers list!

```bash
git clone https://github.com/DaqOpen/pqopen-device.git
cd pqopen-device
chmod +x install.sh
./install.sh
```

## Step 3.1 (optional) Configure Comitup

For headless WiFi setup, the Comitup service from https://github.com/davesteele/comitup  is used.

Modify the comitup config file, to customize the settings (e.g. set an AP password)

```bash
vi /etc/comitup.conf
```



## Step 4: Reboot

When the install script finished, please reboot the device.

```bash
sudo reboot
```



## Step 5: System Check

Now it is time to check, if everything is working as expected

### Check Arduino Connection

Make sure, that the Arduino Due with DueDaq Firmware is connected via USB (Native USB) to the Raspberry Pi.

Check if Arduino Due is recognized by the system. Run the following command:

```bash
lsusb
```

The output should show at least the following lines:

```
Bus 001 Device 002: ID 2341:003e Arduino SA Due
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
```

Important is the listing of the Arduino SA Due.

### Check Service Status

Now we can check the status of the different services

#### daqopen-zmq-server

This service's task is to read the acquired data from the Arduino Due board, add scaling and timing information and publish the data via a ZMQ socket.

```bash
sudo systemctl status daqopen-zmq-server
```

The output should show something like this:

```
● daqopen-zmq-server.service - daqopen-zmq-server Service
     Loaded: loaded (/etc/systemd/system/daqopen-zmq-server.service; enabled; preset: enabled)
     Active: active (running) since Fri 2025-05-09 08:04:17 CEST; 1 day 3h ago
   Main PID: 3031 (python)
      Tasks: 3 (limit: 179)
        CPU: 1h 39min 32.958s
     CGroup: /system.slice/daqopen-zmq-server.service
             └─3031 /opt/pqopen/.venv/bin/python daqopen-zmq-server.py --config /etc/pqopen/daqinfo.toml
```

Important is the Active state *active (running)*

#### pqopen

This is the main service for calculating the power values and creating the output.

```
sudo systemctl status pqopen
```

The output should show something like this:

```
● pqopen.service - pqopen Service
     Loaded: loaded (/etc/systemd/system/pqopen.service; enabled; preset: enabled)
     Active: active (running) since Sat 2025-05-10 09:33:47 CEST; 2h 16min ago
   Main PID: 5641 (python)
      Tasks: 4 (limit: 179)
        CPU: 1h 13min 23.252s
     CGroup: /system.slice/pqopen.service
             └─5641 /opt/pqopen/.venv/bin/python pqopen-app.py --config /etc/pqopen/pqopen-config.toml

```

Important is the Active state *active (running)*

#### persistmq-bridge

The third service is used to bridge MQTT messages from the local broker to a remote broker and taking care of message caching in case of connection errors.

This is optional and can be replaced by a bridge config of the mosquitto broker or directly publishing to the target broker.

```bash
sudo systemctl status persistmq-bridge
```



## Finished installation

Now you finished the installation process and first checks of the system. Now, we can take care of appropriate configuration and adjustment.