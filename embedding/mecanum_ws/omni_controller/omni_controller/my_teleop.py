#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys, select, termios, tty

move_bindings = {
    'a': (0.0, 0.0, -1.0),
    'd': (0.0, 0.0, 1.0),
    'x': (0.0, 0.0, 0.0), #stop
    '\x1b[A' : (0.0, 1.0, 0.0), # up
    '\x1b[B' : (0.0, -1.0, 0.0), # down
    '\x1b[D' : (-1.0, 0.0, 0.0), # left
    '\x1b[C' : (1.0, 0.0, 0.0), # right
    ' ' : (0.0, 0.0, 0.0), #stop
}

#ros2 run teleop_twist_keyboard teleop_twist_keyboard 

def get_key():
    tty.setraw(sys.stdin.fileno())
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    key = ''
    if rlist:
        key = sys.stdin.read(1)
        if key == '\x1b':
            key += sys.stdin.read(2)
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

settings = termios.tcgetattr(sys.stdin)

class TeleopNode(Node):
    
    def __init__(self):
        super().__init__('ny_teleop_key')
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.timer_ = self.create_timer(0.1, self.timer_callback)
        self.get_logger().info('Teleop node started.')

    def timer_callback(self):
        key = get_key()
        if key in move_bindings:
            linear_x, linear_y, angular_z = move_bindings[key]
            msg = Twist()
            msg.linear.x = linear_x
            msg.linear.y = linear_y
            msg.angular.z = angular_z
            self.publisher_.publish(msg)
            self.get_logger().info(f"Published Twist: linear.x={linear_x}, linear.y={linear_y}, angular.z={angular_z}")
        elif key != '':
            self.get_logger().warn(f"Unrecognized key: {key}")
        if key == 'q':
            msg = Twist()
            msg.linear.x = 0.0
            msg.linear.y = 0.0
            msg.amgular.z = 0.0
            self.publisher_.publish(msg)
            self.get_logger().info("Stropping node")
            rclpy.shutdown()

def main(args = None):
    rclpy.init(args=args)
    node = TeleopNode()
    try: 
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    rclpy.shudown()
