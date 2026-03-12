# Pyroscope

**Autonomous wildfire fuel-load mapping rover** - GPS-guided, lidar-navigated, thermal-camera-equipped.

<img src="assets/Poster.png" width="800" alt="Pyroscope Project Poster"/>

> Full resolution: [Poster.pdf](assets/Poster.pdf)

---

This project is grounded in field conditions near Ellensburg, WA, about 2 hours from Seattle.

![Shrubland site](assets/shrubland.jpeg)

One really good place to look at to assess wildfire risk are weather stations. However, weather stations are based mostly on dead-fuels, and there is little signal from actual live-fuel conditions. Pyroscope is designed to fill that gap by providing a mobile platform for collecting live-fuel data by measuring the temperature of the foilage on the ground vs the surrounding air to have a proxy for soil moisture levels. 

Land managers in shrubland ecosystems need reliable surface fuel-load data to plan prescribed burns and reduce wildfire risk, but manual ground sampling is slow, expensive, and hard to scale. A major wildfire in 2012 burned much of this area, highlighting the need for better field intelligence.

Pyroscope was built to close that gap.

<img src="assets/ba5ac9779fb52d08976bb2c3c9e5a83b.jpg" width="700" alt="Pyroscope rover in the field"/>

Pyroscope is a compact rover that carries thermal and environmental sensors and streams mission data to a dashboard in near real time.

## What This Repository Contains

- ROS navigation and sensor stack: `catkin_ws/src/...`
- FastAPI backend APIs and mission control: `application/backend`
- React dashboard frontend: `application`

## Project Structure

```text
pyroscope/
├── assets/
│   ├── Poster.png
│   ├── Poster.pdf
│   └── ...
├── catkin_ws/
│   └── src/
│       ├── pyroscope_navigation/      # Coverage planner, move_base launch, safety nodes
│       ├── pyroscope_sensors/         # Sensor launch/scripts (SHT40, thermal, camera)
│       ├── transbot_bringup/          # Base driver + odometry + TF
│       ├── transbot_ctrl/             # Teleop tools
│       └── transbot_nav/              # Legacy map-based nav package
├── application/
│   ├── backend/                       # FastAPI app, DB models, ROS sensor bridge
│   ├── src/                           # React dashboard source
│   └── package.json
├── SENSOR_INTEGRATION_SETUP.md
└── README.md
```

## System Layout

Typical runtime uses multiple machines:

- Jetson (robot): base bringup, lidar, onboard sensors
- Remote Ubuntu PC (same ROS network): `move_base` + coverage planner (and optionally backend)
- Frontend machine: React dashboard

Main autonomy path:

1. `pyroscope_sensors/launch/jetson_bringup.launch` starts base + lidar + sensors.
2. `pyroscope_navigation/launch/coverage_mission_nav.launch` starts `move_base` and coverage planner.
3. Coverage planner sends waypoints; `move_base` performs local obstacle avoidance with DWA.

## Prerequisites

- Ubuntu 18.04 with ROS Melodic for the ROS stack
- Python 3.9+ for backend
- Node.js 18+ for frontend
- MySQL 8+ for backend persistence

Install ROS navigation deps on the machine running `move_base`:

```bash
sudo apt install ros-melodic-move-base ros-melodic-dwa-local-planner \
  ros-melodic-navfn ros-melodic-move-base-msgs
```

## One-Time Setup

### 1) Build catkin workspace

```bash
cd ~/pyroscope/catkin_ws
catkin_make
source devel/setup.bash
```

### 2) Backend setup

```bash
cd ~/pyroscope/application/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
```

Set environment in `application/backend/.env` (minimum):

```env
DATABASE_URL=mysql+pymysql://<user>:<password>@localhost:3306/pyroscope_db
JWT_SECRET_KEY=<your-secret>
ROS_MASTER_URI=http://<JETSON_IP>:11311
ROS_IP=<BACKEND_PC_IP>
```

### 3) Frontend setup

```bash
cd ~/pyroscope/application
npm install
```

Note: API base URL is currently hardcoded in `application/src/services/api.js`. Update it for your backend host.

## How To Run

### A) ROS Navigation + Sensors (no web stack)

Terminal 1 (Jetson):

```bash
source ~/pyroscope/catkin_ws/devel/setup.bash
roslaunch pyroscope_sensors jetson_bringup.launch # this is a consolidated launch file that launches all the sensors and brings up the robot sensors, lidar, and bringup
```

This launches:

- `transbot_bringup/bringup.launch`
- `rplidar_ros/rplidar.launch`
- `pyroscope_sensors/sensors.launch`

Terminal 2 (Remote PC or same ROS machine):

