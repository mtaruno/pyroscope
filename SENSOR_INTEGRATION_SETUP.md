# Sensor Integration Setup Guide

## Overview
This integration connects your ROS sensor topics to the web dashboard, displaying real-time sensor data and camera feeds.

## Architecture
```
ROS Topics                  ROS Bridge               Backend API           Frontend
─────────────────          ─────────────────       ─────────────────     ─────────────
/sensors/sht40/temperature
/sensors/sht40/humidity    →  ros_sensor_bridge.py  →  /api/sensors/*  →  SensorPanel
/sensors/thermal/mean          (saves to JSON)          (reads JSON)       (displays data)
/sensors/thermal/image     →  (saves images)       →  (serves images)  →  (shows images)
/camera/color/image_raw
```

## Setup Steps

### 1. On the Remote PC (where ROS is running)

#### Install dependencies:
```bash
pip install opencv-python
# cv_bridge should already be installed with ROS
```

#### Make the ROS bridge script executable:
```bash
chmod +x ~/Dev/pyroscope/application/backend/scripts/ros_sensor_bridge.py
```

#### Verify ROS topics are publishing:
```bash
# Check topics exist
rostopic list | grep sensors
rostopic list | grep camera

# Check data is flowing
rostopic echo /sensors/sht40/temperature -n 1
rostopic echo /sensors/sht40/humidity -n 1
rostopic echo /sensors/thermal/mean -n 1
rostopic hz /sensors/thermal/image
rostopic hz /camera/color/image_raw
```

### 2. Start All Services (in order)

#### Terminal 1 - ROS Core:
```bash
roscore
```

#### Terminal 2 - Your sensor publishers:
```bash
# Whatever launch file publishes your sensors
source ~/Dev/pyroscope/catkin_ws/devel/setup.bash
roslaunch <your_sensor_package> <your_sensors.launch>
```

#### Terminal 3 - ROS Sensor Bridge:
```bash
source ~/Dev/pyroscope/catkin_ws/devel/setup.bash
cd ~/Dev/pyroscope/application/backend
python3 scripts/ros_sensor_bridge.py
```

**Expected Output:**
```
[INFO] Sensor bridge started - listening to sensor topics
[INFO] Thermal image saved: (480, 640, 3)
[INFO] RGB image saved: (480, 640, 3)
```

**Verify it's working:**
```bash
# Check JSON file is being updated
watch -n 1 cat ~/Dev/pyroscope/application/backend/sensor_data/latest_sensors.json

# Check images exist
ls -lh ~/Dev/pyroscope/application/backend/sensor_data/
```

#### Terminal 4 - Backend API:
```bash
cd ~/Dev/pyroscope/application/backend
source venv/bin/activate
python run.py
```

### 3. Start Frontend (on Mac)

```bash
cd ~/Dev/pyroscope/application
npm run dev
```

Open http://localhost:5173

---

## Testing the Integration

### 1. Test API Endpoints (from Mac):
```bash
# Get latest sensor values
curl http://10.18.70.16:8000/api/sensors/latest

# Check images are accessible
curl -I http://10.18.70.16:8000/api/sensors/thermal/image
curl -I http://10.18.70.16:8000/api/sensors/rgb/image
```

**Expected Response:**
```json
{
  "temperature": 23.5,
  "humidity": 45.2,
  "thermal_mean": 28.3,
  "thermal_image_url": "/api/sensors/thermal/image",
  "rgb_image_url": "/api/sensors/rgb/image",
  "timestamp": 1708298765.123
}
```

### 2. Check Frontend Display:
- Open browser to http://localhost:5173
- Look for "Live Sensors" panel in the main content area
- Should show:
  - Temperature value updating every second
  - Humidity value updating every second
  - Thermal Mean value updating every second
  - Thermal camera image (colorized)
  - RGB camera image
  - Timestamp of last update

---

## Troubleshooting

### Sensors show "---" (no data)

**Check if ROS topics are publishing:**
```bash
rostopic echo /sensors/sht40/temperature -n 1
```

**Check if ROS bridge is running:**
```bash
ps aux | grep ros_sensor_bridge
```

