# SER8 Troubleshooting Guide

This guide covers the most common recovery actions after a fresh reinstall.

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

## 8) OAK-D camera not detected or not streaming

### Symptom
- `lsusb` shows no Luxonis devices
- DepthAI enumeration returns 0 devices
- Camera appears disconnected

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
1. **Verify USB 3.1 cable and port:**
   ```bash
   # Check which USB bus port is being used
   lsusb -t
   # Look for High-Speed or SuperSpeed; if a camera shows on "1.5 Mb/s", it's on USB 2.0
   ```

2. **Try a different USB 3.1 port (direct to chipset, not hub)**

3. **Reload udev rules:**
   ```bash
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   ```

4. **Check for device firmware issue:**
   ```bash
   python3 << 'EOF'
   import depthai as dai
   devices = dai.Device.getAllAvailableDevices()
   for device in devices:
       print(f"Device {device.getMxId()}: {device.getProductName()}")
       # Try to open and check if it hangs
       try:
           with dai.Device(device) as dev:
               print("  ✓ Device opened successfully")
       except Exception as e:
           print(f"  ✗ Failed to open: {e}")
   EOF
   ```

5. **Power cycle both cameras** (unplug for 10 seconds, replug)

## 9) OAK-D camera stream is present but distorted or low quality

### Symptom
- Point cloud visible in RViz2 but very noisy or sparse
- Camera output jerky or frame rate is low
- Depth values seem inverted or unrealistic

### Checks
```bash
# Check for USB bandwidth saturation
cat /sys/kernel/debug/usb/devices | grep -A5 "Luxonis"

# Verify both cameras are not on same USB hub/controller
lsusb -t

# Check ROS2 message arrival rate
ros2 topic hz /front/camera/points
ros2 topic hz /rear/camera/points
```

### Fix sequence
1. **Ensure USB 3 bandwidth:** Move rear camera to a different USB 3 port (not the same internal hub as the front camera)
2. **Reduce image resolution** (if applicable in launch file):
   ```bash
   # Edit camera launch params to use lower resolution mode
   ```
3. **Check camera lens focus:** OAK-D cameras may need manual lens adjustment; ensure the aperture ring is not obstructing the lens
4. **Verify proper mounting:** Camera must be fixed in place (vibration causes depth instability)

## 10) RViz2 not showing point cloud or cannot connect to the camera system

### Symptom
- RViz2 launches but has no PointCloud2 topics to select
- Terminal shows depthai-ros driver starting but no topics appear

### Checks
```bash
# Verify topics being published
ros2 topic list | grep -i "points\|oak"

# Check if depthai node is actually running
ros2 node list | grep -i "depthai\|oak"

# Inspect topic details
ros2 topic info /front/camera/points
```

### Fix sequence
1. **Ensure ROS environment is sourced in both terminals:**
   ```bash
   source /opt/ros/jazzy/setup.bash
   source ~/ros2_ws/install/setup.bash
   ```

2. **Verify depthai-ros is installed:**
   ```bash
   ros2 pkg list | grep depthai
   ```

3. **Launch depthai driver explicitly:**
   ```bash
   ros2 launch depthai_ros_driver rgbd.launch.py
   ```

4. **If still no topics, check depthai driver logs:**
   ```bash
   # Look for errors in the launch terminal
   # Common: camera not detected, wrong resolution, NN model missing
   ```