# SER8 Installation Guide (Fresh Ubuntu 24.04 LTS)

Use this guide when rebuilding a SER8 from scratch.

Goal:
1. Install required OS modules and ROS 2 Jazzy
2. Assemble and build the Tour Robot ROS workspace
3. Install startup/watchdog runtime files
4. Enable automatic monitoring on boot

---

## 1) Prepare the machine

Log in as the operational user (recommended: `tourrobot`) and update Ubuntu:

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

After reboot, clone this repository (if not already present):

```bash
cd ~
git clone <YOUR_TOUR_ROBOT_REPO_URL> Tour_Robot
```

---

## 2) Install required modules + ROS 2 Jazzy

From the setup folder:

```bash
cd ~/Tour_Robot/Main\ SER8\ Unit/ser8-setup
bash scripts/install-dependencies.sh
```

Ensure ROS setup is sourced for future shells:

```bash
grep -q "source /opt/ros/jazzy/setup.bash" ~/.bashrc || \
   echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## 3) Build the SER8 ROS 2 workspace

Create workspace and copy required packages from this repository:

```bash
mkdir -p ~/ros2_ws/src

cp -r ~/Tour_Robot/robot_msgs ~/ros2_ws/src/
cp -r ~/Tour_Robot/ld19_utils ~/ros2_ws/src/
cp -r ~/Tour_Robot/Main\ SER8\ Unit/Main\ Control ~/ros2_ws/src/main_control
cp -r ~/Tour_Robot/Main\ SER8\ Unit/Launcher ~/ros2_ws/src/Launcher
```

Install package dependencies and build:

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install --packages-select robot_msgs ld19_utils main_control
```

Source workspace overlay now and on every new shell:

```bash
source ~/ros2_ws/install/setup.bash
grep -q "source ~/ros2_ws/install/setup.bash" ~/.bashrc || \
   echo "source ~/ros2_ws/install/setup.bash" >> ~/.bashrc
```

---

## 4) Configure SER8 -> CM5 trust and CM5 sudo rules

Run on SER8:

```bash
cd ~/Tour_Robot/Main\ SER8\ Unit/ser8-setup
bash scripts/setup-ssh-keys.sh
```

On CM5, create/update sudoers rules for the SSH user:

```bash
sudo visudo -f /etc/sudoers.d/tourrobot
```

Add:

```text
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19.service
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19-stack.service
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl status *
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl is-active *
```

---

## 5) Install watchdog + startup runtime files

Run on SER8:

```bash
cd ~/Tour_Robot/Main\ SER8\ Unit/ser8-setup
bash scripts/install-watchdog.sh
bash scripts/install-startup-wrapper.sh
```

This installs:
- `/usr/local/bin/tour_robot/cm5_service_watchdog.py`
- `/usr/local/bin/tour_robot/ser8_startup.py`
- `/usr/local/bin/start-tour-robot`
- `/etc/systemd/system/cm5-watchdog.service`
- `/etc/systemd/system/cm5-watchdog.timer`

---

## 6) Validate autostart behavior

Check watchdog units:

```bash
systemctl status cm5-watchdog.service
systemctl status cm5-watchdog.timer
systemctl list-timers cm5-watchdog.timer
```

Follow logs:

```bash
journalctl -u cm5-watchdog.service -f
```

Verify operator startup command:

```bash
start-tour-robot --no-launch
start-tour-robot
```

---

## 7) Common configuration edits

### Change CM5 host/user or motor endpoint

Edit wrapper settings:

```bash
sudo nano /usr/local/bin/start-tour-robot
```

Update values for:
- `CM5_HOST`
- `CM5_USER`
- `MOTOR_HOST`
- `MOTOR_PORT`

### Change watchdog interval

Edit timer:

```bash
sudo nano /etc/systemd/system/cm5-watchdog.timer
sudo systemctl daemon-reload
sudo systemctl restart cm5-watchdog.timer
```

---

## 8) Reinstall/rollback cleanup

```bash
sudo systemctl stop cm5-watchdog.service cm5-watchdog.timer
sudo systemctl disable cm5-watchdog.service cm5-watchdog.timer

sudo rm -f /etc/systemd/system/cm5-watchdog.service
sudo rm -f /etc/systemd/system/cm5-watchdog.timer
sudo rm -f /usr/local/bin/start-tour-robot
sudo rm -rf /usr/local/bin/tour_robot

sudo systemctl daemon-reload
```