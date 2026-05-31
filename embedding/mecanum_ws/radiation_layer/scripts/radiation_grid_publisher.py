#!/usr/bin/env python3

import rclpy
import rclpy.time
import rclpy.duration
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Float64
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import Image
import tf2_ros
import tf2_geometry_msgs
import numpy as np
import math

# Conditional imports for cv_bridge and cv2 (only when needed for image publishing)
try:
    from cv_bridge import CvBridge
    import cv2
    CV_BRIDGE_AVAILABLE = True
except Exception as e:
    print(f"Warning: cv_bridge/cv2 not available: {e}")
    print("Image publishing will be disabled, but occupancy grid publishing will work normally")
    CV_BRIDGE_AVAILABLE = False
    CvBridge = None
    cv2 = None


class RadiationGridPublisher(Node):
    def __init__(self):
        super().__init__('radiation_grid_publisher')
        
        # Declare parameters with defaults from config file
        self.declare_parameters(
            namespace='',
            parameters=[
                ('radiation_topic', 'dose'),
                ('radiation_frame', 'base_footprint'),  # Better for ground sensors
                ('map_frame', 'map'),
                ('grid_resolution', 0.1),
                ('grid_width', 200),
                ('grid_height', 200),
                ('grid_origin_x', -10.0),
                ('grid_origin_y', -10.0),
                # Robot footprint parameters
                ('use_robot_footprint', True),
                ('robot_radius', 0.3), 
                ('robot_footprint', []),  # List of [x,y] coordinates
                ('footprint_fill_mode', 'full'),
                # Thresholds
                ('lower_threshold', 0.1),
                ('upper_threshold', 10.0),
                ('background_threshold', 0.01),
                ('decay_rate', 1.0),  # No decay - radiation persists
                ('update_rate', 2.0),  # Higher frequency for better tracking
                ('decay_timer_rate', 1.0),
                ('use_occupancy_grid', True),
                ('use_color_image', True),
                ('grid_alpha', 0.7),
                ('blue_threshold', 0.25),
                ('green_threshold', 0.5),
                ('yellow_threshold', 0.75),
                ('output_grid_topic', 'radiation_grid'),
                ('output_image_topic', 'radiation_heatmap_image'),
                ('debug_logging', False),
                ('dynamic_sizing', True),
                ('map_padding_factor', 1.4),
                ('min_grid_size', 400),
            ]
        )
        
        # Get parameters
        self.radiation_topic = self.get_parameter('radiation_topic').get_parameter_value().string_value
        self.radiation_frame = self.get_parameter('radiation_frame').get_parameter_value().string_value
        self.map_frame = self.get_parameter('map_frame').get_parameter_value().string_value
        self.grid_resolution = self.get_parameter('grid_resolution').get_parameter_value().double_value
        self.grid_width = self.get_parameter('grid_width').get_parameter_value().integer_value
        self.grid_height = self.get_parameter('grid_height').get_parameter_value().integer_value
        self.grid_origin_x = self.get_parameter('grid_origin_x').get_parameter_value().double_value
        self.grid_origin_y = self.get_parameter('grid_origin_y').get_parameter_value().double_value
        # Robot footprint parameters
        self.use_robot_footprint = self.get_parameter('use_robot_footprint').get_parameter_value().bool_value
        self.robot_radius = self.get_parameter('robot_radius').get_parameter_value().double_value
        self.robot_footprint = self.get_parameter('robot_footprint').get_parameter_value().string_array_value
        self.footprint_fill_mode = self.get_parameter('footprint_fill_mode').get_parameter_value().string_value
        # Convert string footprint to coordinates if provided
        if len(self.robot_footprint) > 0:
            try:
                # Parse footprint coordinates from string array
                self.robot_footprint = [[float(x) for x in coord.split(',')] for coord in self.robot_footprint]
            except:
                self.get_logger().warn("Failed to parse robot_footprint, using radius instead")
                self.robot_footprint = []
        # Radiation thresholds
        self.lower_threshold = self.get_parameter('lower_threshold').get_parameter_value().double_value
        self.upper_threshold = self.get_parameter('upper_threshold').get_parameter_value().double_value
        self.background_threshold = self.get_parameter('background_threshold').get_parameter_value().double_value
        self.decay_rate = self.get_parameter('decay_rate').get_parameter_value().double_value
        self.update_rate = self.get_parameter('update_rate').get_parameter_value().double_value
        self.decay_timer_rate = self.get_parameter('decay_timer_rate').get_parameter_value().double_value
        self.use_occupancy_grid = self.get_parameter('use_occupancy_grid').get_parameter_value().bool_value
        self.use_color_image = self.get_parameter('use_color_image').get_parameter_value().bool_value
        self.grid_alpha = self.get_parameter('grid_alpha').get_parameter_value().double_value
        self.blue_threshold = self.get_parameter('blue_threshold').get_parameter_value().double_value
        self.green_threshold = self.get_parameter('green_threshold').get_parameter_value().double_value
        self.yellow_threshold = self.get_parameter('yellow_threshold').get_parameter_value().double_value
        self.output_grid_topic = self.get_parameter('output_grid_topic').get_parameter_value().string_value
        self.output_image_topic = self.get_parameter('output_image_topic').get_parameter_value().string_value
        self.debug_logging = self.get_parameter('debug_logging').get_parameter_value().bool_value
        self.dynamic_sizing = self.get_parameter('dynamic_sizing').get_parameter_value().bool_value
        self.map_padding_factor = self.get_parameter('map_padding_factor').get_parameter_value().double_value
        self.min_grid_size = self.get_parameter('min_grid_size').get_parameter_value().integer_value
        
        # Initialize radiation grid
        self.radiation_grid = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)
        
        # TF buffer
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        
        # CV Bridge for image conversion (only if needed and available)
        if self.use_color_image and CV_BRIDGE_AVAILABLE:
            self.bridge = CvBridge()
        elif self.use_color_image and not CV_BRIDGE_AVAILABLE:
            self.get_logger().warn("Image publishing requested but cv_bridge is not available. Disabling image output.")
            self.use_color_image = False

        # Create QoS profile for sensor compatibility
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT, 
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )

        # Publishers and subscribers
        self.dose_sub = self.create_subscription(
            Float64, self.radiation_topic, self.dose_callback, qos_profile)
        
        # Subscribe to SLAM map to adapt radiation grid size (only if dynamic sizing enabled)
        if self.dynamic_sizing:
            self.map_sub = self.create_subscription(
                OccupancyGrid, '/map', self.map_callback, qos_profile)
            self.get_logger().info('Dynamic radiation grid sizing enabled - will adapt to SLAM map')
        
        if self.use_occupancy_grid:
            self.grid_pub = self.create_publisher(
                OccupancyGrid, self.output_grid_topic, 10)
        
        if self.use_color_image and CV_BRIDGE_AVAILABLE:
            self.image_pub = self.create_publisher(
                Image, self.output_image_topic, 10)
        
        # Timers
        self.timer = self.create_timer(self.update_rate, self.publish_radiation_grid)
        self.decay_timer = self.create_timer(self.decay_timer_rate, self.apply_decay)
        
        self.get_logger().info(f'Radiation Grid Publisher started - Topic: {self.radiation_topic}')
        self.get_logger().info(f'CV Bridge available: {CV_BRIDGE_AVAILABLE}, Image publishing: {self.use_color_image and CV_BRIDGE_AVAILABLE}')        
        if self.debug_logging:
            self.get_logger().info(f'Grid: {self.grid_width}x{self.grid_height}, Resolution: {self.grid_resolution}m')
    
    def dose_callback(self, msg):
        try:
            # Validate dose data from RadEye sensor
            if msg.data < 0 or msg.data > 250000:  # Reasonable range check
                self.get_logger().warn(f'Invalid dose reading: {msg.data} μSv/h - ignoring')
                return
                
            # Transform dose measurement to map frame using latest available transform
            point_in = PointStamped()
            point_in.header.frame_id = self.radiation_frame
            # Use time=0 for latest available transform (handles sensor latency)
            point_in.header.stamp = rclpy.time.Time().to_msg()
            point_in.point.x = 0.0
            point_in.point.y = 0.0
            point_in.point.z = 0.0
            
            # Get latest available transform with timeout
            point_out = self.tf_buffer.transform(
                point_in, 
                self.map_frame, 
                timeout=rclpy.duration.Duration(seconds=0.5)  # Longer timeout
            )

            # Apply radiation reading to robot footprint area
            if self.use_robot_footprint:
                if self.debug_logging:
                    self.get_logger().info(f'Using robot footprint at ({point_out.point.x:.2f}, {point_out.point.y:.2f})')
                self.apply_radiation_to_footprint(point_out.point.x, point_out.point.y, msg.data)
            else:
                if self.debug_logging:
                    self.get_logger().info('Using single point radiation')
                # Original single-point application
                grid_x = int((point_out.point.x - self.grid_origin_x) / self.grid_resolution)
                grid_y = int((point_out.point.y - self.grid_origin_y) / self.grid_resolution)
                
                if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                    self.radiation_grid[grid_y, grid_x] = max(
                        self.radiation_grid[grid_y, grid_x], msg.data)
            
            if self.debug_logging:
                self.get_logger().debug(f'Recorded radiation: {msg.data:.2f} μSv/h at ({point_out.point.x:.2f}, {point_out.point.y:.2f})')
            
        except Exception as e:
            self.get_logger().warn(f'Failed to transform dose measurement: {e}')

    def map_callback(self, msg):
        """Callback for SLAM map updates - dynamically resize radiation grid to match"""
        if not self.dynamic_sizing:
            return
            
        try:
            # Check if we need to resize the radiation grid
            slam_width = msg.info.width
            slam_height = msg.info.height
            slam_resolution = msg.info.resolution
            slam_origin_x = msg.info.origin.position.x
            slam_origin_y = msg.info.origin.position.y
            
            # Add configurable padding around the SLAM map
            padding_factor = self.map_padding_factor
            
            # Calculate desired radiation grid dimensions
            desired_width = int(slam_width * padding_factor)
            desired_height = int(slam_height * padding_factor)
            desired_resolution = slam_resolution
            
            # Center the radiation grid around the SLAM map
            padding_width = (desired_width - slam_width) // 2
            padding_height = (desired_height - slam_height) // 2
            desired_origin_x = slam_origin_x - padding_width * desired_resolution
            desired_origin_y = slam_origin_y - padding_height * desired_resolution
            
            # Check if we need to resize (allow small tolerance to avoid constant resizing)
            tolerance = 0.1  # 10cm tolerance
            needs_resize = (
                abs(self.grid_resolution - desired_resolution) > 0.001 or
                abs(self.grid_origin_x - desired_origin_x) > tolerance or
                abs(self.grid_origin_y - desired_origin_y) > tolerance or
                abs(self.grid_width - desired_width) > 10 or
                abs(self.grid_height - desired_height) > 10
            )
            
            if needs_resize:
                self.get_logger().info(f'Resizing radiation grid to match SLAM map:')
                self.get_logger().info(f'  SLAM: {slam_width}x{slam_height}, origin=({slam_origin_x:.2f}, {slam_origin_y:.2f})')
                self.get_logger().info(f'  New radiation: {desired_width}x{desired_height}, origin=({desired_origin_x:.2f}, {desired_origin_y:.2f})')
                
                # Resize the radiation grid while preserving existing data
                self.resize_radiation_grid(desired_width, desired_height, 
                                         desired_resolution, desired_origin_x, desired_origin_y)
        
        except Exception as e:
            self.get_logger().warn(f'Failed to process map update: {e}')

    def resize_radiation_grid(self, new_width, new_height, new_resolution, new_origin_x, new_origin_y):
        """Resize radiation grid while preserving existing radiation data"""
        try:
            # Create new grid
            new_grid = np.zeros((new_height, new_width), dtype=np.float32)
            
            # Copy existing radiation data to new grid
            for old_y in range(self.grid_height):
                for old_x in range(self.grid_width):
                    if self.radiation_grid[old_y, old_x] > 0:
                        # Convert old grid coordinates to world coordinates
                        world_x = self.grid_origin_x + old_x * self.grid_resolution
                        world_y = self.grid_origin_y + old_y * self.grid_resolution
                        
                        # Convert world coordinates to new grid coordinates
                        new_x = int((world_x - new_origin_x) / new_resolution)
                        new_y = int((world_y - new_origin_y) / new_resolution)
                        
                        # Copy data if within new grid bounds
                        if 0 <= new_x < new_width and 0 <= new_y < new_height:
                            new_grid[new_y, new_x] = self.radiation_grid[old_y, old_x]
            
            # Update grid parameters
            self.radiation_grid = new_grid
            self.grid_width = new_width
            self.grid_height = new_height
            self.grid_resolution = new_resolution
            self.grid_origin_x = new_origin_x
            self.grid_origin_y = new_origin_y
            
            self.get_logger().info(f'Successfully resized radiation grid to {new_width}x{new_height}')
            
        except Exception as e:
            self.get_logger().error(f'Failed to resize radiation grid: {e}')

    def apply_radiation_to_footprint(self, robot_x, robot_y, dose_value):
        """Apply radiation reading to the entire robot footprint area"""
        if self.debug_logging:
            self.get_logger().info(f'apply_radiation_to_footprint: use_robot_footprint={self.use_robot_footprint}')
            self.get_logger().info(f'  robot_radius={getattr(self, "robot_radius", "NOT_SET")}')
            self.get_logger().info(f'  robot_footprint={getattr(self, "robot_footprint", "NOT_SET")}')
        
        if hasattr(self, 'robot_radius') and self.robot_radius > 0:
            # Circular footprint
            if self.debug_logging:
                self.get_logger().info('Using circular footprint')
            self.apply_circular_footprint(robot_x, robot_y, dose_value)
        elif hasattr(self, 'robot_footprint') and len(self.robot_footprint) > 0:
            # Rectangular/polygon footprint
            if self.debug_logging:
                self.get_logger().info('Using polygon footprint')
            self.apply_polygon_footprint(robot_x, robot_y, dose_value)
        else:
            # Fallback to single point
            if self.debug_logging:
                self.get_logger().info('Using single point fallback')
            grid_x = int((robot_x - self.grid_origin_x) / self.grid_resolution)
            grid_y = int((robot_y - self.grid_origin_y) / self.grid_resolution)
            if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                self.radiation_grid[grid_y, grid_x] = max(self.radiation_grid[grid_y, grid_x], dose_value)

    def apply_circular_footprint(self, robot_x, robot_y, dose_value):
        """Apply radiation to circular robot footprint"""
        # Calculate grid range to check
        radius_cells = int(self.robot_radius / self.grid_resolution) + 1
        center_x = int((robot_x - self.grid_origin_x) / self.grid_resolution)
        center_y = int((robot_y - self.grid_origin_y) / self.grid_resolution)

        if self.debug_logging:
            self.get_logger().info(f'Applying circular footprint: radius={self.robot_radius}m, center=({robot_x:.2f}, {robot_y:.2f}), radius_cells={radius_cells}')

        cells_filled = 0
        for grid_y in range(center_y - radius_cells, center_y + radius_cells + 1):
            for grid_x in range(center_x - radius_cells, center_x + radius_cells + 1):
                # Check bounds
                if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                    # Calculate world coordinates of this cell
                    cell_world_x = self.grid_origin_x + grid_x * self.grid_resolution + self.grid_resolution / 2.0
                    cell_world_y = self.grid_origin_y + grid_y * self.grid_resolution + self.grid_resolution / 2.0
                    distance = math.sqrt((cell_world_x - robot_x)**2 + (cell_world_y - robot_y)**2)

                    # Apply radiation if within robot radius
                    if distance <= self.robot_radius:
                        if self.footprint_fill_mode == "full":
                            # Use maximum value to preserve radiation trail
                            self.radiation_grid[grid_y, grid_x] = max(self.radiation_grid[grid_y, grid_x], dose_value)
                            cells_filled += 1
                        elif self.footprint_fill_mode == "edge" and abs(distance - self.robot_radius) < self.grid_resolution:
                            self.radiation_grid[grid_y, grid_x] = max(self.radiation_grid[grid_y, grid_x], dose_value)
                            cells_filled += 1
        
        if self.debug_logging:
            self.get_logger().info(f'Filled {cells_filled} cells in circular footprint')
            # Log some radiation values for debugging
            non_zero_cells = np.count_nonzero(self.radiation_grid)
            max_dose = np.max(self.radiation_grid)
            self.get_logger().info(f'Grid stats: {non_zero_cells} non-zero cells, max dose: {max_dose:.3f}')
            
        # Add interpolation between robot positions for smooth trails
        if hasattr(self, 'last_robot_position'):
            self.interpolate_radiation_trail(self.last_robot_position[0], self.last_robot_position[1], 
                                           robot_x, robot_y, dose_value)
        self.last_robot_position = (robot_x, robot_y)

    def interpolate_radiation_trail(self, x1, y1, x2, y2, dose_value):
        """Fill radiation between two robot positions for smooth trails"""
        try:
            # Calculate distance between positions
            distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            
            # Only interpolate if robot moved significantly
            if distance > self.grid_resolution:
                # Number of interpolation points based on distance
                num_points = max(2, int(distance / (self.grid_resolution * 0.5)))
                
                for i in range(num_points):
                    t = i / float(num_points - 1)
                    interp_x = x1 + t * (x2 - x1)
                    interp_y = y1 + t * (y2 - y1)
                    
                    # Apply smaller footprint for interpolated points
                    self.apply_interpolated_footprint(interp_x, interp_y, dose_value)
                    
        except Exception as e:
            if self.debug_logging:
                self.get_logger().debug(f'Trail interpolation failed: {e}')
    
    def apply_interpolated_footprint(self, robot_x, robot_y, dose_value):
        """Apply radiation with smaller footprint for interpolated positions"""
        # Use smaller radius for interpolated points
        interp_radius = self.robot_radius * 0.7
        radius_cells = int(interp_radius / self.grid_resolution) + 1
        center_x = int((robot_x - self.grid_origin_x) / self.grid_resolution)
        center_y = int((robot_y - self.grid_origin_y) / self.grid_resolution)

        for grid_y in range(center_y - radius_cells, center_y + radius_cells + 1):
            for grid_x in range(center_x - radius_cells, center_x + radius_cells + 1):
                if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
                    cell_world_x = self.grid_origin_x + grid_x * self.grid_resolution + self.grid_resolution / 2.0
                    cell_world_y = self.grid_origin_y + grid_y * self.grid_resolution + self.grid_resolution / 2.0
                    distance = math.sqrt((cell_world_x - robot_x)**2 + (cell_world_y - robot_y)**2)

                    if distance <= interp_radius:
                        # Use slightly lower dose for interpolated points
                        interp_dose = dose_value * 0.8
                        self.radiation_grid[grid_y, grid_x] = max(self.radiation_grid[grid_y, grid_x], interp_dose)

    def apply_polygon_footprint(self, robot_x, robot_y, dose_value):
        """Apply radiation to polygonal robot footprint"""
        # This would implement polygon-in-grid checking
        # For now, fallback to circular with estimated radius
        if len(self.robot_footprint) > 0:
            # Estimate radius from footprint vertices
            max_dist = 0
            for point in self.robot_footprint:
                dist = math.sqrt(point[0]**2 + point[1]**2)
                max_dist = max(max_dist, dist)
            # Temporarily use circular approximation
            old_radius = getattr(self, 'robot_radius', 0.3)
            self.robot_radius = max_dist
            self.apply_circular_footprint(robot_x, robot_y, dose_value)
            self.robot_radius = old_radius

    # Dynamic parameter update support
    def parameter_update_callback(self, params):
        updated = False
        for param in params:
            if param.name == 'robot_radius' and param.type_ == param.Type.DOUBLE:
                self.robot_radius = param.value
                updated = True
                self.get_logger().info(f'Updated robot_radius: {self.robot_radius}')
            elif param.name == 'grid_resolution' and param.type_ == param.Type.DOUBLE:
                self.grid_resolution = param.value
                updated = True
                self.get_logger().info(f'Updated grid_resolution: {self.grid_resolution}')
            elif param.name == 'grid_width' and param.type_ == param.Type.INTEGER:
                self.grid_width = param.value
                updated = True
                self.get_logger().info(f'Updated grid_width: {self.grid_width}')
            elif param.name == 'grid_height' and param.type_ == param.Type.INTEGER:
                self.grid_height = param.value
                updated = True
                self.get_logger().info(f'Updated grid_height: {self.grid_height}')
            elif param.name == 'footprint_fill_mode' and param.type_ == param.Type.STRING:
                self.footprint_fill_mode = param.value
                updated = True
                self.get_logger().info(f'Updated footprint_fill_mode: {self.footprint_fill_mode}')
            # Add more parameters as needed
        # If grid size or resolution changed, reallocate grid
        if updated and ('grid_width' in [p.name for p in params] or 'grid_height' in [p.name for p in params] or 'grid_resolution' in [p.name for p in params]):
            self.radiation_grid = np.zeros((self.grid_height, self.grid_width), dtype=np.float32)
            self.get_logger().info('Reallocated radiation grid due to parameter change')
        return rclpy.parameter.ParameterEventHandlerResult(successful=True)
    
    def apply_decay(self):
        """Apply decay to radiation levels over time"""
        self.radiation_grid *= self.decay_rate
        # Zero out very small values
        self.radiation_grid[self.radiation_grid < self.background_threshold] = 0.0
    
    def publish_radiation_grid(self):
        if self.use_occupancy_grid:
            self.publish_occupancy_grid()
        if self.use_color_image:
            self.publish_radiation_image()
    
    def publish_occupancy_grid(self):
        """Publish radiation data as occupancy grid optimized for transparency overlay"""
        grid_msg = OccupancyGrid()
        grid_msg.header.frame_id = self.map_frame
        grid_msg.header.stamp = self.get_clock().now().to_msg()
        
        # Grid info
        grid_msg.info.resolution = self.grid_resolution
        grid_msg.info.width = self.grid_width
        grid_msg.info.height = self.grid_height
        grid_msg.info.origin.position.x = self.grid_origin_x
        grid_msg.info.origin.position.y = self.grid_origin_y
        grid_msg.info.origin.position.z = 0.0
        grid_msg.info.origin.orientation.w = 1.0
        
        # Convert radiation values to occupancy values optimized for transparency
        occupancy_data = []
        cells_with_data = 0
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                dose = self.radiation_grid[y, x]
                if dose <= self.background_threshold:
                    # Use -1 (unknown) for areas without radiation - RViz2 renders these as transparent
                    occupancy_data.append(-1)  
                else:
                    cells_with_data += 1
                    # Map dose to occupancy values for better color differentiation
                    if dose < self.lower_threshold:
                        # Low radiation - light color (low occupancy)
                        occupancy_value = max(1, int((dose / self.lower_threshold) * 30))
                    elif dose > self.upper_threshold:
                        # High radiation - dark color (high occupancy)
                        occupancy_value = 100
                    else:
                        # Scale between lower and upper thresholds
                        normalized = (dose - self.lower_threshold) / (self.upper_threshold - self.lower_threshold)
                        # Use wider range for better color gradation
                        occupancy_value = int(30 + normalized * 70)  # 30-100 range
                    
                    # Ensure minimum visibility while preserving gradation
                    occupancy_data.append(min(100, max(10, occupancy_value)))
        
        grid_msg.data = occupancy_data
        self.grid_pub.publish(grid_msg)
        
        if self.debug_logging:
            max_dose = np.max(self.radiation_grid)
            self.get_logger().debug(f'Published occupancy grid - Max dose: {max_dose:.3f} μSv/h, Cells with data: {cells_with_data}/{self.grid_width*self.grid_height}')
            # self.get_logger().debug(f'RViz2 tip: Set radiation map display Alpha=0.7 for transparency overlay')
    
    def publish_radiation_image(self):
        """Publish radiation data as a colored image with transparency"""
        if not CV_BRIDGE_AVAILABLE:
            self.get_logger().warn("Cannot publish radiation image: cv_bridge not available")
            return
            
        # Create RGBA image (with alpha channel for transparency)
        image = np.zeros((self.grid_height, self.grid_width, 4), dtype=np.uint8)
        
        for y in range(self.grid_height):
            for x in range(self.grid_width):
                dose = self.radiation_grid[y, x]
                
                if dose < self.background_threshold:
                    # Fully transparent where no radiation data
                    image[y, x] = [0, 0, 0, 0]  # BGRA: transparent
                else:
                    # Color mapping using configurable thresholds
                    normalized = min(1.0, max(0.0, 
                        (dose - self.lower_threshold) / (self.upper_threshold - self.lower_threshold)))
                    
                    if normalized < self.blue_threshold:
                        # Blue to cyan
                        t = normalized / self.blue_threshold
                        r, g, b = int(0), int(128 + 127*t), 255
                    elif normalized < self.green_threshold:
                        # Cyan to green
                        t = (normalized - self.blue_threshold) / (self.green_threshold - self.blue_threshold)
                        r, g, b = int(0), 255, int(255 - 255*t)
                    elif normalized < self.yellow_threshold:
                        # Green to yellow
                        t = (normalized - self.green_threshold) / (self.yellow_threshold - self.green_threshold)
                        r, g, b = int(255*t), 255, 0
                    else:
                        # Yellow to red
                        t = (normalized - self.yellow_threshold) / (1.0 - self.yellow_threshold)
                        r, g, b = 255, int(255 - 255*t), 0
                    
                    # Apply alpha transparency based on grid_alpha parameter
                    alpha = int(255 * self.grid_alpha)
                    image[y, x] = [b, g, r, alpha]  # BGRA format for OpenCV
        
        # Convert to ROS Image message with alpha channel
        try:
            image_msg = self.bridge.cv2_to_imgmsg(image, "bgra8")  # Use bgra8 instead of bgr8
            image_msg.header.frame_id = self.map_frame
            image_msg.header.stamp = self.get_clock().now().to_msg()
            self.image_pub.publish(image_msg)
            
            if self.debug_logging:
                non_transparent_pixels = np.sum(image[:, :, 3] > 0)  # Count non-transparent pixels
                self.get_logger().debug(f'Published RGBA image with {non_transparent_pixels} radiation pixels, alpha={self.grid_alpha}')
                
        except Exception as e:
            self.get_logger().warn(f'Failed to publish RGBA image: {e}')
            # Fallback to BGR if BGRA fails
            try:
                bgr_image = image[:, :, :3]  # Remove alpha channel
                image_msg = self.bridge.cv2_to_imgmsg(bgr_image, "bgr8")
                image_msg.header.frame_id = self.map_frame
                image_msg.header.stamp = self.get_clock().now().to_msg()
                self.image_pub.publish(image_msg)
                self.get_logger().info('Published BGR image (RGBA failed)')
            except Exception as e2:
                self.get_logger().error(f'Both RGBA and BGR image publishing failed: {e2}')

        
        # Convert to ROS Image message
        try:
            image_msg = self.bridge.cv2_to_imgmsg(image, "bgr8")
            image_msg.header.frame_id = self.map_frame
            image_msg.header.stamp = self.get_clock().now().to_msg()
            self.image_pub.publish(image_msg)
        except Exception as e:
            self.get_logger().warn(f'Failed to publish image: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = RadiationGridPublisher()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
