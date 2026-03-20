# Navigation Proof of Concept - Quick Start Guide

## Overview

This POC demonstrates autonomous obstacle avoidance using:
- **LD19 LiDAR** (CM5) → publishes `/scan`
- **Vector Field Histogram** (VFH) obstacle avoidance
- **CPP-A24V80A-SA-CAN motor controllers** (2x via USB)
- **Real-time monitoring** via ROS 2 topics

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│ CM5 (Compute Module 5)                                  │
│  └─ ldlidar_stl_ros2_node → publishes /scan            │
└────────────────────────────┬────────────────────────────┘
                             │ ROS 2 Network
┌────────────────────────────▼────────────────────────────┐
│ SER8 (Main Control Computer)                            │
│  └─ navigation_poc                                      │
│      ├─ subscribes /scan                                │
│      ├─ Vector Field Histogram (VFH)                    │
│      ├─ publishes /cmd_vel, /robot_status, /obstacles  │
│      └─ USB → Motor Controllers                         │
└────────────────────────────┬────────────────────────────┘
                             │ USB Serial
┌────────────────────────────▼────────────────────────────┐
│ Motor Controllers (2x CPP-A24V80A-SA-CAN)               │
│  └─ Left wheel + Right wheel (differential drive)      │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Prerequisites

**On CM5:**
- LD19 LiDAR running (`ldlidar_stl_ros2` auto-starts on boot)
- Check: `ros2 topic echo /scan` should show data

**On SER8:**
- ROS 2 Jazzy installed
- Python 3.10+
- `pyserial` package: `pip install pyserial`

### 2. Installation

```bash
# On SER8, navigate to workspace
cd ~/ros2_ws/src/main_control

# Copy POC files (if not already there)
# - ser8_navigation_poc.py
# - motor_controller_stub.py
# - navigation_poc.launch.py (in Launcher/)

# Update setup.py to include POC node
# Add to entry_points:
#   'navigation_poc = main_control.ser8_navigation_poc:main',

# Build package
cd ~/ros2_ws
colcon build --packages-select main_control
source install/setup.bash
```

### 3. Running the POC

**IMPORTANT:** Motors are **disabled by default** for safety.

#### Safe Mode (No Motor Control)
```bash
# Terminal 1: Launch navigation POC
ros2 launch navigation_poc.launch.py

# Terminal 2: Monitor robot status
ros2 topic echo /robot_status

# Terminal 3: Monitor obstacles
ros2 topic echo /obstacle_detection

# Terminal 4: Visualize velocity commands
ros2 topic echo /cmd_vel
```

#### With Motors Enabled (CAUTION: Robot Will Move!)
```bash
# Ensure clear space around robot
# Be ready with emergency stop (Ctrl+C)

ros2 launch navigation_poc.launch.py enable_motors:=true
```

#### Custom Parameters
```bash
# Slower, more cautious
ros2 launch navigation_poc.launch.py \
  enable_motors:=true \
  max_linear_speed:=0.3 \
  safe_distance:=2.0

# Faster, less cautious (not recommended initially)
ros2 launch navigation_poc.launch.py \
  enable_motors:=true \
  max_linear_speed:=0.8 \
  safe_distance:=1.0
```

## Monitoring Topics

### `/robot_status` (String - JSON)
Robot state and performance metrics:
```json
{
  "timestamp": 1234567890.0,
  "state": "NAVIGATING",
  "uptime": 45.2,
  "scan_count": 904,
  "scan_rate": 20.01,
  "heading": 45.3,
  "motors_enabled": true,
  "safety": {
    "safe_distance": 1.5,
    "danger_distance": 0.5,
    "max_linear_speed": 0.5,
    "max_angular_speed": 1.0
  }
}
```

**States:**
- `INITIALIZING` - Starting up
- `READY` - Waiting for scans
- `NAVIGATING` - Normal operation
- `AVOIDING` - Obstacle detected, maneuvering
- `STOPPING` - Danger zone triggered
- `EMERGENCY_STOP` - No safe direction found

### `/obstacle_detection` (String - JSON)
Obstacle zones and closest distances:
```json
{
  "timestamp": 1234567890.0,
  "zones": {
    "front": {
      "obstacle_count": 12,
      "closest_distance": 1.2,
      "safe": true
    },
    "left": {
      "obstacle_count": 3,
      "closest_distance": 2.5,
      "safe": true
    },
    "right": {
      "obstacle_count": 0,
      "closest_distance": null,
      "safe": true
    },
    "rear": {
      "obstacle_count": 5,
      "closest_distance": 3.0,
      "safe": true
    }
  }
}
```

