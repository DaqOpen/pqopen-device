#!/bin/bash

# Installation script for pqopen

# Variables
INSTALL_DIR="/opt/pqopen"
CONFIG_DIR="/etc/pqopen"
DATA_DIR="/var/lib/pqopen"
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
sudo chown -R $USER:$USER $INSTALL_DIR $CONFIG_DIR $DATA_DIR 
sudo chmod -R 755 $INSTALL_DIR $CONFIG_DIR $DATA_DIR

# Copy files
echo "Copying files..."
sudo cp apps/* $INSTALL_DIR/

# Copy example configuration
if [ ! -f "$CONFIG_DIR/pqopen-config.toml" ]; then
    echo "Copying default configuration..."
    sudo cp config/pqopen-config.toml $CONFIG_DIR/pqopen-config.toml
else
    echo "Configuration file already exists, skipping."
fi

# Copy example configuration
if [ ! -f "$CONFIG_DIR/daqinfo.toml" ]; then
    echo "Copying default daqinfo..."
    sudo cp config/daqinfo.toml $CONFIG_DIR/daqinfo.toml
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

# Reload systemd and enable service
echo "Enabling and starting pqopen service..."
sudo systemctl daemon-reload
sudo systemctl enable daqopen-zmq-server.service
sudo systemctl start daqopen-zmq-server.service
sudo systemctl enable pqopen.service
sudo systemctl start pqopen.service

echo "Disabling apt auto update..."
sudo systemctl disable apt-daily.service
sudo systemctl disable apt-daily.timer
sudo systemctl disable apt-daily-upgrade.timer
sudo systemctl disable apt-daily-upgrade.service

echo "Installation completed successfully!"

