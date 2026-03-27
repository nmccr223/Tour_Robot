# SER8 Troubleshooting Guide

This guide covers the most common recovery actions after a fresh reinstall.

## Startup Status (Temporary)

Current behavior:
- Full Tour Robot bringup on SER8 is currently manual.
- An operator must log in and run `start-tour-robot` from a keyboard/session.

Near-term placeholder:
- Implement full system autostart on SER8 power-on (automatic bringup without manual keyboard command).
- Until that is implemented, treat manual `start-tour-robot` execution as a required startup step.

## 0) Repository update on SER8 (do this first)

Before running troubleshooting commands, update the local clone on SER8.

```bash
# Use whichever path exists on this SER8
if [ -d ~/workspace/Tour_Robot ]; then
   cd ~/workspace/Tour_Robot
elif [ -d ~/Tour_Robot ]; then
   cd ~/Tour_Robot
else
   echo "Tour_Robot repository not found in ~/workspace or ~/"
fi

git status -sb
git pull --ff-only
```

If local files were edited on-device, commit or stash before `git pull`.

Related guides:
- `SER8_INSTALLATION_GUIDE.md` -> [Repository update on SER8](SER8_INSTALLATION_GUIDE.md#0-repository-update-on-ser8-do-this-first)
- `../../../cm5_autostart/SER8_INSTALLATION_GUIDE.md` -> [System does not auto-start (manual recovery)](../../../cm5_autostart/SER8_INSTALLATION_GUIDE.md#system-does-not-auto-start-manual-recovery)

## 1) `install-dependencies.sh` fails

### Symptom
- ROS packages fail to install, or apt repository errors appear.

### Checks
```bash
cat /etc/os-release
cat /etc/apt/sources.list.d/ros2.list
sudo apt update
```

### Fix
```bash
cd ~/Tour_Robot/Main\ SER8\ Unit/ser8-setup
bash scripts/install-dependencies.sh
```

If a key/repo issue remains, remove stale ROS list and rerun:

```bash
sudo rm -f /etc/apt/sources.list.d/ros2.list
bash scripts/install-dependencies.sh
```

## 2) `rosdep install` fails

### Symptom
- Missing dependencies during workspace build.

### Checks
```bash
rosdep --version
sudo test -f /etc/ros/rosdep/sources.list.d/20-default.list && echo "rosdep initialized"
```

### Fix
```bash
sudo rosdep init
rosdep update
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
```

## 3) `start-tour-robot` cannot find ROS/workspace

### Symptom
- Wrapper exits with setup file missing.
- Wrapper exits with: `AMENT_TRACE_SETUP_FILES: unbound variable`

### Checks
```bash
ls -l /opt/ros/jazzy/setup.bash
ls -l ~/ros2_ws/install/setup.bash
cat /usr/local/bin/start-tour-robot
```

### Fix
```bash
cd ~/workspace/Tour_Robot/Main\ SER8\ Unit/ser8-setup
bash scripts/install-startup-wrapper.sh
```

If you hit the `AMENT_TRACE_SETUP_FILES` error, reinstalling the wrapper is required so the updated script (which safely sources ROS setup files) is copied into `/usr/local/bin/start-tour-robot`.

If your workspace path differs from `~/ros2_ws`, update:

```bash
sudo nano /usr/local/bin/start-tour-robot
```

## 4) Watchdog service fails or keeps restarting

### Symptom
- `cm5-watchdog.service` is failed/inactive.

### Checks
```bash
systemctl status cm5-watchdog.service
journalctl -u cm5-watchdog.service -n 100 --no-pager
```

### Fix sequence
1. Verify script exists and is executable:
   ```bash
   ls -l /usr/local/bin/tour_robot/cm5_service_watchdog.py
   ```
2. Verify SSH to CM5:
   ```bash
   ssh tourrobot@192.168.10.20 "systemctl is-active ld19.service"
   ```
3. Reinstall watchdog assets:
   ```bash
   cd ~/Tour_Robot/Main\ SER8\ Unit/ser8-setup
   bash scripts/install-watchdog.sh
   ```

## 5) Watchdog timer not triggering

### Checks
```bash
systemctl status cm5-watchdog.timer
systemctl list-timers cm5-watchdog.timer
cat /etc/systemd/system/cm5-watchdog.timer
```

### Fix
```bash
sudo systemctl daemon-reload
sudo systemctl enable cm5-watchdog.timer
sudo systemctl restart cm5-watchdog.timer
```

## 6) CM5 services cannot restart from SER8

### Symptom
- SSH works, but restart command fails with sudo/systemctl permissions error.

### Fix on CM5
```bash
sudo visudo -f /etc/sudoers.d/tourrobot
```

Ensure required lines are present:

```text
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19.service
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19-stack.service
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl status *
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl is-active *
```

## 7) Fast diagnostic commands

```bash
systemctl status cm5-watchdog.service cm5-watchdog.timer
journalctl -u cm5-watchdog.service -n 50 --no-pager
start-tour-robot --no-launch
```

## 8) System does not auto-start (manual recovery)

### Symptom
- Robot stack did not come up after boot, or camera point cloud is missing.

### Start in the correct folders
1. Open terminal in the repository:
   ```bash
   cd ~/Tour_Robot
   ```
2. Then move to the ROS workspace root:
   ```bash
   cd ~/ros2_ws
   ```

### Recovery steps
1. Source ROS + workspace:
   ```bash
   source /opt/ros/jazzy/setup.bash
   source ~/ros2_ws/install/setup.bash
   ```
2. Verify watchdog/timer state (auto-start path):
   ```bash
   systemctl status cm5-watchdog.service cm5-watchdog.timer
   ```
3. Start camera point cloud stack manually from `~/ros2_ws`:
   ```bash
   ros2 launch depthai_ros_driver rgbd_pcl.launch.py
   ```
4. Confirm point cloud topic availability:
   ```bash
   ros2 topic list | grep -E "/stereo/points|/oak/points"
   ros2 topic info /stereo/points
   ```
5. If `/stereo/points` is not present, verify `/oak/points` and remap as needed:
   ```bash
   ros2 topic info /oak/points
   ```

### Important command note
- Some notes may show this by mistake: `ros2 launch depthai_ros_driver rgdb_pcl.launch.py`
- Use the working command name: `ros2 launch depthai_ros_driver rgbd_pcl.launch.py`

## 9) OAK-D camera not detected or not streaming

### Symptom
- `lsusb` shows no Luxonis devices.
- DepthAI enumeration returns 0 devices.
- Camera appears disconnected.

### Checks
```bash
# Verify USB detection
lsusb | grep -i luxonis
lsusb | grep -i movidius

# Check udev rules applied
ls -l /etc/udev/rules.d/99-oak-d.rules

# Verify DepthAI SDK
python3 -c "import depthai as dai; print(dai.Device.getAllAvailableDevices())"

# Check dmesg for USB errors
dmesg | tail -20 | grep -i "usb\|oak"
```

### Fix sequence
1. Verify USB 3.1 cable and port:
   ```bash
   lsusb -t
   ```
2. Try a different USB 3.1 port (direct to chipset, not hub).
3. Reload udev rules:
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```
4. Check for device firmware issue:
   ```bash
   python3 << 'EOF'
   import depthai as dai
   devices = dai.Device.getAllAvailableDevices()
   for device in devices:
       print(f"Device {device.getMxId()}: {device.getProductName()}")
       try:
           with dai.Device(device):
               print("  OK Device opened successfully")
       except Exception as e:
           print(f"  FAIL Failed to open: {e}")
   EOF
   ```
5. Power cycle both cameras (unplug for 10 seconds, then replug).

## 10) OAK-D camera stream is present but distorted or low quality

### Symptom
- Point cloud visible in RViz2 but very noisy or sparse.
- Camera output jerky or frame rate is low.
- Depth values seem inverted or unrealistic.

### Checks
```bash
# Verify both cameras are not on same USB hub/controller
lsusb -t

# Check ROS2 message arrival rate for common topic layouts
ros2 topic hz /oak/points
ros2 topic hz /front/stereo/points
ros2 topic hz /rear/stereo/points
```

### Fix sequence
1. Ensure USB 3 bandwidth: move rear camera to a different USB 3 port.
2. Reduce image resolution if needed in camera launch parameters.
3. Check camera lens focus and mounting stability.

## 11) RViz2 not showing point cloud or cannot connect to camera topics

### Symptom
- RViz2 launches but has no PointCloud2 topics to select.
- Terminal shows depthai-ros driver starting but no points topics appear.

### Checks
```bash
# Verify topics and depthai nodes
ros2 topic list | grep -Ei "points|oak|stereo"
ros2 node list | grep -Ei "depthai|oak"

# Inspect common topic names used in this project
ros2 topic info /oak/points
ros2 topic info /stereo/points
```

### Fix sequence
1. Ensure ROS environment is sourced in both terminals:
   ```bash
   source /opt/ros/jazzy/setup.bash
   source ~/ros2_ws/install/setup.bash
   ```
2. Verify depthai-ros packages are installed:
   ```bash
   ros2 pkg list | grep depthai
   ```
3. Launch the known working camera stack:
   ```bash
   ros2 launch depthai_ros_driver rgbd_pcl.launch.py
   ```
4. In RViz2, validate display settings:
   - Fixed Frame: `oak_rgb_camera_optical_frame`
   - Topic: `/oak/points`
   - Reliability: `Reliable`
   - Durability: `Transient Local`

## 12) Validate Sensor Outputs, Fusion State, and Navigation Feed (SER8)

Use this section before field testing to verify:
- each sensor output is alive,
- fused decision state is being produced,
- and fused inputs are connected to the navigation controller.

### A) Confirm OAK-D and LD19 outputs are present on SER8

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

# Camera streams and summaries
ros2 topic list | grep -E "^/front/oak/points$|^/rear/oak/points$|^/front/oak/detections$|^/rear/oak/detections$|^/front/oak/summary$|^/rear/oak/summary$"

# LD19 streams expected to be visible from CM5
ros2 topic list | grep -E "^/scan$|^/ld19/summary$|^/health/ld19$"
```

If expected topics are missing:
- Start/repair CM5 LD19 services first, then recheck on SER8.
- Verify ROS_DOMAIN_ID and network reachability between SER8 and CM5.

### B) Confirm data rates and sample messages

```bash
ros2 topic hz /front/oak/summary
ros2 topic hz /rear/oak/summary
ros2 topic hz /scan

ros2 topic echo /front/oak/summary --once
ros2 topic echo /rear/oak/summary --once
ros2 topic echo /scan --once
```

Expected:
- Front/rear summaries update continuously.
- `/scan` updates continuously.
- Message samples show valid frame IDs and distance fields.

### C) Confirm fused decision state output

The controller publishes fused debug output on `/fusion/source_state`.
This topic is `std_msgs/String` carrying JSON for quick diagnostics.

```bash
ros2 topic hz /fusion/source_state
ros2 topic echo /fusion/source_state
```

Look for fields such as:
- `mode` (`forward` or `reverse`)
- `primary_sensor` (`front_oak_summary` or `rear_oak_summary`)
- `secondary_sensor` (`ld19_scan`)
- `hard_stop_active`, `slow_zone_active`
- `cmd_linear`, `cmd_angular`

### D) Confirm fused inputs are feeding navigation node

```bash
ros2 node list | grep main_controller
ros2 node info /main_controller

ros2 topic info /front/oak/summary -v
ros2 topic info /rear/oak/summary -v
ros2 topic info /scan -v
```

Expected:
- `/main_controller` exists.
- `/main_controller` appears as a subscriber to front summary, rear summary, and `/scan`.

### E) Functional forward/reverse delegation check

1. Keep this running:
   ```bash
   ros2 topic echo /fusion/source_state
   ```
2. Trigger a forward-driving scenario:
   - Expect `mode: forward`
   - Expect `primary_sensor: front_oak_summary`
   - Expect `secondary_sensor: ld19_scan`
3. Trigger a reverse-driving scenario:
   - Expect `mode: reverse`
   - Expect `primary_sensor: rear_oak_summary`
   - Expect `secondary_sensor: ld19_scan`

If delegation does not match expected mode:
- Verify goal direction and reverse threshold parameters in launch config.
- Verify rear summary freshness if reverse is blocked by policy.

### F) Disable fusion debug topic when not needed

The debug topic can be disabled at runtime by setting:
- `enable_fusion_debug_topic:=False`

This removes `/fusion/source_state` publishing without changing core navigation behavior.
