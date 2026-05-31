#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
import csv
from datetime import datetime
import os

class DoseLogger(Node):
    def __init__(self):
        super().__init__('dose_logger')
        
        # Find the source directory by looking for the package path
        # Start from this file's location and go up to find the package root
        current_file = os.path.abspath(__file__)
        package_dir = os.path.dirname(os.path.dirname(current_file))  # Go up to package root
        default_path = os.path.join(package_dir, 'radiation_logs', 'dose_data.csv')
        self.declare_parameter('file_path', default_path)
        
        # Get parameter
        self.log_file_path = self.get_parameter('file_path').get_parameter_value().string_value
        self.log_file_path = os.path.expanduser(self.log_file_path)
        
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Initialize CSV file with headers
        self.init_csv_file()
        
        # Subscribe to dose topic
        self.subscription = self.create_subscription(
            Float64,
            'dose',
            self.dose_callback,
            10
        )
        
        self.get_logger().info(f'Dose logger started. Saving data to: {self.log_file_path}')
    
    def init_csv_file(self):
        """Initialize CSV file with headers if it doesn't exist"""
        file_exists = os.path.isfile(self.log_file_path)
        
        if not file_exists:
            with open(self.log_file_path, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['timestamp', 'datetime', 'dose_uSv_h'])
            self.get_logger().info(f'Created new log file: {self.log_file_path}')
        else:
            self.get_logger().info(f'Appending to existing log file: {self.log_file_path}')
    
    def dose_callback(self, msg):
        """Callback function to save dose data"""
        timestamp = self.get_clock().now().to_msg()
        timestamp_sec = timestamp.sec + timestamp.nanosec * 1e-9
        datetime_str = datetime.fromtimestamp(timestamp_sec).strftime('%Y-%m-%d %H:%M:%S.%f')
        dose_value = msg.data
        
        # Write data to CSV
        with open(self.log_file_path, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([timestamp_sec, datetime_str, dose_value])
        
        self.get_logger().debug(f'Logged dose: {dose_value} uSv/h at {datetime_str}')

def main(args=None):
    rclpy.init(args=args)
    dose_logger = DoseLogger()
    
    try:
        rclpy.spin(dose_logger)
    except KeyboardInterrupt:
        dose_logger.get_logger().info('Shutting down dose logger...')
    finally:
        dose_logger.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
