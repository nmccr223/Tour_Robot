# VM Setup Guide - SER8 Standin for Testing

## Overview

This guide helps you set up an Ubuntu 24.04 LTS VM as a standin for the SER8 main control computer to test the navigation POC system.

## Prerequisites

- Ubuntu 24.04 LTS VM (VirtualBox, VMware, or Hyper-V)
- 4GB+ RAM allocated to VM
- 20GB+ disk space
- Network connectivity (for installing packages)

## Quick Setup Steps

### 1. Install ROS 2 Jazzy

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install ROS 2 Jazzy
sudo apt install software-properties-common -y
sudo add-apt-repository universe
sudo apt update

# Add ROS 2 repository
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install ros-jazzy-desktop python3-colcon-common-extensions -y

# Install additional dependencies
sudo apt install python3-pip python3-serial -y
pip3 install pyserial
```

### 2. Set Up ROS 2 Workspace

```bash
# Source ROS 2
source /opt/ros/jazzy/setup.bash

# Create workspace
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src

# Clone Tour Robot repository (or transfer files manually)
# Option A: Git clone
git clone https://github.com/nmccr223/Tour_Robot.git

# Option B: Manual transfer (see Transfer Methods below)
```

### 3. Create Package Structure

```bash
cd ~/ros2_ws/src

# Create main_control package directories
mkdir -p main_control/main_control
mkdir -p main_control/resource
mkdir -p main_control/launch

# Copy files from Tour_Robot repo
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/package.xml main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/setup.py main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/setup.cfg main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/resource/main_control main_control/resource/

# Copy Python modules
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/main_control/__init__.py main_control/main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/ser8_navigation_poc.py main_control/main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/motor_controller_stub.py main_control/main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/shutdown_manager_node.py main_control/main_control/
cp Tour_Robot/Main\ SER8\ Unit/Main\ Control/test_scan_publisher.py main_control/main_control/

# Copy launch files
cp Tour_Robot/Main\ SER8\ Unit/Launcher/navigation_poc.launch.py main_control/launch/
```

### 4. Build the Package

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --packages-select main_control

# Source the workspace
source ~/ros2_ws/install/setup.bash

# Add to bashrc for convenience
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
echo "source ~/ros2_ws/install/setup.bash" >> ~/.bashrc
```

## Transfer Methods

### Method 1: Git Clone (Recommended)

```bash
cd ~/ros2_ws/src
git clone https://github.com/nmccr223/Tour_Robot.git
# Then copy files as shown in Step 3
```

### Method 2: Shared Folder (VirtualBox/VMware)

**VirtualBox:**
1. Install Guest Additions in VM
2. VM Settings → Shared Folders → Add folder
3. Share: `C:\Users\no-98\Documents\GitHub\Tour_Robot`
4. Mount point: `/media/sf_Tour_Robot`
5. Auto-mount: Yes

```bash
# Access shared folder
cd /media/sf_Tour_Robot
# Copy files as needed
```

**VMware:**
1. VM Settings → Options → Shared Folders → Enable
2. Add: `C:\Users\no-98\Documents\GitHub\Tour_Robot`

```bash
# Access at
cd /mnt/hgfs/Tour_Robot
```

### Method 3: SCP from Windows (PowerShell)

```powershell
# From Windows PowerShell
scp -r "C:\Users\no-98\Documents\GitHub\Tour_Robot\Main SER8 Unit\Main Control\*.py" user@vm-ip:~/transfer/
```

### Method 4: USB or Network Share

Copy files to USB drive or network location, then access from VM.

## Testing the Setup

### Test 1: Verify Package Built

```bash
source ~/ros2_ws/install/setup.bash

# Check executable is available
ros2 pkg executables main_control
# Should show:
#   main_control navigation_poc
#   main_control shutdown_manager_node
#   main_control test_scan_publisher
```

### Test 2: Run Fake LiDAR

```bash
# Terminal 1: Start fake scan publisher
source ~/ros2_ws/install/setup.bash
ros2 run main_control test_scan_publisher

# Terminal 2: Verify /scan topic
source ~/ros2_ws/install/setup.bash
ros2 topic list | grep scan
ros2 topic hz /scan
ros2 topic echo /scan --no-arr
```

### Test 3: Run Navigation POC

```bash
# Terminal 1: Fake LiDAR (keep running)
ros2 run main_control test_scan_publisher

# Terminal 2: Navigation POC (motors disabled)
source ~/ros2_ws/install/setup.bash
ros2 launch main_control navigation_poc.launch.py enable_motors:=false

# Terminal 3: Monitor status
ros2 topic echo /robot_status

# Terminal 4: Monitor obstacles
ros2 topic echo /obstacle_detection
```

