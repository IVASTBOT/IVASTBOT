#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Quaternion, Twist, Pose, Point, Vector3
from tf2_ros import TransformBroadcaster
from geometry_msgs.msg import TransformStamped
import math
import time

class OdometryNode(Node):
    def __init__(self):
        super().__init__('odometry_node')
        
        # Robot physical parameters (adjust these to match your robot)
        self.wheel_radius = 0.07  # Wheel radius in meters
        self.wheel_base = 0.25   # Distance from center to wheels (meters)

        # Robot state variables
        self.x = 0.0      # Position x (meters)
        self.y = 0.0      # Position y (meters) 
        self.theta = 0.0  # Orientation (radians)
        
        self.vx = 0.0     # Linear velocity x (m/s)
        self.vy = 0.0     # Linear velocity y (m/s)
        self.vth = 0.0    # Angular velocity (rad/s)
        
        # Time tracking
        self.last_time = time.time()
        
        # Publishers
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.velocity_pub = self.create_publisher(Twist, '/vel_robot', 10)
        
        # TF broadcaster
        self.tf_broadcaster = TransformBroadcaster(self)
        
        # Subscriber to wheel velocities
        self.wheel_vel_sub = self.create_subscription(
            Float64MultiArray,
            'vel_enc',
            self.wheel_velocity_callback,
            10
        )
        
        # Timer for odometry publishing
        self.timer = self.create_timer(0.02, self.publish_odometry)  # 50Hz
        
        self.get_logger().info("Odometry node started")
        
    def wheel_velocity_callback(self, msg):
        # Assumes wheel order: [front_left, front_right, rear_left, rear_right]
        if len(msg.data) != 4:
            self.get_logger().warn(f"Expected 4 wheel velocities, got {len(msg.data)}")
            return
            
        # Extract individual wheel velocities (m/s)
        v_fr = msg.data[0]  
        v_fl = msg.data[1]  
        v_rr = msg.data[2]  
        v_rl = msg.data[3]  

        self.vx = (math.sqrt(2)/8)*(-v_fl + v_fr - v_rl + v_rr )
        self.vy = (math.sqrt(2)/8)*(v_fl + v_fr - v_rl - v_rr )
        self.vth = (v_fl + v_fr + v_rl + v_rr) / (4.0 * self.wheel_base)

        # Publish calculated velocities for debugging
        velocity_msg = Twist()
        velocity_msg.linear.x = self.vx
        velocity_msg.linear.y = self.vy
        velocity_msg.linear.z = 0.0
        velocity_msg.angular.x = 0.0
        velocity_msg.angular.y = 0.0
        velocity_msg.angular.z = self.vth
        
        self.velocity_pub.publish(velocity_msg)

        # self.get_logger().info(f"Robot velocities - vx: {self.vx:.3f}, vy: {self.vy:.3f}, vth: {self.vth:.3f}")
        
    def publish_odometry(self):
        """
        Integrate velocities to get position and publish odometry
        """
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            return
            
        # Integrate velocities to get position
        # For differential drive with theta rotation:
        # dx = (vx * cos(theta) - vy * sin(theta)) * dt
        # dy = (vx * sin(theta) + vy * cos(theta)) * dt
        # dtheta = vth * dt
        
        delta_x = (self.vx * math.cos(self.theta) - self.vy * math.sin(self.theta)) * dt
        delta_y = (self.vx * math.sin(self.theta) + self.vy * math.cos(self.theta)) * dt
        delta_th = self.vth * dt
        
        # Update position
        self.x += delta_x
        self.y += delta_y
        self.theta += delta_th
        
        # Normalize theta to [-pi, pi]
        self.theta = math.atan2(math.sin(self.theta), math.cos(self.theta))
        
        # Create quaternion from yaw
        q = self.euler_to_quaternion(0, 0, self.theta)
        
        # Create and publish transform
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_footprint'
        
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation = q
        
        self.tf_broadcaster.sendTransform(t)
        
        # Create and publish odometry message
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'
        
        # Position
        odom.pose.pose.position = Point(x=self.x, y=self.y, z=0.0)
        odom.pose.pose.orientation = q
        
        # Velocity
        odom.twist.twist.linear = Vector3(x=self.vx, y=self.vy, z=0.0)
        odom.twist.twist.angular = Vector3(x=0.0, y=0.0, z=self.vth)
        
        # Covariance matrices (you may want to tune these based on your robot's characteristics)
        odom.pose.covariance = [
            0.1, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.1, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.1
        ]
        
        odom.twist.covariance = [
            0.05, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.05, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, 0.0, 0.0, 0.0, 0.0, 0.05
        ]
        
        self.odom_pub.publish(odom)
        
        self.last_time = current_time
        
    def euler_to_quaternion(self, roll, pitch, yaw):
        """
        Convert Euler angles to quaternion
        """
        cy = math.cos(yaw * 0.5)
        sy = math.sin(yaw * 0.5)
        cp = math.cos(pitch * 0.5)
        sp = math.sin(pitch * 0.5)
        cr = math.cos(roll * 0.5)
        sr = math.sin(roll * 0.5)

        q = Quaternion()
        q.w = cy * cp * cr + sy * sp * sr
        q.x = cy * cp * sr - sy * sp * cr
        q.y = sy * cp * sr + cy * sp * cr
        q.z = sy * cp * cr - cy * sp * sr

        return q

def main(args=None):
    rclpy.init(args=args)
    node = OdometryNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
