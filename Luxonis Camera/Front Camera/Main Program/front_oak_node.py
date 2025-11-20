# front_oak_processor/front_oak_node.py
import math
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import PointCloud2
from sensor_msgs import point_cloud2
from vision_msgs.msg import Detection2DArray
from robot_msgs.msg import FrontCameraSummary  # Custom message defined in your robot_msgs package


class FrontOakProcessor(Node):
    """
    ROS 2 node that post-processes the front OAK-D W outputs.

    Inputs (from Luxonis ROS2/DepthAI driver, via remapping if needed):
      - /front/camera/points      : sensor_msgs/PointCloud2
        Dense depth/point cloud in the camera frame.
      - /front/nn/detections      : vision_msgs/Detection2DArray
        NN-based object/person detections.

    Outputs:
      - /front/oak/summary        : robot_msgs/FrontCameraSummary
        Compact summary with front obstacle distance and person-detection flags.

    Design intent:
      - Run on SER8 (higher compute).
      - Provide a light-weight, low-latency interface for the main controller:
        "Is there anything in front of the camera within X meters?
         Is there a person in the scene?"
    """

    def __init__(self):
        super().__init__('front_oak_processor')

        # ---- Parameters ----
        # Horizontal field of view (FOV) to consider in front of the robot (degrees).
        # Example: 60 -> +/- 30 degrees around camera forward axis.
        self.declare_parameter('fov_deg', 60.0)
        # Maximum distance (meters) to consider in obstacle calculation.
        self.declare_parameter('max_distance', 5.0)
        # Label used in NN detections to identify a "person".
        self.declare_parameter('person_label', 'person')

        # Cache parameter values in radians/float/string for faster access.
        self.fov_rad = math.radians(float(self.get_parameter('fov_deg').value))
        self.max_distance = float(self.get_parameter('max_distance').value)
        self.person_label = str(self.get_parameter('person_label').value)

        # ---- QoS configuration for sensor data ----
        # Use SensorDataQoS equivalent for depth/point cloud: best-effort, shallow queue.
        qos_sensor = rclpy.qos.QoSProfile(
            depth=5,
            reliability=rclpy.qos.QoSReliabilityPolicy.BEST_EFFORT,
            durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE,
        )

        # ---- Subscriptions ----
        # Point cloud (depth) from OAK-D W.
        # NOTE: adjust topic name or remap from the Luxonis launch file if needed.
        self.cloud_sub = self.create_subscription(
            PointCloud2,
            '/front/camera/points',      # Remap to actual Luxonis point cloud topic.
            self.cloud_callback,
            qos_sensor
        )

        # Neural-network detections (e.g., people, obstacles).
        self.det_sub = self.create_subscription(
            Detection2DArray,
            '/front/nn/detections',      # Remap to actual Luxonis detection topic.
            self.detections_callback,
            10  # Reliable, small queue is fine for detections.
        )

        # ---- Publishers ----
        # High-level summary for the main controller and other nodes.
        self.summary_pub = self.create_publisher(
            FrontCameraSummary,
            '/front/oak/summary',
            10  # Reliable, depth=10.
        )

        # ---- Internal state ----
        # Store the most recent NN detections for use when new point clouds arrive.
        self.latest_detections: Optional[Detection2DArray] = None

        self.get_logger().info('FrontOakProcessor initialized')

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def detections_callback(self, msg: Detection2DArray):
        """
        Cache the latest NN detections.

        These will be used in cloud_callback() to set person_detected flags, etc.
        """
        self.latest_detections = msg

    def cloud_callback(self, msg: PointCloud2):
        """
        Called for each incoming depth point cloud.

        We compute:
          - The minimum and mean distance of points within a front cone (FOV)
            and within max_distance.
          - A simple "person detected" flag based on the last NN detections.

        The results are published as FrontCameraSummary on /front/oak/summary.
        """

        # Initialize statistics
        min_dist = float('inf')
        sum_dist = 0.0
        count = 0

        # Iterate through all points in the cloud.
        # NOTE: This assumes the point cloud uses 'x', 'y', 'z' fields and is in
        #       the camera frame with x forward, y left, z down/up (check Luxonis docs).
        for p in point_cloud2.read_points(msg, field_names=('x', 'y', 'z'), skip_nans=True):
            x, y, z = p

            # Only consider points in front of the camera (x > 0).
            if x <= 0.0:
                continue

            # Euclidean distance from the camera origin.
            r = math.sqrt(x * x + y * y + z * z)
            if r > self.max_distance:
                # Ignore points beyond the distance of interest.
                continue

            # Horizontal angle in camera frame.
            # If x is forward and y is left, atan2(y, x) gives yaw relative to forward.
            theta = math.atan2(y, x)
            # Only include points inside the configured FOV cone.
            if abs(theta) > self.fov_rad * 0.5:
                continue

            # Update statistics.
            count += 1
            sum_dist += r
            if r < min_dist:
                min_dist = r

        # Build summary message
        summary = FrontCameraSummary()
        summary.stamp = msg.header.stamp
        summary.frame_id = msg.header.frame_id

        # Populate obstacle-related fields
        if count > 0:
            summary.min_distance = float(min_dist)
            summary.mean_distance = float(sum_dist / count)
            summary.has_obstacle = True
        else:
            summary.min_distance = 0.0
            summary.mean_distance = 0.0
            summary.has_obstacle = False

        # Person-detection fields (high-level safety info)
        summary.person_detected = False
        summary.person_min_distance = 0.0
        num_detections = 0

        if self.latest_detections is not None:
            # Loop through last NN detections; check for "person" label.
            for det in self.latest_detections.detections:
                label = ''
                if det.results:
                    # Many DepthAI/vision_msgs pipelines fill hypothesis.class_id
                    # with the class name or ID; adapt this if your pipeline differs.
                    label = det.results[0].hypothesis.class_id

                if label == self.person_label:
                    summary.person_detected = True
                    # TODO: Use depth / 3D projection to compute actual distance
                    # to the detected person (e.g., by sampling the depth image
                    # at the detection bounding box center).
                    num_detections += 1

        summary.num_points_used = count
        summary.num_detections = num_detections

        # Publish the summary to be consumed by the main controller, etc.
        self.summary_pub.publish(summary)


def main(args=None):
    """
    Standard rclpy entrypoint.
    """
    rclpy.init(args=args)
    node = FrontOakProcessor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Allow clean shutdown on Ctrl+C.
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()