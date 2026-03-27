# CM5 Installation Guide (Fresh Ubuntu 24.04 LTS)

Use this guide when rebuilding a Compute Module 5 from scratch.

Goal:
1. Install required OS modules and ROS 2 Jazzy on CM5
2. Assemble and build the CM5 ROS workspace for LD19
3. Install udev + systemd auto-start for LD19 driver and stack
4. Validate CM5 -> SER8 topic visibility and add troubleshooting steps

System integration note:
- CM5 driver publishes raw LD19 data on /scan_raw; preprocess publishes filtered data on /scan.
- SER8 performs fusion and motion decisions using separate front/rear OAK streams
  plus CM5 LD19 as a secondary forward-facing safety input.

Path naming policy (important):
- CM5 and SER8 do not need matching workspace names.
- This repository clone path and the ROS workspace path are independent on CM5:
  - REPO_ROOT: where Tour_Robot is cloned (examples: ~/workspace/Tour_Robot or ~/Tour_Robot)
  - ROS_WS: CM5 ROS workspace used to build/run LD19 stack (recommended: ~/cm5_ws)
- The only strict requirement is consistency: build and startup scripts must point to the same ROS_WS path.

---

## 0) Repository update on CM5 (do this first)

Before running setup/troubleshooting commands, make sure the local CM5 clone is current.

```bash
# Use whichever path exists on this CM5
if [ -d ~/workspace/Tour_Robot ]; then
   cd ~/workspace/Tour_Robot
elif [ -d ~/Tour_Robot ]; then
   cd ~/cm5_ws 
   #Compute Module 5's workspace was originally built with the name cm5_ws and used USB thumb drives to transfer files. The primary workspace of the project is still in this format within the CM5. /workspace/Tour_Robot does exist however and is used as the repository save location. This was done due to permissions issues when originally trying to update the /cm5_ws and has been left like this to avoid rebuilding the workspace from scratch. All ROS2 Jazzy related files are saved to /cm5_ws and should be sourced from here.
else
   echo "Tour_Robot repository not found in ~/workspace or ~/"
fi

# Ensure you are in /cm5_ws/src when doing this using command cd ~/cm5_ws/src/
git status -sb
git pull --ff-only
# Secondary option to update save files from repository
git pull origin main
git status
```

If files in your local clone were edited on-device, commit or stash before git pull.

Optional: set shell variables so all commands below work with your chosen paths:

```bash
export REPO_ROOT=~/workspace/Tour_Robot
export ROS_WS=~/cm5_ws
```

If you use different names/locations, set them here once and substitute in commands.

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
mkdir -p "$ROS_WS/src"

cp -r "$REPO_ROOT/robot_msgs" "$ROS_WS/src/"
cp -r "$REPO_ROOT/ld19_utils" "$ROS_WS/src/"
```

Install external LD19 driver package (required by launch file):

```bash
cd "$ROS_WS/src"
# Package expected by launch: ldlidar_stl_ros2
# Replace URL/tag if your team uses a specific fork.
git clone https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2.git
```

Install dependencies and build:

```bash
cd "$ROS_WS"
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select robot_msgs ld19_utils ldlidar_stl_ros2
```

Source workspace overlay now and on every shell:

```bash
source "$ROS_WS/install/setup.bash"
grep -q "source $ROS_WS/install/setup.bash" ~/.bashrc || \
  echo "source $ROS_WS/install/setup.bash" >> ~/.bashrc
```

### 3a) If you change CM5 ROS workspace name/path

Use this if you want a custom ROS workspace path (for example `~/cm5_ros` instead of `~/cm5_ws`).

1) Set your target path and build there:

```bash
export ROS_WS=~/cm5_ros
mkdir -p "$ROS_WS/src"
cp -r "$REPO_ROOT/robot_msgs" "$ROS_WS/src/"
cp -r "$REPO_ROOT/ld19_utils" "$ROS_WS/src/"
cd "$ROS_WS/src"
git clone https://github.com/ldrobotSensorTeam/ldlidar_stl_ros2.git
cd "$ROS_WS"
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select robot_msgs ld19_utils ldlidar_stl_ros2
```

2) Ensure CM5 startup scripts source the same ROS workspace:

```bash
sudo nano /usr/local/bin/start_ld19.sh
sudo nano /usr/local/bin/start_ld19_stack.sh
```

Update the workspace source line in both scripts to your ROS_WS path, for example:

```bash
source /home/tourrobotsub/cm5_ros/install/setup.bash
```

3) Restart services after path change:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ld19.service
sudo systemctl restart ld19-stack.service
```

---

## 4) Install LD19 auto-start runtime files

**Workspace:** $REPO_ROOT/cm5_autostart
**Machine:** CM5

Install udev rule, startup scripts, and services:

```bash
cd "$REPO_ROOT/cm5_autostart"

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
- `ld19.service` is the only service that launches the LD19 driver publisher for `/scan_raw`.
- `ld19-stack.service` requires `ld19.service` and launches preprocess + monitor only.
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
- `/scan_raw` exists and updates continuously from the driver.
- `/scan` exists and updates continuously from preprocess (rear blocked sector masked).
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

### 6a) New LD19 blocked-sector preprocessing defaults

The preprocess node now masks rear-facing scans before publishing `/scan`.

Defaults in `ld19_autorun.launch.py`:
- `raw_scan_topic:=/scan_raw`
- `filtered_scan_topic:=/scan`
- `blocked_center_deg:=180.0`
- `blocked_half_width_deg:=90.0` (rear 180 degrees blocked)
- `blocked_extra_margin_deg:=0.0`
- `min_valid_range_m:=0.0`

You can tune these at launch time if required:

```bash
ros2 launch ld19_utils ld19_autorun.launch.py \
  blocked_center_deg:=180.0 \
  blocked_half_width_deg:=90.0 \
  blocked_extra_margin_deg:=5.0 \
  min_valid_range_m:=0.0
```

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
# USB devices are setup to automatically be detected by the system by default. CM5 IO hub being used only has USB0 and USB1.

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
- Confirm that admin level permissions have also been set.

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

### F) `/scan` has two publishers or unstable Hz (duplicate driver)

Run:

```bash
ros2 topic info /scan -v
systemctl status ld19.service
systemctl status ld19-stack.service
ps -ef | grep -Ei "ldlidar_stl_ros2|ldlidar_publisher|ld19" | grep -v grep
```

Expected steady state:
- One `/scan` publisher process from `ld19.service`.
- `ld19-stack.service` running preprocess + monitor only.

If two LD19 driver processes are present:
- Stop manual launch terminals first.
- Restart services cleanly:

```bash
sudo systemctl restart ld19.service
sudo systemctl restart ld19-stack.service
ros2 topic info /scan -v
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
