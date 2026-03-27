LD19 LiDAR Auto-Start (CM5 / Ubuntu 24.04 + ROS 2 Jazzy)

Full setup and recovery guide:
- See `CM5_INSTALLATION_GUIDE.md` in this folder for end-to-end CM5 install, validation, and troubleshooting.

This folder contains the scripts and configuration to automatically start the LD19 LiDAR driver whenever the device is plugged (ttyUSB0/ttyUSB1), and at boot. It uses a udev rule to create a stable symlink /dev/ld19 and a two-stage systemd service architecture:
1. `ld19.service` — runs the driver, which publishes raw scan data to `/scan_raw`
2. `ld19-stack.service` — runs preprocessing (rear-sector masking filter) + monitoring, which publishes filtered `/scan` and summary metrics

Files
- 99-ld19.rules — udev rule creating /dev/ld19 and triggering the systemd service
- start_ld19.sh — start script sourcing ROS 2 + workspace and running the driver with known-good params (publishes `/scan_raw`)
- start_ld19_stack.sh — start script for preprocessing and monitoring nodes (publishes filtered `/scan`)
- ld19.service — systemd unit to run the driver at boot and on hotplug
- ld19-stack.service — systemd unit to run preprocessing + monitoring (depends on ld19.service)

Install Steps (run on CM5)
1. Copy files to system locations
   sudo cp cm5_autostart/99-ld19.rules /etc/udev/rules.d/
   sudo cp cm5_autostart/start_ld19.sh /usr/local/bin/
   sudo cp cm5_autostart/start_ld19_stack.sh /usr/local/bin/
   sudo cp cm5_autostart/ld19.service /etc/systemd/system/
   sudo cp cm5_autostart/ld19-stack.service /etc/systemd/system/

2. Make the start scripts executable
   sudo chmod +x /usr/local/bin/start_ld19.sh
   sudo chmod +x /usr/local/bin/start_ld19_stack.sh

3. Reload udev and systemd, enable services
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   sudo systemctl daemon-reload
   sudo systemctl enable ld19.service
   sudo systemctl enable ld19-stack.service
   sudo systemctl start ld19.service
   sudo systemctl start ld19-stack.service

4. Test hotplug
- Unplug/replug the LD19
- Verify /dev/ld19 exists: ls -l /dev/ld19
- Check service logs: journalctl -u ld19.service -f and journalctl -u ld19-stack.service -f
- Verify topics: ros2 topic list | grep -E "^/scan_raw$|^/scan$|^/ld19/summary$" and ros2 topic hz /scan_raw and ros2 topic hz /scan

Requirements
- ROS 2 Jazzy installed (/opt/ros/jazzy)
- Your workspace built and sourceable (e.g., /home/tourrobotsub/cm5_ws)
- User tourrobotsub in dialout group for serial

Path note
- CM5 ROS workspace naming does not need to match SER8 naming.
- Only ensure the path sourced in start_ld19.sh/start_ld19_stack.sh matches the actual CM5 ROS workspace used to build LD19.

Topic Architecture
- **Raw Data Pipeline:** LD19 driver → `/scan_raw` (raw, unfiltered LiDAR data)
- **Filtered Data Pipeline:** Preprocess node subscribes `/scan_raw` → applies rear-sector masking → publishes `/scan` (filtered, ready for motion control)
- **Summary Metrics:** Monitor node publishes `/ld19/summary` (scan statistics and health status) and `/health/ld19` (health flag)
- **SER8 Integration:** SER8 subscribes to `/scan` on CM5 (filtered data) with matching `ROS_DOMAIN_ID`

Notes
- Vendor/Product IDs in 99-ld19.rules are set to CP210x (10c4:ea60). Adjust if your device uses different IDs.
- The driver parameters match your working manual command.
- The script falls back to /dev/ttyUSB0 and /dev/ttyUSB1 if the symlink is missing.
- Both ld19.service and ld19-stack.service must be enabled for full operation (driver + filtering).
