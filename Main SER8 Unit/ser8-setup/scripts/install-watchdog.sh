#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Installing watchdog runtime files"
sudo mkdir -p /usr/local/bin/tour_robot
sudo cp "$SETUP_ROOT/src/cm5_service_watchdog.py" /usr/local/bin/tour_robot/
sudo chmod +x /usr/local/bin/tour_robot/cm5_service_watchdog.py

echo "Installing systemd units"
sudo cp "$SETUP_ROOT/systemd/cm5-watchdog.service" /etc/systemd/system/
sudo cp "$SETUP_ROOT/systemd/cm5-watchdog.timer" /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/cm5-watchdog.service
sudo chmod 644 /etc/systemd/system/cm5-watchdog.timer

echo "Enabling watchdog service and timer"
sudo systemctl daemon-reload
sudo systemctl enable cm5-watchdog.service
sudo systemctl enable cm5-watchdog.timer
sudo systemctl restart cm5-watchdog.service
sudo systemctl restart cm5-watchdog.timer

echo "Watchdog installation completed."