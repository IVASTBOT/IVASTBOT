#!/usr/bin/env python3
# ============================================================
# bringup.launch.py — Main launch for IvastBot
#
# Launches:
#   1. robot_state_publisher (URDF → TF)
#   2. ros2_control (controller_manager + diff_drive)
#   3. RPLidar A2M8
# ============================================================

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, TimerAction
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    pkg_bringup = get_package_share_directory('bringup')
    xacro_file = os.path.join(pkg_bringup, 'urdf', 'ivastbot.urdf.xacro')
    controllers_file = os.path.join(pkg_bringup, 'config', 'controllers.yaml')

    # ============================================================
    # Launch arguments
    # ============================================================
    serial_port_arg = DeclareLaunchArgument(
        'lidar_serial_port',
        default_value='/dev/ttyUSB0',
        description='Serial port for RPLidar'
    )

    # ============================================================
    # 1. Robot State Publisher (URDF → /robot_description, TF)
    # ============================================================
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        parameters=[{'robot_description': robot_description}],
    )

    # ============================================================
    # 2. ros2_control — controller_manager + spawners
    # ============================================================
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[{'robot_description': robot_description}, controllers_file],
        remappings=[
            ('/drivetrain_controller/cmd_vel_unstamped', '/cmd_vel'),
        ],
        output='screen',
    )

    # Spawners with delay to let controller_manager initialize
    delayed_spawners = TimerAction(
        period=2.0,
        actions=[
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=['joint_state_broadcaster'],
                output='screen',
            ),
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=['drivetrain_controller'],
                output='screen',
            ),
        ],
    )

    # ============================================================
    # 3. RPLidar A2M8 (serial -> /scan)
    # ============================================================
    rplidar_node = Node(
        package='sllidar_ros2',
        executable='sllidar_node',
        name='sllidar_node',
        output='screen',
        parameters=[{
            'channel_type': 'serial',
            'serial_port': LaunchConfiguration('lidar_serial_port'),
            'serial_baudrate': 115200,
            'frame_id': 'laser',
            'inverted': False,
            'angle_compensate': True,
        }],
    )

    return LaunchDescription([
        serial_port_arg,
        robot_state_publisher,
        controller_manager,
        delayed_spawners,
        rplidar_node,
    ])