## Expected Results

When everything is working:

1. **Fake LiDAR** publishes at ~10 Hz to `/scan`
2. **Navigation POC** shows:
   ```
   [INFO] [navigation_poc]: Navigation POC node initialized
   [INFO] [navigation_poc]: Max speeds: linear=0.5 m/s, angular=1.0 rad/s
   [INFO] [navigation_poc]: Motors: DISABLED (simulation mode)
   ```
3. **Robot Status** shows:
   ```json
   {
     "state": "AVOIDING",
     "scan_rate": 10.0,
     "motors_enabled": false
   }
   ```
4. **Obstacle Detection** shows front and left obstacles detected

## Directory Structure on VM

```
~/ros2_ws/
├── build/
├── install/
├── log/
└── src/
    └── main_control/
        ├── package.xml
        ├── setup.py
        ├── setup.cfg
        ├── resource/
        │   └── main_control
        ├── main_control/
        │   ├── __init__.py
        │   ├── ser8_navigation_poc.py
        │   ├── motor_controller_stub.py
        │   ├── shutdown_manager_node.py
        │   └── test_scan_publisher.py
        └── launch/
            └── navigation_poc.launch.py
```

## Troubleshooting

### Package not found after build

```bash
# Rebuild with verbose output
cd ~/ros2_ws
colcon build --packages-select main_control --symlink-install

# Check if package installed
ls ~/ros2_ws/install/main_control/

# Source workspace
source ~/ros2_ws/install/setup.bash
```

### Import errors for motor_controller_stub

```bash
# Verify __init__.py exists
ls ~/ros2_ws/src/main_control/main_control/__init__.py

# Check Python path
echo $PYTHONPATH

# Try importing manually
python3 -c "from main_control import ser8_navigation_poc"
```

### /scan topic not publishing

```bash
# Check if test publisher is running
ros2 node list | grep fake_scan

# Check topic
ros2 topic info /scan

# Verify data
ros2 topic echo /scan --once
```

### Colcon build fails

```bash
# Install missing dependencies
sudo apt install python3-colcon-common-extensions python3-rosdep

# Initialize rosdep (first time only)
sudo rosdep init
rosdep update

# Install package dependencies
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
```

## Next Steps After Setup

1. ✅ Verify fake LiDAR publishes to `/scan`
2. ✅ Confirm navigation POC subscribes and processes data
3. ✅ Monitor obstacle detection zones
4. ✅ Observe velocity commands on `/cmd_vel`
5. ⏳ Test with different obstacle configurations
6. ⏳ When motor protocol available: Update `motor_controller_stub.py`
7. ⏳ Test with motors enabled (in clear space)

## Files You Need from Repo

### Core Files (Required):
- `Main SER8 Unit/Main Control/package.xml` ✓ Created
- `Main SER8 Unit/Main Control/setup.py` ✓ Created
- `Main SER8 Unit/Main Control/setup.cfg` ✓ Created
- `Main SER8 Unit/Main Control/resource/main_control` ✓ Created
- `Main SER8 Unit/Main Control/main_control/__init__.py` ✓ Created
- `Main SER8 Unit/Main Control/ser8_navigation_poc.py` ✓ Exists
- `Main SER8 Unit/Main Control/motor_controller_stub.py` ✓ Exists
- `Main SER8 Unit/Main Control/shutdown_manager_node.py` ✓ Exists
- `Main SER8 Unit/Launcher/navigation_poc.launch.py` ✓ Exists

### Test Files (Optional but recommended):
- `Main SER8 Unit/Main Control/test_scan_publisher.py` ✓ Created

### Documentation (Reference):
- `Main SER8 Unit/README_POC.md` ✓ Exists
- `SHUTDOWN_SYSTEM.md` ✓ Exists

### NOT Needed for This Test:
- Camera control files (ignore)
- HMI GUI files (not running on VM)
- Luxonis Camera folder (skip)

## Quick Commands Reference

```bash
# Build workspace
cd ~/ros2_ws && colcon build --packages-select main_control && source install/setup.bash

# Run fake LiDAR
ros2 run main_control test_scan_publisher

# Run navigation POC
ros2 launch main_control navigation_poc.launch.py

# Monitor topics
ros2 topic echo /robot_status
ros2 topic echo /obstacle_detection
ros2 topic echo /cmd_vel

# Check nodes
ros2 node list

# Check topics
ros2 topic list
```

## Support

- **README_POC.md** - Complete POC documentation
- **SHUTDOWN_SYSTEM.md** - Shutdown system documentation
- GitHub Issues: Report problems on the Tour_Robot repository

---

**Status:** Ready for VM deployment and testing
**Last Updated:** December 5, 2025
