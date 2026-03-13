# Coverage Mission Nav — Tunable Parameters Guide

A complete reference for every parameter you can adjust when testing and tuning
the `coverage_mission_nav.launch` deployment.  Values shown are the current
defaults; you can override most of them on the `roslaunch` command line.

---

## Quick-start launch template

```bash
roslaunch pyroscope_navigation coverage_mission_nav.launch \
  area_width:=10.0        \
  area_height:=10.0       \
  row_spacing:=0.5        \
  waypoint_spacing:=0.5   \
  origin_x:=0.0           \
  origin_y:=0.0           \
  wall_margin:=0.45       \
  dwell_time:=3.0         \
  waypoint_timeout:=60.0  \
  stall_timeout:=12.0     \
  target_cost_threshold:=253
```

---

## 1 · Coverage Planner parameters (`coverage_planner.py`)

These are forwarded through `coverage_mission_nav.launch` arguments and set on
the ROS parameter server under the `coverage_planner` node namespace.

### 1.1 Mission geometry

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `area_width` | `10.0` | m | Total width (X-axis extent) of the survey rectangle. Increase for a larger field; decrease for a smaller plot. |
| `area_height` | `10.0` | m | Total height (Y-axis extent) of the survey rectangle. |
| `row_spacing` | `0.5` | m | Distance between adjacent sweep rows. Smaller → denser coverage but more waypoints and longer mission. Typical range: 0.3 – 1.0 m. |
| `waypoint_spacing` | `0.5` | m | Distance between consecutive waypoints along a single row. Smaller → finer sampling within a row. |
| `origin_x` | `0.0` | m | X-coordinate of the centre of the survey area in the `odom` frame. Shift to place the grid over a different part of the field. |
| `origin_y` | `0.0` | m | Y-coordinate of the centre of the survey area. |
| `wall_margin` | `0.45` | m | Safety buffer inset from the area boundary before the first/last waypoints are placed. Keeps the robot away from fences or plot edges. Must be ≥ robot half-width + `inflation_radius`. |

### 1.2 Timing

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `dwell_time` | `3.0` | s | How long the robot pauses at each waypoint after arriving (e.g., for a sensor capture). Set to `0` to skip pausing. |
| `waypoint_timeout` | `60.0` | s | Maximum time allowed to reach one waypoint. If exceeded the planner records a failure and tries the next target. Increase if the robot legitimately needs longer to navigate around obstacles. |
| `stall_timeout` | `12.0` | s | If the robot makes no progress toward the current goal for this many seconds, the target is abandoned. Increase for slow terrain; decrease for faster failure detection. |
| `progress_log_interval` | `2.0` | s | How often the planner logs its progress percentage. Cosmetic only. |

### 1.3 Target safety / costmap filtering

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `target_cost_threshold` | `253` | 0–255 | Costmap cost above which a target cell is considered occupied/unsafe and will be skipped. `253` is just below `LETHAL_OBSTACLE` (254), so only confirmed lethal obstacles are rejected while high-inflation cells are still treated as reachable. Lower values (e.g. `128`) make the planner more conservative and skip heavily inflated cells too. |
| `target_check_radius` | `0.05` | m | Radius around a candidate target within which the costmap is sampled. Larger → the robot must find a bigger clear patch before committing to a target. |
| `max_target_failures` | `4` | count | Number of consecutive navigation failures on a single target before it is permanently skipped. Increase if obstacles are transient; decrease if you want the planner to move on quickly. |

### 1.4 Path planning service

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `make_plan_tolerance` | `0.25` | m | Goal tolerance passed to the `move_base/make_plan` service when checking reachability. Larger → the global planner accepts plans that land slightly off the exact target, reducing failures in cluttered areas. |
| `progress_epsilon` | `0.05` | m | Minimum improvement in distance-to-goal that counts as "progress". If the robot closes the gap by less than this in one `progress_log_interval` the stall timer keeps running. |

