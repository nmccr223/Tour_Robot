# Robot Graceful Shutdown System

## Overview

This document describes the coordinated graceful shutdown system for the Tour Robot, which ensures clean shutdown of both the SER8 (main control unit) and CM5 (LiDAR processing unit) when triggered from the HMI GUI.

## System Architecture

### Components

1. **SER8 Shutdown Manager** (`Main SER8 Unit/Main Control/shutdown_manager_node.py`)
   - Runs on the SER8 unit
   - Exposes ROS 2 service: `/ser8/shutdown_system` (std_srvs/srv/Empty)
   - Publishes shutdown request to CM5
   - Waits for acknowledgment before shutting down SER8
   - Has configurable timeout (default: 10 seconds)

2. **CM5 Shutdown Handler** (`Ld19/Processing/cm5_shutdown_handler_node.py`)
   - Runs on the CM5 unit
   - Subscribes to `/cm5/shutdown_request` topic
   - Gracefully terminates ROS 2 processes
   - Publishes acknowledgment on `/cm5/shutdown_ack` topic
   - Executes system shutdown

3. **HMI GUI Integration** (`Main SER8 Unit/HMI GUI/hmi_main.py`)
   - Admin menu includes "Shutdown System" button (red styled)
   - Shows confirmation dialog before initiating shutdown
   - Calls `/ser8/shutdown_system` service
   - Displays status messages during shutdown

### Communication Flow

```
User clicks "Shutdown System" button in HMI Admin menu
        ↓
Confirmation dialog appears
        ↓
User confirms shutdown
        ↓
HMI calls /ser8/shutdown_system service
        ↓
SER8 shutdown_manager_node receives service call
        ↓
SER8 publishes "shutdown_now" to /cm5/shutdown_request
        ↓
CM5 shutdown_handler_node receives request
        ↓
CM5 terminates ROS 2 processes
        ↓
CM5 publishes acknowledgment to /cm5/shutdown_ack
        ↓
SER8 waits for acknowledgment (timeout: 10 sec)
        ↓
SER8 initiates shutdown via `sudo shutdown -h now`
        ↓
Both units shutdown gracefully
```

## Topics and Services

### Services
- **`/ser8/shutdown_system`** (std_srvs/srv/Empty)
  - Service server on SER8
  - Called by HMI GUI to initiate shutdown
  - No parameters required, no response expected

### Topics
- **`/cm5/shutdown_request`** (std_msgs/msg/String)
  - Published by: SER8 shutdown_manager_node
  - Subscribed by: CM5 shutdown_handler_node
  - Payload: "shutdown_now"

- **`/cm5/shutdown_ack`** (std_msgs/msg/String)
  - Published by: CM5 shutdown_handler_node
  - Subscribed by: SER8 shutdown_manager_node
  - Payload: "acknowledged"

## Installation

### On SER8

1. Copy `shutdown_manager_node.py` to your ROS 2 package in `Main SER8 Unit/Main Control/`:
   ```bash
   cp shutdown_manager_node.py ~/ros2_ws/src/main_control/main_control/shutdown_manager_node.py
   ```

2. Add entry point in `main_control/setup.py`:
   ```python
   entry_points={
       'console_scripts': [
           'shutdown_manager_node = main_control.shutdown_manager_node:main',
       ],
   },
   ```

3. Build the package:
   ```bash
   cd ~/ros2_ws
   colcon build --packages-select main_control
   source install/setup.bash
   ```

### On CM5

1. Copy `cm5_shutdown_handler_node.py` to your ROS 2 package in `Ld19/Processing/`:
   ```bash
   cp cm5_shutdown_handler_node.py ~/ros2_ws/src/ld19_utils/ld19_utils/cm5_shutdown_handler_node.py
   ```

2. Add entry point in `ld19_utils/setup.py`:
   ```python
   entry_points={
       'console_scripts': [
           'cm5_shutdown_handler = ld19_utils.cm5_shutdown_handler_node:main',
       ],
   },
   ```

3. Build the package:
   ```bash
   cd ~/ros2_ws
   colcon build --packages-select ld19_utils
   source install/setup.bash
   ```

## Running the Shutdown System

### Manual Start (for testing)

**On SER8:**
```bash
source ~/ros2_ws/install/setup.bash
ros2 run main_control shutdown_manager_node
```

**On CM5:**
```bash
source ~/ros2_ws/install/setup.bash
ros2 run ld19_utils cm5_shutdown_handler
```

### Integrated Startup

The nodes should be included in your launch files:

**SER8 system_bringup.launch.py:**
```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # ... other nodes ...
        Node(
            package='main_control',
            executable='shutdown_manager_node',
            name='shutdown_manager',
            output='screen',
        ),
    ])
```

**CM5 ld19_autorun.launch.py:**
```python
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # ... other nodes ...
        Node(
            package='ld19_utils',
            executable='cm5_shutdown_handler',
            name='cm5_shutdown_handler',
            output='screen',
        ),
    ])
```

## Usage

### From HMI GUI

1. Click **Admin** button in main window
2. In Admin window, locate the **Shutdown System** button (red)
3. Click the **Shutdown System** button
4. A confirmation dialog will appear
5. Click **Yes** to confirm shutdown
6. System will:
   - Close the admin window
   - SER8 sends shutdown request to CM5
   - CM5 terminates ROS 2 processes and shuts down
   - SER8 shuts down after receiving acknowledgment
7. Both units will power off

### From Command Line (testing only)

To test the shutdown without using the GUI:

```bash
# On any machine with ROS 2 network access
ros2 service call /ser8/shutdown_system std_srvs/srv/Empty
```

## Logging and Monitoring

### SER8 Shutdown Manager Logs