**Check JSON file is being written:**
```bash
cat ~/Dev/pyroscope/application/backend/sensor_data/latest_sensors.json
```

If file doesn't exist or is empty → ROS bridge not running or topics not publishing

---

### Images show 404

**Check images exist:**
```bash
ls -lh ~/Dev/pyroscope/application/backend/sensor_data/*.jpg
```

**Check image topics are publishing:**
```bash
rostopic hz /sensors/thermal/image
rostopic hz /camera/color/image_raw
```

If 0 Hz → topics not publishing, check your sensor launch file

---

### API returns 500 error

**Check backend logs:**
The terminal running `python run.py` will show errors

**Check file permissions:**
```bash
ls -la ~/Dev/pyroscope/application/backend/sensor_data/
```

All files should be readable by the backend process

---

### Frontend shows "Sensor data unavailable"

**Check CORS:**
The backend might be blocking requests from the frontend.

**Test from Mac:**
```bash
curl http://10.18.70.16:8000/api/sensors/latest
```

If this works but frontend fails → CORS issue (check `.env` CORS_ORIGINS)

**Check browser console:**
Press F12, look for errors in Console tab

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Remote PC (Ubuntu 18.04)                                       │
│                                                                  │
│  ┌──────────────┐                                               │
│  │ ROS Topics   │                                               │
│  │  /sensors/*  │                                               │
│  │  /camera/*   │                                               │
│  └──────┬───────┘                                               │
│         │ subscribe                                             │
│         ↓                                                        │
│  ┌──────────────────┐        saves         ┌─────────────────┐ │
│  │ ros_sensor_      │──────────────────────→│ sensor_data/    │ │
│  │ bridge.py        │  JSON + JPEG          │ latest_sensors  │ │
│  │ (Python/rospy)   │                       │ *.jpg           │ │
│  └──────────────────┘                       └────────┬────────┘ │
│                                                       │ reads    │
│                                              ┌────────↓────────┐│
│                                              │ FastAPI Backend ││
│                                              │ /api/sensors/*  ││
│                                              └────────┬────────┘│
└───────────────────────────────────────────────────────┼─────────┘
                                                        │ HTTP
                                                        ↓
┌─────────────────────────────────────────────────────────────────┐
│  Mac (Development Machine)                                      │
│                                                                  │
│  ┌──────────────────┐         polls every 1s    ┌─────────────┐│
│  │ React Frontend   │←──────────────────────────│ SensorPanel ││
│  │ (Vite)           │                            │ component   ││
│  │ localhost:5173   │                            └─────────────┘│
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Reference

### Backend Files:
- `/backend/scripts/ros_sensor_bridge.py` - ROS subscriber node
- `/backend/app/routers/sensors.py` - API endpoints
- `/backend/app/main.py` - Includes sensors router (line 4, 29)
- `/backend/sensor_data/latest_sensors.json` - Latest sensor values (auto-generated)
- `/backend/sensor_data/thermal_latest.jpg` - Latest thermal image (auto-generated)
- `/backend/sensor_data/rgb_latest.jpg` - Latest RGB image (auto-generated)

### Frontend Files:
- `/src/components/SensorPanel.jsx` - UI component
- `/src/components/SensorPanel.css` - Styling
- `/src/services/api.js` - API client methods (lines 140-149)
- `/src/App.jsx` - Imports and renders SensorPanel (lines 6, 538)

---

## Performance Notes

- Sensor values poll at 1 Hz (1 second intervals)
- ROS bridge saves data at 2 Hz
- Images update whenever ROS publishes (typically 10-30 Hz from cameras, but display updates at 1 Hz max)
- Image cache-busting (`?t=timestamp`) ensures fresh images every refresh

---

## Next Steps

1. **Tune Update Rates**: Adjust polling frequency in `SensorPanel.jsx` line 33 if needed
2. **Add More Sensors**: Subscribe to additional topics in `ros_sensor_bridge.py`
3. **Save Historical Data**: Modify bridge to log to database instead of just latest values
4. **WebSocket for Real-time**: Replace polling with WebSocket connection for sub-second updates
