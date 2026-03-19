#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Installing startup runtime files"
sudo mkdir -p /usr/local/bin/tour_robot
sudo cp "$SETUP_ROOT/src/ser8_startup.py" /usr/local/bin/tour_robot/
sudo chmod +x /usr/local/bin/tour_robot/ser8_startup.py

echo "Installing start-tour-robot wrapper"
sudo cp "$SETUP_ROOT/src/start-tour-robot.sh" /usr/local/bin/start-tour-robot
sudo chmod +x /usr/local/bin/start-tour-robot

echo "Startup wrapper installed successfully at /usr/local/bin/start-tour-robot"