```bash
# View real-time logs
ros2 run main_control shutdown_manager_node

# Or check systemd journal if running as service
journalctl -u ser8_bringup -f
```

Expected log output:
```
[INFO] SER8 shutdown manager ready
[WARNING] Shutdown request received: shutdown_now
[INFO] Acknowledgment sent from CM5
[INFO] Shutting down SER8 now
[CRITICAL] SHUTTING DOWN SER8 NOW
```

### CM5 Shutdown Handler Logs

```bash
# View real-time logs
ros2 run ld19_utils cm5_shutdown_handler

# Or check systemd journal
journalctl -u ld19-stack -f
```

Expected log output:
```
[INFO] CM5 shutdown handler ready
[WARNING] Shutdown request received: shutdown_now
[INFO] Terminating ROS 2 processes
[INFO] Acknowledgment sent to SER8
[CRITICAL] SHUTTING DOWN CM5 NOW
```

## Timeout Behavior

If the CM5 does not respond within the timeout period (default: 10 seconds):

1. SER8 logs a warning: `WARNING: CM5 did not acknowledge shutdown within timeout`
2. SER8 proceeds with shutdown anyway (graceful fallback)
3. Both units will eventually shutdown

### Configuring Timeout

To change the timeout, pass a parameter when launching:

```bash
ros2 run main_control shutdown_manager_node --ros-args -p shutdown_timeout_sec:=15
```

## Troubleshooting

### Shutdown hangs/doesn't complete

**Possible causes:**
1. ROS 2 network connectivity issue between SER8 and CM5
2. Firewall blocking DDS communication
3. Node not running on one of the units

**Solutions:**
- Check ROS 2 domain ID is the same on both units: `echo $ROS_DOMAIN_ID`
- Verify network connectivity: `ping cm5_hostname` from SER8 and vice versa
- Check if nodes are running: `ros2 node list`
- Force shutdown manually: `ssh username@ser8 'sudo shutdown -h now'`

### Service not available

**Error:** `Shutdown service (/ser8/shutdown_system) not available`

**Solutions:**
1. Verify `shutdown_manager_node` is running on SER8: `ros2 node list | grep shutdown`
2. Check if ROS 2 domain is set correctly
3. Restart the node: `pkill shutdown_manager_node` then relaunch

### CM5 doesn't shut down

**Possible causes:**
1. `cm5_shutdown_handler_node` not running on CM5
2. Topic `/cm5/shutdown_request` not being published correctly
3. Insufficient permissions for `sudo shutdown` command

**Solutions:**
1. Verify node is running: `ssh username@cm5 'ros2 node list | grep shutdown'`
2. Check topic data: `ros2 topic echo /cm5/shutdown_request`
3. Verify sudo password-less shutdown is configured (see below)

### Permission denied when calling shutdown

**Setup password-less sudo for shutdown:**

On both SER8 and CM5, edit sudoers file:
```bash
sudo visudo
```

Add these lines at the end:
```
# Allow shutdown without password for ROS user
username ALL=(ALL) NOPASSWD: /sbin/shutdown
```

Replace `username` with the actual username running ROS 2.

## Testing

### End-to-End Test

1. **Start nodes on both units:**
   - SER8: `ros2 run main_control shutdown_manager_node`
   - CM5: `ros2 run ld19_utils cm5_shutdown_handler`

2. **Monitor topics in separate terminal:**
   ```bash
   # Terminal 1: Monitor shutdown requests
   ros2 topic echo /cm5/shutdown_request
   
   # Terminal 2: Monitor acknowledgments
   ros2 topic echo /cm5/shutdown_ack
   ```

3. **Trigger shutdown:**
   ```bash
   ros2 service call /ser8/shutdown_system std_srvs/srv/Empty
   ```

4. **Expected behavior:**
   - Shutdown request appears on Topic 1
   - Acknowledgment appears on Topic 2
   - Both systems shut down

### Unit Tests

To add unit tests, create test files for:
- `test_shutdown_manager_node.py` (tests service server)
- `test_cm5_shutdown_handler_node.py` (tests topic subscription)

Example test structure:
```python
import unittest
import rclpy
from main_control.shutdown_manager_node import CM5ShutdownHandlerNode

class TestShutdownNode(unittest.TestCase):
    def setUp(self):
        rclpy.init()
        self.node = CM5ShutdownHandlerNode()
    
    def tearDown(self):
        self.node.destroy_node()
        rclpy.shutdown()
    
    def test_service_available(self):
        # Test that service is available
        pass
```

## Safety Considerations

1. **Confirmation Required:** The HMI always shows a confirmation dialog before shutdown
2. **Graceful Cleanup:** ROS 2 processes are terminated before system shutdown
3. **Fallback Timeout:** If CM5 doesn't respond, SER8 still shuts down after timeout
4. **Logging:** All shutdown events are logged for audit/debugging purposes
5. **No Auto-Restart:** Once shutdown, both units must be manually powered on again

## Future Enhancements

- [ ] Add graceful node shutdown orchestration (proper signal handling)
- [ ] Implement shutdown status reporting back to HMI
- [ ] Add automatic service health checks before allowing shutdown
- [ ] Create systemd service files for auto-starting shutdown nodes
- [ ] Add telemetry reporting for shutdown events
- [ ] Implement warm restart (reboot) in addition to shutdown

## See Also

- `cm5_autostart/README.md` - LiDAR auto-start system
- `Main SER8 Unit/Launcher/system_bringup.launch.py` - Main launch file
- `Main SER8 Unit/HMI GUI/hmi_main.py` - HMI implementation

## Support

For issues or questions about the shutdown system:
1. Check the Troubleshooting section above
2. Review logs on both units: `journalctl -u SERVICE_NAME -n 50`
3. Test individual components separately
4. Contact the robot development team
