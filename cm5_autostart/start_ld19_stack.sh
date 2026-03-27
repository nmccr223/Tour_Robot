#!/usr/bin/env bash
set -euo pipefail

# Source ROS 2 and workspace
source /opt/ros/jazzy/setup.bash
source /home/tourrobotsub/cm5_ws/install/setup.bash

# Launch secondary LD19 stack only (preprocess + monitor).
# The LD19 driver is started by ld19.service to ensure one /scan publisher.
exec ros2 launch ld19_utils ld19_autorun.launch.py
