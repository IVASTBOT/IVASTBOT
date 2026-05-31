#!/usr/bin/env python3
"""
Flydigi Controller ROS2 Node - Differential Drive
Điều khiển robot 2 bánh vi sai (Kinco iWMC) qua /cmd_vel topic
Tương thích với các tay cầm Flydigi (Apex, Vader, Direwolf, v.v.)

Flydigi trên Linux thường nhận diện qua xinput mode.
Node sẽ tự detect button mapping dựa trên tên tay cầm.

Mapping mặc định (Xinput / Flydigi):
    Left Stick Y    -> Tiến/Lùi (linear.x)
    Right Stick X   -> Quay trái/phải (angular.z)
    Y (axis 3)      -> Tiến
    A (axis 0)      -> Lùi
    X (axis 2)      -> Quay trái
    B (axis 1)      -> Quay phải
    LB (L1)         -> Giảm tốc
    RB (R1)         -> Tăng tốc
    START           -> Thoát (smooth deceleration)
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Float64
import pygame

# ─────────────────────────────────────────────────────────────
# Flydigi button mapping (Xinput mode - mặc định trên Linux)
# Flydigi thường nhận diện như: "Flydigi Vader 2" hoặc tương tự
# Xinput layout tương tự Xbox 360
# ─────────────────────────────────────────────────────────────
BTN_A  = 0    # Nút A (phía dưới)
BTN_B  = 1    # Nút B (phía phải)
BTN_X  = 2    # Nút X (phía trái)
BTN_Y  = 3    # Nút Y (phía trên)
BTN_LB = 4    # L1 / LB
BTN_RB = 5    # R1 / RB
BTN_BACK  = 6   # Back / Select
BTN_START = 7   # Start / Menu
BTN_HOME  = 8   # Home / Logo (nếu có)
BTN_L3 = 9      # Left stick press
BTN_R3 = 10     # Right stick press

# Axis mapping (Flydigi Xinput)
AXIS_LX = 0   # Left stick X
AXIS_LY = 1   # Left stick Y
AXIS_RX = 3   # Right stick X
AXIS_RY = 4   # Right stick Y
AXIS_LT = 2   # Left trigger (L2)
AXIS_RT = 5   # Right trigger (R2)

# Speed parameters
SPEED_STEP  = 0.1         # Bước tăng/giảm tốc max (m/s)
SPEED_MIN   = 0.15        # ~ 180 RPM motor (m/s) — rất chậm
SPEED_MAX   = 0.8         # ~ 950 RPM motor (m/s)
SPEED_INIT  = 0.15        # Khởi động ở tốc độ thấp nhất
MAX_ANGULAR = 1.0         # Vận tốc góc tối đa (rad/s)

# Smooth ramp rates — giá trị nhỏ = mượt hơn
ACCEL_RATE       = 1.0    # Gia tốc tuyến tính (m/s²) — 0→0.15 trong 0.15s
DECEL_RATE       = 1.5    # Giảm tốc tuyến tính (m/s²) — 0.15→0 trong 0.1s
ANGULAR_ACCEL    = 1.5    # Gia tốc góc (rad/s²)
ANGULAR_DECEL    = 1.5    # Giảm tốc góc (rad/s²)

SEND_HZ = 50  # Tần số gửi lệnh (Hz) — cao hơn = mượt hơn

# Deadzone cho analog stick
DEADZONE = 0.15


def ramp_towards(current, target, accel_rate, decel_rate, dt):
    """
    Thay đổi giá trị current tiến dần về target với tốc độ tăng/giảm mượt mà.
    (Copied from kinco_canopen_control.py)
    """
    diff = target - current
    if abs(diff) < 0.001:
        return target

    # Chọn rate: giảm tốc nhanh hơn khi thả nút (target=0)
    if abs(target) < 0.001:
        rate = decel_rate
    else:
        rate = accel_rate

    step = rate * dt
    if abs(diff) <= step:
        return target
    elif diff > 0:
        return current + step
    else:
        return current - step


class FlydigiControllerNode(Node):
    def __init__(self):
        super().__init__('flydigi_controller_node')
        self.publisher_ = self.create_publisher(Twist, '/cmd_vel', 10)
        self.speed_pub_ = self.create_publisher(Float64, '/speed_setting', 10)

        # ROS parameter: chọn joystick theo index (-1 = tự động chọn cái đầu)
        self.declare_parameter('joystick_index', -1)
        joy_idx = self.get_parameter('joystick_index').value

        # Liệt kê tất cả joystick đang kết nối
        n_joy = pygame.joystick.get_count()
        self.get_logger().info(f"Tìm thấy {n_joy} tay cầm:")
        for i in range(n_joy):
            j = pygame.joystick.Joystick(i)
            j.init()
            self.get_logger().info(
                f"  [{i}] {j.get_name()} | Axes: {j.get_numaxes()}, Buttons: {j.get_numbuttons()}")

        # Chọn joystick
        if joy_idx < 0:
            # Tự động tìm tay cầm Flydigi
            joy_idx = self._find_flydigi(n_joy)
            if joy_idx < 0:
                self.get_logger().warn("Không tìm thấy tay cầm Flydigi! Dùng tay cầm đầu tiên.")
                joy_idx = 0

        if joy_idx >= n_joy:
            self.get_logger().error(f"Joystick index {joy_idx} không tồn tại! Chỉ có {n_joy} tay cầm.")
            raise RuntimeError(f"Joystick {joy_idx} not found")

        self.joystick = pygame.joystick.Joystick(joy_idx)
        self.joystick.init()
        joy_name = self.joystick.get_name()
        self.get_logger().info(f"▶ Đang dùng tay cầm [{joy_idx}]: {joy_name}")
        self.get_logger().info(f"  Số trục: {self.joystick.get_numaxes()}, Số nút: {self.joystick.get_numbuttons()}")

        # Detect axis mapping dựa trên số trục
        self._detect_axis_mapping()

        # Speed state
        self.max_linear = SPEED_INIT
        self.max_angular = MAX_ANGULAR
        self._publish_speed()  # Publish tốc độ ban đầu
        self.rb_was_pressed = False
        self.lb_was_pressed = False
        self.rt_was_pressed = False
        self.lt_was_pressed = False

        # Smooth ramp: current velocities (change gradually)
        self.current_v = 0.0      # m/s
        self.current_omega = 0.0  # rad/s

        # Timer at SEND_HZ
        self.dt = 1.0 / SEND_HZ
        self.timer = self.create_timer(self.dt, self.timer_callback)

        self.get_logger().info(f"control motor")
        self.get_logger().info(f"Y: ahead | A: backward | X: left | B: right")
        self.get_logger().info(f"Left Stick: ahead/backward | Right Stick: left/right")
        self.get_logger().info(f"RB(R1)/RT(R2): tăng/giảm tốc độ tiến lùi | LB(L1)/LT(L2): tăng/giảm tốc độ xoay")
        self.get_logger().info(f"Tốc độ ban đầu: linear={self.max_linear:.2f} m/s, angular={self.max_angular:.2f} rad/s")
        self.get_logger().info(f"Ramp: accel={ACCEL_RATE} m/s², decel={DECEL_RATE} m/s²")

    def _find_flydigi(self, n_joy):
        """auto finding flydigi"""
        flydigi_keywords = ['flydigi', 'vader', 'apex', 'direwolf', 'wee']
        for i in range(n_joy):
            j = pygame.joystick.Joystick(i)
            j.init()
            name_lower = j.get_name().lower()
            for keyword in flydigi_keywords:
                if keyword in name_lower:
                    self.get_logger().info(f"found flydigi at index {i}: {j.get_name()}")
                    return i
        return -1

    def _detect_axis_mapping(self):
        """
        Detect axis mapping based on the number of axes of the joystick.
        Flydigi can report 6 or 8 axes depending on model/firmware.
        """
        num_axes = self.joystick.get_numaxes()
        self.get_logger().info(f"Detecting axis mapping for {num_axes} axes...")

        if num_axes >= 6:
            # Xinput standard: LX=0, LY=1, LT=2, RX=3, RY=4, RT=5
            self.axis_lx = 0
            self.axis_ly = 1
            self.axis_rx = 3
            self.axis_ry = 4
            self.get_logger().info("  Mapping: Xinput standard (6+ axes)")
        elif num_axes >= 4:
            # Compact mode: LX=0, LY=1, RX=2, RY=3
            self.axis_lx = 0
            self.axis_ly = 1
            self.axis_rx = 2
            self.axis_ry = 3
            self.get_logger().info("  Mapping: Compact (4 axes)")
        else:
            # Only 2 axes (left stick only)
            self.axis_lx = 0
            self.axis_ly = 1
            self.axis_rx = 0  # dùng chung left stick cho rotation
            self.axis_ry = -1
            self.get_logger().warn("  Only 2 axes! Use left stick for both movement and rotation.")

    def _publish_speed(self):
        """Publish speed setting"""
        msg = Float64()
        msg.data = float(self.max_linear)
        self.speed_pub_.publish(msg)

    def timer_callback(self):
        pygame.event.pump()
        rb_pressed = self.joystick.get_button(BTN_RB)
        lb_pressed = self.joystick.get_button(BTN_LB)
        
        num_axes = self.joystick.get_numaxes()
        rt_pressed = (num_axes > AXIS_RT and self.joystick.get_axis(AXIS_RT) > 0.5)
        lt_pressed = (num_axes > AXIS_LT and self.joystick.get_axis(AXIS_LT) > 0.5)

        # Điều khiển tốc độ tiến lùi (Linear)
        if rb_pressed and not self.rb_was_pressed:
            self.max_linear = min(self.max_linear + SPEED_STEP, SPEED_MAX)
            self.get_logger().info(f"Tốc độ TIẾN LÙI max: {self.max_linear:.2f} m/s")
            self._publish_speed()
        if rt_pressed and not self.rt_was_pressed:
            self.max_linear = max(self.max_linear - SPEED_STEP, SPEED_MIN)
            self.get_logger().info(f"Tốc độ TIẾN LÙI max: {self.max_linear:.2f} m/s")
            self._publish_speed()

        # Điều khiển tốc độ xoay (Angular)
        if lb_pressed and not self.lb_was_pressed:
            self.max_angular = min(self.max_angular + SPEED_STEP, MAX_ANGULAR)
            self.get_logger().info(f"Tốc độ XOAY max: {self.max_angular:.2f} rad/s")
        if lt_pressed and not self.lt_was_pressed:
            self.max_angular = max(self.max_angular - SPEED_STEP, SPEED_MIN)
            self.get_logger().info(f"Tốc độ XOAY max: {self.max_angular:.2f} rad/s")

        self.rb_was_pressed = rb_pressed
        self.lb_was_pressed = lb_pressed
        self.rt_was_pressed = rt_pressed
        self.lt_was_pressed = lt_pressed

        # --- Determine target velocities from buttons ---
        target_v = 0.0
        target_omega = 0.0

        # Button control (D-pad style)
        if self.joystick.get_button(BTN_Y):      # Y = ahead
            target_v = self.max_linear
        elif self.joystick.get_button(BTN_A):     # A = backward
            target_v = -self.max_linear

        # Angular speed uses self.max_angular independent of linear

        if self.joystick.get_button(BTN_X):       # X = left
            target_omega = self.max_angular
        elif self.joystick.get_button(BTN_B):     # B = right
            target_omega = -self.max_angular

        # Analog stick control (only if buttons aren't driving)
        num_axes = self.joystick.get_numaxes()

        if abs(target_v) < 0.001:
            if num_axes > self.axis_ly:
                ax_ly = self.joystick.get_axis(self.axis_ly)
                if abs(ax_ly) > DEADZONE:
                    target_v = -ax_ly * self.max_linear

        if abs(target_omega) < 0.001:
            if num_axes > self.axis_rx:
                ax_rx = self.joystick.get_axis(self.axis_rx)
                if abs(ax_rx) > DEADZONE:
                    target_omega = -ax_rx * self.max_angular
            # Fallback: use left stick X if there is no separate right stick
            elif self.axis_rx == self.axis_lx and num_axes > self.axis_lx:
                ax_lx = self.joystick.get_axis(self.axis_lx)
                if abs(ax_lx) > DEADZONE:
                    target_omega = -ax_lx * self.max_angular

        # --- Smooth ramp towards target ---
        self.current_v = ramp_towards(
            self.current_v, target_v, ACCEL_RATE, DECEL_RATE, self.dt)
        self.current_omega = ramp_towards(
            self.current_omega, target_omega, ANGULAR_ACCEL, ANGULAR_DECEL, self.dt)

        # Publish Twist - Negate to match physical forward direction (-X in URDF)
        msg = Twist()
        msg.linear.x = float(round(self.current_v, 4))
        msg.linear.y = 0.0  # Differential drive can't go sideways
        msg.angular.z = float(round(self.current_omega, 4))
        self.publisher_.publish(msg)

        # Exit on START button (smooth deceleration first)
        if self.joystick.get_numbuttons() > BTN_START and self.joystick.get_button(BTN_START):
            self.get_logger().info("Press START - smooth deceleration and exit...")
            self._smooth_stop()
            stop_msg = Twist()
            self.publisher_.publish(stop_msg)
            raise SystemExit()

    def _smooth_stop(self):
        """Smooth deceleration to zero before exit"""
        for _ in range(int(SEND_HZ * 2)):  
            self.current_v = ramp_towards(
                self.current_v, 0, ACCEL_RATE, DECEL_RATE, self.dt)
            self.current_omega = ramp_towards(
                self.current_omega, 0, ANGULAR_ACCEL, ANGULAR_DECEL, self.dt)

            msg = Twist()
            msg.linear.x = float(round(self.current_v, 4))
            msg.angular.z = float(round(self.current_omega, 4))
            self.publisher_.publish(msg)

            if abs(self.current_v) < 0.001 and abs(self.current_omega) < 0.001:
                break
            import time
            time.sleep(self.dt)


def main(args=None):
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("Not found joystick! Connect USB receiver and try again.")
        print("Tip: Try running 'jstest /dev/input/js0' to check joystick.")
        pygame.quit()
        return

    rclpy.init(args=args)
    node = FlydigiControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Ctrl+C - smooth deceleration...")
        try:
            node._smooth_stop()
            stop_msg = Twist()
            node.publisher_.publish(stop_msg)
        except Exception:
            pass
    except (SystemExit, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        pygame.quit()


if __name__ == '__main__':
    main()