### 1.5 No-target retry behaviour

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `no_target_retry_limit` | `8` | count | How many times the planner retries finding any reachable target before declaring the mission stuck. Increase if the costmap clears slowly. |
| `no_target_retry_sleep` | `1.5` | s | Pause between retry attempts when no reachable target can be found. Gives the costmap time to update. |

---

## 2 · DWA local planner (`config/dwa_planner.yaml`)

The DWA planner handles reactive obstacle avoidance and generates velocity
commands every control cycle.

### 2.1 Velocity limits

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `max_vel_x` | `0.25` | m/s | Maximum forward speed. Increasing this makes the robot faster but leaves less reaction time for obstacle avoidance. Start with ≤ 0.3 m/s outdoors. |
| `min_vel_x` | `0.05` | m/s | Minimum forward speed when moving (prevents the robot stopping mid-trajectory). |
| `max_vel_theta` | `0.8` | rad/s | Maximum angular (turning) speed. ~46 °/s. Reduce if the robot's odometry diverges during fast turns. |
| `min_vel_theta` | `-0.8` | rad/s | Maximum reverse angular speed (must be negative to allow turning both ways). |
| `min_vel_trans` | `0.04` | m/s | Absolute minimum translational speed when any motion is commanded. |
| `max_vel_y` | `0.0` | m/s | Lateral velocity — keep at 0 for a differential-drive robot. |
| `min_vel_y` | `0.0` | m/s | Lateral velocity lower bound — keep at 0. |

### 2.2 Acceleration limits

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `acc_lim_x` | `0.8` | m/s² | Maximum linear acceleration. Lower values produce gentler starts/stops and reduce wheel slip. |
| `acc_lim_theta` | `1.5` | rad/s² | Maximum angular acceleration. |
| `acc_lim_y` | `0.0` | m/s² | Lateral acceleration — keep at 0. |

### 2.3 Goal tolerances

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `xy_goal_tolerance` | `0.15` | m | How close the robot must get to the waypoint position to consider it reached. Tighten for precise coverage; loosen if the robot oscillates trying to reach an exact point. |
| `yaw_goal_tolerance` | `0.30` | rad | Final heading tolerance (~17 °). Coverage missions typically do not require a precise final heading, so this can be relaxed. |
| `latch_xy_goal_tolerance` | `true` | bool | When `true` the robot stops reversing once it is within `xy_goal_tolerance`, even if it drifts out again. Prevents the robot from backing up to meet its goal. |

### 2.4 Forward simulation

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `sim_time` | `2.0` | s | How far ahead the planner simulates candidate trajectories. Longer → smoother paths but higher CPU cost. |
| `sim_granularity` | `0.05` | s | Time step used inside each simulated trajectory. Smaller → finer collision checking but higher CPU cost. |
| `vx_samples` | `10` | count | Number of forward-velocity candidates evaluated per cycle. More → better velocity choice but slower. |
| `vtheta_samples` | `12` | count | Number of angular-velocity candidates evaluated. |
| `vy_samples` | `1` | count | Lateral samples — 1 is correct for a non-holonomic robot. |

### 2.5 Trajectory scoring weights

These three weights are the most impactful DWA tuning knobs.

| Parameter | Default | What it does |
|-----------|---------|--------------|
| `path_distance_bias` | `8.0` | Reward for staying close to the global plan. Higher → robot tracks the planned path tightly; lower → robot cuts corners. |
| `goal_distance_bias` | `16.0` | Reward for moving toward the goal. Higher → robot charges toward the goal even if it deviates from the plan; lower → robot follows the plan more patiently. |
| `occdist_scale` | `0.3` | Penalty for trajectories that pass near obstacles. Higher → robot gives obstacles a wider berth (may get stuck in narrow spaces); lower → robot cuts close to obstacles (may clip them). |

### 2.6 Oscillation and collision prevention

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `oscillation_reset_dist` | `0.20` | m | How far the robot must travel to reset the oscillation detector. |
| `forward_point_distance` | `0.10` | m | Distance of the forward look-ahead point used for collision cost. |
| `stop_time_buffer` | `0.25` | s | Extra time buffer added to deceleration calculations to guarantee a complete stop before an obstacle. |

