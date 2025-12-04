# Shutdown System - Quick Start Guide

## 5-Minute Setup

### Before You Start
- Both SER8 and CM5 are running ROS 2 Jazzy
- Network connectivity exists between both units
- You have SSH access to both machines
- `std_srvs` package is available in your ROS 2 installation

### Installation (Both Units)

1. **Copy shutdown nodes to your workspace**
   ```bash
   # On SER8
   cp shutdown_manager_node.py ~/ros2_ws/src/main_control/main_control/
   
   # On CM5  
   cp cm5_shutdown_handler_node.py ~/ros2_ws/src/ld19_utils/ld19_utils/
   ```

2. **Update setup.py on both units**

   **SER8** (`main_control/setup.py`):
   ```python
   entry_points={
       'console_scripts': [
           'shutdown_manager_node = main_control.shutdown_manager_node:main',
       ],
   },
   ```

   **CM5** (`ld19_utils/setup.py`):
   ```python
   entry_points={
       'console_scripts': [
           'cm5_shutdown_handler = ld19_utils.cm5_shutdown_handler_node:main',
       ],
   },
   ```

3. **Build both packages**
   ```bash
   # On SER8
   cd ~/ros2_ws
   colcon build --packages-select main_control
   source install/setup.bash
   
   # On CM5
   cd ~/ros2_ws
   colcon build --packages-select ld19_utils
   source install/setup.bash
   ```

## Testing (Basic)

### Terminal Test (Don't actually shutdown!)

1. **Start SER8 shutdown manager in Terminal 1:**
   ```bash
   source ~/ros2_ws/install/setup.bash
   ros2 run main_control shutdown_manager_node
   ```

2. **Start CM5 shutdown handler in Terminal 2 (on CM5):**
   ```bash
   source ~/ros2_ws/install/setup.bash
   ros2 run ld19_utils cm5_shutdown_handler
   ```

3. **In a 3rd terminal, trigger the service:**
   ```bash
   ros2 service call /ser8/shutdown_system std_srvs/srv/Empty
   ```

4. **Observe:**
   - Terminal 1 shows: "Shutdown request received"
   - Terminal 2 shows: "Shutdown request received"
   - Both nodes print shutdown sequences
   - Machines begin to shutdown (be ready with Ctrl+C to stop!)

### Pre-Shutdown Check (SAFE!)

Before actually shutting down, test that everything is ready:

```bash
# Check service exists
ros2 service list | grep shutdown_system

# Check if nodes can be launched (without actually shutting down)
# Terminal 1:
ros2 run main_control shutdown_manager_node

# Terminal 2:
ros2 run ld19_utils cm5_shutdown_handler

# Terminal 3: Just check service is there
ros2 service list | grep shutdown_system
```

If this works, you're ready for HMI integration!

## HMI Integration Test

### Setup
1. HMI GUI is running with the modified `hmi_main.py`
2. Both shutdown nodes are running (or in launch file)
3. Network is healthy between all units

### Test Steps

1. **Click Admin button** in HMI main window
2. **Find "Shutdown System" button** (red button in toolbar)
3. **Click "Shutdown System"** button
4. **Confirmation dialog appears:**
   - Text: "Are you sure you want to shutdown the entire robot system?"
   - Options: Yes / No
5. **Click "No"** first (safe test):
   - Dialog closes
   - Nothing happens
   - Robot continues running
6. **Click "Shutdown System" again**
7. **Click "Yes" to actually shutdown:**
   - Status message: "Shutdown Initiated"
   - Admin window closes
   - System begins shutdown sequence

## Expected Behavior Timeline

```
T+0s   : User clicks "Shutdown System" in HMI
T+0.5s : Confirmation dialog appears
T+1s   : User clicks "Yes"
T+1.1s : Status message shows
T+1.5s : SER8 publishes to /cm5/shutdown_request
T+1.6s : CM5 receives request, publishes acknowledgment
T+1.7s : SER8 receives acknowledgment
T+1.8s : CM5 starts terminating ROS 2 processes
T+2s   : CM5 executes: sudo shutdown -h now
T+2.5s : SER8 executes: sudo shutdown -h now
T+5s   : Both units have powered down
```

## Troubleshooting During Testing

### Service call fails: "Service not available"
```bash
# Check node is running
ros2 node list | grep shutdown

# If not there, restart it:
ros2 run main_control shutdown_manager_node
```

