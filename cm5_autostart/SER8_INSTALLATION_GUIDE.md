# SER8 Service Installation Guide

This guide covers installing the CM5 watchdog service and Tour Robot startup script on the SER8.

## Files Created

1. `cm5-watchdog.service` - Systemd service for monitoring CM5
2. `cm5-watchdog.timer` - Timer to run watchdog every 60 seconds
3. `start-tour-robot.sh` - Wrapper script to start the robot system

## Installation Steps on SER8

### Step 1: Create directories and copy scripts

```bash
# Create tour_robot bin directory
sudo mkdir -p /usr/local/bin/tour_robot

# Copy Python scripts from your workspace
sudo cp ~/ros2_ws/src/main_control/main_control/cm5_service_watchdog.py /usr/local/bin/tour_robot/
sudo cp ~/ros2_ws/src/main_control/main_control/ser8_startup.py /usr/local/bin/tour_robot/

# Make scripts executable
sudo chmod +x /usr/local/bin/tour_robot/cm5_service_watchdog.py
sudo chmod +x /usr/local/bin/tour_robot/ser8_startup.py
```

### Step 2: Install systemd service files

```bash
# Copy service and timer files
sudo cp cm5-watchdog.service /etc/systemd/system/
sudo cp cm5-watchdog.timer /etc/systemd/system/

# Set correct permissions
sudo chmod 644 /etc/systemd/system/cm5-watchdog.service
sudo chmod 644 /etc/systemd/system/cm5-watchdog.timer
```

### Step 3: Install startup wrapper

```bash
# Copy wrapper script
sudo cp start-tour-robot.sh /usr/local/bin/start-tour-robot

# Make executable
sudo chmod +x /usr/local/bin/start-tour-robot
```

### Step 4: Enable and start the watchdog service

```bash
# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable cm5-watchdog.service

# Start the service now
sudo systemctl start cm5-watchdog.service

# Check status
sudo systemctl status cm5-watchdog.service
```

### Step 5: (Optional) Enable timer for automatic monitoring

```bash
# Enable timer (runs every 60 seconds)
sudo systemctl enable cm5-watchdog.timer
sudo systemctl start cm5-watchdog.timer

# Check timer status
sudo systemctl status cm5-watchdog.timer
sudo systemctl list-timers cm5-watchdog.timer
```

## Usage

### Starting the Tour Robot System

From any directory on SER8:

```bash
# Full startup with all checks and launch
start-tour-robot

# Check systems only (no launch)
start-tour-robot --no-launch

# Skip service restart attempts on CM5
start-tour-robot --no-restart
```

### Monitoring the Watchdog

```bash
# View live logs
journalctl -u cm5-watchdog.service -f

# View recent logs
journalctl -u cm5-watchdog.service -n 50

# Check service status
sudo systemctl status cm5-watchdog.service
```

### Manual Watchdog Execution

```bash
# Single check
/usr/local/bin/tour_robot/cm5_service_watchdog.py

# Continuous monitoring
/usr/local/bin/tour_robot/cm5_service_watchdog.py --loop 60
```

## Prerequisites

Before installation, ensure:

1. **Passwordless SSH from SER8 to CM5:**
   ```bash
   ssh-keygen -t ed25519
   ssh-copy-id -i ~/.ssh/id_ed25519.pub tourrobot@192.168.10.20
   ```

2. **CM5 sudoers configuration:**
   
   On CM5, edit `/etc/sudoers.d/tourrobot`:
   ```bash
   sudo visudo -f /etc/sudoers.d/tourrobot
   ```
   
   Add:
   ```
   tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19.service
   tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19-stack.service
   tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl status *
   tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl is-active *
   ```

3. **ROS 2 Workspace Built:**
   ```bash
   cd ~/ros2_ws
   source /opt/ros/jazzy/setup.bash
   colcon build --packages-select main_control
   source install/setup.bash
   ```

## Configuration

### Changing CM5 IP or Services

Edit the wrapper script:
```bash
sudo nano /usr/local/bin/start-tour-robot
```

Modify these lines:
```bash
  --cm5-host 192.168.10.20 \
  --cm5-user tourrobot \
  --services ld19.service ld19-stack.service \
```

### Changing Watchdog Interval

Edit the Python script:
```bash
sudo nano /usr/local/bin/tour_robot/cm5_service_watchdog.py
```

Or change the timer:
```bash
sudo nano /etc/systemd/system/cm5-watchdog.timer
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart cm5-watchdog.timer
```

## Troubleshooting

### Watchdog service fails to start

```bash
# Check detailed logs
journalctl -u cm5-watchdog.service -n 100 --no-pager

# Common issues:
# 1. SSH keys not set up - run ssh-copy-id
# 2. Python script not executable - run chmod +x
# 3. CM5 not reachable - check network
```

### Startup script can't find ROS

```bash
# Verify paths in wrapper script
cat /usr/local/bin/start-tour-robot

# Check if ROS is installed
ls /opt/ros/jazzy/setup.bash

# Check workspace
ls ~/ros2_ws/install/setup.bash
```

### Permission denied errors

```bash
# Ensure scripts are executable
sudo chmod +x /usr/local/bin/tour_robot/cm5_service_watchdog.py
sudo chmod +x /usr/local/bin/tour_robot/ser8_startup.py
sudo chmod +x /usr/local/bin/start-tour-robot
```

## Uninstallation

```bash
# Stop and disable services
sudo systemctl stop cm5-watchdog.service
sudo systemctl stop cm5-watchdog.timer
sudo systemctl disable cm5-watchdog.service
sudo systemctl disable cm5-watchdog.timer

# Remove service files
sudo rm /etc/systemd/system/cm5-watchdog.service
sudo rm /etc/systemd/system/cm5-watchdog.timer

# Remove scripts
sudo rm -rf /usr/local/bin/tour_robot
sudo rm /usr/local/bin/start-tour-robot

# Reload systemd
sudo systemctl daemon-reload
```

## File Locations Summary

| File | Location on SER8 |
|------|------------------|
| CM5 Watchdog Script | `/usr/local/bin/tour_robot/cm5_service_watchdog.py` |
| Startup Script | `/usr/local/bin/tour_robot/ser8_startup.py` |
| Startup Wrapper | `/usr/local/bin/start-tour-robot` |
| Watchdog Service | `/etc/systemd/system/cm5-watchdog.service` |
| Watchdog Timer | `/etc/systemd/system/cm5-watchdog.timer` |
