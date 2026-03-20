# SER8 Troubleshooting Guide

This guide covers the most common recovery actions after a fresh reinstall.

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

### Checks
```bash
ls -l /opt/ros/jazzy/setup.bash
ls -l ~/ros2_ws/install/setup.bash
cat /usr/local/bin/start-tour-robot
```

### Fix
```bash
cd ~/Tour_Robot/Main\ SER8\ Unit/ser8-setup
bash scripts/install-startup-wrapper.sh
```

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