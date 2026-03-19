#!/bin/bash

# This script sets up passwordless SSH access from the SER8 to the CM5.

# Define variables
CM5_USER="tourrobot"
CM5_HOST="192.168.10.20"

# Generate SSH key if it doesn't exist
if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
    echo "Generating SSH key..."
    ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519"
fi

# Copy SSH key to CM5
echo "Copying SSH key to $CM5_USER@$CM5_HOST..."
ssh-copy-id -i "$HOME/.ssh/id_ed25519.pub" "$CM5_USER@$CM5_HOST"

echo "Passwordless SSH setup complete."