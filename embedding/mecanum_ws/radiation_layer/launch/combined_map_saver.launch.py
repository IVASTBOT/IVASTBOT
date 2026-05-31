#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Get the launch directory
    radiation_pkg_dir = get_package_share_directory('radiation_layer')
    
    return LaunchDescription([
        # Launch arguments
        DeclareLaunchArgument(
            'output_directory',
            default_value='/tmp/combined_maps',
            description='Directory to save combined maps'
        ),
        
        DeclareLaunchArgument(
            'save_interval',
            default_value='10.0',
            description='Auto-save interval in seconds'
        ),
        
        DeclareLaunchArgument(
            'radiation_alpha',
            default_value='0.6',
            description='Transparency of radiation overlay (0.0-1.0)'
        ),
        
        DeclareLaunchArgument(
            'auto_save',
            default_value='true',
            description='Enable automatic saving'
        ),
        
        # Combined map saver node
        Node(
            package='radiation_layer',
            executable='combined_map_saver.py',
            name='combined_map_saver',
            parameters=[{
                'output_directory': LaunchConfiguration('output_directory'),
                'save_interval': LaunchConfiguration('save_interval'),
                'radiation_alpha': LaunchConfiguration('radiation_alpha'),
                'auto_save': LaunchConfiguration('auto_save'),
                'slam_map_topic': '/map',
                'radiation_map_topic': '/radiation_grid',
            }],
            output='screen'
        ),
    ])