### CM5 doesn't shut down
```bash
# Check CM5 handler is running
ssh user@cm5 'ros2 node list | grep shutdown'

# If not there:
ssh user@cm5 'ros2 run ld19_utils cm5_shutdown_handler'

# Check if it's receiving requests:
ssh user@cm5 'ros2 topic echo /cm5/shutdown_request'
```

### Permission denied error
```bash
# On both SER8 and CM5, edit sudoers:
sudo visudo

# Add this line at the end (replace 'username' with actual user):
username ALL=(ALL) NOPASSWD: /sbin/shutdown
```

### Nothing happens
1. Check ROS_DOMAIN_ID: `echo $ROS_DOMAIN_ID`
2. Verify it's the same on both units
3. Test ping: `ping other_unit_ip`
4. Check logs: `journalctl -n 50`

## Emergency Shutdown (if stuck)

If the system doesn't respond:

```bash
# From another machine via SSH
ssh user@ser8 'sudo shutdown -h now'
ssh user@cm5 'sudo shutdown -h now'

# Or locally on the machine:
sudo shutdown -h now

# Or force power button (last resort):
# Hold power button for 5+ seconds
```

## Safety Checklist

Before doing actual shutdown:

- [ ] Read SHUTDOWN_SYSTEM.md
- [ ] Tested service call from terminal (did NOT click Yes)
- [ ] Both nodes launch without errors  
- [ ] Service appears in `ros2 service list`
- [ ] Can see "Shutdown System" button in HMI Admin window
- [ ] Save all work/data on SER8
- [ ] Let robot finish current operations
- [ ] Network is stable
- [ ] You know how to restart both units
- [ ] You're expecting the shutdown

## Verification Commands

Run these to verify everything is working:

```bash
# Check ROS 2 network
ros2 node list

# Check service
ros2 service list | grep shutdown

# Check topics
ros2 topic list | grep shutdown

# Check if nodes are running
pgrep -f shutdown_manager_node
pgrep -f cm5_shutdown_handler

# Monitor logs on SER8
journalctl -u ser8_bringup -f

# Monitor logs on CM5
journalctl -u ld19-stack -f
```

## After Shutdown

To bring systems back up:

1. **Power on CM5** first (or it starts automatically if powered)
2. **Power on SER8** second
3. **Wait for services to boot** (~30-60 seconds)
4. **Verify systems are running:**
   ```bash
   ros2 node list | grep -E "shutdown|ld19|controller"
   ```
5. **Test shutdown system again** before critical operations

## Common Questions

**Q: Can I interrupt the shutdown once started?**
A: Once acknowledged, both units will shutdown. You cannot interrupt via ROS. Use Ctrl+C on terminal nodes before confirming in HMI.

**Q: What if CM5 doesn't acknowledge?**
A: SER8 will wait 10 seconds, then shutdown anyway. CM5 should shutdown on its own.

**Q: Will this save my work?**
A: No. Make sure to save everything before clicking "Shutdown System".

**Q: Can I shutdown just one unit?**
A: Current implementation shuts down both. To modify, edit the shutdown nodes.

**Q: How long does actual shutdown take?**
A: 5-10 seconds from HMI click to power off.

**Q: Is there a reboot option?**
A: Currently shutdown only. For reboot, use `sudo reboot` from terminal.

## Next Steps After Verification

Once you've verified the shutdown system works:

1. **Add to launch files** - Include nodes in system launch files
2. **Configure systemd services** - For auto-start on boot
3. **Update documentation** - Tell team members about shutdown procedure
4. **Monitor logs** - Check logs after first few production shutdowns
5. **Plan improvements** - Consider enhancements from SHUTDOWN_SYSTEM.md

## Support

If something doesn't work:

1. **Check logs first:** `journalctl -n 100`
2. **Verify network:** `ping other_unit`
3. **Review:** `SHUTDOWN_SYSTEM.md` Troubleshooting section
4. **Test manually:** `ros2 service call /ser8/shutdown_system std_srvs/srv/Empty`
5. **Debug:** Enable ROS 2 logging: `export ROS_LOG_DIR=/tmp/ros_logs`

---

**Last Updated:** 2024
**Status:** Ready for deployment
**Tested On:** ROS 2 Jazzy, Ubuntu 24.04 LTS
