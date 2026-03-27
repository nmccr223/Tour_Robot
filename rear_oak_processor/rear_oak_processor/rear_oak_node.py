"""
Rear OAK-D Lite processor node.

Purpose:
- Consume rear depth point cloud and optional detections.
- Publish a compact rear safety summary for reversing and blind-spot coverage.
- Keep processing light by allowing frame skipping when needed.
"""

import math
from typing import Optional

import rclpy
from rclpy.node import Node

from sensor_msgs.msg import PointCloud2
from sensor_msgs import point_cloud2
from vision_msgs.msg import Detection2DArray
from robot_msgs.msg import FrontCameraSummary


class RearOakProcessor(Node):
    """Generate a compact rear-camera safety summary from OAK-D topics."""

    def __init__(self):
        super().__init__('rear_oak_processor')

        # ------------------------------------------------------------------
        # Parameters
        # ------------------------------------------------------------------
        # Wider rear cone supports safer backing maneuvers.
        self.declare_parameter('fov_deg', 90.0)

        # Rear safety region is shorter than front navigation region.
        self.declare_parameter('max_distance', 3.0)

        # Detection class label treated as person.
        self.declare_parameter('person_label', 'person')

        # Dedicated rear-camera stream topics so rear perception is isolated
        # from front-camera data paths.
        self.declare_parameter('input_cloud_topic', '/rear/oak/points')
        self.declare_parameter('input_detections_topic', '/rear/oak/detections')
        self.declare_parameter('output_summary_topic', '/rear/oak/summary')

        # Optional load shedding: process every (frame_skip + 1)-th cloud.
        self.declare_parameter('frame_skip', 0)

        self.fov_rad = math.radians(float(self.get_parameter('fov_deg').value))
        self.max_distance = float(self.get_parameter('max_distance').value)
        self.person_label = str(self.get_parameter('person_label').value)
        self.frame_skip = int(self.get_parameter('frame_skip').value)
        input_cloud_topic = str(self.get_parameter('input_cloud_topic').value)
        input_detections_topic = str(self.get_parameter('input_detections_topic').value)
        output_summary_topic = str(self.get_parameter('output_summary_topic').value)
        self.frame_counter = 0

        # Match sensor-data QoS published by point cloud source.
        qos_sensor = rclpy.qos.QoSProfile(
            depth=5,
            reliability=rclpy.qos.QoSReliabilityPolicy.BEST_EFFORT,
            durability=rclpy.qos.QoSDurabilityPolicy.VOLATILE,
        )

        self.cloud_sub = self.create_subscription(
            PointCloud2,
            input_cloud_topic,
            self.cloud_callback,
            qos_sensor,
        )

        self.det_sub = self.create_subscription(
            Detection2DArray,
            input_detections_topic,
            self.detections_callback,
            10,
        )

        self.summary_pub = self.create_publisher(
            FrontCameraSummary,
            output_summary_topic,
            10,
        )

        self.latest_detections: Optional[Detection2DArray] = None

        self.get_logger().info(
            f'RearOakProcessor started: cloud={input_cloud_topic}, detections={input_detections_topic}, '
            f'summary={output_summary_topic}'
        )

    def detections_callback(self, msg: Detection2DArray) -> None:
        """Store latest detections for use with the next cloud callback."""
        self.latest_detections = msg

    def cloud_callback(self, msg: PointCloud2) -> None:
        """Compute rear obstacle statistics and publish a summary message."""
        if self.frame_skip > 0:
            self.frame_counter += 1
            if self.frame_counter % (self.frame_skip + 1) != 0:
                return

        min_dist = float('inf')
        sum_dist = 0.0
        count = 0

        # Filtering is analogous to the front node and assumes +x is forward in
        # the camera frame after mounting/orientation setup.
        for x, y, z in point_cloud2.read_points(
            msg,
            field_names=('x', 'y', 'z'),
            skip_nans=True,
        ):
            if x <= 0.0:
                continue

            distance = math.sqrt(x * x + y * y + z * z)
            if distance > self.max_distance:
                continue

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
    node = RearOakProcessor()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
