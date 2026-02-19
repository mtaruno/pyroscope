#!/bin/bash
# Diagnostic script to test sensor data flow

echo "========================================="
echo "Sensor Data Flow Diagnostic"
echo "========================================="
echo ""

# Step 1: Check ROS topic
echo "1. Checking ROS topic /sensors/thermal/mean..."
TOPIC_OUTPUT=$(timeout 2 rostopic echo /sensors/thermal/mean -n 1 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ Topic is publishing: $TOPIC_OUTPUT"
else
    echo "   ✗ Topic NOT publishing or timeout"
    echo "   Run: rostopic list | grep thermal"
    exit 1
fi
echo ""

# Step 2: Check JSON file exists
echo "2. Checking JSON file..."
JSON_FILE=~/Dev/pyroscope/application/backend/sensor_data/latest_sensors.json
if [ -f "$JSON_FILE" ]; then
    echo "   ✓ File exists"
    echo "   Content:"
    cat "$JSON_FILE" | python3 -m json.tool 2>/dev/null || cat "$JSON_FILE"
else
    echo "   ✗ File does not exist: $JSON_FILE"
    echo "   Is ros_sensor_bridge.py running?"
    exit 1
fi
echo ""

# Step 3: Check thermal_mean in JSON
echo "3. Checking thermal_mean value in JSON..."
THERMAL_MEAN=$(cat "$JSON_FILE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('thermal_mean', 'null'))" 2>/dev/null)
if [ "$THERMAL_MEAN" != "null" ] && [ "$THERMAL_MEAN" != "None" ]; then
    echo "   ✓ thermal_mean = $THERMAL_MEAN"
else
    echo "   ✗ thermal_mean is null/missing in JSON"
    echo "   Check ros_sensor_bridge.py logs for errors"
    exit 1
fi
echo ""

# Step 4: Test API endpoint
echo "4. Testing API endpoint..."
API_RESPONSE=$(curl -s http://localhost:8000/api/sensors/latest 2>&1)
if [ $? -eq 0 ]; then
    echo "   ✓ API responded"
    echo "   Response:"
    echo "$API_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$API_RESPONSE"

    # Check if thermal_mean is in response
    API_THERMAL=$(echo "$API_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('thermal_mean', 'null'))" 2>/dev/null)
    if [ "$API_THERMAL" != "null" ] && [ "$API_THERMAL" != "None" ]; then
        echo "   ✓ thermal_mean in API response = $API_THERMAL"
    else
        echo "   ✗ thermal_mean missing from API response"
    fi
else
    echo "   ✗ API request failed"
    echo "   Is backend running? Try: curl http://localhost:8000/health"
fi
echo ""

echo "========================================="
echo "Diagnostic Complete"
echo "========================================="
