#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
import math
import time

class FakeDosePublisher(Node):
    def __init__(self):
        super().__init__('fake_dose_publisher')
        self.publisher = self.create_publisher(Float64, 'dose', 10)
        self.timer = self.create_timer(1.0, self.timer_callback)  # Publish every second
        self.counter = 0
        
    def timer_callback(self):
        msg = Float64()
        # Simulate varying radiation levels across the new threshold ranges
        # Creates a pattern from ~1,000 to ~240,000 μSv/h to test all color zones
        
        # Cycle through different radiation zones over time
        cycle_position = (self.counter % 30) / 30.0  # 0.0 to 1.0 over 30 seconds
        
        if cycle_position < 0.25:
            # Low/Safe zone: 1,000 - 10,000 µSv/h (Blue)
            base_level = 5000
            variation = 4000
            msg.data = base_level + math.sin(self.counter * 0.3) * variation
        elif cycle_position < 0.5:
            # Moderate zone: 10,000 - 60,000 µSv/h (Green)
            base_level = 35000
            variation = 20000
            msg.data = base_level + math.sin(self.counter * 0.3) * variation
        elif cycle_position < 0.75:
            # High zone: 60,000 - 100,000 µSv/h (Yellow)
            base_level = 80000
            variation = 15000
            msg.data = base_level + math.sin(self.counter * 0.3) * variation
        else:
            # Critical zone: 100,000 - 240,000 µSv/h (Red)
            base_level = 170000
            variation = 60000
            msg.data = base_level + math.sin(self.counter * 0.3) * variation
        
        # Ensure values stay within realistic bounds
        msg.data = max(100.0, min(240000.0, msg.data))
        
        self.publisher.publish(msg)
        self.get_logger().info(f'Published fake dose: {msg.data:.1f} μSv/h ({msg.data/1000:.1f} mSv/h)')
        self.counter += 1

def main(args=None):
    rclpy.init(args=args)
    node = FakeDosePublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
