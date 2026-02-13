# Random Exploration Mode

Simple random walk exploration - **no odometry needed!**

## What It Does

The robot:
1. Moves forward for a random duration (default: ~3 seconds)
2. Stops and turns left or right for a random duration (default: ~2 seconds)
3. Repeats forever

This lets you test basic navigation and motor control before setting up odometry or cameras.

## Quick Start

```bash
# On your Jetson
roslaunch pyroscope_navigation random_exploration.launch
```

That's it! Robot will start exploring randomly.

**To stop:** Press `Ctrl+C`

## Tuning the Behavior

### Make it more cautious (slower, shorter movements):
```bash
roslaunch pyroscope_navigation random_exploration.launch \
  forward_speed:=0.15 \
  forward_duration:=2.0 \
  turn_speed:=0.3
```

### Make it more aggressive (faster, longer movements):
```bash
roslaunch pyroscope_navigation random_exploration.launch \
  forward_speed:=0.4 \
  forward_duration:=5.0 \
  turn_speed:=0.8
```

### Parameters:
- `forward_speed` - How fast to move forward (m/s, default: 0.2)
- `forward_duration` - How long to move forward (seconds, default: 3.0)
- `turn_speed` - How fast to turn (rad/s, default: 0.5)
- `turn_duration` - How long to turn (seconds, default: 2.0)

## Testing Workflow

**Phase 1: Indoor test on flat ground**
```bash
# Very slow and safe
roslaunch pyroscope_navigation random_exploration.launch \
  forward_speed:=0.1 turn_speed:=0.3 forward_duration:=2.0
```

**Phase 2: Open area test**
```bash
# Normal speed
roslaunch pyroscope_navigation random_exploration.launch
```

**Phase 3: Rough terrain**
```bash
# Slower but longer movements
roslaunch pyroscope_navigation random_exploration.launch \
  forward_speed:=0.15 forward_duration:=4.0
```

## Adding Obstacle Avoidance Later

When you get the ZED camera working:

1. Create a node that processes depth images
2. Publish `True` to `/obstacle_detected` when obstacle ahead
3. Launch with obstacle detection enabled:
   ```bash
   roslaunch pyroscope_navigation random_exploration.launch use_obstacle_detection:=true
   ```

The explorer will automatically stop and turn away when obstacles detected.

## Behavior Details

- Random variation: ±30% on all durations (prevents predictable patterns)
- Turn direction: Random left or right each time
- Smooth transitions: No abrupt velocity changes
- Clean shutdown: Robot stops when you Ctrl+C

## Advantages Over Waypoint Navigation

For initial testing, random exploration is better because:
- ✓ No odometry required
- ✓ No coordinate frame setup needed
- ✓ Works immediately
- ✓ Good for testing motor control
- ✓ Good for collecting sensor data (future)

## Next Steps

1. **Test basic movement** with random exploration
2. **Add ZED depth processing** for obstacle detection
3. **Switch to waypoint navigation** when you need precise positioning

## Safety Tips

- Start with very slow speeds indoors
- Keep rover on a leash or in a bounded area
- Have emergency stop ready (Ctrl+C or physical e-stop)
- Test on blocks/elevated first to verify motor directions
