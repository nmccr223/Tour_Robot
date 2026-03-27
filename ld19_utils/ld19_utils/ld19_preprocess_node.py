"""
LD19 preprocess node.

Purpose:
- Subscribe to the raw LD19 LaserScan stream.
- Publish a filtered LaserScan with blocked sectors masked.
- Publish compact scan summary metrics for monitoring and debugging.
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
        self.declare_parameter('output_scan_topic', '/scan')
        self.declare_parameter('output_summary_topic', '/ld19/summary')
        self.declare_parameter('num_sectors', 5)
        self.declare_parameter('blocked_center_deg', 180.0)
        self.declare_parameter('blocked_half_width_deg', 90.0)
        self.declare_parameter('blocked_extra_margin_deg', 0.0)
        self.declare_parameter('min_valid_range_m', 0.0)

        input_topic = self.get_parameter('input_scan_topic').get_parameter_value().string_value
        output_scan_topic = self.get_parameter('output_scan_topic').get_parameter_value().string_value
        output_topic = self.get_parameter('output_summary_topic').get_parameter_value().string_value
        self.num_sectors = self.get_parameter('num_sectors').get_parameter_value().integer_value
        self.blocked_center_deg = float(self.get_parameter('blocked_center_deg').value)
        self.blocked_half_width_deg = float(self.get_parameter('blocked_half_width_deg').value)
        self.blocked_extra_margin_deg = float(self.get_parameter('blocked_extra_margin_deg').value)
        self.min_valid_range_m = float(self.get_parameter('min_valid_range_m').value)

        if self.num_sectors <= 0:
            self.get_logger().warning('num_sectors must be > 0; falling back to 5.')
            self.num_sectors = 5
        if self.blocked_half_width_deg < 0.0:
            self.get_logger().warning('blocked_half_width_deg must be >= 0; falling back to 90.')
            self.blocked_half_width_deg = 90.0
        if self.blocked_extra_margin_deg < 0.0:
            self.get_logger().warning('blocked_extra_margin_deg must be >= 0; falling back to 0.')
            self.blocked_extra_margin_deg = 0.0
        if self.min_valid_range_m < 0.0:
            self.get_logger().warning('min_valid_range_m must be >= 0; falling back to 0.')
            self.min_valid_range_m = 0.0

        self.scan_sub = self.create_subscription(
            LaserScan,
            input_topic,
            self.scan_callback,
            10,
        )

        self.filtered_scan_pub = self.create_publisher(
            LaserScan,
            output_scan_topic,
            10,
        )

        self.summary_pub = self.create_publisher(
            LidarScanSummary,
            output_topic,
            10,
        )

        self.get_logger().info(
            'LD19 preprocess started. '
            f'input={input_topic}, output_scan={output_scan_topic}, output_summary={output_topic}, '
            f'num_sectors={self.num_sectors}, blocked_center_deg={self.blocked_center_deg:.1f}, '
            f'blocked_half_width_deg={self.blocked_half_width_deg:.1f}, '
            f'blocked_extra_margin_deg={self.blocked_extra_margin_deg:.1f}, '
            f'min_valid_range_m={self.min_valid_range_m:.2f}'
        )

    def scan_callback(self, msg: LaserScan) -> None:
        """Summarize one scan and publish LidarScanSummary."""
        ranges = self.filter_ranges(msg)
        if not ranges:
            return

        filtered_scan = LaserScan()
        filtered_scan.header = msg.header
        filtered_scan.angle_min = msg.angle_min
        filtered_scan.angle_max = msg.angle_max
        filtered_scan.angle_increment = msg.angle_increment
        filtered_scan.time_increment = msg.time_increment
        filtered_scan.scan_time = msg.scan_time
        filtered_scan.range_min = msg.range_min
        filtered_scan.range_max = msg.range_max
        filtered_scan.ranges = ranges

        if msg.intensities:
            filtered_intensities = list(msg.intensities)
            for i, r in enumerate(ranges):
                if not math.isfinite(r):
                    filtered_intensities[i] = 0.0
            filtered_scan.intensities = filtered_intensities

        self.filtered_scan_pub.publish(filtered_scan)

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

    def filter_ranges(self, msg: LaserScan) -> List[float]:
        """Mask blocked angles and near-floor clutter from one scan."""
        filtered = list(msg.ranges)
        if not filtered:
            return filtered

        blocked_center_rad = math.radians(self.blocked_center_deg)
        blocked_half_width_rad = math.radians(
            self.blocked_half_width_deg + self.blocked_extra_margin_deg
        )

        angle = msg.angle_min
        for i, r in enumerate(filtered):
            in_blocked_sector = (
                blocked_half_width_rad > 0.0
                and abs(self.angle_diff(angle, blocked_center_rad)) <= blocked_half_width_rad
            )
            below_min_valid = math.isfinite(r) and r > 0.0 and r < self.min_valid_range_m

            if in_blocked_sector or below_min_valid:
                filtered[i] = float('inf')

            angle += msg.angle_increment

        return filtered

    @staticmethod
    def angle_diff(a: float, b: float) -> float:
        """Return wrapped smallest angular difference a-b in radians."""
        d = a - b
        while d > math.pi:
            d -= 2.0 * math.pi
        while d < -math.pi:
            d += 2.0 * math.pi
        return d


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
