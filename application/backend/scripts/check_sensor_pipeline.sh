#!/bin/bash
# Complete sensor pipeline diagnostic

echo "=============================================="
echo "SENSOR PIPELINE DIAGNOSTIC"
echo "=============================================="
echo ""

# Step 1: Check ROS topics
echo "1️⃣ CHECKING ROS TOPICS"
echo "══════════════════════════════════════════"
echo "Temperature topic:"
timeout 2 rostopic echo /sensors/sht40/temperature -n 1 2>&1 | head -5
echo ""
echo "Thermal mean topic:"
timeout 2 rostopic echo /sensors/thermal/mean -n 1 2>&1 | head -5
echo ""

# Step 2: Check if sensor bridge is running
echo "2️⃣ CHECKING SENSOR BRIDGE PROCESS"
echo "══════════════════════════════════════════"
if ps aux | grep -v grep | grep ros_sensor_bridge.py > /dev/null; then
    echo "✅ Sensor bridge is RUNNING"
    ps aux | grep ros_sensor_bridge.py | grep -v grep
else
    echo "❌ Sensor bridge is NOT RUNNING"
    echo "   → Start it with: python scripts/ros_sensor_bridge.py"
fi
echo ""

# Step 3: Check ROS node
echo "3️⃣ CHECKING ROS NODE"
echo "══════════════════════════════════════════"
if rosnode list 2>/dev/null | grep sensor_bridge > /dev/null; then
    echo "✅ /sensor_bridge node exists"
    rosnode list | grep sensor
else
    echo "❌ /sensor_bridge node NOT found"
fi
echo ""

# Step 4: Check who's subscribed to topics
echo "4️⃣ CHECKING TOPIC SUBSCRIBERS"
echo "══════════════════════════════════════════"
echo "Who subscribes to /sensors/thermal/mean:"
rostopic info /sensors/thermal/mean 2>/dev/null | grep -A 5 "Subscribers"
echo ""

# Step 5: Check sensor_data directory
echo "5️⃣ CHECKING SENSOR DATA DIRECTORY"
echo "══════════════════════════════════════════"
SENSOR_DIR=~/Dev/pyroscope/application/backend/sensor_data
if [ -d "$SENSOR_DIR" ]; then
    echo "✅ Directory exists: $SENSOR_DIR"
    ls -la "$SENSOR_DIR"
else
    echo "❌ Directory MISSING: $SENSOR_DIR"
    echo "   → Create it with: mkdir -p $SENSOR_DIR"
fi
echo ""

# Step 6: Check JSON file
echo "6️⃣ CHECKING JSON FILE"
echo "══════════════════════════════════════════"
JSON_FILE=~/Dev/pyroscope/application/backend/sensor_data/latest_sensors.json
if [ -f "$JSON_FILE" ]; then
    echo "✅ JSON file exists"
    echo "Content:"
    cat "$JSON_FILE" | python3 -m json.tool 2>/dev/null || cat "$JSON_FILE"
    echo ""
    echo "Last modified:"
    stat "$JSON_FILE" | grep Modify
else
    echo "❌ JSON file MISSING: $JSON_FILE"
    echo "   → Sensor bridge should create this automatically"
fi
echo ""

# Step 7: Check backend API
echo "7️⃣ CHECKING BACKEND API"
echo "══════════════════════════════════════════"
if ps aux | grep -v grep | grep "python.*run.py" > /dev/null; then
    echo "✅ Backend is RUNNING"
else
    echo "❌ Backend is NOT RUNNING"
    echo "   → Start it with: cd ~/Dev/pyroscope/application/backend && python run.py"
fi
echo ""

# Step 8: Test API endpoint locally
echo "8️⃣ TESTING API ENDPOINT (LOCAL)"
echo "══════════════════════════════════════════"
curl -s http://localhost:8000/api/sensors/latest 2>&1 | python3 -m json.tool 2>/dev/null || echo "Failed to reach API"
echo ""

# Step 9: Check from Mac IP
echo "9️⃣ TESTING API ENDPOINT (FROM MAC)"
echo "══════════════════════════════════════════"
MY_IP=$(hostname -I | awk '{print $1}')
echo "Server IP: $MY_IP"
echo "Test from Mac with: curl http://$MY_IP:8000/api/sensors/latest"
echo ""

# Summary
echo "=============================================="
echo "DIAGNOSTIC COMPLETE"
echo "=============================================="
echo ""
echo "If sensors still unavailable, check above for:"
echo "  ❌ Missing processes (sensor bridge, backend)"
echo "  ❌ Missing files (JSON, directory)"
echo "  ❌ Null values in JSON (topics not publishing)"
echo ""
