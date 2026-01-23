# Pyroscope Navigation - Quick Start Guide

## What You Have

A simple waypoint-based navigation controller for local exploration. You manually send waypoints, the robot drives to them. Later you'll add obstacle avoidance.

## File Overview

```
pyroscope_navigation/
├── scripts/
│   ├── waypoint_controller.py      # Main controller (drives to waypoints)
│   ├── test_single_waypoint.py     # Helper to send waypoints
│   └── state_machine.py            # (Not used for exploration - ignore)
├── launch/
│   ├── exploration.launch          # Use this one!
│   └── navigation.launch           # (Plot-based - ignore)
└── config/
    └── mission_config.yaml         # (Not needed for exploration - ignore)
```

## On Your Jetson Orin

### 1. Build
```bash
cd ~/pyroscope
catkin_make
source devel/setup.bash
```

### 2. Start the controller
```bash
roslaunch pyroscope_navigation exploration.launch
```

### 3. Send a waypoint
In another terminal:
```bash
# Go forward 2 meters
rosrun pyroscope_navigation test_single_waypoint.py 2.0 0.0

# Go to (3m east, 1m north)
rosrun pyroscope_navigation test_single_waypoint.py 3.0 1.0
```

### 4. Watch it work
```bash
# See velocity commands
rostopic echo /cmd_vel

# See when goal reached
rostopic echo /nav/goal_reached
```

## Tuning

If robot is too aggressive/fast:
```bash
roslaunch pyroscope_navigation exploration.launch max_linear_vel:=0.2 linear_gain:=0.3
```

If robot is too slow:
```bash
roslaunch pyroscope_navigation exploration.launch max_linear_vel:=0.5 linear_gain:=0.7
```

## Next Steps

1. Test basic movement on flat ground
2. Tune gains for your rover's characteristics
3. Test on rough terrain
4. Later: Add ZED depth processing for obstacle avoidance

## Required Topics

The controller needs:
- `/odom` or `/zed2i/odom` - for position tracking
- Publishes to `/cmd_vel` - velocity commands for your rover

Make sure your ZED camera or wheel encoders are publishing odometry!
