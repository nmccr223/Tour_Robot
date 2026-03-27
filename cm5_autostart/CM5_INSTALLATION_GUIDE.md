# CM5 Installation Guide (Fresh Ubuntu 24.04 LTS)

Use this guide when rebuilding a Compute Module 5 from scratch.

Goal:
1. Install required OS modules and ROS 2 Jazzy on CM5
2. Assemble and build the CM5 ROS workspace for LD19
3. Install udev + systemd auto-start for LD19 driver and stack
4. Validate CM5 -> SER8 topic visibility and add troubleshooting steps

System integration note:
- CM5 publishes LD19 data (primary topic: /scan).
- SER8 performs fusion and motion decisions using separate front/rear OAK streams
  plus CM5 LD19 as a secondary forward-facing safety input.

---

## 0) Repository update on CM5 (do this first)

Before running setup/troubleshooting commands, make sure the local CM5 clone is current.

```bash
# Use whichever path exists on this CM5
if [ -d ~/workspace/Tour_Robot ]; then
   cd ~/workspace/Tour_Robot
elif [ -d ~/Tour_Robot ]; then
   cd ~/Tour_Robot
else
   echo "Tour_Robot repository not found in ~/workspace or ~/"
fi

git status -sb
git pull --ff-only
# Secondary option to update save files from repository
git pull origin main
git status
```

If files in your local clone were edited on-device, commit or stash before git pull.

---

## 1) Prepare the machine

**Workspace:** ~ (home directory)
**Machine:** CM5

Log in as the operational user (current service units use `tourrobotsub`) and update Ubuntu:

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

After reboot, create a workspace folder and clone this repository.

```bash
mkdir -p ~/workspace
cd ~/workspace

# Replace URL with your actual repo URL
git clone https://github.com/YOUR_ORG/Tour_Robot.git Tour_Robot
```

---

## 2) Install ROS 2 Jazzy and build tools

**Workspace:** ~
**Machine:** CM5

Install basic ROS and build tooling:

```bash
sudo apt update
sudo apt install -y \
  software-properties-common \
  curl \
  git \
  python3-colcon-common-extensions \
  python3-rosdep \
  python3-vcstool \
  ros-jazzy-ros-base
```

Initialize rosdep if this is a new OS image:

```bash
sudo rosdep init || true
rosdep update
```

Source ROS setup in future shells:

```bash
grep -q "source /opt/ros/jazzy/setup.bash" ~/.bashrc || \
  echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## 3) Build the CM5 ROS 2 workspace

**Workspace:** ~/cm5_ws
**Machine:** CM5

Create workspace and copy required packages from repository:

```bash
mkdir -p ~/cm5_ws/src

cp -r ~/workspace/Tour_Robot/robot_msgs ~/cm5_ws/src/
cp -r ~/workspace/Tour_Robot/ld19_utils ~/cm5_ws/src/
```

Install external LD19 driver package (required by launch file):

```bash
cd ~/cm5_ws/src
# Package expected by launch: ldlidar_stl_ros2
# Replace URL/tag if your team uses a specific fork.
git clone https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2.git
```

Install dependencies and build:

```bash
cd ~/cm5_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select robot_msgs ld19_utils ldlidar_stl_ros2
```

Source workspace overlay now and on every shell:

```bash
source ~/cm5_ws/install/setup.bash
grep -q "source ~/cm5_ws/install/setup.bash" ~/.bashrc || \
  echo "source ~/cm5_ws/install/setup.bash" >> ~/.bashrc
```

---

## 4) Install LD19 auto-start runtime files

**Workspace:** ~/workspace/Tour_Robot/cm5_autostart
**Machine:** CM5

Install udev rule, startup scripts, and services:

```bash
cd ~/workspace/Tour_Robot/cm5_autostart

sudo cp 99-ld19.rules /etc/udev/rules.d/
sudo cp start_ld19.sh /usr/local/bin/
sudo cp start_ld19_stack.sh /usr/local/bin/
sudo cp ld19.service /etc/systemd/system/
sudo cp ld19-stack.service /etc/systemd/system/

sudo chmod +x /usr/local/bin/start_ld19.sh
sudo chmod +x /usr/local/bin/start_ld19_stack.sh
```

Reload udev/systemd and enable services:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger

sudo systemctl daemon-reload
sudo systemctl enable ld19.service
sudo systemctl enable ld19-stack.service
sudo systemctl restart ld19.service
sudo systemctl restart ld19-stack.service
```

Notes:
- `ld19-stack.service` requires `ld19.service` and starts preprocess + monitor.
- Current scripts assume workspace path `/home/tourrobotsub/cm5_ws`.
- If your username/path differs, edit `/usr/local/bin/start_ld19.sh` and `/usr/local/bin/start_ld19_stack.sh`.

---

## 5) Validate CM5 locally

Check device and service status:

```bash
ls -l /dev/ld19
systemctl status ld19.service
systemctl status ld19-stack.service
```

Watch live logs:

```bash
journalctl -u ld19.service -f
journalctl -u ld19-stack.service -f
```

Confirm ROS topics on CM5:

```bash
source /opt/ros/jazzy/setup.bash
source ~/cm5_ws/install/setup.bash

ros2 topic list | grep -E "^/scan$|^/ld19/summary$|^/health/ld19$"
ros2 topic hz /scan
ros2 topic echo /scan --once
ros2 topic echo /ld19/summary --once
```

