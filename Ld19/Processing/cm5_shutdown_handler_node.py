"""
CM5 Shutdown Handler Node

Listens for shutdown requests from SER8, executes CM5 shutdown, and sends acknowledgment back.

Usage:
  ros2 run ldlidar_node cm5_shutdown_handler_node

This node will run on the CM5 and gracefully handle shutdown requests from the SER8.
"""

import subprocess
import time
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CM5ShutdownHandlerNode(Node):
    def __init__(self):
        super().__init__('cm5_shutdown_handler')
        
        self.declare_parameter('shutdown_request_topic', '/cm5/shutdown_request')
        self.declare_parameter('shutdown_ack_topic', '/cm5/shutdown_ack')
        
        self.shutdown_request_topic = self.get_parameter('shutdown_request_topic').value
        self.shutdown_ack_topic = self.get_parameter('shutdown_ack_topic').value
        
        # Publisher for acknowledgment back to SER8
        self.ack_pub = self.create_publisher(String, self.shutdown_ack_topic, 10)
        
        # Subscriber for shutdown requests from SER8
        self.shutdown_sub = self.create_subscription(
            String, self.shutdown_request_topic, self.on_shutdown_request, 10
        )
        
        self.get_logger().info("CM5 shutdown handler ready")
        self.get_logger().info(f"  Listening on: {self.shutdown_request_topic}")
        self.get_logger().info(f"  Ack topic: {self.shutdown_ack_topic}")
    
    def on_shutdown_request(self, msg: String):
        """Handle shutdown request from SER8."""
        self.get_logger().warning(f"Shutdown request received: {msg.data}")
        
        if msg.data.lower() == "shutdown_now":
            # Send acknowledgment to SER8
            ack_msg = String()
            ack_msg.data = "acknowledged"
            self.ack_pub.publish(ack_msg)
            self.get_logger().info("Acknowledgment sent to SER8")
            
            # Give SER8 time to receive ack before CM5 shuts down
            time.sleep(1)
            
            # Initiate CM5 shutdown
            self.shutdown_cm5()
    
    def shutdown_cm5(self):
        """Initiate graceful CM5 shutdown."""
        self.get_logger().critical("SHUTTING DOWN CM5 NOW")
        
        try:
            # Graceful shutdown: kill ROS 2 processes first
            self.get_logger().info("Terminating ROS 2 processes...")
            subprocess.run(['pkill', '-TERM', 'ros2'], timeout=5)
            time.sleep(1)
            
            # Then system shutdown
            self.get_logger().info("Executing system shutdown: sudo shutdown -h now")
            subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
            
            # Wait for shutdown to execute
            time.sleep(10)
        except Exception as e:
            self.get_logger().error(f"Error during CM5 shutdown: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = CM5ShutdownHandlerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