### `/cmd_vel` (Twist)
Velocity commands sent to motors:
```
linear:
  x: 0.35  # m/s forward
  y: 0.0
  z: 0.0
angular:
  x: 0.0
  y: 0.0
  z: 0.15  # rad/s turn rate
```

### `/scan` (LaserScan)
Raw LiDAR data from CM5 (already publishing).

## Visualization with RViz

```bash
# Launch RViz
rviz2

# Add displays:
# - LaserScan → Topic: /scan
# - TF → Shows robot frame
# - RobotModel (if URDF available)

# Fixed Frame: lidar or base_link
```

### OAK-D PointCloud2 (Verified ROS2 Jazzy Setup)

Use the Luxonis launch that brings up the required stack
(`depthai_ros_driver`, `depthai_filters`, and `robot_state_publisher`):

```bash
ros2 launch depthai_ros_driver rgbd_pcl.launch.py
```

Working RViz2 PointCloud2 display values:

- `Fixed Frame`: `oak_rgb_camera_optical_frame`
- `Topic`: `/oak/points`
- `Reliability Policy`: `Reliable`
- `Durability Policy`: `Transient Local`
- `Color Transformation`: `RGB8`

Repository RViz profile:

```bash
rviz2 -d "Main SER8 Unit/Launcher/oak_pointcloud.rviz"
```

## Algorithm: Vector Field Histogram (VFH)

**How it works:**

1. **Sector Division:** Divides 360° scan into 72 sectors (5° each)
2. **Obstacle Density:** Calculates obstacle "magnitude" per sector:
   - `distance < danger` → high density (10.0)
   - `danger < distance < safe` → medium density (scaled)
   - `distance > safe` → low density (0.0)
3. **Valley Detection:** Finds continuous sectors with low obstacle density
4. **Best Direction:** Selects widest valley closest to goal/heading
5. **Velocity Generation:** 
   - `No obstacles` → move forward
   - `Obstacles in safe zone` → reduce speed, turn to valley
   - `Obstacles in danger zone` → stop immediately
   - `No safe valley` → emergency stop

**Parameters:**
- `safe_distance`: 1.5m (slow down zone)
- `danger_distance`: 0.5m (emergency stop zone)
- `num_sectors`: 72 (5° resolution)

**Advantages:**
- Proven algorithm (used in NASA rovers)
- Handles dynamic environments
- Similar to Nav2 DWA/TEB planners
- Tunable for different behaviors

## Motor Controller Integration

### Current Status: STUB

The `motor_controller_stub.py` provides the interface but needs actual USB protocol implementation.

### When You Get the Protocol:

1. **Locate the TODO comments** in `motor_controller_stub.py`
2. **Update `_connect()` method:** Add initialization commands
3. **Update `set_velocity()` method:** Implement actual velocity command format
4. **Test incrementally:**
   ```bash
   python3 motor_controller_stub.py
   ```

### Common Protocol Types:
- **ASCII commands** (e.g., `VEL 1.2 1.5\r\n`)
- **Binary packets** (use `struct.pack()`)
- **CAN-over-USB** (may need `python-can` library)
- **Modbus RTU** (use `pymodbus`)

### Example: ASCII Protocol
```python
def set_velocity(self, left_speed, right_speed):
    cmd = f"VEL {left_speed:.3f} {right_speed:.3f}\r\n"
    self._send_command(cmd.encode())
```

### Example: Binary Protocol
```python
import struct

def set_velocity(self, left_speed, right_speed):
    # Pack as: header(1 byte) + left(float) + right(float)
    packet = struct.pack('<Bff', 0xAA, left_speed, right_speed)
    self._send_command(packet)
```

## Safety Features

✅ **Motors disabled by default** - Requires explicit `enable_motors:=true`
✅ **Multi-zone obstacle detection** - Front/Left/Right/Rear monitoring
✅ **Emergency stop** - Triggers when no safe direction
✅ **Distance-based speed scaling** - Slows near obstacles
✅ **Graceful shutdown** - Stops motors on Ctrl+C

## Testing Procedure

