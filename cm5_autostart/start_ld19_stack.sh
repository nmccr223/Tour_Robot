#!/usr/bin/env bash
set -euo pipefail

# Source ROS 2 and workspace
source /opt/ros/jazzy/setup.bash
source /home/tourrobotsub/cm5_ws/install/setup.bash

# Launch combined stack (driver + preprocess + monitor)
# Uses /dev/ld19 by default; override via port:=/dev/ttyUSB0 if needed
exec ros2 launch ld19_utils ld19_autorun.launch.py