Expected:
- `/scan` exists and updates continuously.
- `/ld19/summary` exists from preprocess node.
- `/health/ld19` exists from monitor node.

---

## 6) Validate CM5 -> SER8 connectivity

Run these checks on SER8 to ensure CM5 topics are discoverable:

```bash
# On SER8
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash

printenv ROS_DOMAIN_ID
ros2 topic list | grep -E "^/scan$|^/ld19/summary$"
ros2 topic hz /scan
```

If `/scan` does not appear on SER8:
- Verify CM5 and SER8 use the same `ROS_DOMAIN_ID`.
- Verify both machines are on reachable network interfaces.
- Check firewalls or VLAN isolation.

---

## 7) Common configuration edits

### Change CM5 service user

Current CM5 units use `User=tourrobotsub`.
If you use another account:

```bash
sudo nano /etc/systemd/system/ld19.service
sudo nano /etc/systemd/system/ld19-stack.service
sudo systemctl daemon-reload
sudo systemctl restart ld19.service ld19-stack.service
```

### Change LD19 serial path behavior

Primary serial path comes from `/dev/ld19` symlink via udev rule in:
- `/etc/udev/rules.d/99-ld19.rules`

Fallback search (`ttyUSB0..2`) is in:
- `/usr/local/bin/start_ld19.sh`

After editing udev rules:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### Change ROS networking values for services

Edit unit files and update:

```bash
sudo nano /etc/systemd/system/ld19.service
sudo nano /etc/systemd/system/ld19-stack.service
# Adjust Environment=ROS_DOMAIN_ID and ROS_LOCALHOST_ONLY as needed
sudo systemctl daemon-reload
sudo systemctl restart ld19.service ld19-stack.service
```

---

## 8) Troubleshooting

### A) /dev/ld19 does not appear

```bash
lsusb
dmesg | tail -n 80
ls -l /dev/ttyUSB*
sudo udevadm info -a -n /dev/ttyUSB0 | head -n 60
```

Actions:
- Confirm adapter vendor/product IDs match `99-ld19.rules` (default CP210x 10c4:ea60).
- If IDs differ, update rule and reload udev.
- Verify cable/power and that LD19 is physically spinning.

### B) ld19.service repeatedly restarts

```bash
systemctl status ld19.service
journalctl -u ld19.service -n 200 --no-pager
```

Actions:
- Verify `/usr/local/bin/start_ld19.sh` exists and is executable.
- Verify ROS setup paths in script are correct.
- Manually run script once to view immediate errors:

```bash
source /opt/ros/jazzy/setup.bash
source ~/cm5_ws/install/setup.bash
/usr/local/bin/start_ld19.sh
```

### C) /scan missing but serial data exists

```bash
source /opt/ros/jazzy/setup.bash
source ~/cm5_ws/install/setup.bash

ros2 run ldlidar_stl_ros2 ldlidar_stl_ros2_node --ros-args \
  -p product_name:=LDLiDAR_LD19 \
  -p topic_name:=scan \
  -p port_name:=/dev/ld19 \
  -p port_baudrate:=230400 \
  -p frame_id:=base_laser \
  -p laser_scan_dir:=false
```

If manual run works but service does not:
- Compare environment/path differences between interactive shell and systemd service.
- Confirm `User=` in service has access to workspace files.

### D) /scan present on CM5 but not visible on SER8

Actions:
- Check `ROS_DOMAIN_ID` on both machines.
- Ensure `ROS_LOCALHOST_ONLY=0` for cross-machine discovery.
- Verify L2/L3 network reachability (ping each side).
- Restart DDS participants by restarting nodes/services after network changes.

### E) /ld19/summary or /health/ld19 missing

Actions:
- Check `ld19-stack.service` status/logs.
- Verify `ld19_utils` built in `~/cm5_ws`.
- Confirm entry points resolve:

```bash
source /opt/ros/jazzy/setup.bash
source ~/cm5_ws/install/setup.bash
ros2 run ld19_utils ld19_preprocess_node
ros2 run ld19_utils ld19_monitor_node
```

---

## 9) Manual recovery sequence (CM5)

Use this after a failed boot or after large config changes.

```bash
# 1) Source ROS + workspace
source /opt/ros/jazzy/setup.bash
source ~/cm5_ws/install/setup.bash

# 2) Restart services in order
sudo systemctl daemon-reload
sudo systemctl restart ld19.service
sleep 2
sudo systemctl restart ld19-stack.service

# 3) Validate topics
ros2 topic list | grep -E "^/scan$|^/ld19/summary$|^/health/ld19$"
ros2 topic hz /scan
```

---

## 10) Uninstall / cleanup

```bash
sudo systemctl stop ld19-stack.service ld19.service
sudo systemctl disable ld19-stack.service ld19.service

sudo rm -f /etc/systemd/system/ld19-stack.service
sudo rm -f /etc/systemd/system/ld19.service
sudo rm -f /usr/local/bin/start_ld19_stack.sh
sudo rm -f /usr/local/bin/start_ld19.sh
sudo rm -f /etc/udev/rules.d/99-ld19.rules

sudo systemctl daemon-reload
sudo udevadm control --reload-rules
sudo udevadm trigger
```
