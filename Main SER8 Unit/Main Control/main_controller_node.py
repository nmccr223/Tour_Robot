# main_control/main_controller_node.py
import math
import socket
import struct
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from vision_msgs.msg import Detection2DArray  # or your chosen message
from builtin_interfaces.msg import Time

# Replace with your AprilTag message type
from apriltag_msgs.msg import AprilTagDetections  # Example; adjust to your package

from .udp_motor_client import UdpMotorClient


class MainController(Node):
    def __init__(self):
        super().__init__('main_controller')

        # Parameters
        self.declare_parameter('control_rate_hz', 20.0)
        self.declare_parameter('hard_stop_distance', 0.4)
        self.declare_parameter('slow_down_distance', 1.0)
        self.declare_parameter('max_linear_speed', 0.4)
        self.declare_parameter('max_angular_speed', 0.8)
        self.declare_parameter('motor_host', '192.168.10.2')
        self.declare_parameter('motor_port', 5005)
        self.declare_parameter('use_cmd_vel_topic', False)

        self.control_rate = float(self.get_parameter('control_rate_hz').value)
        self.hard_stop_distance = float(self.get_parameter('hard_stop_distance').value)
        self.slow_down_distance = float(self.get_parameter('slow_down_distance').value)
        self.max_linear_speed = float(self.get_parameter('max_linear_speed').value)
        self.max_angular_speed = float(self.get_parameter('max_angular_speed').value)
        self.use_cmd_vel_topic = bool(self.get_parameter('use_cmd_vel_topic').value)

        # Networking to CM5
        motor_host = self.get_parameter('motor_host').value
        motor_port = int(self.get_parameter('motor_port').value)
        self.motor_client = UdpMotorClient(motor_host, motor_port)

        # Internal state
        self.last_odom: Optional[Odometry] = None
        self.last_scan: Optional[LaserScan] = None
        self.last_front_detections: Optional[Detection2DArray] = None
        self.last_rear_detections: Optional[Detection2DArray] = None
        self.last_apriltags: Optional[AprilTagDetections] = None

        # Goal (map frame or odom frame) – you will set this externally
        self.goal_x = 0.0
        self.goal_y = 0.0
        self.goal_yaw = 0.0
        self.has_goal = False

        # Subscribers
        self.create_subscription(Odometry, '/odometry/filtered', self.odom_callback, 10)
        self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)
        self.create_subscription(Detection2DArray,
                                 '/front/oak/detections', self.front_det_callback, 10)
        self.create_subscription(Detection2DArray,
                                 '/rear/oak/detections', self.rear_det_callback, 10)
        self.create_subscription(AprilTagDetections,
                                 '/apriltag_detections', self.apriltag_callback, 10)

        # Optionally expose /cmd_vel (if you later want Nav2 to drive base)
        self.cmd_vel_pub = None
        if self.use_cmd_vel_topic:
            self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Timer for control loop
        self.control_timer = self.create_timer(1.0 / self.control_rate, self.control_loop)

        self.seq = 0
        self.get_logger().info('MainController node initialized.')

    # --- Callbacks updating state ---

    def odom_callback(self, msg: Odometry):
        self.last_odom = msg

    def scan_callback(self, msg: LaserScan):
        self.last_scan = msg

    def front_det_callback(self, msg: Detection2DArray):
        self.last_front_detections = msg

    def rear_det_callback(self, msg: Detection2DArray):
        self.last_rear_detections = msg

    def apriltag_callback(self, msg: AprilTagDetections):
        self.last_apriltags = msg
        # TODO: Use tags to update self.goal_x/y or refine pose if desired

    # --- Goal management API (could be extended to a service/action) ---

    def set_goal(self, x: float, y: float, yaw: float):
        self.goal_x = x
        self.goal_y = y
        self.goal_yaw = yaw
        self.has_goal = True
        self.get_logger().info(f'Set goal: x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}')

    # --- Control loop ---

    def control_loop(self):
        now = self.get_clock().now()

        if not self.has_goal or self.last_odom is None or self.last_scan is None:
            # Not enough info to control yet
            return

        pose_x, pose_y, pose_yaw = self.extract_pose(self.last_odom)
        v_cmd, w_cmd = self.compute_command(pose_x, pose_y, pose_yaw, now)

        # Saturate speeds
        v_cmd = max(min(v_cmd, self.max_linear_speed), -self.max_linear_speed)
        w_cmd = max(min(w_cmd, self.max_angular_speed), -self.max_angular_speed)

        # Publish or send to CM5
        if self.use_cmd_vel_topic and self.cmd_vel_pub is not None:
            twist = Twist()
            twist.linear.x = v_cmd
            twist.angular.z = w_cmd
            self.cmd_vel_pub.publish(twist)
        else:
            self.seq += 1
            self.motor_client.send_cmd_vel(self.seq, now, v_cmd, w_cmd)

    # --- Core decision logic ---

    def compute_command(self, x: float, y: float, yaw: float, now: Time):
        """
        Compute (v, w) based on:
        - Current pose (x, y, yaw)
        - Goal (self.goal_x/y/yaw)
        - LiDAR scan and camera detections
        """

        # If obstacle too close, emergency stop
        if self.is_emergency_stop():
            return 0.0, 0.0

        # Simple proportional controller towards goal (placeholder)
        dx = self.goal_x - x
        dy = self.goal_y - y
        goal_dist = math.hypot(dx, dy)

        # If near goal, rotate to desired yaw and stop
        if goal_dist < 0.1:
            yaw_error = self.angle_diff(self.goal_yaw, yaw)
            if abs(yaw_error) < math.radians(5.0):
                # Goal reached
                return 0.0, 0.0
            else:
                v = 0.0
                w = 0.5 * yaw_error  # TODO: tune
                return v, w

        # Orient towards goal
        desired_heading = math.atan2(dy, dx)
        heading_error = self.angle_diff(desired_heading, yaw)

        # Basic P control with slow-down near obstacles
        v = 0.3 * (1.0 if not self.is_slow_down_zone() else 0.3)
        w = 1.0 * heading_error

        # TODO:
        # - Replace this with a local planner that considers LiDAR scans more explicitly
        # - Use OAK detections to create virtual obstacles in certain directions

        return v, w

    # --- Helpers ---

    def is_emergency_stop(self) -> bool:
        """Return True if anything is within hard_stop_distance in front."""
        scan = self.last_scan
        if scan is None:
            return False

        # Check a narrow sector ahead (e.g. +/- 20 degrees)
        sector = math.radians(20.0)
        angle = scan.angle_min
        min_ahead = float('inf')
        for r in scan.ranges:
            if scan.range_min < r < scan.range_max:
                if abs(angle) < sector:
                    if r < min_ahead:
                        min_ahead = r
            angle += scan.angle_increment

        if min_ahead < self.hard_stop_distance:
            return True
        return False

    def is_slow_down_zone(self) -> bool:
        """Return True if close obstacle or person detected."""
        # Start with LiDAR
        scan = self.last_scan
        if scan is not None:
            sector = math.radians(45.0)
            angle = scan.angle_min
            min_ahead = float('inf')
            for r in scan.ranges:
                if scan.range_min < r < scan.range_max:
                    if abs(angle) < sector and r < min_ahead:
                        min_ahead = r
                angle += scan.angle_increment
            if min_ahead < self.slow_down_distance:
                return True

        # TODO: integrate OAK detections:
        #  - Check if any person/object detection is in front and within some depth.
        #  - Use depth/point cloud to estimate their distance.

        return False

    @staticmethod
    def extract_pose(odom: Odometry):
        x = odom.pose.pose.position.x
        y = odom.pose.pose.position.y
        q = odom.pose.pose.orientation
        yaw = MainController.quat_to_yaw(q.x, q.y, q.z, q.w)
        return x, y, yaw

    @staticmethod
    def quat_to_yaw(x, y, z, w) -> float:
        """Convert quaternion to yaw."""
        # yaw (z-axis rotation)
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)

    @staticmethod
    def angle_diff(a, b) -> float:
        """Compute smallest difference between two angles."""
        d = a - b
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        return d


def main(args=None):
    rclpy.init(args=args)
    node = MainController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()