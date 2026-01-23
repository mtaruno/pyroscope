cmake_minimum_required(VERSION 3.0.2)
project(pyroscope_navigation)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  geometry_msgs
  nav_msgs
  tf
)

catkin_package()

catkin_install_python(PROGRAMS
  scripts/state_machine.py
  scripts/waypoint_controller.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
)

install(DIRECTORY config/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
)
