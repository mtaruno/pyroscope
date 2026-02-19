# pyroscope_sensors

ROS nodes that publish SHT40 (temperature/humidity) and thermal camera data on the Jetson.

## Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/sensors/sht40/temperature` | `std_msgs/Float64` | Air temperature (°C) |
| `/sensors/sht40/humidity` | `std_msgs/Float64` | Relative humidity (%) |
| `/sensors/thermal/mean` | `std_msgs/Float64` | Thermal frame mean temperature (°C) |
| `/sensors/thermal/image` | `sensor_msgs/Image` | Latest thermal image (optional) |

## Jetson setup

1. Build the workspace (from `pyroscope` repo root):
   ```bash
   cd ~/pyroscope/catkin_ws
   catkin_make
   # or: catkin build
   source devel/setup.bash
   ```

2. Start `roscore` on the Jetson (if not already running):
   ```bash
   roscore
   ```

3. Run the sensor nodes:
   ```bash
   roslaunch pyroscope_sensors sensors.launch
   ```
   Optional args: `sht40_simulate:=true`, `thermal_simulate:=true`, `thermal_rate:=0.33`, `thermal_publish_image:=false`.

4. Ensure the Jetson and your PC are on the same network. On the PC, set:
   ```bash
   export ROS_MASTER_URI=http://<JETSON_IP>:11311
   export ROS_IP=<PC_IP>   # or ROS_HOSTNAME
   ```
   so the backend (on the PC) can subscribe to these topics.

## Parameters

- `~pyroscope_root`: Path to the pyroscope repo (contains `sht40_reader.py`, `thermal_capture.py`). Set by launch file.
- `~rate` (sht40): Publish rate in Hz (default 1.0).
- `~rate` (thermal): Publish rate in Hz (default 0.33).
- `~simulate`: If true, use simulated data when hardware is unavailable.
