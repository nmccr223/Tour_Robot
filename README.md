# Tour Robot Repository

Central repository for Tour Robot control, perception, deployment, and operational documentation across SER8, CM5, PLC motor control, and camera pipelines.

## Architecture at a Glance

```text
					 Tour Robot System (Control + Perception)

   Front OAK-D (USB) ----\
						  \
						   >------ [ SER8 Main Control ] ------ TCP:5005 ------ [ PLC Motor Controller ]
						  /
	Rear OAK-D (USB) -----/

									  |
									  | Ethernet / SSH / ROS 2 integration
									  |
								  [ CM5 LiDAR Unit ]

   [ TL-SG108E Managed Switch ] provides L2 switching for internal robot network links.
```

## Who Should Read What

| Role | Start Here | Then Go To |
|---|---|---|
| Operator / Technician | Quick Operator Path | [SHUTDOWN_QUICK_START.md](SHUTDOWN_QUICK_START.md), [Main SER8 Unit/ser8-setup/docs/PREREQUISITES.md](Main%20SER8%20Unit/ser8-setup/docs/PREREQUISITES.md) |
| Integration / Deployment Engineer | Engineering Path | [Main SER8 Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md](Main%20SER8%20Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md), [Main SER8 Unit/PLC_MOTOR_CONTROLLER_GUIDE.md](Main%20SER8%20Unit/PLC_MOTOR_CONTROLLER_GUIDE.md) |
| Controls / Runtime Maintainer | Architecture and Network sections | [Main SER8 Unit/Main Control](Main%20SER8%20Unit/Main%20Control), [Main SER8 Unit/Launcher](Main%20SER8%20Unit/Launcher) |

## Quick Operator Path

Use this path when software is already installed and you need safe startup, validation, and shutdown.

### Pre-Run Checks

1. Confirm no active fault or emergency stop condition.
2. Confirm network reachability from SER8 to CM5 and PLC.
3. Confirm hardware links are in place:
	- PLC Ethernet connected
	- CM5 online
	- Front and rear OAK cameras connected via USB

### Start Sequence

1. Run startup command on SER8:

```bash
start-tour-robot
```

2. Confirm core services/nodes are healthy.
3. Confirm camera and LiDAR topics are present.
4. Confirm PLC endpoint is reachable before enabling motion.

### Shutdown Sequence

1. Follow [SHUTDOWN_QUICK_START.md](SHUTDOWN_QUICK_START.md) for operator procedure.
2. See [SHUTDOWN_SYSTEM.md](SHUTDOWN_SYSTEM.md) for detailed coordinated behavior.

### Operator Escalation Rules

1. If CM5 is unreachable, treat as network or SSH trust issue.
2. If PLC endpoint is unreachable, treat as motion-critical and stop operation.
3. If startup partially succeeds, collect logs and escalate to maintainer.

## Engineering Path

## System Overview

The platform is composed of:

1. SER8 main control runtime and launch orchestration
2. CM5 LiDAR processing and watchdog target services
3. PLC motor controller command endpoint
4. Front and rear OAK camera processing nodes
5. Shared ROS 2 message package

Reference docs:

1. Installation and rebuild: [Main SER8 Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md](Main%20SER8%20Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md)
2. Prerequisites: [Main SER8 Unit/ser8-setup/docs/PREREQUISITES.md](Main%20SER8%20Unit/ser8-setup/docs/PREREQUISITES.md)
3. PLC integration: [Main SER8 Unit/PLC_MOTOR_CONTROLLER_GUIDE.md](Main%20SER8%20Unit/PLC_MOTOR_CONTROLLER_GUIDE.md)

## Network and Addressing

Default control subnet:

1. 192.168.10.0/24

Default endpoint values:

1. PLC: 192.168.10.2 on TCP port 5005
2. CM5: 192.168.10.20
3. SER8 control NIC: 192.168.10.10
4. TL-SG108E management target: 192.168.10.254

PLC-ID-based model:

1. Define PLC as 192.168.10.N
2. Derive SER8 as 192.168.10.(N + 8)
3. Derive CM5 as 192.168.10.(N + 18)

Authoritative switch setup and address planning:

1. [Main SER8 Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md](Main%20SER8%20Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md#L487)

## Repository Structure

Top-level components:

1. [Main SER8 Unit](Main%20SER8%20Unit): main control, launcher, HMI, setup scripts, docs
2. [Ld19](Ld19): LiDAR processing implementation
3. [ld19_utils](ld19_utils): LiDAR utility package and launch support
4. [front_oak_processor](front_oak_processor): front camera ROS package
5. [rear_oak_processor](rear_oak_processor): rear camera ROS package
6. [robot_msgs](robot_msgs): shared ROS message definitions
7. [cm5_autostart](cm5_autostart): CM5 systemd and startup assets
8. [PLC](PLC): PLC firmware and sketches
9. [Luxonis Camera](Luxonis%20Camera): camera launcher and program assets

## Build and Deployment

For full rebuild and dependency steps, follow:

1. [Main SER8 Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md](Main%20SER8%20Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md)

Core ROS 2 packages in normal SER8 workspace builds:

1. robot_msgs
2. ld19_utils
3. front_oak_processor
4. rear_oak_processor
5. main_control

## Verification Checklist

Minimum checks after setup or network/config change:

1. SER8 can ping CM5.
2. SER8 can SSH to CM5.
3. SER8 can reach PLC endpoint on port 5005.
4. Required launch path completes without communication errors.
5. Required camera topics are present.
6. Shutdown service path is discoverable and testable.

## Troubleshooting Entry Points

1. Install and startup issues: [Main SER8 Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md](Main%20SER8%20Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md)
2. PLC communication issues: [Main SER8 Unit/PLC_MOTOR_CONTROLLER_GUIDE.md](Main%20SER8%20Unit/PLC_MOTOR_CONTROLLER_GUIDE.md)
3. Shutdown workflow: [SHUTDOWN_SYSTEM.md](SHUTDOWN_SYSTEM.md), [SHUTDOWN_QUICK_START.md](SHUTDOWN_QUICK_START.md)

## Safety and Change Control

1. Do not run motion tests unless emergency stop path is verified.
2. Treat PLC connectivity failures as stop-work conditions.
3. Update docs whenever endpoint IPs, service names, or launch behavior changes.
4. Validate updates in controlled mode before field operation.

## Documentation Index

1. Install guide: [Main SER8 Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md](Main%20SER8%20Unit/ser8-setup/docs/SER8_INSTALLATION_GUIDE.md)
2. Prerequisites: [Main SER8 Unit/ser8-setup/docs/PREREQUISITES.md](Main%20SER8%20Unit/ser8-setup/docs/PREREQUISITES.md)
3. PLC guide: [Main SER8 Unit/PLC_MOTOR_CONTROLLER_GUIDE.md](Main%20SER8%20Unit/PLC_MOTOR_CONTROLLER_GUIDE.md)
4. Shutdown quick start: [SHUTDOWN_QUICK_START.md](SHUTDOWN_QUICK_START.md)
5. Shutdown architecture: [SHUTDOWN_SYSTEM.md](SHUTDOWN_SYSTEM.md)
6. Shutdown index: [SHUTDOWN_INDEX.md](SHUTDOWN_INDEX.md)

## Current Status

1. Manual bringup workflow is available and documented.
2. Watchdog and startup runtime files are available in setup docs.
3. Full automatic power-on startup remains a planned enhancement.

## License

Add project license and sharing policy here.
