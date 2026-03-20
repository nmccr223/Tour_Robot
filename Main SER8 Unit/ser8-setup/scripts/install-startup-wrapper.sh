#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SETUP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MAIN_CONTROL_STARTUP="$SETUP_ROOT/../Main Control/ser8_startup.py"

echo "Installing startup runtime files"
sudo mkdir -p /usr/local/bin/tour_robot
if [[ -f "$MAIN_CONTROL_STARTUP" ]]; then
	sudo cp "$MAIN_CONTROL_STARTUP" /usr/local/bin/tour_robot/ser8_startup.py
else
	echo "ERROR: Startup orchestrator not found at: $MAIN_CONTROL_STARTUP"
	exit 1
fi
sudo chmod +x /usr/local/bin/tour_robot/ser8_startup.py

echo "Installing start-tour-robot wrapper"
sudo cp "$SETUP_ROOT/src/start-tour-robot.sh" /usr/local/bin/start-tour-robot
sudo chmod +x /usr/local/bin/start-tour-robot

echo "Startup wrapper installed successfully at /usr/local/bin/start-tour-robot"