```bash
source ~/pyroscope/catkin_ws/devel/setup.bash

# the front end takes care of this, but this could be manually run as well: 
roslaunch pyroscope_navigation coverage_mission_nav.launch \
  area_width:=3.0 area_height:=3.0 row_spacing:=1.0 waypoint_spacing:=1.0 \
  origin_x:=0.0 origin_y:=0.0 dwell_time:=3.0 waypoint_timeout:=60.0
```

What to expect:

- `move_base` topics appear (`/move_base/status`, costmaps, plans)
- `/coverage/progress` advances from `0/N` to `N/N`
- Robot follows a lawnmower pattern centered around `(origin_x, origin_y)` in `odom`
- If waypoints fail repeatedly, planner attempts recovery (clear costmaps) and continues mission

Quick checks:

```bash
rostopic echo /coverage/progress
rostopic echo /move_base/status
rosrun tf tf_monitor
```

Expected TF chain: `odom -> base_link -> laser`

Emergency cancel current goal:

```bash
rostopic pub -1 /move_base/cancel actionlib_msgs/GoalID '{}'
```

### B) Full Stack (ROS + Backend + Frontend)

Terminal 1 (Jetson):

```bash
source ~/pyroscope/catkin_ws/devel/setup.bash
roslaunch pyroscope_sensors jetson_bringup.launch
```

Terminal 2 (Backend host):

```bash
cd ~/pyroscope/application/backend
source venv/bin/activate
python run.py
```

Terminal 3 (Frontend host):

```bash
cd ~/pyroscope/application
npm run dev
```

Open dashboard: `http://localhost:5173`

What to expect:

- Backend on `:8000` with `/docs` and `/health`
- If `ROS_MASTER_URI` is set, ROS sensor bridge auto-starts at backend startup
- `/api/sensors/availability` returns `available: true` when required topics are present
- Dashboard shows live sensor data and mission controls

API sanity checks:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/sensors/availability
curl http://localhost:8000/api/robot/mission/status
```

## Mission API Quickstart

Start mission:

```bash
curl -X POST http://localhost:8000/api/robot/mission/start \
  -H "Content-Type: application/json" \
  -d '{"area_width":3.0,"area_height":3.0,"row_spacing":1.0,"waypoint_spacing":1.0,"origin_x":0.0,"origin_y":0.0}'
```

Check status:

```bash
curl http://localhost:8000/api/robot/mission/status
```

Stop mission:

```bash
curl -X POST http://localhost:8000/api/robot/mission/stop
```

## Other Useful Launch Modes

Keyboard teleop:

```bash
roslaunch transbot_ctrl transbot_keyboard.launch
```

Manual waypoint controller:

```bash
roslaunch pyroscope_navigation exploration.launch
rosrun pyroscope_navigation test_single_waypoint.py 2.0 1.0
```

Random exploration:

```bash
roslaunch pyroscope_navigation random_exploration.launch
```

Standalone safety layer:

```bash
roslaunch pyroscope_navigation obstacle_avoidance.launch
```

## Key Launch Files

| Launch file                                                             | Purpose                                            |
| ----------------------------------------------------------------------- | -------------------------------------------------- |
| `catkin_ws/src/pyroscope_sensors/launch/jetson_bringup.launch`          | One-command robot bringup (base + lidar + sensors) |
| `catkin_ws/src/pyroscope_navigation/launch/coverage_mission_nav.launch` | Primary autonomous coverage (`move_base` + DWA)    |
| `catkin_ws/src/pyroscope_navigation/launch/exploration.launch`          | Manual waypoint navigation                         |
| `catkin_ws/src/pyroscope_navigation/launch/random_exploration.launch`   | Random walk mobility test mode                     |
| `catkin_ws/src/pyroscope_navigation/launch/obstacle_avoidance.launch`   | Lidar obstacle detector + safety stop              |

## Troubleshooting

- `move_base` not found:
  - Install ROS nav packages listed in Prerequisites.
- Planner waits for action server then aborts:
  - Confirm `coverage_mission_nav.launch` is running and TF chain is valid.
- Sensors unavailable in backend:
  - Verify `ROS_MASTER_URI`/`ROS_IP`, then run:
    - `application/backend/scripts/diagnose_sensor_availability.sh`
- Odometry missing:
  - Run `catkin_ws/src/pyroscope_navigation/scripts/check_topics.sh`

## Known Caveats

- Use `coverage_mission_nav.launch` as the primary autonomous mode.
- `coverage_mission.launch` is legacy and not the preferred demo path.
- Very small mission areas can trigger edge-case waypoint fallback behavior.

## Additional Documentation

- `catkin_ws/src/pyroscope_navigation/README.md`
- `catkin_ws/src/pyroscope_sensors/README.md`
- `application/backend/SETUP.md`
- `application/backend/ROS_SENSOR_SETUP.md`
- `SENSOR_INTEGRATION_SETUP.md`
