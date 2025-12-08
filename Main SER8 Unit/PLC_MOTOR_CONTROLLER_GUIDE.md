# PLC Motor Controller Configuration Guide

## Overview

The Tour Robot uses a **P1AM-200 PLC** (Productivity Open Arduino-compatible controller) with motor drive modules to control differential drive motors via TCP/IP commands from the SER8.

## Hardware Setup

### P1AM-200 PLC Configuration

**Network Settings (Configure in Arduino code):**
- IP Address: `192.168.10.2`
- Subnet: `255.255.255.0`
- Gateway: `192.168.10.1`
- TCP Port: `5005`

**Motor Controllers:**
- Left Drive: Connected to PLC discrete outputs
- Right Drive: Connected to PLC discrete outputs
- Emergency Stop: Digital input monitoring

### Arduino Code File

**Location:** `d:\AI and Data Class\moretestA.cpp.ino`

**Important:** This file contains test functions that must remain intact. Do not modify test code sections when updating network settings.

## Network Configuration

### Update PLC IP Settings

In `moretestA.cpp.ino`, locate the Ethernet initialization section and update:

```cpp
// Network configuration
byte mac[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0xFE, 0xED };  // Keep existing MAC
IPAddress ip(192, 168, 10, 2);        // PLC IP address
IPAddress gateway(192, 168, 10, 1);   // Network gateway
IPAddress subnet(255, 255, 255, 0);   // Subnet mask

EthernetServer server(5005);  // TCP port for SER8 communication
```

### Network Topology

```
┌─────────────────────────────────────────────────────────────┐
│                     Tour Robot Network                       │
│                     172.16.0.0/24 + 192.168.10.0/24         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  CM5 (LiDAR) ◄──── Ethernet ────► SER8 (Main Control)      │
│  172.16.0.3                        172.16.0.2               │
│                                     │                        │
│                                     │ Ethernet (different    │
│                                     │ subnet/VLAN)           │
│                                     │                        │
│                                     ▼                        │
│                          PLC Motor Controller               │
│                          192.168.10.2:5005                  │
│                               │                              │
│                               ├─► Left Motor Drive          │
│                               └─► Right Motor Drive         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Note:** The PLC is on a separate subnet (`192.168.10.x`) from the CM5/SER8 connection (`172.16.0.x`). The SER8 requires dual network interfaces or routing configuration.

## TCP Command Protocol

### Commands Sent from SER8 to PLC

The PLC accepts ASCII commands terminated with newline (`\n`):

| Command | Description | PLC Response |
|---------|-------------|--------------|
| `START` | Forward motion (both drives) | ACK |
| `STOP` | Stop all motors | ACK |
| `TURN` | Turn left (standard) | ACK |
| `TURN_RIGHT` | Turn right (standard) | ACK |
| `SHARP_TURN` | Sharp turn left | ACK |
| `SHARP_TURN_RIGHT` | Sharp turn right | ACK |
| `FORWARD_LEFT` | Forward with left bias | ACK |
| `FORWARD_RIGHT` | Forward with right bias | ACK |
| `REVERSE` | Reverse motion | ACK |
| `REVERSE_LEFT` | Reverse with left bias | ACK |
| `REVERSE_RIGHT` | Reverse with right bias | ACK |
| `SPEED_<0-100>` | Set speed percentage | ACK |
| `STATUS` | Query emergency stop & faults | `ESTOP:0,FAULT:0` |

### Example Command Sequences

**Forward at 50% speed:**
```
SPEED_50\n
START\n
```

**Turn left:**
```
TURN\n
```

**Stop:**
```
STOP\n
```

**Query status:**
```
STATUS\n
← ESTOP:0,FAULT:0
```

## SER8 Integration

### Python Motor Client

**File:** `Main SER8 Unit/Main Control/plc_motor_client.py`

**Usage in ROS 2 nodes:**

```python
from plc_motor_client import PLCMotorClient

# Initialize client
motor_client = PLCMotorClient(host='192.168.10.2', port=5005, timeout=2.0)

# Connect
if motor_client.connect():
    # Send velocity command (normalized -1.0 to 1.0)
    motor_client.set_velocity(linear=0.5, angular=0.0)  # Forward 50%
    
    # Check status
    status = motor_client.get_status()
    if status['emergency_stop']:
        print("EMERGENCY STOP ACTIVE!")
    
    # Stop motors
    motor_client.stop()
    
    # Disconnect
    motor_client.disconnect()
```

### Main Controller Integration

**File:** `Main SER8 Unit/Main Control/main_controller_node.py`

The main controller automatically:
- Connects to PLC on startup
- Converts ROS `/cmd_vel` to PLC commands
- Monitors PLC health (emergency stop, drive faults)
- Handles reconnection if TCP connection drops

**Configuration:**
```yaml
main_controller_node:
  ros__parameters:
    motor_host: "192.168.10.2"
    motor_port: 5005
    max_linear_speed: 0.4  # m/s
    max_angular_speed: 0.8  # rad/s
