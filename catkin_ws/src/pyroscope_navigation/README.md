# Pyroscope Navigation Package

Local exploration and waypoint navigation for the Pyroscope fuel-sampling rover.

## Overview

Simple waypoint-based navigation controller that drives the robot to target locations. You send waypoints manually, and the controller handles low-level motion control. Perfect for testing basic movement and building up to obstacle avoidance.

## Architecture

```
Manual Waypoint Input (you or another node)
    ↓ publishes target waypoints
Waypoint Controller (waypoint_controller.py)
    ↓ publishes velocity commands
/cmd_vel → Robot
```

### Topics

**Published:**
- `/cmd_vel` (geometry_msgs/Twist) - Velocity commands to robot
- `/nav/goal_reached` (std_msgs/Bool) - Signal when goal is reached
- `/nav/current_pose` (geometry_msgs/PoseStamped) - Current robot pose (republished from odom)

**Subscribed:**
- `/odom` or `/zed2i/odom` (nav_msgs/Odometry) - Robot odometry
- `/nav/target_waypoint` (geometry_msgs/PoseStamped) - Target waypoint to navigate to

## Quick Start (on Jetson)

### 1. Build the package

```bash
cd ~/pyroscope  # or your workspace
catkin_make
source devel/setup.bash
```

### 2. Launch the controller

```bash
roslaunch pyroscope_navigation exploration.launch
```

### 3. Send waypoints

**Option A: Using the test script**
```bash
# Send robot to (3m, 2m)
rosrun pyroscope_navigation test_single_waypoint.py 3.0 2.0
```

**Option B: Using rostopic directly**
```bash
rostopic pub /nav/target_waypoint geometry_msgs/PoseStamped "
header:
  frame_id: 'odom'
pose:
  position: {x: 5.0, y: 0.0, z: 0.0}
  orientation: {w: 1.0}"
```

### 4. Monitor progress

```bash
# Watch velocity commands
rostopic echo /cmd_vel

# Check if goal reached
rostopic echo /nav/goal_reached

# View current position
rostopic echo /nav/current_pose
```

## Configuration

### Controller Parameters

Tune in launch file or via command line:

```bash
roslaunch pyroscope_navigation exploration.launch linear_gain:=0.4 max_linear_vel:=0.5
```

**Key parameters:**
- `linear_gain` - Proportional gain for forward motion (default: 0.5)
- `angular_gain` - Proportional gain for turning (default: 1.5)
- `max_linear_vel` - Maximum forward velocity in m/s (default: 0.3)
- `max_angular_vel` - Maximum turn rate in rad/s (default: 0.8)
- `goal_tolerance` - Distance to consider goal reached in meters (default: 0.5)
- `control_frequency` - Control loop rate in Hz (default: 10.0)

## Control Algorithm

The waypoint controller uses simple proportional control:

1. **Calculate error**: Distance and heading to target waypoint
2. **Angular velocity**: Turn to face target (proportional to heading error)
3. **Linear velocity**: Move forward when facing target (proportional to distance)
4. **Stop**: When within goal_tolerance of target

## Tuning for Your Tank Rover

### Start with conservative settings:
```bash
roslaunch pyroscope_navigation exploration.launch \
  linear_gain:=0.3 \
  angular_gain:=1.0 \
  max_linear_vel:=0.2 \
  max_angular_vel:=0.6
```

### If robot oscillates or overshoots:
- Reduce `linear_gain` and `angular_gain`
- Increase `goal_tolerance`
- Lower max velocities

### If robot moves too slowly:
- Increase `max_linear_vel`
- Increase `linear_gain` (carefully)

### For rough terrain:
- Lower gains to avoid aggressive corrections
- Tank/skid-steer rovers have wheel slip - expect some overshoot
- May need asymmetric tuning (different gains for straight vs turns)

## Testing Workflow

1. **Test basic movement**: Send nearby waypoint (1-2m)
2. **Test turning**: Send waypoint to the side
3. **Test longer distances**: Gradually increase waypoint distance
4. **Test sequences**: Send multiple waypoints in succession

## Future Enhancements

The architecture has hooks for adding:
- **Obstacle avoidance**: Add occupancy grid processing, modify controller to avoid obstacles
- **Recovery behaviors**: Backup and retry when stuck
- **Pure pursuit controller**: Smoother path following
- **IMU monitoring**: Safety layer for slope detection
- **Dynamic window approach (DWA)**: Local planning with obstacle consideration

## Adding Obstacle Avoidance Later

When you're ready to add obstacle avoidance:

1. Create a node that processes ZED depth → occupancy grid
2. Publish to `/occupancy_grid` topic
3. Modify waypoint controller to:
   - Check planned trajectory against occupancy grid
   - Stop or turn if obstacles detected
   - OR: Add a local planner layer between waypoint sender and controller

## Troubleshooting

**Robot doesn't move:**
- Check `/odom` or `/zed2i/odom` is publishing: `rostopic hz /odom`
- Verify `/cmd_vel` topic name matches your robot
- Check controller is receiving waypoints: `rostopic echo /nav/target_waypoint`
- Controller params may be too conservative - increase max velocities

**Robot spins in place:**
- Odometry might be wrong or drifting
- Try increasing `goal_tolerance`
- Check coordinate frame (should be `odom` frame)

**Robot overshoots:**
- Reduce controller gains
- Increase goal_tolerance
- Lower max velocities

**No odometry available:**
- Verify ZED camera is running and publishing
- Check topic name: `rostopic list | grep odom`
- May need to remap topic in launch file

## Example Usage Session

```bash
# Terminal 1: Launch controller
roslaunch pyroscope_navigation exploration.launch

# Terminal 2: Send test waypoints
rosrun pyroscope_navigation test_single_waypoint.py 2.0 0.0   # 2m forward
# Wait for goal reached...
rosrun pyroscope_navigation test_single_waypoint.py 2.0 2.0   # Turn and move
# Wait...
rosrun pyroscope_navigation test_single_waypoint.py 0.0 0.0   # Return to origin
```
