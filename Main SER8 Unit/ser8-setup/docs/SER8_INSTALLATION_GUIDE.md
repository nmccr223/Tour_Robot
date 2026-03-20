# SER8 Installation Guide (Fresh Ubuntu 24.04 LTS)

Use this guide when rebuilding a SER8 from scratch.

Goal:
1. Install required OS modules and ROS 2 Jazzy
2. Assemble and build the Tour Robot ROS workspace
3. Install startup/watchdog runtime files
4. Enable automatic monitoring on boot

---

## 0) Repository update on SER8 (do this first)

Before running setup/troubleshooting commands, make sure the local SER8 clone is current.

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
# Secondary option to update save files from repository
git pull origin main 
git status # To see current update status and check if versions match
```

If files in your local clone were edited on-device, commit or stash before `git pull`.

Related recovery section:
- `TROUBLESHOOTING.md` -> [System does not auto-start (manual recovery)](TROUBLESHOOTING.md#8-system-does-not-auto-start-manual-recovery)

---

## 1) Prepare the machine

**Workspace:** `~` (home directory)
**Machine:** SER8

Log in as the operational user (recommended: `tourrobot`) and update Ubuntu:

```bash
sudo apt update
sudo apt upgrade -y
sudo reboot
```

After reboot, create a workspace folder and clone this repository.

Do not use angle brackets (`<...>`) in the command; Bash interprets them as redirection.

```bash
mkdir -p ~/workspace
cd ~/workspace

# Replace URL with your actual repo URL
git clone https://github.com/YOUR_ORG/Tour_Robot.git Tour_Robot
```

---

## 2) Install required modules + ROS 2 Jazzy

**Workspace:** `~/workspace/Tour_Robot/Main SER8 Unit/ser8-setup`
**Machine:** SER8

From the setup folder:

```bash
cd ~/workspace/Tour_Robot/Main\ SER8\ Unit/ser8-setup
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

**Workspace:** `~/ros2_ws` (create new, separate from Tour_Robot repo)
**Machine:** SER8

Create workspace and copy required packages from this repository:

```bash
mkdir -p ~/ros2_ws/src

cp -r ~/workspace/Tour_Robot/robot_msgs ~/ros2_ws/src/
cp -r ~/workspace/Tour_Robot/ld19_utils ~/ros2_ws/src/
cp -r ~/workspace/Tour_Robot/Main\ SER8\ Unit/Main\ Control ~/ros2_ws/src/main_control
cp -r ~/workspace/Tour_Robot/Main\ SER8\ Unit/Launcher ~/ros2_ws/src/Launcher
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

## 4) Install and validate OAK-D cameras

**Workspace:** `~` (home directory, any location on SER8)
**Machine:** SER8

The SER8 uses two OAK-D cameras:
- **Front:** OAK-D W (wide stereo, 127° FOV, for obstacle and person detection)
- **Rear:** OAK-D Lite (stereo, 90° FOV, for backup safety checks)

### 4a) Install DepthAI SDK and depthai-ros driver

Install DepthAI library and ROS 2 packages:

```bash
pip3 install depthai opencv-python
sudo apt install -y ros-jazzy-depthai-ros
```

Verify DepthAI is importable:

```bash
python3 -c "import depthai as dai; print(f'DepthAI version: {dai.__version__}')"
```

### 4b) Set up udev rules for camera USB access

Create a udev rule so the SER8 user can access USB cameras without `sudo`:

```bash
sudo tee /etc/udev/rules.d/99-oak-d.rules > /dev/null <<EOF
# OAK-D camera USB access rule
SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 4c) Connect cameras and detect hardware

Physically connect **both cameras via USB 3.1** to the SER8. OAK-D devices need USB 3 for full bandwidth.

Verify both cameras are detected:

```bash
lsusb | grep -Ei "luxonis|movidius|myriad|03e7"

python3 << 'EOF'
import depthai as dai
devices = dai.Device.getAllAvailableDevices()
print(f"Found {len(devices)} OAK-D device(s):")
for d in devices:
    print(f"  - {d.getMxId()} ({d.getName()})")
EOF
```

