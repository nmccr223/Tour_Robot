#!/usr/bin/env python3
"""
PLC Motor Controller TCP Client
--------------------------------
TCP client for P1AM-200 PLC motor controller communication.

Connects to the PLC at configurable IP:port and translates ROS 2 cmd_vel
(Twist) messages into PLC motor commands (START, STOP, TURN, etc.).

The PLC runs Arduino code that listens on TCP and controls two motor drives
via discrete I/O signals.

Commands supported:
- START: Forward motion (both drives)
- STOP: Stop both drives
- TURN: Standard turn (one drive forward, one stopped/reversed)
- SHARP_TURN: Tight turn (opposite drive directions)
- SPEED_<0-100>: Set speed percentage
- FORWARD_LEFT: Forward with left turn bias
- FORWARD_RIGHT: Forward with right turn bias
- STATUS: Query emergency stop and drive status

Safety features:
- Emergency stop monitoring
- Drive fault detection
- Connection timeout handling
- Automatic reconnection

Usage:
    from plc_motor_client import PLCMotorClient
    
    client = PLCMotorClient(host='192.168.10.2', port=5005)
    if client.connect():
        client.send_command('START')
        status = client.get_status()
        client.set_velocity(0.5, 0.0)  # Forward at 50% speed
        client.stop()
"""

import socket
import time
import logging
from typing import Optional, Tuple, Dict
from enum import Enum


class PLCCommand(Enum):
    """PLC command strings matching Arduino code."""
    START = "START"
    STOP = "STOP"
    TURN = "TURN"
    SHARP_TURN = "SHARP_TURN"
    STATUS = "STATUS"
    # Extended commands for differential drive
    FORWARD_LEFT = "FORWARD_LEFT"
    FORWARD_RIGHT = "FORWARD_RIGHT"
    REVERSE = "REVERSE"
    REVERSE_LEFT = "REVERSE_LEFT"
    REVERSE_RIGHT = "REVERSE_RIGHT"


