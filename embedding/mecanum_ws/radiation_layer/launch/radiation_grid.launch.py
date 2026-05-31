#!/usr/bin/env python3
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch.conditions import IfCondition
from launch_ros.actions import Node


def generate_launch_description():
    # Get the launch directory
    radiation_pkg_dir = get_package_share_directory('radiation_layer')
    config_file = os.path.join(radiation_pkg_dir, 'config', 'radiation_config.yaml')
    
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'config_file',
            default_value=config_file,
            description='Path to radiation layer config file'
        ),
        
        DeclareLaunchArgument(
            'use_fake_dose',
            default_value='false',
            description='Use fake dose publisher for testing'
        ),
        
        DeclareLaunchArgument(
            'use_static_tf',
            default_value='false',
            description='Use static transform publishers (disable for real robot)'
        ),
        
        # Fake dose publisher (conditional)
        ExecuteProcess(
            condition=IfCondition(LaunchConfiguration('use_fake_dose')),
            cmd=['python3', os.path.join(radiation_pkg_dir, 'scripts', 'fake_dose_publisher.py')],
            output='screen'
        ),
        
        # Static transform publishers (for testing - disable for real robot)
        Node(
            condition=IfCondition(LaunchConfiguration('use_static_tf')),
            package='tf2_ros',
            executable='static_transform_publisher',
            name='map_odom_broadcaster',
            arguments=['0', '0', '0', '0', '0', '0', 'map', 'odom']
        ),
        
        Node(
            condition=IfCondition(LaunchConfiguration('use_static_tf')),
            package='tf2_ros',
            executable='static_transform_publisher',
            name='odom_base_broadcaster',
            arguments=['0', '0', '0', '0', '0', '0', 'odom', 'base_footprint']
        ),
        
        # Radiation grid publisher
        Node(
            package='radiation_layer',
            executable='radiation_grid_publisher.py',
            name='radiation_grid_publisher',
            parameters=[LaunchConfiguration('config_file')],
            output='screen'
        ),
    ])
