#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Declare launch arguments
    linear_velocity_arg = DeclareLaunchArgument(
        'linear_velocity',
        default_value='0.2',
        description='Maximum linear velocity in m/s'
    )
    
    angular_velocity_arg = DeclareLaunchArgument(
        'angular_velocity',
        default_value='0.5',
        description='Maximum angular velocity in rad/s'
    )
    
    deadzone_arg = DeclareLaunchArgument(
        'deadzone',
        default_value='0.1',
        description='Joystick deadzone threshold'
    )
    
    velocity_step_arg = DeclareLaunchArgument(
        'velocity_step',
        default_value='0.05',
        description='Velocity adjustment step for X/Y/A/B buttons'
    )
    
    input_timeout_arg = DeclareLaunchArgument(
        'input_timeout',
        default_value='0.5',
        description='Safety timeout in seconds for auto-stop when no input'
    )
    
    device_arg = DeclareLaunchArgument(
        'device',
        default_value='/dev/input/js0',
        description='Joystick device path'
    )
    
    # Joy node - publishes gamepad input to /joy topic
    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        parameters=[{
            'dev': LaunchConfiguration('device'),
            'deadzone': 0.05,
            'autorepeat_rate': 20.0,
        }],
        output='screen'
    )
    
    # Simple gamepad teleop node - converts /joy to /cmd_vel for 4-wheel omni robot
    simple_gamepad_teleop_node = Node(
        package='gamepad',
        executable='gamepad_teleop',
        name='gamepad_teleop',
        parameters=[{
            'linear_velocity': LaunchConfiguration('linear_velocity'),
            'angular_velocity': LaunchConfiguration('angular_velocity'),
            'deadzone': LaunchConfiguration('deadzone'),
            'velocity_step': LaunchConfiguration('velocity_step'),
            'input_timeout': LaunchConfiguration('input_timeout'),
            'linear_x_axis': 0,    # Left stick X axis (strafe left/right)
            'linear_y_axis': 1,    # Left stick Y axis (forward/backward)
            'angular_axis': 3,     # Right stick X axis (rotation)
            'right_stick_y_axis': 4, # Right stick Y axis (tank-style forward/backward)
            'button_a': 0,         # A button (decrease linear vel)
            'button_b': 1,         # B button (increase angular vel)
            'button_x': 2,         # X button (decrease angular vel)
            'button_y': 3,         # Y button (increase linear vel)
            'dpad_vertical_axis': 7,   # D-pad up/down axis
            'dpad_horizontal_axis': 6, # D-pad left/right axis
            'dpad_rotation_button_l': 4, # L1 button for left rotation
            'dpad_rotation_button_r': 5, # R1 button for right rotation
        }],
        output='screen'
    )
    
    # Log info message
    log_info = LogInfo(
        msg=[
            '\n',
            '=' * 60, '\n',
            '4-WHEEL OMNI ROBOT GAMEPAD TELEOP LAUNCHED\n',
            '=' * 60, '\n',
            'Controls:\n',
            '  Left Stick: Omni movement (X=strafe, Y=forward/backward)\n',
            '  Right Stick: Tank-style (X=rotation, Y=forward/backward)\n',
            '  D-pad: Discrete movement (Up/Down/Left/Right)\n',
            '  L1/R1: Discrete rotation (left/right)\n',
            '  L2+R2: Emergency stop\n',
            '  Y button: Increase linear velocity\n',
            '  A button: Decrease linear velocity\n',
            '  B button: Increase angular velocity\n',
            '  X button: Decrease angular velocity\n',
            '\n',
            'Safety Features:\n',
            '  Auto-stop timeout: When no input detected\n',
            '  Emergency stop: L2+R2 triggers together\n',
            '\n',
            'Publishing to: /cmd_vel\n',
            'Subscribing to: /joy\n',
            '=' * 60, '\n'
        ]
    )

    return LaunchDescription([
        linear_velocity_arg,
        angular_velocity_arg,
        deadzone_arg,
        velocity_step_arg,
        input_timeout_arg,
        device_arg,
        log_info,
        joy_node,
        simple_gamepad_teleop_node,
    ])
