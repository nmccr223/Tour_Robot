"""
Front OAK-D W processor node.

Purpose:
- Consume depth point cloud and neural-network detections from the front OAK-D camera.
- Reduce high-bandwidth sensor streams into a compact summary message.
- Provide low-latency obstacle and person-presence signals to the main controller.

Why this node exists:
- The raw PointCloud2 topic can be expensive to process in every downstream node.
- Navigation logic primarily needs a few safety metrics, not the entire cloud.
- This node centralizes the cloud filtering and summary generation.
"""

import math
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import PointCloud2
from sensor_msgs import point_cloud2
from vision_msgs.msg import Detection2DArray
from robot_msgs.msg import FrontCameraSummary


class FrontOakProcessor(Node):
    """Generate a compact front-camera safety summary from OAK-D topics."""

    def __init__(self):
        super().__init__('front_oak_processor')

        # ------------------------------------------------------------------
        # Parameters
        # ------------------------------------------------------------------
        # Horizontal field of view used for obstacle statistics (degrees).
        # Only points inside this angular cone are considered relevant.
        self.declare_parameter('fov_deg', 60.0)

        # Maximum point distance (meters) included in obstacle statistics.
        # This bounds computation to the useful near/mid-range area.
        self.declare_parameter('max_distance', 5.0)

        # Detection class label treated as a person.
        # The value depends on the detector's class naming convention.
        self.declare_parameter('person_label', 'person')

        # Dedicated front-camera stream topics.
        # These are parameters so front and rear streams can be fully separated
        # without code changes and can be remapped per deployment.
        self.declare_parameter('input_cloud_topic', '/front/oak/points')
        self.declare_parameter('input_detections_topic', '/front/oak/detections')
        self.declare_parameter('output_summary_topic', '/front/oak/summary')

        self.fov_rad = math.radians(float(self.get_parameter('fov_deg').value))
        self.max_distance = float(self.get_parameter('max_distance').value)
        self.person_label = str(self.get_parameter('person_label').value)
        input_cloud_topic = str(self.get_parameter('input_cloud_topic').value)
        input_detections_topic = str(self.get_parameter('input_detections_topic').value)
        output_summary_topic = str(self.get_parameter('output_summary_topic').value)

        # ------------------------------------------------------------------
        # QoS
        # ------------------------------------------------------------------
        # PointCloud2 usually uses best-effort sensor QoS to minimize latency.
        # Matching this policy avoids incompatible QoS subscriptions.
        qos_sensor = rclpy.qos.QoSProfile(
            depth=5,
            reliability=rclpy.qos.QoSReliabilityPolicy.BEST_EFFORT,
            durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE,
        )

        # ------------------------------------------------------------------
        # Subscriptions
        # ------------------------------------------------------------------
        # Input cloud topic name is kept generic and can be remapped in launch.
        self.cloud_sub = self.create_subscription(
            PointCloud2,
            input_cloud_topic,
            self.cloud_callback,
            qos_sensor,
        )

        # Input detections from DepthAI/vision pipeline.
        self.det_sub = self.create_subscription(
            Detection2DArray,
            input_detections_topic,
            self.detections_callback,
            10,
        )

        # ------------------------------------------------------------------
        # Publisher
        # ------------------------------------------------------------------
        # Summary topic used by main controller fusion logic.
        self.summary_pub = self.create_publisher(
            FrontCameraSummary,
            output_summary_topic,
            10,
        )

        # Cache last detections so each cloud can be paired with recent NN info.
        self.latest_detections: Optional[Detection2DArray] = None

        self.get_logger().info(
            f'FrontOakProcessor started: cloud={input_cloud_topic}, detections={input_detections_topic}, '
            f'summary={output_summary_topic}'
        )

    def detections_callback(self, msg: Detection2DArray) -> None:
        """Store latest detections for use when processing incoming clouds."""
        self.latest_detections = msg

    def cloud_callback(self, msg: PointCloud2) -> None:
        """
        Compute summary metrics from the current cloud.

        Outputs include:
        - minimum obstacle distance in front cone
        - mean obstacle distance in front cone
        - obstacle presence flag
        - person-detected flag from latest NN detections
        """
        min_dist = float('inf')
        sum_dist = 0.0
        count = 0

        # Iterate XYZ points and keep only points that represent forward obstacles
        # within configured FOV and distance limits.
        for x, y, z in point_cloud2.read_points(
            msg,
            field_names=('x', 'y', 'z'),
            skip_nans=True,
        ):
            # Ignore points behind the camera frame origin.
            if x <= 0.0:
                continue

            # Euclidean distance from camera origin.
            distance = math.sqrt(x * x + y * y + z * z)
            if distance > self.max_distance:
                continue

            # Keep points only within horizontal FOV cone.
            heading = math.atan2(y, x)
            if abs(heading) > self.fov_rad * 0.5:
                continue

            count += 1
            sum_dist += distance
            if distance < min_dist:
                min_dist = distance

        summary = FrontCameraSummary()
        summary.stamp = msg.header.stamp
        summary.frame_id = msg.header.frame_id

        if count > 0:
            summary.has_obstacle = True
            summary.min_distance = float(min_dist)
            summary.mean_distance = float(sum_dist / count)
        else:
            summary.has_obstacle = False
            summary.min_distance = 0.0
            summary.mean_distance = 0.0

        # Person detection is derived from the latest detection message.
        # Distance-to-person can be added later using depth projection.
        summary.person_detected = False
        summary.person_min_distance = 0.0
        summary.num_detections = 0

        if self.latest_detections is not None:
            for det in self.latest_detections.detections:
                label = ''
                if det.results:
                    label = det.results[0].hypothesis.class_id
                if label == self.person_label:
                    summary.person_detected = True
                    summary.num_detections += 1

        summary.num_points_used = count
        self.summary_pub.publish(summary)


def main(args=None) -> None:
    """Standard ROS2 Python entrypoint."""
    rclpy.init(args=args)
    node = FrontOakProcessor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
