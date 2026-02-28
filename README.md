# pyroscope

This is a shrubland close to Ellensburg, WA, which is around a 2 hour drive away from Seattle. 

![shrubs](shrubland.jpeg)

One problem that these land managers face are wildfires. In this area itself, there was a huge one in 2012 that burned much of the trees that make up the shrubland. Land managers need to know the fuel load of these shrubberies to make plans about wildfire initiatives. But they don't have the time to sit around and do that. Worse, nobody really collects data on the ground in these environments. Neither can they usually afford people to walk these trails and manually measure fuel loads. 

Now here's what we made to combat this problem:

![Rover on Shrubs](ba5ac9779fb52d08976bb2c3c9e5a83b.jpg)


Pyroscope is a rover equipped with a depth camera, GPS, and thermal camera. It is designed to automate plot scale surface-fuel sampling for prescribed fire and AI fuel mapping. 

Pyroscope is small, lightweight, and maneuverable. This is in contrast to typical rovers that roam around the forest that are often larger and crush vegetation as it moves. 

The idea is that land managers will get a dashboard that gives them near real time information of ground conditions; and get alerts of potential wildfire outbreaks.

Here is the architecture of Pyroscope:
![alt text](<CleanShot 2026-02-12 at 00.28.06@2x.png>)

### Navigation

The navigation system is built on ROS Melodic and runs across two machines: the Transbot (Jetson) handles hardware drivers and sensors, while a remote Ubuntu 18.04 PC runs navigation modules such as obstacle detection and high-level path planning.

Here's the simplest operation, teleooperating the robot: roslaunch transbot_ctrl transbot_keyboard.launch

Known environment issues:
- If there is no rospkg, do pip3 install rospkg
- 


#### SLAM & Mapping
- GMapping builds a 2D occupancy grid map using the RPLidar and wheel odometry
- Drive the robot manually with keyboard teleop to map the environment
- Save the map for later use with `map_saver`

`rosrun map_server map_saver -f ~/maps.hector_map`


#### Autonomous Navigation
- AMCL localizes the robot against a saved map
- `move_base` with DWA local planner handles point-to-point navigation and path planning

#### Coverage Path Planning
- Boustrophedon (lawnmower) pattern covers a configurable rectangular area (default 10m x 10m, 1m spacing)
- Pauses 3 seconds at each waypoint for thermal camera capture (`/coverage/capture_ready`)
- Publishes mission progress to `/coverage/progress`

To launch this coverage mission:
1. roscore (on remote PC)
2. roslaunch transbot_bringup bringup.launch (on Transbot)
3. roslaunch rplidar_ros rplidar.launch (on Transbot)
4. roslaunch transbot_nav navigation.launch map_file:=$(rospack find transbot_nav)/maps/pyroscope_map.yaml (on remote PC)
5. rviz
6. Make sure that you source the devel/setup.bash
7. roslaunch pyroscope_navigation coverage_mission.launch
8. roslaunch pyroscope_navigation coverage_mission.launch \
    area_width:=5.0 \
    area_height:=5.0 \
    row_spacing:=0.8 \
    waypoint_spacing:=0.5 \
    origin_x:=0.0 \
    origin_y:=0.0 \
    dwell_time:=2.0 \
    waypoint_timeout:=30.0

Testing the odometry:
timeout 3 rostopic pub /cmd_vel geometry_msgs/Twist '{linear: {x: 0.3}}'


If you want to publish zero velocity in attempt to stop the robot:
`rostopic pub -1 /cmd_vel geometry_msgs/Twist '{linear: {x: 0, y: 0, z: 0}, angular: {x: 0, y: 0, z: 0}}`

Monitoring:
7. rostopic echo /coverage/progress
8. rostopic echo /coverage/complete
9. rostopic echo/nav/goal_reached
10. rostopic hz /scan
11. rosrun tf view_frames && evince frames.pdf

rosrun tf static_transform_publisher 0 0 0.15 0 0 0 base_link laser 100 &

rosrun tf tf_monitor

Make sure odometry is working:
# Terminal 1: Start teleop keyboard
roslaunch transbot_ctrl transbot_keyboard.launch

# Terminal 2: Watch X position
rostopic echo /odom --filter "print('x:', m.pose.pose.position.x, '  y:', m.pose.pose.position.y)"

# Drive forward with keyboard (W key or up arrow)
# Watch the terminal

Expected behavior:
- ✅ X value increases as you drive forward → Odometry works!
- ❌ X value stays at 0.0 → Odometry broken!

#### Obstacle Avoidance (move_base + costmaps)

The coverage mission uses ROS `move_base` with DWA local planning and rolling-window costmaps to navigate around obstacles in real time. No pre-built map is required -- the costmaps are built live from lidar data.

- **Global costmap** -- 15x15m rolling window in the `odom` frame. NavfnROS plans a path from robot to each waypoint.
- **Local costmap** -- 4x4m rolling window. DWA local planner samples velocity trajectories and picks the best one that avoids obstacles.
- **Inflation layer** -- expands detected obstacles by 0.25m so the robot keeps a safe buffer.

When an obstacle appears in the lidar scan, the costmap marks it, DWA steers around it, and NavfnROS replans the global path if needed. If the robot still can't reach a waypoint within the timeout, it skips and moves on.

**Prerequisites (install once on the remote PC):**

```bash
sudo apt install ros-melodic-move-base ros-melodic-dwa-local-planner \
  ros-melodic-navfn ros-melodic-move-base-msgs
```

**To launch the coverage mission with obstacle avoidance:**

