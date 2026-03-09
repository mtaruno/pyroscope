# Pyroscope Session Context — Feb 24, 2026

## Active Repos
- **Main repo (USE THIS):** `/Users/matthewtaruno/Dev/pyroscope/`
- **Ignore:** `/Users/matthewtaruno/Dev/pyroscope_backend/` (old, unused)
- Frontend: `pyroscope/application/src/`
- Backend: `pyroscope/application/backend/`
- ROS packages: `pyroscope/catkin_ws/src/pyroscope_navigation/`

## Current Active Problem: Heatmap Invisible After Robot Scan

### Root Cause
- `ScanWaypointSample` model has NO lat/lng columns (only air_temp, humidity, thermal_mean)
- Backend heatmap endpoint (`scans.py:248-282`) spreads waypoints over the physical scan area (3m)
- 3m in GPS degrees = ~0.000027 degrees = ~20px at zoom 20
- But `BoundaryLayer` fits map to 200m view = ~1300px wide
- Result: 3m heatmap overlay is an invisible speck in the center

### Planned Fix (in plan file, pending approval)
- **One-line change** in `application/backend/app/routers/scans.py` line ~256
- Change `area_m` from parsed scan area (3m) to `50.0` (matching the 50m inner boundary displayed on the map)
- Plan file: `~/.claude/plans/fluttering-waddling-snowflake.md`

## Completed Work This Session

### 1. move_base Obstacle Avoidance
- Replaced `waypoint_controller.py` + `safety_stop.py` with ROS `move_base` navigation stack
- Created costmap configs (costmap_common.yaml, global_costmap.yaml, local_costmap.yaml, dwa_planner.yaml)
- Created `coverage_mission_nav.launch` launch file
- Modified `coverage_planner.py` to use `actionlib.SimpleActionClient` with `MoveBaseAction`

### 2. Robot Driving Into Walls (Multiple Iterations)
- inflation_radius: 0.15 -> 0.25 -> 0.18 -> **0.15** (final)
- cost_scaling_factor: 3.0 -> 5.0 -> 10.0 -> **3.0** (final)
- Added WALL_MARGIN = 0.20m in coverage_planner.py
- **Key fix:** Centered waypoint grid on origin instead of offsetting from (0,0)
  ```python
  min_x = self.origin_x - self.area_width / 2.0 + WALL_MARGIN
  max_x = self.origin_x + self.area_width / 2.0 - WALL_MARGIN
  ```

### 3. Stop Scan Killing Backend
- `os.killpg()` was killing the backend's own process group
- Fixed: added `pgid != os.getpgrp()` safety check before killing

### 4. Progress Tracking Mismatch
- Frontend, backend, and planner all calculated total waypoints differently
- Aligned all three to use same formula: `_calc_total_waypoints(area_width, area_height, row_spacing, waypoint_spacing, wall_margin=0.20)`

### 5. Scan Config Modal
- Changed area options from [3, 25, 50] to [1, 2, 3] m
- Changed precision options from [1, 5] to [0.25, 0.5, 1] m
- Added origin X/Y, row spacing, dwell time, waypoint timeout config fields

### 6. Removed Fuel Upload Popup
- Removed Wildlands AI fuel estimation popup after scan completion
- Goes straight to scan results now

### 7. Waypoint Retry Loop Fix
- Removed `continue` that caused infinite retry of same failed waypoint
- Now skips to next waypoint after 3 consecutive failures + costmap clear

### 8. Database Issues (Remote PC)
- Created `scan_waypoint_samples` table on remote PC
- Fixed missing `captured_at` column

## Key Files Modified

| File | Changes |
|------|---------|
| `application/backend/app/routers/robot.py` | `_calc_total_waypoints()`, process group safety, launch `coverage_mission_nav.launch` |
| `application/backend/app/routers/scans.py` | Heatmap endpoint queries waypoint samples, spreads in grid (needs 50m fix) |
| `application/src/components/ScanConfigModal.jsx` | 1/2/3m areas, advanced config fields, aligned waypoint calc |
| `application/src/components/ScanConfigModal.css` | Styles for new input fields |
| `application/src/App.jsx` | Removed fuel upload popup, pass advanced config to mission API |
| `catkin_ws/src/pyroscope_navigation/scripts/coverage_planner.py` | move_base integration, wall margin, centered grid, costmap clearing |
| `catkin_ws/src/pyroscope_navigation/config/costmap_common.yaml` | inflation_radius=0.15, cost_scaling_factor=3.0 |
| `catkin_ws/src/pyroscope_navigation/config/dwa_planner.yaml` | occdist_scale=0.5, goal_distance_bias=24.0 |

## Known Remaining Issues
1. **Heatmap invisible** — fix planned (see above)
2. **Robot occasionally drives into walls** — wall margin + centering helped but not fully resolved
3. **Files need SCP to remote PC** after changes (costmap configs, coverage_planner.py, backend files)
4. **Remote PC MySQL** may need schema updates as code evolves

## Architecture Notes
- Multi-machine: Jetson (hardware) → Ubuntu PC (ROS nav + backend) → Mac (frontend dev)
- ROS sensor bridge: background thread subscribing to `/voltage`, `/sensors/*`, `/camera/*`
- Battery: voltage_to_percent 9.6V=0%, 12.6V=100% (3S LiPo)
- Backend: FastAPI + SQLAlchemy + MySQL
- Frontend: React + Leaflet + Vite
