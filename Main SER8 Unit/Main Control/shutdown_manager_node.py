"""
SER8 Shutdown Manager Node

Sends a shutdown command to the CM5, waits for acknowledgment, then shuts down the SER8.
Integrates with HMI GUI via ROS 2 service call.

Usage:
  ros2 service call /ser8/shutdown_system std_srvs/srv/Empty

Or from code:
  ros2 run main_control shutdown_manager_node
  # Then in another terminal:
  ros2 service call /ser8/shutdown_system std_srvs/srv/Empty
"""

import os
import signal
import subprocess
import time
import rclpy
from rclpy.node import Node
from std_srvs.srv import Empty
from std_msgs.msg import String
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ShutdownManagerNode(Node):
    def __init__(self):
        super().__init__('shutdown_manager')
        
        self.declare_parameter('cm5_shutdown_topic', '/cm5/shutdown_request')
        self.declare_parameter('cm5_ack_topic', '/cm5/shutdown_ack')
        self.declare_parameter('shutdown_timeout_sec', 10.0)
        
        self.cm5_shutdown_topic = self.get_parameter('cm5_shutdown_topic').value
        self.cm5_ack_topic = self.get_parameter('cm5_ack_topic').value
        self.shutdown_timeout = self.get_parameter('shutdown_timeout_sec').value
        
        # Publisher for shutdown request to CM5
        self.shutdown_pub = self.create_publisher(String, self.cm5_shutdown_topic, 10)
        
        # Subscriber for CM5 acknowledgment
        self.ack_received = False
        self.ack_sub = self.create_subscription(
            String, self.cm5_ack_topic, self.on_cm5_ack, 10
        )
        
        # Service for HMI to call
        self.shutdown_service = self.create_service(
            Empty, '/ser8/shutdown_system', self.handle_shutdown_request
        )
        
        self.get_logger().info(f"Shutdown manager ready. Service: /ser8/shutdown_system")
        self.get_logger().info(f"  CM5 shutdown topic: {self.cm5_shutdown_topic}")
        self.get_logger().info(f"  CM5 ack topic: {self.cm5_ack_topic}")
        self.get_logger().info(f"  Shutdown timeout: {self.shutdown_timeout} sec")
    
    def on_cm5_ack(self, msg: String):
        """Callback when CM5 acknowledges shutdown."""
        self.get_logger().info(f"CM5 shutdown acknowledgment received: {msg.data}")
        if msg.data.lower() in ['ok', 'acknowledged', 'confirmed']:
            self.ack_received = True
    
    def handle_shutdown_request(self, request, response):
        """Handle shutdown request from HMI."""
        self.get_logger().warning("SHUTDOWN REQUEST RECEIVED FROM HMI")
        
        try:
            # Step 1: Send shutdown request to CM5
            self.get_logger().info("Sending shutdown command to CM5...")
            shutdown_msg = String()
            shutdown_msg.data = "shutdown_now"
            self.shutdown_pub.publish(shutdown_msg)
            
            # Step 2: Wait for CM5 acknowledgment
            self.ack_received = False
            start_time = time.time()
            while not self.ack_received and (time.time() - start_time) < self.shutdown_timeout:
                time.sleep(0.1)
            
            if self.ack_received:
                self.get_logger().info("CM5 acknowledged shutdown. Waiting 2 seconds before SER8 shutdown...")
                time.sleep(2)
            else:
                self.get_logger().warning(f"No CM5 acknowledgment after {self.shutdown_timeout} sec. Proceeding with SER8 shutdown anyway.")
                time.sleep(1)
            
            # Step 3: Shutdown the SER8
            self.get_logger().critical("SHUTTING DOWN SER8 NOW")
            self.initiate_ser8_shutdown()
            
        except Exception as e:
            self.get_logger().error(f"Error during shutdown sequence: {e}")
            return response
        
        return response
    
    def initiate_ser8_shutdown(self):
        """Initiate system shutdown on SER8."""
        try:
            # Use system shutdown command (works on Linux/Ubuntu)
            self.get_logger().info("Executing system shutdown: sudo shutdown -h now")
            subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
            
            # Alternative (less graceful):
            # os.system('sudo shutdown -h now')
            
            # Give it time to start the shutdown
            time.sleep(5)
        except Exception as e:
            self.get_logger().error(f"Failed to initiate shutdown: {e}")
            # Fallback: force exit
            self.get_logger().critical("Forcing exit...")
            os._exit(1)


def main(args=None):
    rclpy.init(args=args)
    node = ShutdownManagerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
