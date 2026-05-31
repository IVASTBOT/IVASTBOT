#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from sensor_msgs.msg import Image
# from cv_bridge import CvBridge  # Commented out due to ROS2 Foxy compatibility issues
import numpy as np
import cv2
import os
from datetime import datetime

# Try to import cv_bridge, but handle the error gracefully
try:
    from cv_bridge import CvBridge
    CV_BRIDGE_AVAILABLE = True
except Exception as e:
    print(f"cv_bridge import failed: {e}")
    CV_BRIDGE_AVAILABLE = False


class CombinedMapSaver(Node):
    def __init__(self):
        super().__init__('combined_map_saver')
        
        # Declare parameters
        self.declare_parameters(
            namespace='',
            parameters=[
                ('slam_map_topic', '/map'),
                ('radiation_map_topic', '/radiation_grid'),
                ('output_directory', '/tmp/combined_maps'),
                ('save_interval', 10.0),  # seconds
                ('radiation_alpha', 0.6),  # transparency of radiation overlay
                ('auto_save', True),
                ('manual_save_service', True),
            ]
        )
        
        # Get parameters
        self.slam_map_topic = self.get_parameter('slam_map_topic').get_parameter_value().string_value
        self.radiation_map_topic = self.get_parameter('radiation_map_topic').get_parameter_value().string_value
        self.output_directory = self.get_parameter('output_directory').get_parameter_value().string_value
        self.save_interval = self.get_parameter('save_interval').get_parameter_value().double_value
        self.radiation_alpha = self.get_parameter('radiation_alpha').get_parameter_value().double_value
        self.auto_save = self.get_parameter('auto_save').get_parameter_value().bool_value
        
        # Create output directory
        os.makedirs(self.output_directory, exist_ok=True)
        
        # Initialize variables
        self.slam_map = None
        self.radiation_map = None
        # Initialize cv_bridge only if available
        if CV_BRIDGE_AVAILABLE:
            self.bridge = CvBridge()
        else:
            self.get_logger().warn("cv_bridge not available, combined map saving may not work properly")
            self.bridge = None
        
        # Subscribers
        self.slam_sub = self.create_subscription(
            OccupancyGrid, self.slam_map_topic, self.slam_map_callback, 10)
        self.radiation_sub = self.create_subscription(
            OccupancyGrid, self.radiation_map_topic, self.radiation_map_callback, 10)
        
        # Timer for auto-save
        if self.auto_save:
            self.save_timer = self.create_timer(self.save_interval, self.auto_save_combined_map)
        
        # Service for manual save (you can call: ros2 service call /save_combined_map std_srvs/srv/Empty)
        from std_srvs.srv import Empty
        self.save_service = self.create_service(Empty, 'save_combined_map', self.manual_save_callback)
        
        self.get_logger().info(f'Combined Map Saver started')
        self.get_logger().info(f'Output directory: {self.output_directory}')
        self.get_logger().info(f'Auto-save: {self.auto_save} (every {self.save_interval}s)')
    
    def slam_map_callback(self, msg):
        """Store the latest SLAM map"""
        self.slam_map = msg
        
    def radiation_map_callback(self, msg):
        """Store the latest radiation map"""
        self.radiation_map = msg
    
    def manual_save_callback(self, request, response):
        """Service callback for manual save"""
        success = self.save_combined_map()
        if success:
            self.get_logger().info('Manual save completed successfully')
        else:
            self.get_logger().warn('Manual save failed - missing map data')
        return response
    
    def auto_save_combined_map(self):
        """Timer callback for auto-save"""
        if self.save_combined_map():
            self.get_logger().info('Auto-save completed')
    
    def save_combined_map(self):
        """Combine and save both maps"""
        if self.slam_map is None or self.radiation_map is None:
            self.get_logger().warn('Missing map data - cannot save combined map')
            return False
        
        try:
            # Convert SLAM map to image
            slam_image = self.occupancy_grid_to_image(self.slam_map, is_slam=True)
            
            # Convert radiation map to colored image
            radiation_image = self.occupancy_grid_to_image(self.radiation_map, is_slam=False)
            
            # Ensure both images have the same size
            if slam_image.shape[:2] != radiation_image.shape[:2]:
                # Resize radiation map to match SLAM map
                radiation_image = cv2.resize(radiation_image, (slam_image.shape[1], slam_image.shape[0]))
            
            # Combine the images
            combined_image = self.overlay_images(slam_image, radiation_image)
            
            # Save the combined image
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"combined_map_{timestamp}.png"
            filepath = os.path.join(self.output_directory, filename)
            
            cv2.imwrite(filepath, combined_image)
            
            # Also save individual maps for reference
            slam_filename = f"slam_map_{timestamp}.png"
            radiation_filename = f"radiation_map_{timestamp}.png"
            cv2.imwrite(os.path.join(self.output_directory, slam_filename), slam_image)
            cv2.imwrite(os.path.join(self.output_directory, radiation_filename), radiation_image)
            
            self.get_logger().info(f'Saved combined map: {filepath}')
            return True
            
        except Exception as e:
            self.get_logger().error(f'Failed to save combined map: {e}')
            return False
    
    def occupancy_grid_to_image(self, grid_msg, is_slam=True):
        """Convert OccupancyGrid to OpenCV image"""
        width = grid_msg.info.width
        height = grid_msg.info.height
        data = np.array(grid_msg.data, dtype=np.int8)
        data = data.reshape((height, width))
        
        if is_slam:
            # SLAM map: -1=unknown(gray), 0=free(white), 100=occupied(black)
            image = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Unknown areas (gray)
            image[data == -1] = [128, 128, 128]
            # Free space (white)
            image[data == 0] = [255, 255, 255]
            # Occupied space (black)
            image[data == 100] = [0, 0, 0]
            # Intermediate values (gradual gray)
            for val in range(1, 100):
                mask = (data == val)
                gray_level = 255 - int(val * 2.55)
                image[mask] = [gray_level, gray_level, gray_level]
                
        else:
            # Radiation map: convert to heatmap colors
            image = np.zeros((height, width, 3), dtype=np.uint8)
            
            for y in range(height):
                for x in range(width):
                    value = data[y, x]
                    if value == -1:
                        # No radiation data - transparent (will be overlaid)
                        image[y, x] = [0, 0, 0]  # Black for transparency
                    else:
                        # Convert radiation value to color
                        normalized = value / 100.0  # 0-1 range
                        image[y, x] = self.value_to_color(normalized)
        
        return image
    
    def value_to_color(self, normalized_value):
        """Convert normalized value (0-1) to color (BGR format)"""
        if normalized_value < 0.25:
            # Blue to cyan
            t = normalized_value / 0.25
            return [255, int(128 + 127*t), 0]  # BGR
        elif normalized_value < 0.5:
            # Cyan to green
            t = (normalized_value - 0.25) / 0.25
            return [int(255 - 255*t), 255, 0]
        elif normalized_value < 0.75:
            # Green to yellow
            t = (normalized_value - 0.5) / 0.25
            return [0, 255, int(255*t)]
        else:
            # Yellow to red
            t = (normalized_value - 0.75) / 0.25
            return [0, int(255 - 255*t), 255]
    
    def overlay_images(self, background, overlay):
        """Overlay radiation map on SLAM map with transparency"""
        # Create mask for areas with radiation data (non-black pixels)
        overlay_gray = cv2.cvtColor(overlay, cv2.COLOR_BGR2GRAY)
        mask = overlay_gray > 0
        
        # Combine images
        result = background.copy()
        
        # Apply radiation overlay where there's data
        for c in range(3):
            result[:, :, c] = np.where(
                mask,
                (1 - self.radiation_alpha) * background[:, :, c] + self.radiation_alpha * overlay[:, :, c],
                background[:, :, c]
            )
        
        return result.astype(np.uint8)


def main(args=None):
    rclpy.init(args=args)
    node = CombinedMapSaver()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
