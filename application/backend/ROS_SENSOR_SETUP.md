# ROS sensor setup (Jetson + PC backend)

When sensors (SHT40, thermal camera) are connected to the Jetson, they publish ROS topics. The backend on your PC can subscribe to these topics instead of calling scripts via subprocess.

## 1. Jetson setup

### Build and run sensor nodes

On the Jetson (with the pyroscope repo and catkin workspace):

```bash
cd ~/pyroscope/catkin_ws
catkin_make
source devel/setup.bash
```

Start `roscore` (if not already running):

```bash
roscore
```

In another terminal, launch the sensor nodes:

```bash
source devel/setup.bash
roslaunch pyroscope_sensors sensors.launch
```

This starts:

- **sht40_node**: publishes `/sensors/sht40/temperature` and `/sensors/sht40/humidity` (default 1 Hz).
- **thermal_node**: publishes `/sensors/thermal/mean` and optionally `/sensors/thermal/image` (default ~0.33 Hz).

Optional launch args: `sht40_simulate:=true`, `thermal_simulate:=true`, `thermal_publish_image:=false`.

### Network

Ensure the Jetson and your PC are on the same network. Note the Jetson’s IP (e.g. `192.168.1.10`).

## 2. PC backend setup

On the PC where the FastAPI backend runs:

### Install ROS (to subscribe to Jetson topics)

You need a ROS installation and `rospy` (and optionally `cv_bridge` for thermal image). For example on Ubuntu:

```bash
sudo apt install ros-melodic-rospy ros-melodic-std-msgs ros-melodic-sensor-msgs ros-melodic-cv-bridge
source /opt/ros/melodic/setup.bash
```

Then run the backend in an environment where ROS is sourced, or set the same in your shell before starting the backend.

### Point backend to Jetson’s ROS master

Set these **before** starting the backend (e.g. in `.env` or in the shell):

- **ROS_MASTER_URI**: Jetson’s roscore (replace with your Jetson IP):

  ```bash
  export ROS_MASTER_URI=http://192.168.1.10:11311
  ```

- **ROS_IP** (or **ROS_HOSTNAME**): your PC’s IP on the same network, so the Jetson can send topic data to the PC:

  ```bash
  export ROS_IP=192.168.1.20
  ```

Optional: put them in `application/backend/.env`:

```env
ROS_MASTER_URI=http://192.168.1.10:11311
ROS_IP=192.168.1.20
```

The backend reads these from the environment or from `app.config` (Settings).

### Start the backend

Start the backend as usual (with ROS env vars set or loaded from `.env`). When you click “Start Scan”, the backend will:

1. If `ROS_MASTER_URI` is set: start a ROS subscriber thread to `/sensors/sht40/temperature`, `/sensors/sht40/humidity`, `/sensors/thermal/mean`, and optionally `/sensors/thermal/image`, and use the latest values every 3 s for waypoint samples.
2. If `ROS_MASTER_URI` is not set: keep using the previous subprocess method (calling `sht40_reader.py` and `thermal_capture.py`), which is still valid when running the backend on the Jetson or without ROS.

## 3. Summary

| Where        | What |
|-------------|------|
| **Jetson**  | Run `roscore` and `roslaunch pyroscope_sensors sensors.launch` so SHT40 and thermal data are published. |
| **PC**      | Install ROS (rospy, etc.), set `ROS_MASTER_URI` and `ROS_IP`, then start the backend; it will subscribe to the Jetson topics and record waypoint data from them. |
