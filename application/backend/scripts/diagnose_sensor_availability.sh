#!/bin/bash
# Diagnostic for "sensors unavailable" issue
# Run this on the Remote PC (HP laptop) where backend is running

echo "=========================================="
echo "SENSOR AVAILABILITY DIAGNOSTIC"
echo "=========================================="
echo ""

# Read config from .env
cd ~/Dev/pyroscope/application/backend
if [ -f .env ]; then
    echo "✅ Found .env file"
    echo ""
    echo "Current ROS Configuration:"
    grep "ROS_MASTER_URI" .env
    grep "ROS_IP" .env
    echo ""
else
    echo "❌ .env file not found!"
    exit 1
fi

# Extract values
ROS_MASTER_URI=$(grep "ROS_MASTER_URI=" .env | cut -d'=' -f2)
ROS_IP=$(grep "ROS_IP=" .env | cut -d'=' -f2 | grep -v "^#")

echo "Parsed values:"
echo "  ROS_MASTER_URI: $ROS_MASTER_URI"
echo "  ROS_IP: $ROS_IP"
echo ""

# Step 1: Check network connectivity to ROS master
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 1: Network Connectivity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$ROS_MASTER_URI" ]; then
    echo "❌ ROS_MASTER_URI is empty!"
    echo "   → Backend cannot check ROS topics"
    exit 1
fi

# Extract IP from ROS_MASTER_URI (http://10.0.0.46:11311 -> 10.0.0.46)
JETSON_IP=$(echo $ROS_MASTER_URI | sed 's/http:\/\///' | cut -d':' -f1)
JETSON_PORT=$(echo $ROS_MASTER_URI | sed 's/http:\/\///' | cut -d':' -f2)

echo "Jetson Nano IP: $JETSON_IP"
echo "Jetson Nano Port: $JETSON_PORT"
echo ""

echo "Testing connection to Jetson..."
if ping -c 2 $JETSON_IP > /dev/null 2>&1; then
    echo "✅ Can ping Jetson at $JETSON_IP"
else
    echo "❌ CANNOT ping Jetson at $JETSON_IP"
    echo "   → Network issue between Remote PC and Jetson"
    echo ""
    echo "Possible fixes:"
    echo "   1. Check if Jetson is powered on"
    echo "   2. Check if both devices on same network"
    echo "   3. Update ROS_MASTER_URI in .env to correct Jetson IP"
    exit 1
fi
echo ""

echo "Testing ROS master port..."
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$JETSON_IP/$JETSON_PORT" 2>/dev/null; then
    echo "✅ ROS master port $JETSON_PORT is reachable"
else
    echo "❌ CANNOT reach ROS master port $JETSON_PORT"
    echo "   → ROS master may not be running on Jetson"
    echo ""
    echo "On Jetson, check: roscore should be running"
    exit 1
fi
echo ""

# Step 2: Check if backend can see ROS topics
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 2: ROS Topic Availability (from Backend PC)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Set environment for this shell
export ROS_MASTER_URI=$ROS_MASTER_URI
export ROS_IP=$ROS_IP

echo "Checking required sensor topics..."
echo ""

REQUIRED_TOPICS=(
    "/sensors/sht40/temperature"
    "/sensors/sht40/humidity"
    "/sensors/thermal/mean"
    "/camera/color/image_raw"
)

ALL_AVAILABLE=true
for topic in "${REQUIRED_TOPICS[@]}"; do
    if timeout 2 rostopic list 2>/dev/null | grep -q "^${topic}$"; then
        echo "✅ $topic"
    else
        echo "❌ $topic (NOT FOUND)"
        ALL_AVAILABLE=false
    fi
done
echo ""

if [ "$ALL_AVAILABLE" = true ]; then
    echo "✅ ALL required topics are available!"
    echo ""
    echo "Backend should report sensors as available."
    echo "If it doesn't, backend may need restart to pick up ROS connection."
else
    echo "❌ Some topics are MISSING"
    echo ""
    echo "On Jetson, make sure these are running:"
    echo "   roslaunch pyroscope_sensors sensors.launch"
    echo ""
    echo "You can verify on Jetson with:"
    echo "   rostopic list | grep sensors"
    exit 1
fi

# Step 3: Test backend API directly
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "STEP 3: Backend API Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "Testing /api/sensors/availability endpoint..."
RESPONSE=$(curl -s http://localhost:8000/api/sensors/availability 2>&1)

echo "Response:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

if echo "$RESPONSE" | grep -q '"available": true' || echo "$RESPONSE" | grep -q '"available":true'; then
    echo "✅ Backend reports sensors AVAILABLE!"
elif echo "$RESPONSE" | grep -q '"available": false' || echo "$RESPONSE" | grep -q '"available":false'; then
    echo "❌ Backend reports sensors UNAVAILABLE"
    echo ""
    echo "Likely causes:"
    echo "   1. Backend hasn't established ROS connection yet"
    echo "   2. Backend needs restart to pick up .env changes"
    echo "   3. Python rospy module not available in backend environment"
    echo ""
    echo "Try restarting backend:"
    echo "   cd ~/Dev/pyroscope/application/backend"
    echo "   python run.py"
else
    echo "⚠️  Unexpected response from backend"
    echo ""
    echo "Is backend running?"
    echo "   ps aux | grep 'python.*run.py'"
fi
echo ""

# Step 4: Summary
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo ""
echo "If all steps passed but frontend still shows 'sensors unavailable':"
echo ""
echo "1. Check frontend is connecting to correct backend IP"
echo "   File: application/src/services/api.js"
echo "   Should be: http://$ROS_IP:8000/api"
echo ""
echo "2. Restart backend to ensure ROS connection established:"
echo "   cd ~/Dev/pyroscope/application/backend"
echo "   python run.py"
echo ""
echo "3. Check browser console for errors (F12 in browser)"
echo ""
