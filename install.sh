#!/bin/bash

# Installation script for pqopen

# Variables
INSTALL_DIR="/opt/pqopen"
CONFIG_DIR="/etc/pqopen"
DATA_DIR="/var/lib/pqopen"
CACHE_DIR="/var/lib/persistmq"
USER="daqopen"
DEVICE_ID_FILE="$CONFIG_DIR/device-id"

echo "Starting installation of pqopen..."

# Create necessary directories
echo "Creating directories..."
sudo mkdir -p $INSTALL_DIR
sudo mkdir -p $CONFIG_DIR
sudo mkdir -p $DATA_DIR

# Set permissions
echo "Setting permissions..."
sudo chown -R $USER:$USER $INSTALL_DIR $CONFIG_DIR $DATA_DIR $CACHE_DIR
sudo chmod -R 755 $INSTALL_DIR $CONFIG_DIR $DATA_DIR $CACHE_DIR

# Copy files
echo "Copying files..."
sudo cp apps/* $INSTALL_DIR/
sudo cp -r modules $INSTALL_DIR/

# Copy example configuration
if [ ! -f "$CONFIG_DIR/pqopen-config.toml" ]; then
    echo "Copying default configuration..."
    sudo cp config/pqopen-config.toml $CONFIG_DIR/pqopen-config.toml
else
    echo "Configuration file already exists, skipping."
fi

# Copy example daqinfo configuration
if [ ! -f "$CONFIG_DIR/daqinfo.toml" ]; then
    echo "Copying default daqinfo..."
    sudo cp config/daqinfo.toml $CONFIG_DIR/daqinfo.toml
else
    echo "DaqInfo file already exists, skipping."
fi

# Copy example configuration of persistmq
if [ ! -f "$CONFIG_DIR/persistmq-conf.toml" ]; then
    echo "Copying default persistmq-conf..."
    sudo cp config/persistmq-conf.toml $CONFIG_DIR/persistmq-conf.toml
else
    echo "DaqInfo file already exists, skipping."
fi

# Generate a UUID and save it as device-id
if [ ! -f "$DEVICE_ID_FILE" ]; then
    echo "Generating a new UUID for the device..."
    UUID=$(uuid -v 4)
    echo $UUID | sudo tee $DEVICE_ID_FILE > /dev/null
    echo "Device ID saved to $DEVICE_ID_FILE: $UUID"
else
    echo "Device ID already exists, skipping UUID generation."
fi

# Install Virtual Environment
echo "Creating Python-Environment: .venv"
python3 -m venv $INSTALL_DIR/.venv

echo "Activate Environment"
source $INSTALL_DIR/.venv/bin/activate

echo "Installing Python-Packages"
#pip install --upgrade pip
pip install pqopen-lib
pip install paho-mqtt
pip install persistmq
pip install pgiod

echo "Deactivate Environment"
deactivate

# Create a systemd service file for daqopen-server
echo "Creating systemd service for daqopen-zmq-server..."
cat <<EOF | sudo tee /etc/systemd/system/daqopen-zmq-server.service
[Unit]
Description=daqopen-zmq-server Service
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/.venv/bin/python daqopen-zmq-server.py --config $CONFIG_DIR/daqinfo.toml
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=60s
StandardOutput=journal
StandardError=journal
User=$USER
Group=$USER
IOSchedulingClass=realtime
IOSchedulingPriority=0
CPUAffinity=3
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99

[Install]
WantedBy=multi-user.target
EOF


# Create a systemd service file for pqopen
echo "Creating systemd service..."
cat <<EOF | sudo tee /etc/systemd/system/pqopen.service
[Unit]
Description=pqopen Service
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/.venv/bin/python pqopen-app.py --config $CONFIG_DIR/pqopen-config.toml
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=60s
StandardOutput=journal
StandardError=journal
User=$USER
Group=$USER
Nice=-1

[Install]
WantedBy=multi-user.target
EOF

# Create a systemd servce file for persistmq-bridge
cat <<EOF | sudo tee /etc/systemd/system/persistmq-bridge.service
[Unit]
Description=PersistMQ Bridge Service
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/.venv/bin/python persistmq-bridge.py --config $CONFIG_DIR/persistmq-conf.toml
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=60s
StandardOutput=journal
StandardError=journal
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF

# Create a systemd servce file for status-monitor
cat <<EOF | sudo tee /etc/systemd/system/pqopen-status-monitor.service
[Unit]
Description=PQopen Status Monitor for LEDs
After=network.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/.venv/bin/python status-monitor.py --config $CONFIG_DIR/statusmonitor-conf.toml
WorkingDirectory=$INSTALL_DIR
Restart=always
RestartSec=60s
StandardOutput=journal
StandardError=journal
User=$USER
Group=$USER

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
echo "Enabling and starting pqopen service..."
sudo systemctl daemon-reload
sudo systemctl enable daqopen-zmq-server.service
sudo systemctl start daqopen-zmq-server.service
sudo systemctl enable pqopen.service
sudo systemctl start pqopen.service
sudo systemctl enable persistmq-bridge.service
sudo systemctl start persistmq-bridge.service
sudo systemctl enable pqopen-status-monitor.service
sudo systemctl start pqopen-status-monitor.service

echo "Disabling apt auto update..."
sudo systemctl disable apt-daily.service
sudo systemctl disable apt-daily.timer
sudo systemctl disable apt-daily-upgrade.timer
sudo systemctl disable apt-daily-upgrade.service

# Install Comitup WiFi
wget https://davesteele.github.io/comitup/deb/davesteele-comitup-apt-source_1.2_all.deb
sudo dpkg -i davesteele-comitup-apt-source*.deb
sudo apt-get update
sudo apt-get install -y comitup

sudo rm /etc/network/interfaces
sudo systemctl mask dnsmasq.service
sudo systemctl mask systemd-resolved.service
sudo systemctl mask dhcpd.service
sudo systemctl mask dhcpcd.service
sudo systemctl mask wpa-supplicant.service
sudo systemctl enable NetworkManager.service

# Disable WIFI Power Management
cat <<EOF | sudo tee /etc/NetworkManager/conf.d/powersave.conf
[connection]
wifi.powersave = 2
EOF

# Set Default IO Values for LEDs
cat <<EOF | sudo tee -a /boot/firmware/config.txt
gpio=17,27=op,dh
EOF


# Install mosquitto broker, may be used as gateway
sudo apt-get install -y mosquitto

# Install chrony as time client
sudo apt install -y chrony

echo "Installation completed successfully!"

