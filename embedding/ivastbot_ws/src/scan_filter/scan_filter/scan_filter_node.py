#!/usr/bin/env python3
"""
Scan Filter Node — Filters laser scan points that hit the robot body.
Subscribes to /scan_raw, publishes /scan with self-scan points removed.
Works directly in laser frame coordinates for simplicity.
"""

import math
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class ScanFilterNode(Node):
    def __init__(self):
        super().__init__('scan_filter_node')

        # Robot footprint (meters) — centered on base_link
        self.declare_parameter('footprint_x', 0.50)
        self.declare_parameter('footprint_y', 0.50)
        self.declare_parameter('padding', 0.03)

        # Lidar position relative to base_link
        self.declare_parameter('lidar_x', 0.212)
        self.declare_parameter('lidar_y', 0.0)
        self.declare_parameter('lidar_yaw', 3.14159)  # 180° rotation from URDF

        fp_x = self.get_parameter('footprint_x').value
        fp_y = self.get_parameter('footprint_y').value
        padding = self.get_parameter('padding').value
        self.lidar_x = self.get_parameter('lidar_x').value
        self.lidar_y = self.get_parameter('lidar_y').value
        self.lidar_yaw = self.get_parameter('lidar_yaw').value

        # Half dimensions with padding
        self.half_x = fp_x / 2.0 + padding
        self.half_y = fp_y / 2.0 + padding

        self.cos_yaw = math.cos(self.lidar_yaw)
        self.sin_yaw = math.sin(self.lidar_yaw)

        # Subscribe directly to /scan_raw, publish to /scan
        self.sub = self.create_subscription(
            LaserScan, '/scan_raw', self.scan_callback, 10)
        self.pub = self.create_publisher(LaserScan, '/scan', 10)

        self.get_logger().info(
            f'Scan filter: footprint={fp_x}x{fp_y}m + {padding}m padding, '
            f'lidar@({self.lidar_x},{self.lidar_y}), yaw={self.lidar_yaw:.2f}, '
            f'half_box=({self.half_x:.3f}, {self.half_y:.3f})')
        self.get_logger().info('Subscribing /scan_raw -> publishing /scan')

    def scan_callback(self, msg: LaserScan):
        filtered = LaserScan()
        filtered.header = msg.header
        filtered.angle_min = msg.angle_min
        filtered.angle_max = msg.angle_max
        filtered.angle_increment = msg.angle_increment
        filtered.time_increment = msg.time_increment
        filtered.scan_time = msg.scan_time
        filtered.range_min = msg.range_min
        filtered.range_max = msg.range_max
        filtered.ranges = list(msg.ranges)
        filtered.intensities = list(msg.intensities) if msg.intensities else []

        cos_y = self.cos_yaw
        sin_y = self.sin_yaw
        hx = self.half_x
        hy = self.half_y
        lx_off = self.lidar_x
        ly_off = self.lidar_y
        r_min = msg.range_min
        r_max = msg.range_max

        count_filtered = 0
        angle = msg.angle_min

        for i in range(len(filtered.ranges)):
            r = filtered.ranges[i]
            if r < r_min or r > r_max or math.isinf(r) or math.isnan(r):
                angle += msg.angle_increment
                continue

            # Point in laser frame
            px = r * math.cos(angle)
            py = r * math.sin(angle)

            # Transform to base_link frame
            bx = cos_y * px - sin_y * py + lx_off
            by = sin_y * px + cos_y * py + ly_off

            # Check if point is inside robot footprint box
            if -hx < bx < hx and -hy < by < hy:
                filtered.ranges[i] = float('inf')
                count_filtered += 1

            angle += msg.angle_increment

        self.pub.publish(filtered)


def main(args=None):
    rclpy.init(args=args)
    node = ScanFilterNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
