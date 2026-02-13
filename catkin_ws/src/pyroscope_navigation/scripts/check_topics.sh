#!/bin/bash
# Quick diagnostic script to check ROS topics

echo "=== Checking ROS Topics ==="
echo ""

echo "1. Checking for odometry topics:"
rostopic list | grep -i odom || echo "  No odometry topics found"
echo ""

echo "2. Checking if /odom is publishing:"
timeout 2 rostopic hz /odom 2>/dev/null || echo "  /odom is NOT publishing"
echo ""

echo "3. Checking if /cmd_vel exists:"
rostopic info /cmd_vel 2>/dev/null || echo "  /cmd_vel topic not found"
echo ""

echo "4. Current active topics:"
rostopic list
echo ""

echo "5. Active nodes:"
rosnode list
