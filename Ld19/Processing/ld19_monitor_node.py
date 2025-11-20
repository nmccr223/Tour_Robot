import math
import time

import rclpy
from rclpy.node import Node
from robot_msgs.msg import LidarScanSummary
from diagnostic_msgs.msg import DiagnosticArray, DiagnosticStatus, KeyValue


class Ld19MonitorNode(Node):
    def __init__(self):
        super().__init__('ld19_monitor')

        self.declare_parameter('min_rate_hz', 5.0)
        self.declare_parameter('warn_rate_hz', 8.0)

        self.min_rate = float(self.get_parameter('min_rate_hz').value)
        self.warn_rate = float(self.get_parameter('warn_rate_hz').value)

        self.last_stamp = None
        self.last_ros_time = None
        self.last_seq = 0

        self.summary_sub = self.create_subscription(
            LidarScanSummary, '/ld19/summary', self.summary_callback, 10)

        self.diag_pub = self.create_publisher(
            DiagnosticArray, '/health/ld19', 10)

        self.timer = self.create_timer(1.0, self.timer_callback)

    def summary_callback(self, msg: LidarScanSummary):
        self.last_stamp = msg.stamp
        self.last_ros_time = self.get_clock().now()

    def timer_callback(self):
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

            kv_rate = KeyValue(key='rate_hz', value=f'{rate:.1f}')
            status.values.append(kv_rate)

            if rate < self.min_rate:
                status.level = DiagnosticStatus.ERROR
                status.message = 'Scan rate too low'
            elif rate < self.warn_rate:
                status.level = DiagnosticStatus.WARN
                status.message = 'Scan rate below nominal'
            else:
                status.level = DiagnosticStatus.OK
                status.message = 'OK'

        diag_array = DiagnosticArray()
        diag_array.header.stamp = now.to_msg()
        diag_array.status.append(status)

        self.diag_pub.publish(diag_array)


def main(args=None):
    rclpy.init(args=args)
    node = Ld19MonitorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()