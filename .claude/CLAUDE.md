# Pyroscope — Claude Context

## What This Project Is
Autonomous fire-risk scanning robot (Transbot SE) that drives a lawnmower pattern over a field area, pausing at each waypoint to capture thermal + RGB images and SHT40 temperature/humidity data. A FastAPI backend + React frontend controls the mission and displays results.

## Hardware
- **Jetson**: runs all drivers, sensors, odometry, EKF, IMU. IP: `10.19.255.63`
- **Remote PC**: runs move_base, coverage_planner, backend, frontend. IP: `10.19.113.86`
- **ROS Master**: on the remote PC (`ROS_MASTER_URI=http://10.19.113.86:11311`)
- LiDAR: rplidar, topic `/scan`, frame `laser`
- IMU: topic `/imu/data` via `imu_filter_madgwick`
- Thermal camera: `/sensors/thermal/image`, `/sensors/thermal/mean`
- RealSense RGB: `/camera/color/image_raw`
- SHT40: `/sensors/sht40/temperature`, `/sensors/sht40/humidity`

## ROS Architecture
```
Jetson (bringup):
  transbot_driver → /transbot/get_vel
  base_node       → /odom_raw (child_frame_id: "dummy" — intentional, EKF handles it)
  ekf_localization → /odom + TF: odom → base_link
  imu_filter_madgwick → /imu/data
  robot_state_publisher → TF: dummy → base_link (from URDF, dangling — harmless)
  static_transform_publisher → TF: base_link → laser (15cm above base)
  static_transform_publisher → TF: base_link → imu_link

Remote PC (coverage mission):
  move_base (DWA + rolling costmaps, odom frame, no static map)
  coverage_planner (lawnmower pattern → move_base action client)
```

## TF Tree
```
odom → base_link          (EKF, published on Jetson)
       → laser            (static, published on Jetson)
       → imu_link         (static, published on Jetson)
       → arm_Link → ...   (URDF joints, robot_state_publisher)

dummy → base_link         (robot_state_publisher from URDF root — dangling, harmless)
```

**Critical**: ALL TF must originate from the Jetson. The `base_link → laser` static transform was moved from `coverage_mission_nav.launch` (remote PC) into `bringup.launch` (Jetson) to prevent the "two or more unconnected trees" error in move_base.

## Key Config Files
| File | Purpose |
|------|---------|
| `catkin_ws/src/transbot_bringup/launch/bringup.launch` | Jetson bringup: drivers, EKF, IMU, TF |
| `catkin_ws/src/pyroscope_sensors/launch/jetson_bringup.launch` | Top-level Jetson launch (includes bringup + LiDAR + sensors) |
| `catkin_ws/src/pyroscope_navigation/launch/coverage_mission_nav.launch` | Remote PC: move_base + coverage_planner |
| `catkin_ws/src/pyroscope_navigation/scripts/coverage_planner.py` | Lawnmower coverage planner |
| `catkin_ws/src/transbot_bringup/param/ekf/robot_localization.yaml` | EKF config |
| `catkin_ws/src/pyroscope_navigation/config/costmap_common.yaml` | Shared costmap params |
| `catkin_ws/src/pyroscope_navigation/config/global_costmap.yaml` | Global costmap (15x15m rolling window) |
| `catkin_ws/src/pyroscope_navigation/config/local_costmap.yaml` | Local costmap (4x4m rolling window) |
| `catkin_ws/src/pyroscope_navigation/config/dwa_planner.yaml` | DWA local planner |

## EKF Config (robot_localization.yaml)
- `base_link_frame: base_link` (was `dummy` — caused odom→base_link TF to never publish)
- `odom_frame: odom`, `world_frame: odom`
- Fuses `/odom_raw` (velocities) + `/imu/data` (yaw + yaw rate)
- Publishes filtered odom to `/odom`, TF `odom → base_link`

## Coverage Planner
- **Approach**: simple boustrophedon (lawnmower) grid — NOT costmap-aware
- Sends waypoints sequentially via move_base action client
- On failure/timeout: retries up to `max_waypoint_failures` (3), then skips and continues
- Publishes: `/coverage/capture_ready` (Bool), `/coverage/progress` (String), `/coverage/total_points` (Int32), `/coverage/complete` (Bool)
- Default area: 10x10m, 1.0m row/waypoint spacing, 0.45m wall margin, 60s waypoint timeout
- **Why lawnmower over costmap-aware**: robot operates in open fields with sparse obstacles; costmap-aware planner added complexity that introduced failures without benefit

## Known Issues & Fixes Applied
1. **`base_link_frame: dummy` in EKF yaml** → changed to `base_link`. Jetson must be pulled and bringup restarted for this to take effect.
2. **`base_link → laser` TF on remote PC** → moved to Jetson's `bringup.launch` so entire TF tree originates from one machine. Prevents "two or more unconnected trees" error.
3. **`import tf` in coverage_planner.py** → removed (tf module not needed in lawnmower planner, was causing Python tf2 import error).
4. **`waypoint_timeout` was 30s** → increased to 60s in backend, frontend, and launch defaults.
5. **`xy_goal_tolerance` was 0.15m** → loosened to 0.25m; `yaw_goal_tolerance` 0.30 → 0.50.

## Deployment
- **Jetson**: runs `roslaunch pyroscope_sensors jetson_bringup.launch`
- **Remote PC**: backend (`python run.py` from `application/backend/`) launches `coverage_mission_nav.launch` as a subprocess when mission starts
- **After any change to Jetson files** (bringup.launch, robot_localization.yaml, base.cpp, etc.): `git pull` on Jetson + `pkill -f "roslaunch pyroscope_sensors jetson_bringup"` + restart bringup
- **After any change to remote PC files** (coverage_planner.py, launch files, costmap configs): `git pull` on remote PC, restart backend

## Diagnostics Cheatsheet
```bash
# Verify TF tree is connected (run on remote PC)
rosrun tf tf_echo odom laser        # should stream live transforms
rosrun tf tf_echo odom base_link    # should stream live transforms

# Check EKF is publishing TF (run on remote PC)
rostopic echo /tf | grep child_frame_id   # should show: base_link, laser, imu_link etc

# Check move_base received a goal
rostopic echo /move_base/status

# Check robot is being commanded
rostopic echo /cmd_vel

# Check mission progress
rostopic echo /coverage/progress
rostopic echo /coverage/complete

# Check all nodes are up (Jetson nodes should be visible from remote PC)
rosnode list
```

## Code Style Rules
- **Python 2 only** — `coverage_planner.py` runs on ROS Melodic (Python 2). Never use non-ASCII characters (em-dashes `—`, curly quotes, etc.) in comments or strings. Python 2 will throw `SyntaxError: Non-ASCII character '\xe2'` at startup. Use plain ASCII only: `--` instead of `—`, straight quotes only.

## Common Failure Modes
| Symptom | Cause | Fix |
|---------|-------|-----|
| `Costmap2DROS transform timeout, global_pose stamp: 0.0000` | EKF TF not reaching remote PC's move_base | Ensure base_link→laser TF is in Jetson bringup, not coverage_mission_nav.launch |
| `two or more unconnected trees` | TF published from two machines separately | All TF must come from Jetson |
| `move_base action server not available` | move_base stuck in costmap init loop (TF issue) | Fix TF first |
| `coverage mission 0/0 complete` immediately | move_base action server never came up | Fix TF / move_base init |
| `TF_OLD_DATA unknown_publisher` | Harmless warning, transient at startup | Ignore |
| `could not find transform dummy to base_link` | Harmless — dummy is a dangling URDF root | Ignore |
