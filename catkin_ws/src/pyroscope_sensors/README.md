# pyroscope_sensors

ROS nodes that publish SHT40 (temperature/humidity) and thermal camera data on the Jetson.

## Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/sensors/sht40/temperature` | `std_msgs/Float64` | Air temperature (°C) |
| `/sensors/sht40/humidity` | `std_msgs/Float64` | Relative humidity (%) |
| `/sensors/thermal/mean` | `std_msgs/Float64` | Thermal frame mean temperature (°C) |
| `/sensors/thermal/image` | `sensor_msgs/Image` | Latest thermal image (optional) |
| `/camera/color/image_raw` | `sensor_msgs/Image` | RealSense D435i RGB (when `realsense_enabled:=true`) |

## Quick check: rostopic echo (after sensors.launch is running)

Run these in a **separate terminal** (with `source devel/setup.bash` and same `ROS_MASTER_URI` if needed):

```bash
# SHT40 (Arduino serial)
rostopic echo /sensors/sht40/temperature
rostopic echo /sensors/sht40/humidity

# Thermal
rostopic echo /sensors/thermal/mean

# RealSense RGB (image topic: use hz to confirm, echo would dump raw data)
rostopic hz /camera/color/image_raw
```

Use **Ctrl+C** to stop each command. For image topics (`/sensors/thermal/image`, `/camera/color/image_raw`), use `rostopic hz <topic>` to confirm data flow instead of `echo`.

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
   Optional args: `sht40_port:=/dev/ttyUSB0` (if Arduino is on ttyUSB0), `thermal_rate:=0.33`, `thermal_publish_image:=false`, `realsense_enabled:=false`.

4. Ensure the Jetson and your PC are on the same network. On the PC, set:
   ```bash
   export ROS_MASTER_URI=http://<JETSON_IP>:11311
   export ROS_IP=<PC_IP>   # or ROS_HOSTNAME
   ```
   so the backend (on the PC) can subscribe to these topics.

## Parameters

- `~pyroscope_root`: Path to the pyroscope repo (contains `sht40_reader.py`, `thermal_capture.py`). Set by launch file.
- `~port` (sht40): Serial port for Arduino (default `/dev/ttyUSB0`; some boards use `/dev/ttyACM0`).
- `~baud` (sht40): Serial baud rate (default 9600).
- `~rate` (sht40): Publish rate in Hz (default 1.0).
- `~rate` (thermal): Publish rate in Hz (default 0.33).
- `~publish_image` (thermal): Whether to publish thermal image (default true).
