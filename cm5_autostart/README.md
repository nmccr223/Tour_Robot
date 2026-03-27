LD19 LiDAR Auto-Start (CM5 / Ubuntu 24.04 + ROS 2 Jazzy)

Full setup and recovery guide:
- See `CM5_INSTALLATION_GUIDE.md` in this folder for end-to-end CM5 install, validation, and troubleshooting.

This folder contains the scripts and configuration to automatically start the LD19 LiDAR driver whenever the device is plugged (ttyUSB0/ttyUSB1), and at boot. It uses a udev rule to create a stable symlink /dev/ld19 and a systemd service to launch the ROS 2 driver with your working parameters.

Files
- 99-ld19.rules — udev rule creating /dev/ld19 and triggering the systemd service
- start_ld19.sh — start script sourcing ROS 2 + workspace and running the driver with known-good params
- ld19.service — systemd unit to run the start script at boot and on hotplug

Install Steps (run on CM5)
1. Copy files to system locations
   sudo cp cm5_autostart/99-ld19.rules /etc/udev/rules.d/
   sudo cp cm5_autostart/start_ld19.sh /usr/local/bin/
   sudo cp cm5_autostart/ld19.service /etc/systemd/system/

2. Make the start script executable
   sudo chmod +x /usr/local/bin/start_ld19.sh

3. Reload udev and systemd, enable service
   sudo udevadm control --reload-rules
   sudo udevadm trigger
   sudo systemctl daemon-reload
   sudo systemctl enable ld19.service
   sudo systemctl start ld19.service

4. Test hotplug
- Unplug/replug the LD19
- Verify /dev/ld19 exists: ls -l /dev/ld19
- Check service logs: journalctl -u ld19.service -f
- Verify topics: ros2 topic list | grep -E "^/scan$|scan$" and ros2 topic hz /scan

Requirements
- ROS 2 Jazzy installed (/opt/ros/jazzy)
- Your workspace built and sourceable (e.g., /home/tourrobotsub/cm5_ws)
- User tourrobotsub in dialout group for serial

Path note
- CM5 ROS workspace naming does not need to match SER8 naming.
- Only ensure the path sourced in start_ld19.sh/start_ld19_stack.sh matches the actual CM5 ROS workspace used to build LD19.

Notes
- Vendor/Product IDs in 99-ld19.rules are set to CP210x (10c4:ea60). Adjust if your device uses different IDs.
- The driver parameters match your working manual command.
- The script falls back to /dev/ttyUSB0 and /dev/ttyUSB1 if the symlink is missing.
- To auto-start preprocess/monitor as well, you can wrap them in another script or build a combined launch and update ExecStart in ld19.service.
