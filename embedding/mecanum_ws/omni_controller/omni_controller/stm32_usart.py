import rclpy
from rclpy.node import Node
from std_msgs.msg import Int32MultiArray, Float64MultiArray
from geometry_msgs.msg import Twist
import serial
import threading
import math
import time

class SerialBridgeNode(Node):
    def __init__(self):
        super().__init__('serial_bridge')

        # Wheel parameters
        self.wheel_radius = 0.07  # Wheel radius in meters

        # Mở cổng UART with shorter timeout for more responsive reading
        self.ser = serial.Serial('/dev/ttyUSB1', 9600, timeout=0.1)
        
        # Thread lock for serial write operations
        self.serial_lock = threading.Lock()

        # Publisher: dữ liệu từ STM32 gửi lên (raw encoder data)
        self.publisher_ = self.create_publisher(Int32MultiArray, 'serial_data', 10)
        
        # Publisher: wheel velocities in m/s
        self.vel_publisher = self.create_publisher(Float64MultiArray, 'vel_enc', 10)

        # Subscriber: dữ liệu gửi xuống STM32
        self.subscription = self.create_subscription(
            Twist,
            '/cmd_vel',
            self.write_to_serial,
            10
        )

        # Thread riêng để đọc UART liên tục
        self.read_thread = threading.Thread(target=self.read_serial_loop, daemon= True)
        self.read_thread.start()
        self.get_logger().info("Serial bridge node started.")

    #ros2 topic pub /to_stm32 std_msgs/String "data: 'Vx,Vy,W'"
    #ros2 topic pub /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"
    def write_to_serial(self, msg: Twist):
        try:
            linear_x = msg.linear.x
            linear_y = msg.linear.y
            angular_z = msg.angular.z

            # Biến các giá trị thành chuỗi cách nhau dấu ','
            vel_str = f"{linear_x},{linear_y},{angular_z}"

            data = vel_str.strip() + '\n'
            
            # Use thread lock to ensure atomic write operations
            with self.serial_lock:
                self.ser.write(data.encode('utf-8'))
                self.ser.flush()  # Ensure data is sent immediately
            # self.get_logger().info(f"[TX] Sent: {data}")
        except Exception as e:
            self.get_logger().error(f"Error sending to STM32: {e}")
                
    def read_serial_loop(self):
        while rclpy.ok():
            try:
                # Check if data is available in the input buffer
                if self.ser.in_waiting > 0:
                    raw = self.ser.readline()
                    #self.get_logger().info(f"Raw bytes: {raw}")
                    clean = raw.replace(b'\x00', b'').decode('utf-8').strip()

                    if clean:
                        values = clean.split(',')      # Tách các phần tử theo dấu phẩy
                        try:
                            values = [int(v) for v in values]

                            # Publish raw encoder data
                            msg = Int32MultiArray()
                            msg.data = values
                            self.publisher_.publish(msg)
                            
                            # Convert RPM to m/s and publish wheel velocities
                            if len(values) == 4:  # Ensure we have 4 encoder values
                                wheel_velocities = self.convert_rpm_to_ms(values)
                                vel_msg = Float64MultiArray()
                                vel_msg.data = wheel_velocities
                                self.vel_publisher.publish(vel_msg)
                                
                                # self.get_logger().info(f"[RX] Encoder RPM: {values}")
                                # self.get_logger().info(f"[RX] Wheel velocities (m/s): {[round(v, 3) for v in wheel_velocities]}")
                            else:
                                self.get_logger().warn(f"Expected 4 encoder values, got {len(values)}: {values}")
                        except ValueError as ve:
                            self.get_logger().warn(f"Failed to parse values: {clean} - {ve}")
                else:
                    # Small sleep to prevent excessive CPU usage when no data available
                    threading.Event().wait(0.001)  # 1ms sleep
            except Exception as e:
                self.get_logger().error(f"Error reading from STM32: {e}")
                # Brief pause before retrying to avoid rapid error loops
                threading.Event().wait(0.01)
    
    def convert_rpm_to_ms(self, rpm_values):
        """
        Convert RPM values to linear velocity in m/s
        Formula: v = (RPM * 2 * π * radius) / 60
        """
        velocities = []
        for rpm in rpm_values:
            # Convert RPM to rad/s: rpm * (2π/60)
            angular_velocity = rpm * (2 * math.pi / 60.0)
            # Convert to linear velocity: v = ω * r
            linear_velocity = angular_velocity * self.wheel_radius
            velocities.append(linear_velocity)
        return velocities

def main(args=None):
    rclpy.init(args=args)
    node = SerialBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shutdown()
