# pyroscope

This is a shrubland close to Ellensburg, WA, which is around a 2 hour drive away from Seattle. 

![shrubs](shrubland.jpg)


One problem that these land managers face are wildfires. In this area itself, there was a huge one in 2012 that burned much of the trees that make up the shrubland. Land managers need to know the fuel load of these shrubberies to make plans about wildfire initiatives. But they don't have the time to sit around and do that. Worse, nobody really collects data on the ground in these environments. Neither can they usually afford people to walk these trails and manually measure fuel loads. 

Now here's what we made to combat this problem:

![Rover on Shrubs](ba5ac9779fb52d08976bb2c3c9e5a83b.jpg)


Pyroscope is a rover equipped with a depth camera, GPS, and thermal camera. It is designed to automate plot scale surface-fuel sampling for prescribed fire and AI fuel mapping. 

Pyroscope is small, lightweight, and maneuverable. This is in contrast to typical rovers that roam around the forest that are often larger and crush vegetation as it moves. 

The idea is that land managers will get a dashboard.

### Navigation

The navigation system is built on ROS Melodic and runs across two machines: the Transbot (Jetson) handles hardware drivers and sensors, while a remote Ubuntu 18.04 PC runs the higher-level planning and navigation.

#### SLAM & Mapping
- GMapping builds a 2D occupancy grid map using the RPLidar and wheel odometry
- Drive the robot manually with keyboard teleop to map the environment
- Save the map for later use with `map_saver`

#### Autonomous Navigation
- AMCL localizes the robot against a saved map
- `move_base` with DWA local planner handles point-to-point navigation and path planning

#### Coverage Path Planning
- Boustrophedon (lawnmower) pattern covers a configurable rectangular area (default 10m x 10m, 1m spacing)
- Pauses 3 seconds at each waypoint for thermal camera capture (`/coverage/capture_ready`)
- Publishes mission progress to `/coverage/progress`

#### Obstacle Avoidance (two layers)
- **Lidar obstacle detector** — monitors the front ±30° arc of the RPLidar scan. Publishes `/obstacle_detected` when anything is within 0.30m
- **Safety stop** — last-resort layer that overrides `/cmd_vel` with a stop command whenever an obstacle is detected. Works during teleop, autonomous navigation, or exploration

#### Key Launch Files

| Launch File | Description |
|---|---|
| `transbot_slam/slam_gmapping.launch` | Build a map with GMapping |
| `transbot_nav/navigation.launch` | AMCL + move_base navigation with a saved map |
| `pyroscope_navigation/coverage_mission.launch` | Full coverage mission (planner + obstacle avoidance) |
| `pyroscope_navigation/obstacle_avoidance.launch` | Standalone obstacle avoidance layer |
| `transbot_ctrl/transbot_keyboard.launch` | Keyboard teleoperation |

### Perception
Percetion is led by Chenghao Wang. The perception system is responsible for taking downward-facing images of the fuel plots and estimating the surface fuel loads from these images.

### Hardware
Hardware is led by Annika An. 


### Evaluating Success
- Decision-ready plots per staff-day.
  - Plots that have (a) QC-passed images, (b) model fuel estimates, and (c) appear on a unit dashboard actually used by the planner.
  - Baseline (manual): ~14 plots/day.
  - MVP target (robot): ≥30 plots/day.
