# main_control/udp_motor_client.py
import socket
import struct
from rclpy.time import Time


class UdpMotorClient:
    """
    Simple UDP client to send velocity commands to the motor controller CM5.
    Packet format:
      uint32 seq
      float32 timestamp_sec
      float32 linear_x
      float32 angular_z
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Pre-compile struct for efficiency
        self.packet_struct = struct.Struct('<Ifff')  # little-endian

    def send_cmd_vel(self, seq: int, now: Time, v: float, w: float):
        # Convert ROS Time to float seconds
        t_sec = float(now.nanoseconds) / 1e9
        data = self.packet_struct.pack(seq, t_sec, v, w)
        self.sock.sendto(data, (self.host, self.port))