# Pyroscope -- Claude Context

## What This Project Is
Autonomous fire-risk scanning robot (Transbot SE) that drives a lawnmower pattern over a field area, pausing at each waypoint to capture thermal + RGB images and SHT40 temperature/humidity data. A FastAPI backend + React frontend controls the mission and displays results.

## Hardware
- **Jetson**: runs all drivers, sensors, odometry, EKF, IMU. IP: `10.19.255.63`
- **Remote PC**: runs move_base, coverage_planner, backend, frontend. IP: `10.19.113.86`
- **ROS Master**: on the remote PC (`ROS_MASTER_URI=http://10.19.113.86:11311`)
- LiDAR: rplidar, topic `/scan`, frame `laser` (360 degree)
- IMU: topic `/imu/data` via `imu_filter_madgwick`
- Thermal camera: `/sensors/thermal/image`, `/sensors/thermal/mean`
- RealSense RGB: `/camera/color/image_raw`
- SHT40: `/sensors/sht40/temperature`, `/sensors/sht40/humidity`

## ROS Architecture
```
Jetson (bringup):
  transbot_driver -> /transbot/get_vel
  base_node       -> /odom_raw (child_frame_id: "dummy" -- intentional, EKF handles it)
  ekf_localization -> /odom + TF: odom -> base_link
  imu_filter_madgwick -> /imu/data
  robot_state_publisher -> TF: dummy -> base_link (from URDF, dangling -- harmless)
  static_transform_publisher -> TF: base_link -> laser (15cm above base)
  static_transform_publisher -> TF: base_link -> imu_link

Remote PC (coverage mission):
  slam_gmapping -> /map + TF: map -> odom (when SLAM available)
  move_base (DWA + SLAM global costmap in map frame, local costmap in map frame)
  coverage_planner (map-aware lawnmower pattern -> move_base action client)
```

## TF Tree
```
map -> odom -> base_link    (map->odom from gmapping on remote PC, odom->base_link from EKF on Jetson)
               -> laser     (static, published on Jetson)
               -> imu_link  (static, published on Jetson)
               -> arm_Link  (URDF joints, robot_state_publisher)

dummy -> base_link          (robot_state_publisher from URDF root -- dangling, harmless)
```

**Critical**: ALL base TF must originate from the Jetson. The `base_link -> laser` static transform lives in `bringup.launch` (Jetson). A fallback also exists in `coverage_mission_nav.launch` for cases when Jetson bringup doesn't publish it.

## Key Config Files
| File | Purpose |
|------|---------|
| `catkin_ws/src/transbot_bringup/launch/bringup.launch` | Jetson bringup: drivers, EKF, IMU, TF |
| `catkin_ws/src/pyroscope_sensors/launch/jetson_bringup.launch` | Top-level Jetson launch (includes bringup + LiDAR + sensors) |
| `catkin_ws/src/pyroscope_navigation/launch/coverage_mission_nav.launch` | Remote PC: gmapping + move_base + coverage_planner |
| `catkin_ws/src/pyroscope_navigation/scripts/coverage_planner.py` | Map-aware coverage planner with proximity capture |
| `catkin_ws/src/transbot_bringup/param/ekf/robot_localization.yaml` | EKF config |
| `catkin_ws/src/pyroscope_navigation/config/costmap_common.yaml` | Shared costmap params |
| `catkin_ws/src/pyroscope_navigation/config/global_costmap_slam.yaml` | Global costmap (SLAM static layer, map frame) |
| `catkin_ws/src/pyroscope_navigation/config/local_costmap.yaml` | Local costmap (4x4m rolling window, map frame) |
| `catkin_ws/src/pyroscope_navigation/config/dwa_planner.yaml` | DWA local planner |
| `catkin_ws/src/pyroscope_navigation/config/gmapping.yaml` | GMapping SLAM params |

