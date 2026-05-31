#!/usr/bin/env python3
"""
Launch file for robot bringup with ros2_control (C++ hardware interface).
Uses:
  - controller_manager (loads KincoCANopenHW plugin)
  - diff_drive_controller (kinematics + odometry + TF)
  - joint_state_broadcaster
"""

import os
from launch import LaunchDescription
from launch.actions import TimerAction
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # Paths
    pkg_dir = get_package_share_directory('motor')
    urdf_file = os.path.join(pkg_dir, 'urdf', 'hinson_robot.urdf.xacro')
    controllers_file = os.path.join(pkg_dir, 'config', 'controllers.yaml')

    robot_description = ParameterValue(
        Command(['xacro ', urdf_file]), value_type=str)

    # ============================================================
    # 1. Robot State Publisher — URDF model + static TF
    # ============================================================
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}]
    )

    # ============================================================
    # 2. Controller Manager — loads C++ hardware plugin
    # ============================================================
    controller_manager = Node(
        package='controller_manager',
        executable='ros2_control_node',
        parameters=[
            {'robot_description': robot_description},
            controllers_file,
        ],
        output='screen',
        remappings=[
            ('/drivetrain_controller/cmd_vel_unstamped', '/cmd_vel'),
        ],
    )

    # ============================================================
    # 3. Spawn controllers (after controller_manager starts)
    # ============================================================
    joint_state_broadcaster_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['joint_state_broadcaster',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )

    drivetrain_controller_spawner = Node(
        package='controller_manager',
        executable='spawner',
        arguments=['drivetrain_controller',
                   '--controller-manager', '/controller_manager'],
        output='screen',
    )

    # Delay spawners to ensure controller_manager is ready
    delayed_spawners = TimerAction(
        period=2.0,
        actions=[
            joint_state_broadcaster_spawner,
            drivetrain_controller_spawner,
        ],
    )

    # ============================================================
    # 4. Lidar node (TCP -> /scan)
    # ============================================================
    hins_lidar = Node(
        package='hins_le_ros2',
        executable='hins_le_ros2_node',
        name='hins_le_ros2_node',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'frame_id': 'laser_frame',
            'change_param': True,
            'laser_ip': '192.168.10.52',
            'laser_port': 8080,
            'measure_frequency_kHz': '200',
            'motor_speed': '20',
            'point_sampling': '2',
            'filter_level': '2',
            'shadows_filter_level': 1,
            'shadows_filter_max_angle': 175.0,
            'shadows_filter_min_angle': 5.0,
            'shadows_filter_neighbors': 1,
            'shadows_filter_window': 5,
            'shadows_traverse_step': 1,
            'min_angle': 0.0,
            'max_angle': 361.0,
            'use_udp': False,
        }]
    )

    # ============================================================
    # 5. Scan filter (/scan -> /scan_filtered)
    # ============================================================
    scan_filter = Node(
        package='motor',
        executable='scan_filter_node',
        name='scan_filter_node',
        output='screen',
        parameters=[{
            'robot_length':     0.9,
            'robot_width':      0.5,
            'laser_offset_x':   0.4,
            'laser_offset_y':   0.0,
            'footprint_margin': 0.05,
        }]
    )

    return LaunchDescription([
        robot_state_publisher,
        controller_manager,
        delayed_spawners,
        hins_lidar,
        scan_filter,
    ])
