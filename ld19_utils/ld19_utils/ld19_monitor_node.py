"""
LD19 monitor node.

Purpose:
- Subscribe to /ld19/summary health stream.
- Publish diagnostic_msgs/DiagnosticArray on /health/ld19.

This gives operators a quick live status of LiDAR freshness/rate.
"""

import rclpy
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue
from rclpy.node import Node

from robot_msgs.msg import LidarScanSummary


class Ld19MonitorNode(Node):
    """Monitor LD19 summary stream and publish diagnostics."""

    def __init__(self) -> None:
        super().__init__('ld19_monitor')

        # Diagnostic thresholds for scan freshness/rate interpretation.
        self.declare_parameter('min_rate_hz', 5.0)
        self.declare_parameter('warn_rate_hz', 8.0)

        self.min_rate = float(self.get_parameter('min_rate_hz').value)
        self.warn_rate = float(self.get_parameter('warn_rate_hz').value)

        self.last_ros_time = None

        self.summary_sub = self.create_subscription(
            LidarScanSummary,
            '/ld19/summary',
            self.summary_callback,
            10,
        )

        self.diag_pub = self.create_publisher(
            DiagnosticArray,
            '/health/ld19',
            10,
        )

        # Emit diagnostics at fixed cadence regardless of incoming summary rate.
        self.timer = self.create_timer(1.0, self.timer_callback)

    def summary_callback(self, msg: LidarScanSummary) -> None:
        """Track time of latest summary reception for health calculations."""
        self.last_ros_time = self.get_clock().now()

    def timer_callback(self) -> None:
        """Publish current LD19 diagnostic state."""
        now = self.get_clock().now()
        status = DiagnosticStatus()
        status.name = 'LD19 LiDAR'
        status.hardware_id = 'ld19'
        status.values = []

        if self.last_ros_time is None:
            status.level = DiagnosticStatus.STALE
            status.message = 'No data received'
        else:
            dt = (now - self.last_ros_time).nanoseconds / 1e9
            rate = 1.0 / dt if dt > 0.0 else 0.0

            status.values.append(KeyValue(key='rate_hz', value=f'{rate:.1f}'))

            if rate < self.min_rate:
                status.level = DiagnosticStatus.ERROR
                status.message = 'Scan rate too low'
            elif rate < self.warn_rate:
                status.level = DiagnosticStatus.WARN
                status.message = 'Scan rate below nominal'
            else:
                status.level = DiagnosticStatus.OK
                status.message = 'OK'

        diag = DiagnosticArray()
        diag.header.stamp = now.to_msg()
        diag.status.append(status)
        self.diag_pub.publish(diag)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Ld19MonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