---

## 3 · Costmap parameters

### 3.1 Shared obstacle & inflation layer (`config/costmap_common.yaml`)

Loaded into both the global and local costmap namespaces.

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `footprint` | `[[-0.125,-0.10],[-0.125,0.10],[0.125,0.10],[0.125,-0.10]]` | m | Robot collision polygon (25 cm × 20 cm rectangle). Update if you swap the chassis. |
| `obstacle_layer/laser_scan/obstacle_range` | `4.0` | m | Maximum range at which LIDAR readings are used to **mark** obstacles. |
| `obstacle_layer/laser_scan/raytrace_range` | `5.0` | m | Maximum range used to **clear** (raytrace through) free space. Should be ≥ `obstacle_range`. |
| `obstacle_layer/laser_scan/max_obstacle_height` | `0.5` | m | Points above this height are ignored. |
| `obstacle_layer/laser_scan/min_obstacle_height` | `0.0` | m | Points below this height are ignored. |
| `inflation_layer/inflation_radius` | `0.20` | m | Distance to inflate obstacles outward. Effectively adds this buffer around every obstacle. Must be ≥ robot half-width for safe navigation (robot half-width ≈ 0.125 m). |
| `inflation_layer/cost_scaling_factor` | `2.0` | — | Exponential decay rate of inflation cost with distance. Higher → cost drops off faster (narrower inflation band). |
| `resolution` | `0.05` | m/cell | Costmap grid resolution (5 cm). |

### 3.2 Global costmap (`config/global_costmap.yaml`)

Used by the global planner (NavFn) for full path planning.

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `global_costmap/update_frequency` | `4.0` | Hz | How often the global costmap is rebuilt from sensor data. Lower → less CPU; higher → faster obstacle updates for global planning. |
| `global_costmap/publish_frequency` | `2.0` | Hz | How often the costmap is published for visualisation/consumers. |
| `global_costmap/transform_tolerance` | `3.0` | s | Maximum age of TF data before the costmap reports a TF error. |
| `global_costmap/width` | `15.0` | m | Rolling-window width centred on the robot. Larger → more context for global planning; more RAM and CPU. |
| `global_costmap/height` | `15.0` | m | Rolling-window height. |

### 3.3 Local costmap (`config/local_costmap.yaml`)

Used by the DWA planner for reactive obstacle avoidance.

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `local_costmap/update_frequency` | `5.0` | Hz | Should be ≥ `controller_frequency` so the DWA planner always has fresh obstacle data. |
| `local_costmap/publish_frequency` | `2.0` | Hz | Publication rate for visualisation. |
| `local_costmap/transform_tolerance` | `3.0` | s | TF staleness tolerance. |
| `local_costmap/width` | `4.0` | m | Rolling-window width for immediate surroundings. |
| `local_costmap/height` | `4.0` | m | Rolling-window height. |

---

## 4 · move_base core parameters (inline in `coverage_mission_nav.launch`)

| Parameter | Default | Unit | What it does |
|-----------|---------|------|--------------|
| `planner_frequency` | `1.0` | Hz | How often the global plan is recomputed. Higher → plan updates more quickly around new obstacles; higher CPU cost. |
| `controller_frequency` | `5.0` | Hz | How often the DWA planner computes and sends a velocity command. Increase for faster obstacle response; must be ≤ `local_costmap/update_frequency`. |
| `planner_patience` | `8.0` | s | How long move_base waits for the global planner before triggering a recovery behaviour. |
| `controller_patience` | `8.0` | s | How long move_base waits for the local planner to make progress before triggering a recovery behaviour. |
| `oscillation_timeout` | `30.0` | s | Time the robot can oscillate (detected by `oscillation_distance`) before a recovery is triggered. |
| `oscillation_distance` | `0.15` | m | Robot must move this far to reset the oscillation timer. |
| `NavfnROS/allow_unknown` | `true` | bool | Allows the global planner to plan through unknown (grey) costmap cells. **Must stay `true`** for mapless operation — setting it to `false` prevents planning in unexplored space. |
| `NavfnROS/default_tolerance` | `0.5` | m | Goal tolerance for the global planner. Increase if NavFn repeatedly fails to find a plan to exact goal positions. |
| `recovery_behavior_enabled` | `false` | bool | Disabling recovery keeps behaviour deterministic in open outdoor spaces. Enable (`true`) if the robot frequently gets hard-stuck. |
| `conservative_reset_dist` | `0.50` | m | Radius around the robot that is cleared during a conservative reset recovery. |