### 4d) Validate camera streams with RViz2 visualization

PointCloud2 is provided by the verified DepthAI launch included in system bringup:
- `ros2 launch depthai_ros_driver rgbd_pcl.launch.py`

In this repository, the validated PointCloud2 topic is:
- `/oak/points`

Start the system and verify the pointcloud topic before opening RViz2:

```bash
start-tour-robot --require-camera-topics
ros2 topic list | grep -E "^/oak/points$"
ros2 topic echo /oak/points --once
```

If bringup is not running, you can test DepthAI directly:

```bash
source /opt/ros/jazzy/setup.bash
ros2 launch depthai_ros_driver rgbd_pcl.launch.py
```

**Terminal 2: Start RViz2 for point cloud visualization**

```bash
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
rviz2 -d ~/workspace/Tour_Robot/Main\ SER8\ Unit/Launcher/oak_pointcloud.rviz
```

If the profile is unavailable, configure RViz2 manually:
1. Set **Fixed Frame** to `oak_rgb_camera_optical_frame`.
2. Add `PointCloud2` display.
3. Set **Topic** to `/oak/points`.
4. Set **Reliability Policy** to `Reliable`.
5. Set **Durability Policy** to `Transient Local`.
6. Set **Color Transformer** to `RGB8`.

Expected result:
- The point cloud should show environment geometry in front of the camera.
- Data should begin once a subscriber is connected (RViz2, processor nodes, or navigation).

### 4d.1) DepthAI launch arguments used by system bringup

`system_bringup.launch.py` includes `depthai_ros_driver/rgbd_pcl.launch.py` with explicit defaults from `--show-args`:

- `name:=oak`
- `camera_model:=OAK-D`
- `parent_frame:=oak-d-base-frame`
- `cam_pos_x:=0.0`
- `cam_pos_y:=0.0`
- `cam_pos_z:=0.0`
- `cam_roll:=0.0`
- `cam_pitch:=0.0`
- `cam_yaw:=0.0`
- `params_file:=/opt/ros/jazzy/share/depthai_ros_driver/config/rgdb.yaml`
- `use_rviz:=False`
- `rectify_rgb:=True`
- `rs_compat:=False`

These defaults are intentional for baseline operation. Calibrate and tune camera behavior in OAK Viewer as needed.

### 4e) Quick camera health check

Run this Python script to confirm both cameras stream successfully:

