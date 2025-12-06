#!/usr/bin/env bash
# Tour Robot System Startup Wrapper
# Place in /usr/local/bin/start-tour-robot on SER8

set -e

echo "================================================"
echo "  Tour Robot System Startup"
echo "================================================"
echo ""

# Configuration
ROS_SETUP="/opt/ros/jazzy/setup.bash"
WORKSPACE_SETUP="/home/tourrobot/ros2_ws/install/setup.bash"
STARTUP_SCRIPT="/usr/local/bin/tour_robot/ser8_startup.py"

# Source ROS environment
if [ -f "$ROS_SETUP" ]; then
    source "$ROS_SETUP"
    echo "✓ Sourced ROS 2 Jazzy environment"
else
    echo "✗ ROS 2 setup not found: $ROS_SETUP"
    exit 1
fi

# Source workspace
if [ -f "$WORKSPACE_SETUP" ]; then
    source "$WORKSPACE_SETUP"
    echo "✓ Sourced workspace environment"
else
    echo "✗ Workspace setup not found: $WORKSPACE_SETUP"
    exit 1
fi

echo ""

# Run startup script with provided arguments
exec /usr/bin/python3 "$STARTUP_SCRIPT" \
  --cm5-host 192.168.10.20 \
  --cm5-user tourrobot \
  --services ld19.service ld19-stack.service \
  --motor-host 192.168.10.2 \
  --motor-port 5005 \
  "$@"