---

## 5 · Practical tuning scenarios

### Robot navigates but misses many coverage points

- Decrease `row_spacing` and `waypoint_spacing` for denser waypoints.
- Decrease `target_cost_threshold` (e.g. to `200`) so the planner rejects unsafe
  targets earlier, avoiding wasted navigation attempts.

### Robot is too slow

- Increase `max_vel_x` in `dwa_planner.yaml` (try `0.35`).
- Increase `acc_lim_x` to reach top speed sooner (try `1.2`).
- Lower `sim_time` slightly (e.g. to `1.5`) to reduce planning latency.

### Robot frequently reports "stalled" or "timeout"

- Increase `stall_timeout` to `20.0` and `waypoint_timeout` to `90.0`.
- Increase `controller_patience` and `planner_patience` in the launch file.
- Check that `max_vel_x` is not too low (minimum ~0.1 m/s for outdoor terrain).

### Robot clips or collides with obstacles

- Increase `inflation_radius` in `costmap_common.yaml` (try `0.30` m).
- Increase `occdist_scale` in `dwa_planner.yaml` (try `0.6`).
- Decrease `target_cost_threshold` so obstacle-adjacent targets are skipped.

### Robot oscillates or overshoots waypoints

- Increase `xy_goal_tolerance` in `dwa_planner.yaml` (try `0.25` m).
- Reduce `goal_distance_bias` (try `10.0`) so the planner brakes earlier.
- Reduce `max_vel_x` and `acc_lim_x` for gentler motion.

### "No reachable target found" messages dominate the log

- Increase `no_target_retry_limit` to `15` and `no_target_retry_sleep` to `3.0`.
- Increase `global_costmap/update_frequency` to `6.0` Hz so the costmap clears
  faster after the robot moves.
- Lower `target_cost_threshold` to allow targets near (but not inside) inflated
  obstacle zones.

### Robot gets permanently stuck

- Set `recovery_behavior_enabled` to `true` in the launch file.
- Enable `clearing_rotation_allowed` to let move_base spin in place to clear
  obstacle cells from the local costmap.

---

## 6 · Should parameter tuning alone be sufficient?

**Yes, for most issues in an obstacle-free or lightly cluttered environment.**
The navigation stack is fully functional: the costmap-aware target selector,
DWA planner, and move_base recovery pipeline provide a solid foundation that
responds well to parameter changes.

**However, some failure modes require code changes, not just tuning:**

| Symptom | Likely root cause | Fix |
|---------|-------------------|-----|
| Robot spins at the first waypoint indefinitely | Odometry not publishing or wrong frame name | Check `/odom` topic and TF tree |
| Global planner always fails (`allow_unknown false` warning) | `NavfnROS/allow_unknown` was accidentally set to `false` | Set back to `true` |
| Coverage grid is not centred on the physical field | `origin_x` / `origin_y` set to the wrong values | Measure field origin in `odom` coordinates |
| Robot navigates into inflated obstacle zones | `target_cost_threshold` too permissive (253 accepts all non-lethal costs including high-inflation cells) | Lower to ≤ 200 for conservative operation |
| Very large areas (>15 m) with no plan found | Global costmap window too small | Increase `global_costmap/width` and `height` |
| Mission completes but field not fully covered | `row_spacing` too large relative to sensor FOV | Halve `row_spacing` |

In summary: **start with the parameters in Section 5 above**, iterate one change
at a time, and watch the `/coverage/progress` and `/move_base/status` topics to
understand what the planner is doing.
