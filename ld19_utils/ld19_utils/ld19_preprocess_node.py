"""
LD19 preprocess node.

Purpose:
- Subscribe to the raw LD19 LaserScan stream.
- Publish compact scan summary metrics for monitoring and debugging.

Note:
- This node does not replace /scan; it augments it with /ld19/summary.
"""

import math
from typing import List

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan

from robot_msgs.msg import LidarScanSummary


class Ld19PreprocessNode(Node):
    """Compute per-scan statistics and sector minima from raw LaserScan."""

    def __init__(self) -> None:
        super().__init__('ld19_preprocess')

        # ------------------------------------------------------------------
        # Parameters
        # ------------------------------------------------------------------
        self.declare_parameter('input_scan_topic', '/ld19/scan')
        self.declare_parameter('output_summary_topic', '/ld19/summary')
        self.declare_parameter('num_sectors', 5)

        input_topic = self.get_parameter('input_scan_topic').get_parameter_value().string_value
        output_topic = self.get_parameter('output_summary_topic').get_parameter_value().string_value
        self.num_sectors = self.get_parameter('num_sectors').get_parameter_value().integer_value

        if self.num_sectors <= 0:
            self.get_logger().warning('num_sectors must be > 0; falling back to 5.')
            self.num_sectors = 5

        self.scan_sub = self.create_subscription(
            LaserScan,
            input_topic,
            self.scan_callback,
            10,
        )

        self.summary_pub = self.create_publisher(
            LidarScanSummary,
            output_topic,
            10,
        )

        self.get_logger().info(
            f'LD19 preprocess started. input={input_topic}, output={output_topic}, num_sectors={self.num_sectors}'
        )

    def scan_callback(self, msg: LaserScan) -> None:
        """Summarize one scan and publish LidarScanSummary."""
        ranges = list(msg.ranges)
        if not ranges:
            return

        valid_ranges: List[float] = []
        for r in ranges:
            if math.isfinite(r) and r > 0.0:
                valid_ranges.append(r)

        summary = LidarScanSummary()
        summary.stamp = msg.header.stamp
        summary.frame_id = msg.header.frame_id
        summary.num_sectors = self.num_sectors

        if valid_ranges:
            summary.num_readings = len(valid_ranges)
            summary.min_distance = min(valid_ranges)
            summary.max_distance = max(valid_ranges)
            summary.mean_distance = float(sum(valid_ranges) / len(valid_ranges))
        else:
            summary.num_readings = 0
            summary.min_distance = 0.0
            summary.max_distance = 0.0
            summary.mean_distance = 0.0

        # Sectorized minima give a lightweight directional obstacle profile.
        sector_mins = [0.0 for _ in range(self.num_sectors)]

        angle_min = msg.angle_min
        angle_increment = msg.angle_increment

        if angle_increment == 0.0:
            # Fallback path for malformed scans: bucket by sample index.
            total = len(ranges)
            for i, r in enumerate(ranges):
                if not (math.isfinite(r) and r > 0.0):
                    continue
                sector_index = min(int(i * self.num_sectors / total), self.num_sectors - 1)
                current_min = sector_mins[sector_index]
                if current_min == 0.0 or r < current_min:
                    sector_mins[sector_index] = r
        else:
            # Normal path: bucket by angle position in scan span.
            total_angle = abs(angle_increment) * len(ranges)
            if total_angle <= 0.0:
                total_angle = 1.0

            for i, r in enumerate(ranges):
                if not (math.isfinite(r) and r > 0.0):
                    continue
                angle = angle_min + i * angle_increment
                norm = (angle - angle_min) / total_angle
                norm = max(0.0, min(1.0, norm))
                sector_index = min(int(norm * self.num_sectors), self.num_sectors - 1)
                current_min = sector_mins[sector_index]
                if current_min == 0.0 or r < current_min:
                    sector_mins[sector_index] = r

        summary.sector_min_distances = sector_mins
        self.summary_pub.publish(summary)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Ld19PreprocessNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