```bash
python3 << 'EOF'
import depthai as dai
import time

def test_camera(device_info, name):
    """Test streaming from a single camera."""
    print(f"\nTesting {name}...")
    with dai.Device(device_info) as device:
        # Create pipeline
        pipeline = dai.Pipeline()
        
        # Spatial detection node
        stereo = pipeline.createStereoDepth()
        
        # RGB + depth output
        cam_rgb = pipeline.createColorCamera()
        spatial_det_nn = pipeline.createYoloSpatialDetectionPostProcessor()
        
        spatial_det_nn.setBoundingBoxScaleFactor(0.5)
        spatial_det_nn.setDepthLowerThreshold(100)
        spatial_det_nn.setDepthUpperThreshold(5000)
        
        # Yolo specific parameters
        spatial_det_nn.setNumClasses(80)
        spatial_det_nn.setCoordinateSize(4)
        spatial_det_nn.setAnchors([10,14, 23,27, 37,58, 81,82, 135,169, 344,319])
        spatial_det_nn.setAnchorMasks({"side26": [1,2,3], "side13": [3,4,5]})
        spatial_det_nn.setIouThreshold(0.5)
        spatial_det_nn.setBlobPath("/path/to/model.blob")  # Optional: replace with your NN model
        
        # Stereo depth
        stereo.setDefaultProfilePreset(dai.node.StereoDepth.PresetMode.HIGH_DENSITY)
        stereo.setDepthAlign(dai.CameraBbProperties.ImageOrientation.RGB_CAPTURED)
        
        # Connect nodes
        cam_rgb.preview.link(spatial_det_nn.input)
        spatial_det_nn.passthrough.link(stereo.rectifyLeft)
        spatial_det_nn.spatialDetectionOut.link(spatial_det_nn.input)
        stereo.depth.link(spatial_det_nn.inputDepth)
        
        # Output
        xout_rgb = pipeline.createXLinkOut()
        xout_rgb.setStreamName("rgb")
        cam_rgb.preview.link(xout_rgb.input)
        
        device.startPipeline(pipeline)
        
        # Capture a frame
        q_rgb = device.getOutputQueue(name="rgb", maxSize=4, blocking=False)
        for _ in range(30):  # Try 30 frames
            in_rgb = q_rgb.get()
            if in_rgb:
                print(f"  ✓ {name} streaming OK (frame shape: {in_rgb.getData().shape})")
                return True
            time.sleep(0.1)
    
    print(f"  ✗ {name} failed to stream")
    return False

try:
    devices = dai.Device.getAllAvailableDevices()
    if len(devices) < 2:
        print(f"ERROR: Expected 2 cameras, found {len(devices)}")
        exit(1)
    
    for i, device_info in enumerate(devices):
        camera_name = "Front OAK-D W" if i == 0 else "Rear OAK-D Lite"
        test_camera(device_info, camera_name)
        time.sleep(0.5)
    
    print("\n✓ Both cameras OK!")
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
EOF
```

### 4f) Alignment verification checklist

After visualizing both cameras in RViz2:

- [ ] **Front camera:** Point cloud shows a clear view forward. No significant warping or blind spots.
- [ ] **Rear camera:** Point cloud shows clear view behind. Check for mounting bracket shadows.
- [ ] **Depth range:** Objects 0.5–2m ahead are well-captured (good point density).
- [ ] **No USB bandwidth issues:** Streams are smooth; no frame drops in terminal output.
- [ ] **Camera ports labeled:** Mark which USB port is front, which is rear (for future reference).

If a camera stream is missing or distorted:
1. Verify the USB cable is **USB 3.0 or 3.1** (not 2.0).
2. Try a different USB port on the SER8 (direct to chipset, not hub).
3. Check `dmesg` for USB enumeration errors.

---

## 5) Configure SER8 -> CM5 trust and CM5 sudo rules

**Workspace (SER8):** `~/workspace/Tour_Robot/Main SER8 Unit/ser8-setup`
**Workspace (CM5):** `/etc/sudoers.d/` (sudoers file editing)
**Machines:** SER8 (step 1) → CM5 (step 2)

Run on SER8:

```bash
cd ~/workspace/Tour_Robot/Main\ SER8\ Unit/ser8-setup
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

## 6) Install watchdog + startup runtime files

**Workspace:** `~/workspace/Tour_Robot/Main SER8 Unit/ser8-setup`
**Machine:** SER8

Run on SER8:

```bash
cd ~/workspace/Tour_Robot/Main\ SER8\ Unit/ser8-setup
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

## 7) Validate autostart behavior

**Workspace:** Any directory (commands operate on system services)
**Machine:** SER8

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

## 8) Common configuration edits

**Workspace:** System-wide edits (no specific directory)
**Machine:** SER8

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

## 9) Reinstall/rollback cleanup

**Workspace:** Any directory (system-wide cleanup operations)
**Machine:** SER8

```bash
sudo systemctl stop cm5-watchdog.service cm5-watchdog.timer
sudo systemctl disable cm5-watchdog.service cm5-watchdog.timer

sudo rm -f /etc/systemd/system/cm5-watchdog.service
sudo rm -f /etc/systemd/system/cm5-watchdog.timer
sudo rm -f /usr/local/bin/start-tour-robot
sudo rm -rf /usr/local/bin/tour_robot

sudo systemctl daemon-reload
```