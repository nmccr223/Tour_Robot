#!/usr/bin/env python3
"""
SER8 Navigation Proof of Concept
---------------------------------
Demonstrates autonomous obstacle avoidance using LD19 LiDAR data.

Features:
- Vector Field Histogram (VFH) obstacle avoidance
- Real-time obstacle detection and monitoring
- Motor control interface (USB to CPP-A24V80A-SA-CAN)
- Status and visualization topics

Run on SER8 main control computer.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import math
import time
import json
from collections import deque

# Import motor controller (placeholder until real protocol provided)
try:
    from motor_controller_stub import MotorController
except ImportError:
    print("Warning: motor_controller_stub not found. Motor control disabled.")
    MotorController = None


class ObstacleZone:
    """Represents obstacle detection in a specific angular zone."""
    def __init__(self, name, angle_start, angle_end, min_distance):
        self.name = name
        self.angle_start = angle_start
        self.angle_end = angle_end
        self.min_distance = min_distance
        self.obstacles = []
        self.closest_distance = float('inf')
        self.obstacle_count = 0


class VectorFieldHistogram:
    """
    Vector Field Histogram for obstacle avoidance.
    
    Divides 360° scan into sectors, calculates obstacle density,
    and finds safe navigation corridors.
    """
    
    def __init__(self, num_sectors=72, safe_distance=1.5, danger_distance=0.5):
        self.num_sectors = num_sectors
        self.sector_angle = 2 * math.pi / num_sectors
        self.safe_distance = safe_distance
        self.danger_distance = danger_distance
        self.histogram = [0.0] * num_sectors
        
    def update(self, ranges, angle_min, angle_increment):
        """Update histogram with new scan data."""
        self.histogram = [0.0] * self.num_sectors
        
        for i, r in enumerate(ranges):
            if r <= 0 or math.isinf(r) or math.isnan(r):
                continue
                
            angle = angle_min + i * angle_increment
            # Normalize angle to [0, 2π]
            angle = angle % (2 * math.pi)
            
            sector = int(angle / self.sector_angle)
            if 0 <= sector < self.num_sectors:
                # Calculate obstacle magnitude (closer = higher value)
                if r < self.danger_distance:
                    magnitude = 10.0
                elif r < self.safe_distance:
                    magnitude = 5.0 * (self.safe_distance - r) / (self.safe_distance - self.danger_distance)
                else:
                    magnitude = 0.0
                    
                self.histogram[sector] += magnitude
    
    def find_best_direction(self, current_heading=0.0, goal_direction=None):
        """
        Find the best safe direction to navigate.
        
        Returns: (angle, is_safe) tuple
        """
        # Find valleys (safe sectors)
        valleys = []
        in_valley = False
        valley_start = 0
        
        threshold = 2.0  # Obstacle density threshold
        
        for i in range(self.num_sectors):
            if self.histogram[i] < threshold:
                if not in_valley:
                    valley_start = i
                    in_valley = True
            else:
                if in_valley:
                    valleys.append((valley_start, i - 1))
                    in_valley = False
        
        # Handle wrap-around
        if in_valley:
            valleys.append((valley_start, self.num_sectors - 1))
        
        if not valleys:
            # No safe direction - emergency stop
            return (current_heading, False)
        
        # Find best valley (widest, closest to goal/heading)
        best_valley = None
        best_score = -float('inf')
        
        for start, end in valleys:
            # Calculate valley center
            if end < start:  # Wrap-around
                center = ((start + end + self.num_sectors) / 2) % self.num_sectors
            else:
                center = (start + end) / 2
            
            center_angle = center * self.sector_angle
            
            # Valley width
            if end < start:
                width = (self.num_sectors - start + end + 1)
            else:
                width = end - start + 1
            
            # Score based on width and alignment with goal/heading
            score = width * 10
            
            if goal_direction is not None:
                angle_diff = abs(center_angle - goal_direction)
                angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
                score -= angle_diff * 5
            else:
                # Prefer current heading
                angle_diff = abs(center_angle - current_heading)
                angle_diff = min(angle_diff, 2 * math.pi - angle_diff)
                score -= angle_diff * 3
            
            if score > best_score:
                best_score = score
                best_valley = (start, end, center_angle)
        
        if best_valley:
            return (best_valley[2], True)
        else:
            return (current_heading, False)


class NavigationPOCNode(Node):
    """Main POC node for autonomous navigation."""
    
    def __init__(self):
        super().__init__('navigation_poc')
        
        # Parameters
        self.declare_parameter('max_linear_speed', 0.5)  # m/s
        self.declare_parameter('max_angular_speed', 1.0)  # rad/s
        self.declare_parameter('safe_distance', 1.5)  # meters
        self.declare_parameter('danger_distance', 0.5)  # meters
        self.declare_parameter('enable_motors', False)  # Safety: disabled by default
        
        self.max_linear_speed = self.get_parameter('max_linear_speed').value
        self.max_angular_speed = self.get_parameter('max_angular_speed').value
        self.safe_distance = self.get_parameter('safe_distance').value
        self.danger_distance = self.get_parameter('danger_distance').value
        self.enable_motors = self.get_parameter('enable_motors').value
        
        # State
        self.current_heading = 0.0
        self.robot_state = "INITIALIZING"
        self.start_time = time.time()
        self.scan_count = 0
        self.last_scan_time = None
        
        # VFH obstacle avoidance
        self.vfh = VectorFieldHistogram(
            num_sectors=72,
            safe_distance=self.safe_distance,
            danger_distance=self.danger_distance
        )
        
        # Obstacle zones for monitoring
        self.zones = {
            'front': ObstacleZone('Front', -math.pi/6, math.pi/6, float('inf')),
            'left': ObstacleZone('Left', math.pi/6, math.pi/2, float('inf')),
            'right': ObstacleZone('Right', -math.pi/2, -math.pi/6, float('inf')),
            'rear': ObstacleZone('Rear', 5*math.pi/6, -5*math.pi/6, float('inf'))
        }
        
        # Motor controller
        self.motor_controller = None
        if MotorController and self.enable_motors:
            try:
                self.motor_controller = MotorController()
                self.get_logger().info("Motor controller initialized")
            except Exception as e:
                self.get_logger().error(f"Failed to initialize motor controller: {e}")
        else:
            self.get_logger().warn("Motors disabled or controller not available")
        
        # ROS 2 subscribers
        self.scan_sub = self.create_subscription(
            LaserScan,
            '/scan',
            self.scan_callback,
            10
        )
        
        # ROS 2 publishers
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.status_pub = self.create_publisher(String, '/robot_status', 10)
        self.obstacle_pub = self.create_publisher(String, '/obstacle_detection', 10)
        
        # Timers
        self.create_timer(0.1, self.status_timer_callback)  # 10 Hz status update
        
        self.robot_state = "READY"
        self.get_logger().info("Navigation POC node initialized")
        self.get_logger().info(f"Max speeds: linear={self.max_linear_speed} m/s, angular={self.max_angular_speed} rad/s")
        self.get_logger().info(f"Safety distances: safe={self.safe_distance}m, danger={self.danger_distance}m")
        self.get_logger().info(f"Motors: {'ENABLED' if self.enable_motors else 'DISABLED (simulation mode)'}")
    
    def scan_callback(self, msg: LaserScan):
        """Process incoming LiDAR scan and perform obstacle avoidance."""
        self.last_scan_time = time.time()
        self.scan_count += 1
        
        # Update VFH with scan data
        self.vfh.update(msg.ranges, msg.angle_min, msg.angle_increment)
        
        # Update obstacle zones
        self.update_obstacle_zones(msg)
        
        # Publish obstacle detection status
        self.publish_obstacle_status()
        
        # Determine safe navigation direction
        best_direction, is_safe = self.vfh.find_best_direction(self.current_heading)
        
        # Generate velocity commands
        if not is_safe:
            self.robot_state = "EMERGENCY_STOP"
            linear_vel = 0.0
            angular_vel = 0.0
            self.get_logger().warn("No safe direction found - EMERGENCY STOP")
        else:
            # Check front zone for immediate danger
            if self.zones['front'].closest_distance < self.danger_distance:
                self.robot_state = "STOPPING"
                linear_vel = 0.0
                angular_vel = 0.0
            elif self.zones['front'].closest_distance < self.safe_distance:
                self.robot_state = "AVOIDING"
                # Slow down when approaching obstacles
                linear_vel = self.max_linear_speed * 0.3
                # Turn towards safe direction
                angle_diff = best_direction - self.current_heading
                angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                angular_vel = max(-self.max_angular_speed, 
                                min(self.max_angular_speed, angle_diff * 2.0))
            else:
                self.robot_state = "NAVIGATING"
                linear_vel = self.max_linear_speed * 0.7
                # Gentle steering towards safe direction
                angle_diff = best_direction - self.current_heading
                angle_diff = (angle_diff + math.pi) % (2 * math.pi) - math.pi
                angular_vel = max(-self.max_angular_speed * 0.5,
                                min(self.max_angular_speed * 0.5, angle_diff))
        
        # Update heading estimate
        self.current_heading = (self.current_heading + angular_vel * 0.05) % (2 * math.pi)
        
        # Publish velocity command
        self.publish_velocity(linear_vel, angular_vel)
    
    def update_obstacle_zones(self, scan: LaserScan):
        """Update obstacle detection zones with scan data."""
        for zone in self.zones.values():
            zone.obstacles = []
            zone.closest_distance = float('inf')
            zone.obstacle_count = 0
        
        for i, r in enumerate(scan.ranges):
            if r <= 0 or math.isinf(r) or math.isnan(r):
                continue
            
            angle = scan.angle_min + i * scan.angle_increment
            angle = (angle + math.pi) % (2 * math.pi) - math.pi  # Normalize to [-π, π]
            
            for zone in self.zones.values():
                if self._angle_in_range(angle, zone.angle_start, zone.angle_end):
                    zone.obstacles.append((angle, r))
                    zone.obstacle_count += 1
                    if r < zone.closest_distance:
                        zone.closest_distance = r
    
    def _angle_in_range(self, angle, start, end):
        """Check if angle is within range, handling wrap-around."""
        if start <= end:
            return start <= angle <= end
        else:  # Wrap-around case
            return angle >= start or angle <= end
    
    def publish_velocity(self, linear, angular):
        """Publish velocity command and send to motors."""
        # Publish to ROS topic
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.cmd_vel_pub.publish(msg)
        
        # Send to motor controller if available
        if self.motor_controller:
            try:
                # Convert twist to differential drive
                # left_speed = linear - (angular * wheel_base / 2)
                # right_speed = linear + (angular * wheel_base / 2)
                # For now, simple approximation
                wheel_base = 0.5  # meters (adjust to your robot)
                left_speed = linear - (angular * wheel_base / 2)
                right_speed = linear + (angular * wheel_base / 2)
                
                self.motor_controller.set_velocity(left_speed, right_speed)
            except Exception as e:
                self.get_logger().error(f"Motor control error: {e}")
    
    def publish_obstacle_status(self):
        """Publish obstacle detection status for monitoring."""
        status = {
            'timestamp': time.time(),
            'zones': {}
        }
        
        for name, zone in self.zones.items():
            status['zones'][name] = {
                'obstacle_count': zone.obstacle_count,
                'closest_distance': zone.closest_distance if zone.closest_distance != float('inf') else None,
                'safe': zone.closest_distance > self.safe_distance
            }
        
        msg = String()
        msg.data = json.dumps(status)
        self.obstacle_pub.publish(msg)
    
    def status_timer_callback(self):
        """Publish robot status for monitoring."""
        uptime = time.time() - self.start_time
        scan_rate = self.scan_count / uptime if uptime > 0 else 0
        
        status = {
            'timestamp': time.time(),
            'state': self.robot_state,
            'uptime': uptime,
            'scan_count': self.scan_count,
            'scan_rate': round(scan_rate, 2),
            'last_scan_age': time.time() - self.last_scan_time if self.last_scan_time else None,
            'heading': round(math.degrees(self.current_heading), 1),
            'motors_enabled': self.enable_motors,
            'safety': {
                'safe_distance': self.safe_distance,
                'danger_distance': self.danger_distance,
                'max_linear_speed': self.max_linear_speed,
                'max_angular_speed': self.max_angular_speed
            }
        }
        
        msg = String()
        msg.data = json.dumps(status)
        self.status_pub.publish(msg)
    
    def shutdown(self):
        """Graceful shutdown - stop motors."""
        self.get_logger().info("Shutting down - stopping motors")
        self.publish_velocity(0.0, 0.0)
        if self.motor_controller:
            self.motor_controller.stop()


def main(args=None):
    rclpy.init(args=args)
    node = NavigationPOCNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
