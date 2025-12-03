#!/usr/bin/env bash
set -euo pipefail

# Source ROS 2 and workspace
source /opt/ros/jazzy/setup.bash
source /home/tourrobotsub/cm5_ws/install/setup.bash

DEV="/dev/ld19"
if [ ! -e "$DEV" ]; then
  for d in /dev/ttyUSB0 /dev/ttyUSB1; do
    if [ -e "$d" ]; then DEV="$d"; break; fi
  done
fi

if [ ! -e "$DEV" ]; then
  echo "LD19 device not found"; exit 1
fi

# Start the driver with working parameters
exec ros2 run ldlidar_stl_ros2 ldlidar_stl_ros2_node \
  --ros-args \
  -p product_name:=LDLiDAR_LD19 \
  -p topic_name:=scan \
  -p port_name:=$DEV \
  -p port_baudrate:=230400 \
  -p frame_id:=base_laser \
  -p laser_scan_dir:=false
