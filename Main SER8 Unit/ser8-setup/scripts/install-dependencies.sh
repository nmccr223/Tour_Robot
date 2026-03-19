#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Updating apt metadata"
sudo apt update

echo "[2/5] Installing base tools"
sudo apt install -y \
    software-properties-common \
    curl \
    gnupg \
    lsb-release \
    ca-certificates \
    git \
    openssh-client \
    python3 \
    python3-pip \
    python3-venv \
    python3-colcon-common-extensions \
    python3-rosdep \
    python3-vcstool \
    build-essential \
    cmake

echo "[3/5] Enabling ROS 2 apt repository"
sudo add-apt-repository -y universe
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" \
    | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

echo "[4/5] Installing ROS 2 Jazzy"
sudo apt update
sudo apt install -y ros-jazzy-desktop

echo "[5/5] Initializing rosdep"
if ! sudo test -f /etc/ros/rosdep/sources.list.d/20-default.list; then
    sudo rosdep init
fi
rosdep update

echo "Dependencies installed successfully."