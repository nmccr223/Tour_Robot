#!/usr/bin/env bash
set -eo pipefail

echo "Sourcing ROS 2 environment..."
source /opt/ros/jazzy/setup.bash
source /home/tourrobotsub/cm5_ws/install/setup.bash

set -u

# Resolve device symlink or fallbacks
echo "Checking for LD19 device symlink..."
DEV="/dev/ld19"
if [ ! -e "$DEV" ]; then
  echo "/dev/ld19 not found, checking ttyUSB0/ttyUSB1/ttyUSB2..."
  for d in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyUSB2; do
    if [ -e "$d" ]; then
      DEV="$d"
      echo "Found device: $DEV"
      break
    fi
  done
fi

if [ ! -e "$DEV" ]; then
  echo "LD19 device not found on /dev/ld19 or ttyUSB[0-2]"
  exit 1
fi

echo "Device permissions:"; ls -l "$DEV"

# Try configurations; exit on first success and keep the driver running
BAUDS=(230400 115200)
PRODUCTS=(LDLiDAR_LD19 LDLiDAR_LD06)

for BAUD in "${BAUDS[@]}"; do
  for PRODUCT in "${PRODUCTS[@]}"; do
    echo "=========================================="
    echo "Trying: $PRODUCT @ $BAUD on $DEV"
    echo "=========================================="

    ros2 run ldlidar_stl_ros2 ldlidar_stl_ros2_node \
      --ros-args \
      -p product_name:="$PRODUCT" \
      -p topic_name:=scan_raw \
      -p port_name:="$DEV" \
      -p port_baudrate:="$BAUD" \
      -p frame_id:=base_laser \
      -p laser_scan_dir:=false &
    PID=$!

    # Watch service logs up to 8s for success marker
    ok=0
    for i in $(seq 1 8); do
      sleep 1
      if journalctl --no-pager -u ld19.service -n 50 | grep -q "ldlidar communication is normal"; then
        ok=1
        break
      fi
    done

    if [ "$ok" -eq 1 ]; then
      echo "SUCCESS: $PRODUCT @ $BAUD on $DEV"
      # Keep the driver in foreground for systemd
      wait "$PID"
      exit 0
    else
      echo "No data yet; stopping attempt and trying next..."
      kill -TERM "$PID" 2>/dev/null || true
      sleep 1
    fi
  done
done

echo "All configurations failed."
exit 1