```

## Testing the PLC Connection

### From SER8 Terminal

```bash
# Source ROS workspace
source /home/vboxuser/ser8_ws/install/setup.bash

# Test PLC connection
ros2 run main_control plc_motor_test

# Expected output:
# PLC Motor Client Test
# ==================================================
# 
# Connecting to PLC at 192.168.10.2:5005...
# ✓ Connected successfully
# 
# Querying status...
#   Emergency Stop: OK
#   Drive Fault: OK
# 
# Testing commands (5 seconds each):
#   → Setting speed to 30%...
#   → Forward motion...
#   → Stopping...
#   → Turn left...
#   → Stopping...
# 
# ✓ Test complete
```

### Using netcat for Manual Testing

```bash
# From SER8, connect to PLC
nc 192.168.10.2 5005

# Type commands (press Enter after each):
STATUS
SPEED_30
START
STOP
```

## Safety Features

### Emergency Stop Monitoring

The PLC monitors an emergency stop button via digital input. When activated:
- All motor drives are disabled
- PLC responds to `STATUS` with `ESTOP:1`
- SER8 logs error and stops sending motion commands

### Drive Fault Detection

Motor drives report fault conditions (overcurrent, overtemp, etc.):
- PLC monitors drive fault signals
- PLC responds to `STATUS` with `FAULT:1`
- SER8 logs error and requires manual intervention

### Connection Timeout

If TCP connection is lost:
- SER8 automatically attempts reconnection every 5 seconds
- Motors remain in last commanded state (PLC side)
- Consider adding watchdog timer on PLC to stop motors if no commands received for N seconds

## Troubleshooting

### Cannot Connect to PLC

**Check network connectivity:**
```bash
# From SER8
ping 192.168.10.2
```

If ping fails:
- Verify SER8 has correct IP on PLC subnet interface
- Check ethernet cable between SER8 and PLC
- Verify PLC power and Ethernet module status LEDs

**Check PLC is listening:**
```bash
# From SER8
nc -zv 192.168.10.2 5005
```

Should report "succeeded" if PLC is listening.

### Motors Not Responding

1. **Check emergency stop button** - Release if engaged
2. **Check drive faults:**
   ```bash
   ros2 run main_control plc_motor_test
   # Look for "Drive Fault: FAULT"
   ```
3. **Check drive power** - Verify 24V power to motor drives
4. **Check PLC outputs** - Use PLC diagnostic software to verify outputs are toggling

### Commands Not Executing

1. **Check command format** - Must end with `\n`
2. **Check PLC code** - Verify command parsing in Arduino code
3. **Check serial monitor** - Connect USB to PLC and monitor Arduino Serial output for debugging

## PLC Code Modifications (If Needed)

### Adding New Commands

In `moretestA.cpp.ino`, locate the command parsing section:

```cpp
void loop() {
  EthernetClient client = server.available();
  if (client) {
    if (client.available()) {
      String command = client.readStringUntil('\n');
      command.trim();
      
      // Add new command here:
      if (command == "YOUR_NEW_COMMAND") {
        // Your motor control logic
        client.println("ACK");
      }
      // ... existing commands ...
    }
  }
}
```

### Updating Network Settings

Only modify these lines in `moretestA.cpp.ino`:

```cpp
IPAddress ip(192, 168, 10, 2);        // PLC IP
IPAddress gateway(192, 168, 10, 1);   // Gateway
EthernetServer server(5005);          // Port
```

**Do NOT modify:**
- Test function code
- Motor drive logic
- Safety interlocks
- Emergency stop handling

## Deployment Checklist

- [ ] PLC programmed with correct IP: `192.168.10.2`
- [ ] PLC listening on port `5005`
- [ ] SER8 can ping `192.168.10.2`
- [ ] Emergency stop button tested and working
- [ ] Drive faults clear (no overcurrent/overtemp)
- [ ] Test commands work (`STATUS`, `START`, `STOP`)
- [ ] ROS 2 main_control package built and sourced
- [ ] `plc_motor_test` executable passes all tests
- [ ] Launch file configured with correct `motor_host` and `motor_port`

## Reference Files

| File | Location | Purpose |
|------|----------|---------|
| PLC Arduino Code | `d:\AI and Data Class\moretestA.cpp.ino` | P1AM-200 motor controller firmware |
| Python Motor Client | `Main SER8 Unit/Main Control/plc_motor_client.py` | TCP client library |
| Main Controller Node | `Main SER8 Unit/Main Control/main_controller_node.py` | ROS 2 integration |
| Launch File | `Main SER8 Unit/Launcher/system_bringup.launch.py` | System startup |
| Setup Script | `Main SER8 Unit/Main Control/setup.py` | Package configuration |

## Support

For motor controller issues:
1. Check this guide first
2. Test with `plc_motor_test` to isolate ROS vs PLC issues
3. Use `nc` for manual command testing
4. Review PLC Serial monitor output via USB connection
