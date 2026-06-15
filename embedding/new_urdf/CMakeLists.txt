cmake_minimum_required(VERSION 3.8)
project(urdf4)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY config launch meshes urdf textures
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
