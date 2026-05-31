#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import pygame


class GamepadSocketNode(Node):
    def __init__(self):
        super().__init__("gamepad_socket_node")
        self.publisher_ = self.create_publisher(Twist, "/cmd_vel", 10)

        # Kết nối với tay cầm đầu tiên
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        self.get_logger().info(f"Đã kết nối với tay cầm: {self.joystick.get_name()}")

        # Timers
        self.timer = self.create_timer(0.1, self.timer_callback)  # 10 Hz

        #variable
        self.v_x = 0
        self.v_y = 0
        self.w = 0
    

    def timer_callback(self):
        # Xử lý sự kiện
        pygame.event.pump()
        
        # Đọc trạng thái các nút                                                                        
        buttons = [self.joystick.get_button(i) for i in range(self.joystick.get_numbuttons())]
        
        # Đọc cần analog (trục)
        axes = [self.joystick.get_axis(i) for i in range(self.joystick.get_numaxes())]
        
        # D-pad (hat/axes 8-9 hoặc buttons 11-14)
        if self.joystick.get_numhats() > 0:
            hat = self.joystick.get_hat(0)
            listhat = list(hat)

        # Xử lý dữ liệu
        if buttons[2] == 1:
            self.v_y -= 0.02
            if self.v_y <= 0:
                self.v_y = 0

        if buttons[1] == 1:
            self.v_y += 0.02
            if self.v_y > 0.9:
                self.v_y = 0.9

        if buttons[0] == 1:
            self.v_x -= 0.02
            if self.v_x <= 0:
                self.v_x = 0

        if buttons[3] == 1:
            self.v_x += 0.02
            if self.v_x > 0.9:
                self.v_x = 0.9

        self.v_x = round(self.v_x, 2)
        self.v_y = round(self.v_y, 2)

        if listhat[1] == 1:
            v_xt = self.v_x
        elif listhat[1] == -1:
            if self.v_x >= 0:
                v_xt = -self.v_x
        elif listhat[1] == 0:
            v_xt = 0

        if listhat[0] == 1:
            v_yt = -self.v_y
        elif listhat[0] == -1:
            if self.v_y >= 0:
                v_yt = self.v_y
        elif listhat[0] == 0:
            v_yt = 0

        if round(axes[2]) == 1:
            self.w -= 0.02
            if self.w <= 0:
                self.w = 0
        
        if round(axes[5]) == 1:
            self.w += 0.02
            if self.w > 2:
                self.w = 2
        self.w = round(self.w, 2)

        if buttons[4] == 1 and buttons[5] == 0:
            wt = -self.w
        elif buttons[4] == 0 and buttons[5] == 1:
            wt = self.w
        elif buttons[4] == 0 and buttons[5] == 0:
            wt = 0

        # Đảo trục Y cần analog trái
        axes[1] = axes[1]*-1
        if round(axes[0], 2) != 0:
            if axes[0] > 0: 
                v_yt = round(((axes[0])/10)+self.v_y, 2)
            elif axes[0] < 0:
                v_yt = round(((axes[0])/10)-self.v_y, 2)
        if round(axes[1], 2) != 0:
            if axes[1] > 0:
                v_xt = round(((axes[1])/10)+self.v_x, 2) 
            elif axes[1] < 0:
                v_xt = round(((axes[1])/10)-self.v_x, 2) 

        # Thoát nếu nhấn nút Start
        if buttons[7]:  
            self.get_logger().info("Đã nhấn nút START - thoát.")
            rclpy.shutdown()
        
        data = [v_xt, v_yt, wt]

        msg = Twist()
        msg.linear.x = float(data[0])
        msg.linear.y = float(data[1])
        msg.angular.z = float(data[2])
        self.publisher_.publish(msg)
        self.get_logger().info(str(msg))


def main(args=None):
    pygame.init()
    pygame.joystick.init()
    rclpy.init(args=args)
        
    node = GamepadSocketNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Người dùng dừng node.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
