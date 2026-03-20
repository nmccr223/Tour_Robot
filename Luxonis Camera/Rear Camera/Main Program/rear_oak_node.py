# rear_oak_processor/rear_oak_node.py
"""
Rear OAK-D Lite processor node.

This node runs on the SER8 and consumes:
  - A depth point cloud from the rear OAK-D Lite camera.
  - (Optionally) NN detections from the rear camera.

It produces a compact summary message that the main controller can use to decide:
  - Is there any obstacle behind the robot within a short distance?
  - Optionally, is there a person behind the robot?

Compared to the front camera pipeline, this is intentionally lighter:
  - Shorter max distance (backup zone only).
  - Optional frame skipping to reduce CPU load.

This node is also a candidate for a future C++ port if Python CPU usage
becomes critical, but is currently implemented in Python for faster iteration.
"""

import math
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import PointCloud2
from sensor_msgs import point_cloud2
from vision_msgs.msg import Detection2DArray
from robot_msgs.msg import FrontCameraSummary  # Reuse same msg type


class RearOakProcessor(Node):
    """
    SER8-side processor for the rear OAK-D Lite camera.

    Inputs (from Luxonis ROS2/DepthAI driver, via remapping if needed):
      - /rear/camera/points      : sensor_msgs/PointCloud2
        Dense depth/point cloud in the rear camera frame.
      - /rear/nn/detections      : vision_msgs/Detection2DArray (optional)
        NN-based object/person detections.

    Output:
      - /rear/oak/summary        : robot_msgs/FrontCameraSummary
        Compact summary with:
          - min/mean distance of obstacles behind the robot
          - optional person_detected flag
    """

    def __init__(self):
        super().__init__('rear_oak_processor')

        # ------------------------------------------------------------------
        # Parameters
        # ------------------------------------------------------------------
        # Horizontal field of view (degrees) for rear safety.
        self.declare_parameter('fov_deg', 90.0)        # +/- 45 deg
        # Max distance (meters) for backing-up safety checks.
        self.declare_parameter('max_distance', 3.0)
        # NN label used to mark "person".
        self.declare_parameter('person_label', 'person')
        # Process every (frame_skip + 1)-th frame to save CPU (0 = every frame).
        self.declare_parameter('frame_skip', 0)

        self.fov_rad = math.radians(float(self.get_parameter('fov_deg').value))
        self.max_distance = float(self.get_parameter('max_distance').value)
        self.person_label = str(self.get_parameter('person_label').value)
        self.frame_skip = int(self.get_parameter('frame_skip').value)
        self.frame_counter = 0

        # QoS for depth data: equivalent to SensorDataQoS.
        qos_sensor = rclpy.qos.QoSProfile(
            depth=5,
            reliability=rclpy.qos.QoSReliabilityPolicy.BEST_EFFORT,
            durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE,
        )

        # ------------------------------------------------------------------
        # Subscriptions
        # ------------------------------------------------------------------
        # Rear depth point cloud: topic name will be remapped in the launch file
        # from whatever depthai-ros publishes (e.g. /oak/points).
        self.cloud_sub = self.create_subscription(
            PointCloud2,
            '/rear/camera/points',
            self.cloud_callback,
            qos_sensor,
        )

        # Optional NN detections from rear camera.
        self.det_sub = self.create_subscription(
            Detection2DArray,
            '/rear/nn/detections',
            self.detections_callback,
            10,
        )

        # ------------------------------------------------------------------
        # Publisher
        # ------------------------------------------------------------------
        self.summary_pub = self.create_publisher(
            FrontCameraSummary,
            '/rear/oak/summary',
            10,
        )

        # Internal detection cache.
        self.latest_detections: Optional[Detection2DArray] = None

        self.get_logger().info('RearOakProcessor initialized')

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def detections_callback(self, msg: Detection2DArray):
        """Cache latest NN detections from the rear camera."""
        self.latest_detections = msg

    def cloud_callback(self, msg: PointCloud2):
        """
        Process an incoming rear depth point cloud.

        Logic:
          - Optionally skip frames (frame_skip) to save CPU.
          - Filter points to those within a rear FOV cone and max_distance.
          - Compute min and mean distance.
          - Combine with NN detections to fill summary.
        """
        if self.frame_skip > 0:
            self.frame_counter += 1
            if self.frame_counter % (self.frame_skip + 1) != 0:
                return

        min_dist = float('inf')
        sum_dist = 0.0
        count = 0

        # NOTE: adjust for your actual rear camera TF:
        # This assumes +x in the rear camera frame is the "danger" direction
        # (toward the robot). If the axes differ, update this sign check.
        for x, y, z in point_cloud2.read_points(
            msg, field_names=('x', 'y', 'z'), skip_nans=True
        ):
            if x <= 0.0:
                continue

            r = math.sqrt(x * x + y * y + z * z)
            if r > self.max_distance:
                continue

            theta = math.atan2(y, x)
            if abs(theta) > self.fov_rad * 0.5:
                continue

            count += 1
            sum_dist += r
            if r < min_dist:
                min_dist = r

        summary = FrontCameraSummary()
        summary.stamp = msg.header.stamp
        summary.frame_id = msg.header.frame_id

        if count > 0:
            summary.min_distance = float(min_dist)
            summary.mean_distance = float(sum_dist / count)
            summary.has_obstacle = True
        else:
            summary.min_distance = 0.0
            summary.mean_distance = 0.0
            summary.has_obstacle = False

        # Optional: simple person-detection flag from NN results.
        summary.person_detected = False
        summary.person_min_distance = 0.0
        num_detections = 0

        if self.latest_detections is not None:
            for det in self.latest_detections.detections:
                label = ''
                if det.results:
                    label = det.results[0].hypothesis.class_id
                if label == self.person_label:
                    summary.person_detected = True
                    # TODO: estimate actual distance using depth and bbox if needed.
                    num_detections += 1

        summary.num_points_used = count
        summary.num_detections = num_detections

        self.summary_pub.publish(summary)


def main(args=None):
    """Standard rclpy entrypoint for the rear camera processor."""
    rclpy.init(args=args)
    node = RearOakProcessor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()