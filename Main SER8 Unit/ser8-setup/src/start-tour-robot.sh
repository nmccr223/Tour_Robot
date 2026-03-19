#!/usr/bin/env bash
# Tour Robot System Startup Wrapper
# Place in /usr/local/bin/start-tour-robot on SER8

set -euo pipefail

echo "================================================"
echo "  Tour Robot System Startup"
echo "================================================"
echo ""

# Configuration (override with env vars if needed)
ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
WORKSPACE_SETUP="${WORKSPACE_SETUP:-$HOME/ros2_ws/install/setup.bash}"
STARTUP_SCRIPT="${STARTUP_SCRIPT:-/usr/local/bin/tour_robot/ser8_startup.py}"

CM5_HOST="${CM5_HOST:-192.168.10.20}"
CM5_USER="${CM5_USER:-tourrobot}"
MOTOR_HOST="${MOTOR_HOST:-192.168.10.2}"
MOTOR_PORT="${MOTOR_PORT:-5005}"

# Source ROS environment
if [[ -f "$ROS_SETUP" ]]; then
    # shellcheck disable=SC1090
    source "$ROS_SETUP"
    echo "✓ Sourced ROS 2 Jazzy environment"
else
    echo "✗ ROS 2 setup not found: $ROS_SETUP"
    exit 1
fi

# Source workspace
if [[ -f "$WORKSPACE_SETUP" ]]; then
    # shellcheck disable=SC1090
    source "$WORKSPACE_SETUP"
    echo "✓ Sourced workspace environment"
else
    echo "✗ Workspace setup not found: $WORKSPACE_SETUP"
    exit 1
fi

echo ""

# Run startup script with provided arguments
exec /usr/bin/python3 "$STARTUP_SCRIPT" \
  --cm5-host "$CM5_HOST" \
  --cm5-user "$CM5_USER" \
  --services ld19.service ld19-stack.service \
  --motor-host "$MOTOR_HOST" \
  --motor-port "$MOTOR_PORT" \
  "$@"