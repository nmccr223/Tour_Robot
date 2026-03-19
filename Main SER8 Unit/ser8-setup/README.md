# SER8 Reinstall Guide (Ubuntu 24.04 + ROS 2 Jazzy)

This folder is the authoritative setup kit for rebuilding a SER8 from a fresh Ubuntu 24.04 LTS install.

It covers:
- Installing required modules and tools
- Installing ROS 2 Jazzy
- Building the Tour Robot ROS workspace
- Installing watchdog + startup scripts
- Enabling autostart behavior for day-to-day operation

## What this folder contains

- `scripts/install-dependencies.sh`: Installs base dependencies and ROS 2 Jazzy, then initializes `rosdep`
- `scripts/setup-ssh-keys.sh`: Creates SSH keys and configures passwordless SSH to CM5
- `scripts/install-watchdog.sh`: Installs `cm5_service_watchdog.py` and systemd watchdog units
- `scripts/install-startup-wrapper.sh`: Installs `ser8_startup.py` and `start-tour-robot` wrapper
- `systemd/cm5-watchdog.service`: Watchdog service definition
- `systemd/cm5-watchdog.timer`: Periodic trigger for watchdog service
- `src/cm5_service_watchdog.py`: CM5 service monitor/restart logic
- `src/ser8_startup.py`: Startup orchestrator checks + launch
- `src/start-tour-robot.sh`: Command wrapper used by operators

## Quick start (fresh SER8)

Run from the repository root on SER8 (example repo location: `~/workspace/Tour_Robot`):

```bash
cd ~/workspace/Tour_Robot/Main\ SER8\ Unit/ser8-setup

# 1) Install dependencies and ROS2 Jazzy
bash scripts/install-dependencies.sh

# 2) Configure SSH trust from SER8 -> CM5
bash scripts/setup-ssh-keys.sh

# 3) Build ROS workspace (see full guide for copy/build commands)

# 4) Install watchdog + startup wrapper
bash scripts/install-watchdog.sh
bash scripts/install-startup-wrapper.sh

# 5) Verify services
systemctl status cm5-watchdog.service
systemctl status cm5-watchdog.timer
```

## Full documentation

- Detailed rebuild steps: `docs/SER8_INSTALLATION_GUIDE.md`
- Required assumptions and prep: `docs/PREREQUISITES.md`
- Common failure recovery: `docs/TROUBLESHOOTING.md`

## Daily operation

After setup, operators can run:

```bash
start-tour-robot
```

Useful options:

```bash
start-tour-robot --no-launch
start-tour-robot --no-restart
```