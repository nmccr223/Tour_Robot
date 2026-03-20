# SER8 Installation Guide (Fresh Ubuntu 24.04 LTS)

Use this guide when rebuilding a SER8 from scratch.

Goal:
1. Install required OS modules and ROS 2 Jazzy
2. Assemble and build the Tour Robot ROS workspace
3. Install startup/watchdog runtime files
4. Enable automatic monitoring on boot

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
python3 -c "import depthai as dai; d=dai.Device.getAllAvailableDevices(); print (dir(d[0]))"

#This command will give all available usb devices attached to the system that work with the depthai library

### 4d) Validate camera streams with RViz2 visualization

To ensure cameras are aimed and functioning correctly, we'll visualize the depth point clouds.

**Terminal 1: Launch depthai-ros driver with both cameras**

Create a test launcher that runs both cameras (front and rear) on their respective USB buses:

```bash
cat > /tmp/test_both_cameras.launch.py << 'EOF'
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        # Front OAK-D W
        Node(
            package='depthai_ros_driver',
            executable='rgbd_imaging_node',
            name='front_oak',
            namespace='front',
            parameters=[{
                'device_type': 'OAK-D-W',
                'camera_name': 'oak',
                'mode': 'depth',
                'tf_prefix': 'front_oak',
            }],
            output='screen',
        ),
        # Rear OAK-D Lite
        Node(
            package='depthai_ros_driver',
            executable='rgbd_imaging_node',
            name='rear_oak',
            namespace='rear',
            parameters=[{
                'device_type': 'OAK-D-Lite',
                'camera_name': 'oak',
                'mode': 'depth',
                'tf_prefix': 'rear_oak',
            }],
            output='screen',
        ),
    ])
EOF

# Source ROS and run
source /opt/ros/jazzy/setup.bash
ros2 launch /tmp/test_both_cameras.launch.py
```

**Terminal 2: Start RViz2 for point cloud visualization**

```bash
source /opt/ros/jazzy/setup.bash
rviz2
```

In RViz2:
1. **Set Fixed Frame** to `front_oak_rgb_frame` (or `rear_oak_rgb_frame` for the rear view)
2. **Add a PointCloud2 display:**
   - Click `Add` → `PointCloud2`
   - Set **Topic** to `/front/depth/color/points` (front) or `/rear/depth/color/points` (rear)
3. **Adjust the points visualization:**
   - Increase `Point Size` to 2–3 (for visibility)
   - Set `Style` to `Squares` or `Flat Squares`
4. **Look at the point cloud:**
   - The point cloud should show your environment's geometry
   - Check for proper depth from the camera forward direction
   - Verify left/right barrel distortion is minimal

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