class PLCMotorClient:
    """
    TCP client for P1AM-200 PLC motor controller.
    
    Handles connection management, command sending, and status monitoring
    for the tour robot's differential drive system.
    """
    
    def __init__(self, host: str = '192.168.10.2', port: int = 5005, 
                 timeout: float = 2.0, reconnect_interval: float = 5.0):
        """
        Initialize PLC motor client.
        
        Args:
            host: PLC IP address
            port: PLC TCP port
            timeout: Socket timeout in seconds
            reconnect_interval: Seconds between reconnection attempts
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.reconnect_interval = reconnect_interval
        
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.last_connect_attempt = 0
        
        self.logger = logging.getLogger('PLCMotorClient')
        
        # Motor state tracking
        self.current_speed = 0
        self.emergency_stop_active = False
        self.drive_fault = False
        
    def connect(self) -> bool:
        """
        Establish TCP connection to PLC.
        
        Returns:
            True if connected successfully, False otherwise
        """
        current_time = time.time()
        if current_time - self.last_connect_attempt < self.reconnect_interval:
            return False
            
        self.last_connect_attempt = current_time
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.connected = True
            self.logger.info(f"Connected to PLC at {self.host}:{self.port}")
            return True
        except (socket.error, socket.timeout) as e:
            self.logger.error(f"Failed to connect to PLC: {e}")
            self.connected = False
            if self.socket:
                self.socket.close()
                self.socket = None
            return False
    
    def disconnect(self):
        """Close TCP connection to PLC."""
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                self.logger.error(f"Error closing socket: {e}")
            finally:
                self.socket = None
                self.connected = False
                self.logger.info("Disconnected from PLC")
    
    def send_command(self, command: str) -> bool:
        """
        Send command to PLC.
        
        Args:
            command: Command string (e.g., 'START', 'STOP', 'SPEED_50')
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected:
            if not self.connect():
                return False
        
        try:
            message = f"{command}\n"
            self.socket.sendall(message.encode('utf-8'))
            self.logger.debug(f"Sent command: {command}")
            return True
        except (socket.error, socket.timeout) as e:
            self.logger.error(f"Failed to send command '{command}': {e}")
            self.connected = False
            return False
    
    def receive_response(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Receive response from PLC.
        
        Args:
            timeout: Override default timeout
            
        Returns:
            Response string or None if failed
        """
        if not self.connected:
            return None
        
        try:
            if timeout:
                self.socket.settimeout(timeout)
            data = self.socket.recv(1024)
            response = data.decode('utf-8').strip()
            self.logger.debug(f"Received: {response}")
            return response
        except socket.timeout:
            self.logger.warning("Timeout waiting for PLC response")
            return None
        except (socket.error, UnicodeDecodeError) as e:
            self.logger.error(f"Error receiving response: {e}")
            self.connected = False
            return None
        finally:
            if timeout:
                self.socket.settimeout(self.timeout)
    
    def get_status(self) -> Dict[str, bool]:
        """
        Query PLC status (emergency stop, drive faults).
        
        Returns:
            Dict with 'emergency_stop' and 'drive_fault' keys
        """
        if not self.send_command(PLCCommand.STATUS.value):
            return {'emergency_stop': True, 'drive_fault': True}
        
        response = self.receive_response(timeout=1.0)
        if not response:
            return {'emergency_stop': True, 'drive_fault': True}
        
        # Parse response (format: "ESTOP:0,FAULT:0")
        status = {'emergency_stop': False, 'drive_fault': False}
        try:
            parts = response.split(',')
            for part in parts:
                if 'ESTOP:1' in part:
                    status['emergency_stop'] = True
                if 'FAULT:1' in part:
                    status['drive_fault'] = True
            
            self.emergency_stop_active = status['emergency_stop']
            self.drive_fault = status['drive_fault']
        except Exception as e:
            self.logger.error(f"Failed to parse status response: {e}")
        
        return status
    
    def set_velocity(self, linear: float, angular: float) -> bool:
        """
        Set motor velocities based on linear/angular twist.
        
        Converts ROS Twist message (linear.x, angular.z) into PLC motor commands
        using differential drive kinematics.
        
        Args:
            linear: Forward velocity (-1.0 to 1.0, m/s normalized)
            angular: Angular velocity (-1.0 to 1.0, rad/s normalized)
            
        Returns:
            True if command sent successfully
        """
        # Clamp inputs
        linear = max(-1.0, min(1.0, linear))
        angular = max(-1.0, min(1.0, angular))
        
        # Differential drive: left_speed = linear - angular, right_speed = linear + angular
        left_speed = linear - angular
        right_speed = linear + angular
        
        # Normalize to [-1.0, 1.0]
        max_speed = max(abs(left_speed), abs(right_speed))
        if max_speed > 1.0:
            left_speed /= max_speed
            right_speed /= max_speed
        
        # Determine command based on speed combination
        if abs(linear) < 0.05 and abs(angular) < 0.05:
            # Dead zone - stop
            return self.stop()
        elif abs(angular) < 0.1:
            # Mostly forward/reverse
            if linear > 0:
                speed_pct = int(abs(linear) * 100)
                self.send_command(f"SPEED_{speed_pct}")
                return self.send_command(PLCCommand.START.value)
            else:
                speed_pct = int(abs(linear) * 100)
                self.send_command(f"SPEED_{speed_pct}")
                return self.send_command(PLCCommand.REVERSE.value)
        elif abs(linear) < 0.1:
            # Mostly turning in place
            if abs(angular) > 0.5:
                return self.send_command(PLCCommand.SHARP_TURN.value if angular > 0 else "SHARP_TURN_RIGHT")
            else:
                return self.send_command(PLCCommand.TURN.value if angular > 0 else "TURN_RIGHT")
        else:
            # Combined motion
            speed_pct = int(abs(linear) * 100)
            self.send_command(f"SPEED_{speed_pct}")
            if angular > 0.1:
                return self.send_command(PLCCommand.FORWARD_LEFT.value)
            elif angular < -0.1:
                return self.send_command(PLCCommand.FORWARD_RIGHT.value)
            else:
                return self.send_command(PLCCommand.START.value)
    
    def stop(self) -> bool:
        """
        Emergency stop - halt all motor motion.
        
        Returns:
            True if command sent successfully
        """
        self.current_speed = 0
        return self.send_command(PLCCommand.STOP.value)
    
    def set_speed(self, speed_percent: int) -> bool:
        """
        Set motor speed percentage.
        
        Args:
            speed_percent: Speed from 0 to 100
            
        Returns:
            True if command sent successfully
        """
        speed_percent = max(0, min(100, speed_percent))
        self.current_speed = speed_percent
        return self.send_command(f"SPEED_{speed_percent}")
    
    def is_healthy(self) -> bool:
        """
        Check if PLC connection and motors are healthy.
        
        Returns:
            True if connected and no faults
        """
        if not self.connected:
            return False
        
        status = self.get_status()
        return not (status['emergency_stop'] or status['drive_fault'])
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        self.disconnect()
    
    def __del__(self):
        """Cleanup on deletion."""
        self.disconnect()


if __name__ == '__main__':
    # Test the PLC motor client
    logging.basicConfig(level=logging.DEBUG)
    
    print("PLC Motor Client Test")
    print("=" * 50)
    
    client = PLCMotorClient(host='192.168.10.2', port=5005)
    
    print(f"\nConnecting to PLC at {client.host}:{client.port}...")
    if not client.connect():
        print("FAILED to connect. Check PLC IP/port and network.")
        exit(1)
    
    print("✓ Connected successfully\n")
    
    # Test status
    print("Querying status...")
    status = client.get_status()
    print(f"  Emergency Stop: {'ACTIVE' if status['emergency_stop'] else 'OK'}")
    print(f"  Drive Fault: {'FAULT' if status['drive_fault'] else 'OK'}")
    
    # Test commands
    print("\nTesting commands (5 seconds each):")
    
    print("  → Setting speed to 30%...")
    client.set_speed(30)
    time.sleep(1)
    
    print("  → Forward motion...")
    client.send_command('START')
    time.sleep(5)
    
    print("  → Stopping...")
    client.stop()
    time.sleep(1)
    
    print("  → Turn left...")
    client.send_command('TURN')
    time.sleep(3)
    
    print("  → Stopping...")
    client.stop()
    time.sleep(1)
    
    print("\n✓ Test complete")
    client.disconnect()