## Coverage Planner (current architecture)
- **SLAM integration**: gmapping builds /map on the fly, publishes map->odom TF
- **Map-aware waypoints**: queries SLAM `/map` for free cells (value==0), only places waypoints in confirmed free space. Falls back to blind grid if SLAM unavailable.
- **Frame auto-detection**: checks for `map->odom` TF at startup (10s timeout). Uses `map` frame if SLAM is running, falls back to `odom` frame if not.
- **Proximity-based capture**: fires `capture_ready` when robot is within `xy_goal_tolerance` (0.5m) of waypoint, even if move_base aborts/times out.
- **Costmap snapping**: before navigating to each waypoint, snaps it to nearest low-cost costmap cell if the original position became occupied.
- **RViz markers**: publishes MarkerArray to `/coverage/waypoint_markers` (green=done, yellow=current, grey=pending)
- **Waypoint skipping**: skips waypoints that are in high-cost costmap areas or scan-blocked
- Publishes: `/coverage/capture_ready` (Bool), `/coverage/progress` (String), `/coverage/complete` (Bool)
- Default area: 10x10m, 1.0m row/waypoint spacing, 0.30m wall margin, 25s waypoint timeout
- `waypoint_cost_threshold`: 200 (costmap cells >= this are considered occupied)
- `xy_goal_tolerance`: 0.5m, `yaw_goal_tolerance`: 0.8rad

## Backend Capture Service
- `waypoint_capture_service.py` runs a background thread that waits for `/coverage/capture_ready` events via ROS bridge
- On each capture_ready: saves SHT40 data, thermal image, RGB image to DB as `ScanWaypointSample`
- `captured_points` counter increments only after successful `db.commit()` (not before)
- Frontend polls `/api/scans/{id}/progress` for live updates

## EKF Config (robot_localization.yaml)
- `base_link_frame: base_link` (was `dummy` -- caused odom->base_link TF to never publish)
- `odom_frame: odom`, `world_frame: odom`
- Fuses `/odom_raw` (velocities) + `/imu/data` (yaw + yaw rate)
- Publishes filtered odom to `/odom`, TF `odom -> base_link`

## Deployment
- **Jetson**: runs `roslaunch pyroscope_sensors jetson_bringup.launch`
- **Remote PC**: backend (`python run.py` from `application/backend/`) launches `coverage_mission_nav.launch` as a subprocess when mission starts
- **Before launching**: kill stale ROS nodes (`rosnode kill -a`) to avoid "new node registered with same name" conflicts
- **After any change to Jetson files**: `git pull` on Jetson + `pkill -f "roslaunch pyroscope_sensors jetson_bringup"` + restart bringup
- **After any change to remote PC files**: `git pull` on remote PC, restart backend

## Diagnostics Cheatsheet
```bash
# Verify TF tree (run on remote PC)
rosrun tf tf_echo map base_link     # should stream if SLAM is running
rosrun tf tf_echo odom base_link    # should always stream if Jetson bringup is up
rosrun tf tf_echo odom laser        # should always stream

# Check SLAM is publishing
rostopic echo /map -n 1             # should show occupancy grid
rosrun tf tf_echo map odom          # should stream if gmapping is running

# Check move_base
rostopic echo /move_base/status
rostopic echo /cmd_vel

# Check mission progress
rostopic echo /coverage/progress
rostopic echo /coverage/capture_ready
rostopic echo /coverage/complete

# Check all nodes
rosnode list
```

## Code Style Rules
- **Python 2 only** -- `coverage_planner.py` runs on ROS Melodic (Python 2). Never use non-ASCII characters (em-dashes, curly quotes, arrows, etc.) in comments or strings. Python 2 will throw `SyntaxError: Non-ASCII character '\xe2'` at startup. Use plain ASCII only: `--` instead of em-dash, straight quotes only, `->` instead of arrow.

## Common Failure Modes
| Symptom | Cause | Fix |
|---------|-------|-----|
| `timed out waiting for transform from base_link to map` | gmapping not running (no map->odom TF) | Check if gmapping started, kill stale nodes, restart |
| `two or more unconnected trees` | gmapping not running OR TF published from two machines | Ensure gmapping is up; all base TF from Jetson |
| `new node registered with same name` | Stale ROS node from previous session | `rosnode kill -a` before launching |
| `Costmap2DROS transform timeout` | EKF TF not reaching remote PC | Ensure Jetson bringup is running |
| `move_base action server not available` | move_base stuck in costmap init (TF issue) | Fix TF first |
| `global frame odom, plan frame map` | Frame mismatch in costmaps | Both costmaps should use map frame when SLAM is active |
| `SyntaxError: Non-ASCII character` | Unicode in Python 2 file | Replace with ASCII equivalents |
| `CoveragePlanner has no attribute X` | Missing init for new attribute | Always define in __init__ |
| Dashboard shows captures but "Waiting for first capture" | captured_points counter bug | Ensure counter increments after db.commit() |
| Frontend doesn't navigate to results after stop | closeFuelPrompt missing navigation | Call loadAndShowScanResult in closeFuelPrompt |
