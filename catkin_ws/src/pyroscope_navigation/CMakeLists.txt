cmake_minimum_required(VERSION 3.0.2)
project(pyroscope_navigation)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  nav_msgs
  tf
  actionlib
  move_base_msgs
)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/waypoint_controller.py
  scripts/coverage_planner.py
  scripts/lidar_obstacle_detector.py
  scripts/safety_stop.py
  scripts/random_explorer.py
  scripts/fake_odom.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)

install(DIRECTORY config/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
)