1. roscore (on remote PC)
2. roslaunch transbot_bringup bringup.launch (on Transbot)
3. roslaunch rplidar_ros rplidar.launch (on Transbot)
4. source ~/pyroscope/catkin_ws/devel/setup.bash (on remote PC)
5. roslaunch pyroscope_navigation coverage_mission_nav.launch \
    area_width:=3.0 \
    area_height:=3.0 \
    row_spacing:=1.0 \
    waypoint_spacing:=1.0

Note: steps 2-3 provide `/odom`, `/scan`, and the `odom -> base_link` TF that move_base requires. The launch file adds the `base_link -> laser` static TF.

**Verify move_base is running:**

```bash
rostopic list | grep move_base
```

Should see `/move_base/status`, `/move_base/global_costmap/costmap`, `/move_base/local_costmap/costmap`

```bash
rosrun tf tf_monitor
```

Should show the full chain: `odom -> base_link -> laser`

**Monitor mission progress:**

```bash
rostopic echo /coverage/progress
rostopic echo /move_base/status
```

**Rviz visualization:**

Open rviz and set Fixed Frame to `odom`. Add these displays:

| Display    | Topic                                        | What it shows                              |
| ---------- | -------------------------------------------- | ------------------------------------------ |
| LaserScan  | `/scan`                                      | Raw lidar points                           |
| Map        | `/move_base/local_costmap/costmap`           | 4x4m obstacle grid around robot            |
| Map        | `/move_base/global_costmap/costmap`          | 15x15m planning grid                       |
| Path       | `/move_base/NavfnROS/plan`                   | Global planned route (green)               |
| Path       | `/move_base/DWAPlannerROS/local_plan`        | Local DWA trajectory (red)                 |
| Pose       | `/move_base/current_goal`                    | Current target waypoint                    |

Place an object between the robot and the next waypoint -- you should see the costmap light up and the local path curve around it.

**Troubleshooting:**

- "Cannot launch node of type move_base/move_base" -- run the `sudo apt install` line above
- "Waiting for move_base action server..." then aborts -- check `rosnode list` for `/move_base` and terminal output for TF or `/scan` errors
- Robot spinning in place -- goal may be inside an inflated obstacle. Check the costmap in rviz
- Global planner fails -- waypoint may be outside the 15m costmap window. The planner warns at startup if consecutive waypoints exceed 7.5m

#### Legacy Obstacle Avoidance (coverage_mission.launch)

The original `coverage_mission.launch` is still available as a fallback. It uses a simpler approach with no path planning:
- **Lidar obstacle detector** -- monitors the front +/-30 deg arc of the RPLidar scan. Publishes `/obstacle_detected` when anything is within 0.30m
- **Safety stop** -- overrides `/cmd_vel` with a stop command whenever an obstacle is detected
- The robot stops on obstacle detection and skips the waypoint after 5 seconds

#### Key Launch Files
| Launch File                                          | Description                                              |
| ---------------------------------------------------- | -------------------------------------------------------- |
| `transbot_slam/slam_gmapping.launch`                 | Build a map with GMapping                                |
| `transbot_nav/navigation.launch`                     | AMCL + move_base navigation with a saved map             |
| `pyroscope_navigation/coverage_mission_nav.launch`   | Coverage mission with move_base obstacle avoidance       |
| `pyroscope_navigation/coverage_mission.launch`       | Coverage mission with simple stop-on-obstacle (legacy)   |
| `pyroscope_navigation/obstacle_avoidance.launch`     | Standalone obstacle avoidance layer                      |
| `transbot_ctrl/transbot_keyboard.launch`             | Keyboard teleoperation                                   |

#### ZED 2i Testing
Simple hardware test:
1. Plug the ZED 2i into a USB 3.0 port
2. Run lsusb - you should see the camera listed as a USB device
3. Check USB connection: dmesg | tail after plugging in

With SDK installed:
1. Download ZED SDK (make sure it's the right version for the Jetson)
2. Install prerequisites: sudo apt install zstd
3. Install the SDK following their installer
4. Run test tools:
  - ZED_Explorer - GUI tool to test camera
  - ZED_Depth_Viewer - View depth output
  - Run sample applications in /usr/local/zed/tools/

### Backend

Instructions for setting up the backend:
1. Install MySQL (using MySQL 8.0 for Ubuntu 18.04)
2. ...

To test from the backend:
                                                                                  
1. Start the backend                                                             
  cd /Users/matthewtaruno/Dev/pyroscope/application/backend
  python run.py

2. Start a mission via API
  curl -X POST http://localhost:8000/api/robot/mission/start \
    -H "Content-Type: application/json" \
    -d '{"area_width": 10.0, "area_height": 10.0, "row_spacing": 1.0,
  "waypoint_spacing": 1.0}'

3. Check status
  curl http://localhost:8000/api/robot/mission/status

4. Stop mission
  curl -X POST http://localhost:8000/api/robot/mission/stop


### Perception
Percetion is led by Chenghao Wang. The perception system is responsible for taking downward-facing images of the fuel plots and estimating the surface fuel loads from these images.

### Hardware + Design
This is led by Annika An. She designed the hardware for the robot, putting together the Lidar, cameras, and other sensors. She also designed the front-end dashboard for the robot.

### Evaluating Success
- Decision-ready plots per staff-day.
  - Plots that have (a) QC-passed images, (b) model fuel estimates, and (c) appear on a unit dashboard actually used by the planner.
  - Baseline (manual): ~14 plots/day.
  - MVP target (robot): ≥30 plots/day.


