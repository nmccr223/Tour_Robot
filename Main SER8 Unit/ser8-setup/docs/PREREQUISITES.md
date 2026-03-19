# Prerequisites for SER8 Rebuild

Use this checklist before running the installation guide.

## Operating System

- Fresh install of Ubuntu 24.04 LTS on SER8
- Network connectivity to internet (for apt/rosdep) and to CM5 (LAN)

## User and access

- You have a normal user account with sudo rights (recommended username: `tourrobot`)
- You can log into CM5 over SSH from SER8

## Repository availability

- This repository is present on SER8 at `~/workspace/Tour_Robot` (or an equivalent path)
- The following folders exist in the repo:
	- `Main SER8 Unit/ser8-setup`
	- `Main SER8 Unit/Main Control`
	- `Main SER8 Unit/Launcher`
	- `robot_msgs`
	- `ld19_utils`

## Network assumptions (default values)

- CM5 host: `192.168.10.20`
- CM5 SSH user: `tourrobot`
- PLC/motor host: `192.168.10.2`
- PLC/motor UDP/TCP endpoint: `5005`

If your network differs, update `/usr/local/bin/start-tour-robot` after installation.

## CM5-side requirements

On CM5, allow passwordless `systemctl` operations for the SSH user:

```bash
sudo visudo -f /etc/sudoers.d/tourrobot
```

Required entries:

```text
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19.service
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl restart ld19-stack.service
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl status *
tourrobot ALL=(ALL) NOPASSWD: /bin/systemctl is-active *
```

## Validation pre-checks (recommended)

From SER8, before full bringup:

```bash
ping -c 1 192.168.10.20
ssh tourrobot@192.168.10.20 "hostname"
```

If these fail, resolve connectivity first, then continue with `SER8_INSTALLATION_GUIDE.md`.