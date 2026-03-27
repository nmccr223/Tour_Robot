# main_control/main_controller_node.py
"""
Main motion controller for SER8.

Fusion model implemented in this file:
- Primary short-range obstacle source: OAK summaries from front/rear processors.
- Secondary coverage source: LD19 LaserScan (/scan), used as fallback and gap filler.

Design intent:
- Keep OAK-D point cloud as the dominant sensor for near-field navigation.
- Retain LD19 as redundant safety and extended coverage when OAK summaries are stale
  or when LiDAR sees an obstacle that camera summaries miss.
"""

import math
import json
from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String
from vision_msgs.msg import Detection2DArray

from apriltag_msgs.msg import AprilTagDetections
from robot_msgs.msg import FrontCameraSummary

from .plc_motor_client import PLCMotorClient


class MainController(Node):
    """Central controller that consumes localization + fused safety signals."""

    def __init__(self):
        super().__init__('main_controller')

        # ------------------------------------------------------------------
        # Parameters controlling motion limits and safety thresholds.
        # ------------------------------------------------------------------
        self.declare_parameter('control_rate_hz', 20.0)
        self.declare_parameter('hard_stop_distance', 0.4)
        self.declare_parameter('slow_down_distance', 1.0)
        self.declare_parameter('max_linear_speed', 0.4)
        self.declare_parameter('max_angular_speed', 0.8)
        self.declare_parameter('motor_host', '192.168.10.2')
        self.declare_parameter('motor_port', 5005)
        self.declare_parameter('use_cmd_vel_topic', False)

        # Sensor-fusion parameters.
        self.declare_parameter('camera_summary_timeout_sec', 0.75)
        self.declare_parameter('prefer_oak_primary', True)
        self.declare_parameter('allow_reverse_motion', True)
        self.declare_parameter('reverse_heading_threshold_deg', 120.0)
        self.declare_parameter('max_reverse_speed', 0.25)
        self.declare_parameter('require_rear_summary_for_reverse', True)

        # LD19 secondary-layer cones for forward/reverse safety checks.
        # Forward cones are centered at 0 deg (robot front).
        # Reverse cones are centered at 180 deg (robot rear).
        self.declare_parameter('ld19_forward_stop_cone_deg', 20.0)
        self.declare_parameter('ld19_reverse_stop_cone_deg', 20.0)
        self.declare_parameter('ld19_forward_slow_cone_deg', 45.0)
        self.declare_parameter('ld19_reverse_slow_cone_deg', 45.0)

        # Fusion debug publication controls.
        # This debug stream is intended for validation and troubleshooting of
        # direction-based sensor delegation and command generation.
        #
        # Topic: /fusion/source_state (std_msgs/String containing JSON)
        #
        # If you prefer to physically disable the feature in production, this
        # entire publisher block can be commented out. In normal usage, set
        # enable_fusion_debug_topic:=False to disable at runtime.
        self.declare_parameter('enable_fusion_debug_topic', True)

        self.control_rate = float(self.get_parameter('control_rate_hz').value)
        self.hard_stop_distance = float(self.get_parameter('hard_stop_distance').value)
        self.slow_down_distance = float(self.get_parameter('slow_down_distance').value)
        self.max_linear_speed = float(self.get_parameter('max_linear_speed').value)
        self.max_angular_speed = float(self.get_parameter('max_angular_speed').value)
        self.use_cmd_vel_topic = bool(self.get_parameter('use_cmd_vel_topic').value)
        self.camera_summary_timeout_sec = float(
            self.get_parameter('camera_summary_timeout_sec').value
        )
        self.prefer_oak_primary = bool(self.get_parameter('prefer_oak_primary').value)
        self.allow_reverse_motion = bool(self.get_parameter('allow_reverse_motion').value)
        self.reverse_heading_threshold_deg = float(
            self.get_parameter('reverse_heading_threshold_deg').value
        )
        self.max_reverse_speed = float(self.get_parameter('max_reverse_speed').value)
        self.require_rear_summary_for_reverse = bool(
            self.get_parameter('require_rear_summary_for_reverse').value
        )
        self.ld19_forward_stop_cone_deg = float(
            self.get_parameter('ld19_forward_stop_cone_deg').value
        )
        self.ld19_reverse_stop_cone_deg = float(
            self.get_parameter('ld19_reverse_stop_cone_deg').value
        )
        self.ld19_forward_slow_cone_deg = float(
            self.get_parameter('ld19_forward_slow_cone_deg').value
        )
        self.ld19_reverse_slow_cone_deg = float(
            self.get_parameter('ld19_reverse_slow_cone_deg').value
        )
        self.enable_fusion_debug_topic = bool(
            self.get_parameter('enable_fusion_debug_topic').value
        )

        # ------------------------------------------------------------------
        # PLC motor client setup.
        # ------------------------------------------------------------------
        motor_host = self.get_parameter('motor_host').value
        motor_port = int(self.get_parameter('motor_port').value)
        self.motor_client = PLCMotorClient(host=motor_host, port=motor_port, timeout=2.0)

        if not self.motor_client.connect():
            self.get_logger().warning(
                f'Failed to connect to PLC at {motor_host}:{motor_port}; '
                'commands will retry automatically.'
            )
        else:
            self.get_logger().info(
                f'Connected to PLC motor controller at {motor_host}:{motor_port}'
            )

        # ------------------------------------------------------------------
        # Internal state cache for latest messages.
        # ------------------------------------------------------------------
        self.last_odom: Optional[Odometry] = None
        self.last_scan: Optional[LaserScan] = None
        self.last_front_detections: Optional[Detection2DArray] = None
        self.last_rear_detections: Optional[Detection2DArray] = None
        self.last_apriltags: Optional[AprilTagDetections] = None

        # New fused-summary inputs from OAK processor nodes.
        self.last_front_summary: Optional[FrontCameraSummary] = None
        self.last_rear_summary: Optional[FrontCameraSummary] = None

        # Goal (set externally by higher-level planner or UI).
        self.goal_x = 0.0
        self.goal_y = 0.0
        self.goal_yaw = 0.0
        self.has_goal = False

        # ------------------------------------------------------------------
        # Subscriptions.
        # ------------------------------------------------------------------
        self.create_subscription(Odometry, '/odometry/filtered', self.odom_callback, 10)

        # Secondary sensor: LD19 scan from CM5.
        self.create_subscription(LaserScan, '/scan', self.scan_callback, 10)

        # Primary sensor summaries from SER8 camera processors.
        self.create_subscription(
            FrontCameraSummary,
            '/front/oak/summary',
            self.front_summary_callback,
            10,
        )
        self.create_subscription(
            FrontCameraSummary,
            '/rear/oak/summary',
            self.rear_summary_callback,
            10,
        )

        # Existing detection feeds retained for future richer behavior.
        self.create_subscription(
            Detection2DArray,
            '/front/oak/detections',
            self.front_det_callback,
            10,
        )
        self.create_subscription(
            Detection2DArray,
            '/rear/oak/detections',
            self.rear_det_callback,
            10,
        )

        self.create_subscription(
            AprilTagDetections,
            '/apriltag_detections',
            self.apriltag_callback,
            10,
        )

        # Optional publication path if motion is consumed as cmd_vel downstream.
        self.cmd_vel_pub = None
        if self.use_cmd_vel_topic:
            self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Optional fusion debug stream.
        self.fusion_debug_pub = None
        if self.enable_fusion_debug_topic:
            self.fusion_debug_pub = self.create_publisher(String, '/fusion/source_state', 10)

        # Main control loop timer.
        self.control_timer = self.create_timer(1.0 / self.control_rate, self.control_loop)

        self.seq = 0
        self.get_logger().info(
            'MainController initialized with OAK-primary + LD19-secondary fusion.'
        )
        if self.enable_fusion_debug_topic:
            self.get_logger().info(
                'Fusion debug topic enabled: /fusion/source_state (JSON in std_msgs/String)'
            )

    # ------------------------------------------------------------------
    # State update callbacks.
    # ------------------------------------------------------------------

    def odom_callback(self, msg: Odometry) -> None:
        self.last_odom = msg

    def scan_callback(self, msg: LaserScan) -> None:
        self.last_scan = msg

    def front_summary_callback(self, msg: FrontCameraSummary) -> None:
        self.last_front_summary = msg

    def rear_summary_callback(self, msg: FrontCameraSummary) -> None:
        self.last_rear_summary = msg

    def front_det_callback(self, msg: Detection2DArray) -> None:
        self.last_front_detections = msg

    def rear_det_callback(self, msg: Detection2DArray) -> None:
        self.last_rear_detections = msg

    def apriltag_callback(self, msg: AprilTagDetections) -> None:
        self.last_apriltags = msg
        # TODO: use tags to update goals or improve localization.

    # ------------------------------------------------------------------
    # Goal management.
    # ------------------------------------------------------------------

    def set_goal(self, x: float, y: float, yaw: float) -> None:
        self.goal_x = x
        self.goal_y = y
        self.goal_yaw = yaw
        self.has_goal = True
        self.get_logger().info(f'Set goal: x={x:.2f}, y={y:.2f}, yaw={yaw:.2f}')

    # ------------------------------------------------------------------
    # Control loop.
    # ------------------------------------------------------------------

    def control_loop(self) -> None:
        if not self.has_goal or self.last_odom is None:
            return

        # Require at least one obstacle source before issuing motion commands.
        if not self.has_any_obstacle_source():
            return

        pose_x, pose_y, pose_yaw = self.extract_pose(self.last_odom)

        # Determine intended motion direction for this cycle.
        # The same flag is used by command computation and debug reporting.
        dx = self.goal_x - pose_x
        dy = self.goal_y - pose_y
        goal_heading = math.atan2(dy, dx)
        drive_in_reverse = self.should_drive_in_reverse(goal_heading, pose_yaw)

        v_cmd, w_cmd = self.compute_command(pose_x, pose_y, pose_yaw)

        # Clamp motion command to configured safety limits.
        v_cmd = max(min(v_cmd, self.max_linear_speed), -self.max_linear_speed)
        w_cmd = max(min(w_cmd, self.max_angular_speed), -self.max_angular_speed)

        if self.use_cmd_vel_topic and self.cmd_vel_pub is not None:
            twist = Twist()
            twist.linear.x = v_cmd
            twist.angular.z = w_cmd
            self.cmd_vel_pub.publish(twist)
        else:
            # Normalize to controller interface expected range.
            linear_normalized = v_cmd / self.max_linear_speed if self.max_linear_speed > 0 else 0.0
            angular_normalized = w_cmd / self.max_angular_speed if self.max_angular_speed > 0 else 0.0

            if not self.motor_client.set_velocity(linear_normalized, angular_normalized):
                self.get_logger().warning('Failed to send velocity command to PLC.')

            # Health check every ~1 second at 20 Hz default.
            if self.seq % 20 == 0 and not self.motor_client.is_healthy():
                self.get_logger().error(
                    'PLC motor controller unhealthy; inspect E-stop and drive fault state.'
                )

            self.seq += 1

        # Publish post-command fusion state for diagnostics.
        self.publish_fusion_debug(v_cmd, w_cmd, pose_x, pose_y, pose_yaw, drive_in_reverse)

    # ------------------------------------------------------------------
    # Core decision logic.
    # ------------------------------------------------------------------

    def compute_command(self, x: float, y: float, yaw: float):
        """Compute linear and angular velocity command from fused perception."""

        dx = self.goal_x - x
        dy = self.goal_y - y
        goal_dist = math.hypot(dx, dy)

        if goal_dist < 0.1:
            yaw_error = self.angle_diff(self.goal_yaw, yaw)
            if abs(yaw_error) < math.radians(5.0):
                return 0.0, 0.0
            return 0.0, 0.5 * yaw_error

        goal_heading = math.atan2(dy, dx)
        drive_in_reverse = self.should_drive_in_reverse(goal_heading, yaw)

        # Hard stop has highest priority over all other behaviors.
        if self.is_emergency_stop(drive_in_reverse):
            return 0.0, 0.0

        # Heading controller depends on intended motion direction.
        if drive_in_reverse:
            # Keep robot rear-facing toward goal while backing up.
            desired_heading = self.wrap_angle(goal_heading + math.pi)
        else:
            desired_heading = goal_heading
        heading_error = self.angle_diff(desired_heading, yaw)

        # Speed policy:
        # - nominal forward speed when clear
        # - reduced speed when fused logic indicates caution zone
        if drive_in_reverse:
            base_speed = min(0.3, max(self.max_reverse_speed, 0.0))
            speed_sign = -1.0
        else:
            base_speed = 0.3
            speed_sign = 1.0

        v = speed_sign * base_speed * (1.0 if not self.is_slow_down_zone(drive_in_reverse) else 0.3)
        w = 1.0 * heading_error

        return v, w

    def should_drive_in_reverse(self, goal_heading: float, yaw: float) -> bool:
        """
        Decide whether the controller should command reverse motion.

        Strategy:
        - If reverse mode is enabled and the goal lies substantially behind the
          robot (angular difference above threshold), drive in reverse.
        - Otherwise drive forward.
        """
        if not self.allow_reverse_motion:
            return False

        heading_error_to_goal = abs(self.angle_diff(goal_heading, yaw))
        reverse_threshold = math.radians(self.reverse_heading_threshold_deg)
        return heading_error_to_goal >= reverse_threshold

    def publish_fusion_debug(
        self,
        v_cmd: float,
        w_cmd: float,
        x: float,
        y: float,
        yaw: float,
        drive_in_reverse: bool,
    ) -> None:
        """
        Publish per-cycle fusion and command state for operator diagnostics.

        What this topic is for:
        - Verifying which camera stream is acting as primary for the current
          direction (front for forward, rear for reverse).
        - Confirming LD19 is active as the secondary layer in both directions.
        - Explaining why the controller is slowing or stopping.
        - Comparing command outputs while tuning thresholds.
        """
        if self.fusion_debug_pub is None:
            return

        front_fresh = self.summary_is_fresh(self.last_front_summary)
        rear_fresh = self.summary_is_fresh(self.last_rear_summary)
        ld19_available = self.last_scan is not None

        if drive_in_reverse:
            primary_sensor = 'rear_oak_summary'
            ld19_stop_min = self.min_scan_in_sector(180.0, self.ld19_reverse_stop_cone_deg)
            ld19_slow_min = self.min_scan_in_sector(180.0, self.ld19_reverse_slow_cone_deg)
        else:
            primary_sensor = 'front_oak_summary'
            ld19_stop_min = self.min_scan_in_sector(0.0, self.ld19_forward_stop_cone_deg)
            ld19_slow_min = self.min_scan_in_sector(0.0, self.ld19_forward_slow_cone_deg)

        payload = {
            'mode': 'reverse' if drive_in_reverse else 'forward',
            'primary_sensor': primary_sensor,
            'secondary_sensor': 'ld19_scan',
            'front_summary_fresh': front_fresh,
            'rear_summary_fresh': rear_fresh,
            'ld19_available': ld19_available,
            'ld19_stop_min_distance': 0.0 if math.isinf(ld19_stop_min) else float(ld19_stop_min),
            'ld19_slow_min_distance': 0.0 if math.isinf(ld19_slow_min) else float(ld19_slow_min),
            'hard_stop_active': self.is_emergency_stop(drive_in_reverse),
            'slow_zone_active': self.is_slow_down_zone(drive_in_reverse),
            'cmd_linear': float(v_cmd),
            'cmd_angular': float(w_cmd),
            'pose_x': float(x),
            'pose_y': float(y),
            'pose_yaw': float(yaw),
        }

        msg = String()
        msg.data = json.dumps(payload)
        self.fusion_debug_pub.publish(msg)

    # ------------------------------------------------------------------
    # Fusion helpers.
    # ------------------------------------------------------------------

    def has_any_obstacle_source(self) -> bool:
        """Return True when at least one obstacle source is available."""
        if self.last_scan is not None:
            return True
        if self.summary_is_fresh(self.last_front_summary):
            return True
        if self.summary_is_fresh(self.last_rear_summary):
            return True
        return False

    def summary_is_fresh(self, summary: Optional[FrontCameraSummary]) -> bool:
        """Validate that a camera summary exists and is recent enough to trust."""
        if summary is None:
            return False

        # Compare message timestamp to current ROS clock to avoid stale readings.
        now_ns = self.get_clock().now().nanoseconds
        msg_ns = int(summary.stamp.sec) * 1_000_000_000 + int(summary.stamp.nanosec)
        age_sec = (now_ns - msg_ns) / 1_000_000_000.0

        # Negative age can happen during clock jumps; treat as stale for safety.
        if age_sec < 0.0:
            return False
        return age_sec <= self.camera_summary_timeout_sec

    def min_scan_in_sector(self, center_deg: float, half_width_deg: float) -> float:
        """
        Return minimum valid LD19 range inside a configurable angular sector.

        Parameters are in degrees in the robot base frame convention:
        - center_deg=0   -> forward sector
        - center_deg=180 -> rear sector
        """
        scan = self.last_scan
        if scan is None:
            return float('inf')

        center = math.radians(center_deg)
        half_width = math.radians(half_width_deg)
        angle = scan.angle_min
        min_distance = float('inf')
        for distance in scan.ranges:
            if scan.range_min < distance < scan.range_max:
                if abs(self.angle_diff(angle, center)) < half_width:
                    min_distance = min(min_distance, distance)
            angle += scan.angle_increment
        return min_distance

    def is_emergency_stop(self, drive_in_reverse: bool) -> bool:
        """
        Return True if fused perception indicates an immediate stop condition.

        Priority order:
        Forward mode:
        1) Fresh front OAK summary (primary sensor).
        2) LD19 front sector (secondary/fallback sensor).

        Reverse mode:
        1) Fresh rear OAK summary (primary sensor).
        2) LD19 rear sector (secondary/fallback sensor).
        3) If configured, block reverse when rear summary is stale.
        """
        if drive_in_reverse:
            rear_fresh = self.summary_is_fresh(self.last_rear_summary)
            if rear_fresh and self.last_rear_summary is not None:
                rear = self.last_rear_summary
                if rear.has_obstacle and 0.0 < rear.min_distance < self.hard_stop_distance:
                    return True
                if rear.person_detected and 0.0 < rear.person_min_distance < self.hard_stop_distance:
                    return True

            # LD19 remains active as secondary layer in reverse mode.
            if self.min_scan_in_sector(180.0, self.ld19_reverse_stop_cone_deg) < self.hard_stop_distance:
                return True

            # Safety policy: do not reverse blind when rear summary is mandatory.
            if self.require_rear_summary_for_reverse and not rear_fresh:
                return True
            return False

        front_fresh = self.summary_is_fresh(self.last_front_summary)

        # Primary OAK stop gate for forward operation.
        if front_fresh and self.last_front_summary is not None:
            front = self.last_front_summary
            if front.has_obstacle and 0.0 < front.min_distance < self.hard_stop_distance:
                return True
            if front.person_detected and 0.0 < front.person_min_distance < self.hard_stop_distance:
                return True

        # Secondary LD19 stop gate (forward-facing redundancy).
        if self.min_scan_in_sector(0.0, self.ld19_forward_stop_cone_deg) < self.hard_stop_distance:
            return True

        return False

    def is_slow_down_zone(self, drive_in_reverse: bool) -> bool:
        """
        Return True if fused perception indicates caution-speed driving.

        Logic:
        - Forward mode: front OAK summary primary, LD19 secondary.
        - Reverse mode: rear OAK summary primary, LD19 secondary.
        """
        if drive_in_reverse:
            rear_fresh = self.summary_is_fresh(self.last_rear_summary)
            if rear_fresh and self.last_rear_summary is not None:
                rear = self.last_rear_summary
                if rear.has_obstacle and 0.0 < rear.min_distance < self.slow_down_distance:
                    return True
                if rear.person_detected:
                    return True

            # LD19 remains active as secondary layer during reverse navigation.
            if self.min_scan_in_sector(180.0, self.ld19_reverse_slow_cone_deg) < self.slow_down_distance:
                return True

            if self.require_rear_summary_for_reverse and not rear_fresh:
                return True
            return False

        front_fresh = self.summary_is_fresh(self.last_front_summary)

        if self.prefer_oak_primary and front_fresh and self.last_front_summary is not None:
            front = self.last_front_summary
            if front.has_obstacle and 0.0 < front.min_distance < self.slow_down_distance:
                return True
            if front.person_detected:
                return True

        # If front summary is stale/unavailable, LD19 still provides slowdown coverage.
        if self.min_scan_in_sector(0.0, self.ld19_forward_slow_cone_deg) < self.slow_down_distance:
            return True

        # If preference is disabled, OAK still contributes as additional signal.
        if not self.prefer_oak_primary and front_fresh and self.last_front_summary is not None:
            front = self.last_front_summary
            if front.has_obstacle and 0.0 < front.min_distance < self.slow_down_distance:
                return True
            if front.person_detected:
                return True

        return False

    @staticmethod
    def wrap_angle(angle: float) -> float:
        """Wrap angle to [-pi, pi] for stable heading computations."""
        while angle > math.pi:
            angle -= 2 * math.pi
        while angle < -math.pi:
            angle += 2 * math.pi
        return angle

    # ------------------------------------------------------------------
    # Math helpers.
    # ------------------------------------------------------------------

    @staticmethod
    def extract_pose(odom: Odometry):
        x = odom.pose.pose.position.x
        y = odom.pose.pose.position.y
        q = odom.pose.pose.orientation
        yaw = MainController.quat_to_yaw(q.x, q.y, q.z, q.w)
        return x, y, yaw

    @staticmethod
    def quat_to_yaw(x, y, z, w) -> float:
        """Convert quaternion orientation to yaw angle (radians)."""
        siny_cosp = 2.0 * (w * z + x * y)
        cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
        return math.atan2(siny_cosp, cosy_cosp)

    @staticmethod
    def angle_diff(a, b) -> float:
        """Return wrapped smallest angular difference a-b in radians."""
        d = a - b
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        return d


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MainController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()