### Phase 1: Simulation (Motors Disabled)
1. Launch POC in safe mode
2. Walk around robot with obstacles
3. Monitor `/obstacle_detection` - verify zones update
4. Check `/cmd_vel` - verify appropriate commands generated
5. Verify robot state changes (NAVIGATING → AVOIDING → STOPPING)

### Phase 2: Motor Test (Stationary)
1. Elevate robot wheels off ground
2. Enable motors: `enable_motors:=true`
3. Verify wheels respond to velocity commands
4. Test emergency stop (Ctrl+C)

### Phase 3: Live Test (Clear Area Required)
1. Clear 5m × 5m space
2. Place obstacles at various distances
3. Enable motors with conservative parameters:
   ```bash
   ros2 launch navigation_poc.launch.py \
     enable_motors:=true \
     max_linear_speed:=0.2 \
     safe_distance:=2.0
   ```
4. Monitor behavior - should avoid obstacles
5. Be ready to stop (Ctrl+C or emergency button)

### Phase 4: Parameter Tuning
Adjust based on robot performance:
- Too cautious? Decrease `safe_distance`, increase `max_linear_speed`
- Too aggressive? Increase `safe_distance`, decrease `max_linear_speed`
- Jerky motion? Adjust angular speed limits in code

## Troubleshooting

### No /scan data on SER8
```bash
# Check CM5 is publishing
ssh user@cm5 'ros2 topic list | grep scan'

# Check ROS_DOMAIN_ID matches
echo $ROS_DOMAIN_ID  # Should be same on both

# Check network connectivity
ping cm5_ip_address
```

### Motors not responding
```bash
# Check USB connection
ls /dev/ttyUSB*  # Should show device

# Check motor controller initialized
ros2 topic echo /robot_status | grep motors_enabled
# Should show "motors_enabled": true

# Test stub directly
python3 motor_controller_stub.py
```

### Robot always in EMERGENCY_STOP
- LiDAR may be blocked/dirty - clean sensor
- Too many obstacles - clear space
- `safe_distance` too large - reduce parameter
- VFH threshold too strict - adjust in code (line ~102)

### High latency / slow response
```bash
# Check scan rate
ros2 topic hz /scan  # Should be ~10-20 Hz

# Check CPU usage
top  # Look for high CPU processes

# Reduce VFH sectors (edit line 66)
# num_sectors=72 → num_sectors=36
```

## Parameters Reference

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `enable_motors` | false | bool | Enable motor control |
| `max_linear_speed` | 0.5 | 0.1-2.0 m/s | Maximum forward speed |
| `max_angular_speed` | 1.0 | 0.1-3.0 rad/s | Maximum turn rate |
| `safe_distance` | 1.5 | 0.5-5.0 m | Slow-down zone |
| `danger_distance` | 0.5 | 0.1-1.0 m | Emergency stop zone |

## Next Steps

1. ✅ **POC Running** - Verify basic obstacle avoidance works
2. ⏳ **Motor Protocol** - Implement actual USB communication
3. ⏳ **Parameter Tuning** - Optimize for your robot's dynamics
4. ⏳ **Add Goal Navigation** - Extend VFH to navigate to destinations
5. ⏳ **Integrate with HMI** - Connect to location selection system
6. ⏳ **Add Mapping** - SLAM for building environment maps
7. ⏳ **Nav2 Migration** - Replace VFH with full Nav2 stack

## Code Organization

```
Main SER8 Unit/
├── Main Control/
│   ├── ser8_navigation_poc.py      # Main POC node (VFH + control)
│   └── motor_controller_stub.py    # Motor interface (needs protocol)
└── Launcher/
    └── navigation_poc.launch.py    # Launch file with parameters
```

## Support

**Common Issues:**
- See Troubleshooting section above
- Check logs: `ros2 topic echo /robot_status`
- Monitor obstacles: `ros2 topic echo /obstacle_detection`

**For Development:**
- VFH algorithm: Lines 57-147 in `ser8_navigation_poc.py`
- Motor control: `motor_controller_stub.py`
- Obstacle zones: Lines 254-275 in `ser8_navigation_poc.py`

**Ready for Production:**
- Once motor protocol implemented
- After live testing in controlled environment
- When parameters tuned for your robot
- After safety validation

---

**Status:** Proof of Concept Ready
**Motors:** Stub (needs USB protocol)
**Algorithm:** VFH (production-quality)
**Safety:** Multi-layered protection
