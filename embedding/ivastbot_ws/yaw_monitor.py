#!/usr/bin/env python3
"""Print yaw (in degrees) from /drivetrain_controller/odom continuously.

Usage:
    python3 yaw_monitor.py

Steps:
    1. Run bringup in another terminal: ros2 launch bringup bringup.launch.py
    2. Run this script
    3. Press 'r' + Enter to RESET yaw to 0 (sets current as reference)
    4. Physically rotate the robot 360 degrees
    5. Read the final yaw value
"""

import math
import select
import sys

import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


class YawMonitor(Node):
    def __init__(self):
        super().__init__("yaw_monitor")
        self.offset = 0.0
        self.last_yaw = 0.0
        self.sub = self.create_subscription(
            Odometry,
            "/drivetrain_controller/odom",
            self.cb,
            10,
        )
        self.timer = self.create_timer(0.1, self.check_input)

    def cb(self, msg):
        q = msg.pose.pose.orientation
        yaw = math.atan2(
            2.0 * (q.w * q.z + q.x * q.y),
            1.0 - 2.0 * (q.y * q.y + q.z * q.z),
        )
        self.last_yaw = math.degrees(yaw)
        rel = self.last_yaw - self.offset
        print(f"\rYaw: {self.last_yaw:+8.2f}°   |   Δ since reset: {rel:+8.2f}°   ", end="", flush=True)

    def check_input(self):
        # non-blocking stdin read
        if select.select([sys.stdin], [], [], 0)[0]:
            line = sys.stdin.readline().strip().lower()
            if line == "r":
                self.offset = self.last_yaw
                print(f"\n[reset] reference yaw set to {self.offset:.2f}°")


def main():
    rclpy.init()
    node = YawMonitor()
    print("Yaw monitor running. Press 'r' + Enter to reset reference, Ctrl+C to quit.\n")
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
