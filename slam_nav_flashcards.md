# SLAM & Navigation Stack Flashcards
> Grounded in the Pyroscope Transbot configuration

---

## PART 1: THE BIG PICTURE

### Card 1 — Two-Phase Workflow
**Q: What are the two distinct phases of autonomous robot navigation, and which nodes run in each?**

A: **Phase 1: Mapping (SLAM)** — Run `slam_gmapping` + teleop. Drive the robot around to build an occupancy grid map. Save it with `map_saver`. No autonomous navigation happens here.

**Phase 2: Navigation (Localization + Planning)** — Run `navigation.launch`. Load the saved map, localize with AMCL, plan paths with move_base. GMapping is OFF — the map is static now.

> In your repo: `slam_gmapping.launch` is Phase 1. `navigation.launch` is Phase 2. They never run simultaneously.

---

### Card 2 — The Three TF Frames
**Q: What are the three coordinate frames (`map`, `odom`, `base_link`) and who publishes each transform?**

A:
- **`map` → `odom`**: Published by **AMCL**. Corrects accumulated drift. Updated whenever AMCL gets a good laser match against the static map.
- **`odom` → `base_link`**: Published by **EKF** (robot_localization). Smooth, continuous, but drifts over time. Fuses wheel odometry + IMU.
- **`base_link` → `laser`**: Published by a **static_transform_publisher**. Fixed offset — your LiDAR sits 0.15m above base_link.

> The key insight: `odom` frame is smooth but drifts. `map` frame is globally correct but can jump. AMCL's job is to publish the correction between them.

---

### Card 3 — The Full Data Pipeline
**Q: Trace the data flow from LiDAR scan to wheel motors during autonomous navigation.**

A:
```
RPLidar (/scan)
    |
    v
AMCL — matches scan against static map → publishes map→odom TF
    |
    v
move_base receives:
  - Robot pose (from TF tree: map→odom→base_link)
  - Goal pose (from rviz or code)
  - Costmaps (built from static map + live /scan)
    |
    ├→ Global planner: A*/Dijkstra on global costmap → full path
    |
    └→ DWA local planner: samples velocity commands,
       scores them against local costmap → best /cmd_vel
           |
           v
       transbot_driver.py → serial → motors
```

---

## PART 2: SLAM (GMapping)

### Card 4 — What GMapping Actually Does
**Q: What algorithm does GMapping use, and what are its inputs and output?**

A: **Rao-Blackwellized Particle Filter (FastSLAM).**

**Inputs:** `/scan` (laser) + `/odom` (wheel odometry via TF)
**Output:** `/map` (occupancy grid) + `map→odom` TF

Each of your **30 particles** carries its own copy of the entire map. The particle filter weighs particles by how well their map explains the current laser scan. Over time, particles with better maps survive.

> Your config: 30 particles, 5cm resolution, 30m x 30m map, updates every 0.2m traveled or 0.2 rad turned.

---

### Card 5 — Occupancy Grid
**Q: What is an occupancy grid map, and what do the cell values mean?**

A: A 2D grid where each cell stores the probability of being occupied.
- **0** = definitely free space
- **100** = definitely an obstacle
- **-1** = unknown (never observed)

Your map resolution is **0.05m (5cm per cell)**. A 30m x 30m map = 600 x 600 = 360,000 cells. Each particle in GMapping maintains its own copy, so 30 particles = 30 maps in memory.

> This is what `map_saver` writes to disk as a `.pgm` image + `.yaml` metadata file.

---

### Card 6 — Why GMapping Needs Odometry
**Q: Why does GMapping require odometry, and what happens if odometry drifts?**

A: GMapping uses odometry as a **motion prior** — it predicts where the robot moved between scans. The particle filter then corrects this prediction using scan matching.

If odometry is bad:
- Particles spread out more to cover the uncertainty
- Scan matching has to work harder to find the right alignment
- With extreme drift, particles may converge on the wrong map

> This is why your EKF (fusing wheels + IMU) matters even during mapping. Better odom prediction = fewer particles needed = less CPU on the Jetson.

---

### Card 7 — GMapping vs Cartographer
**Q: Why did you choose GMapping over Cartographer for the Transbot?**

A:
| | GMapping | Cartographer |
|---|---|---|
| Algorithm | Particle filter | Graph optimization |
| Loop closure | No | Yes |
| CPU load | Low (30 particles) | High (submap matching) |
| Tuning | Few params | Complex Lua configs |
| Best for | Small areas, good odom | Large areas, revisits |

GMapping wins for the MVP because: small indoor spaces, Jetson compute constraints, simpler tuning. Cartographer would be better for large outdoor mapping at Beezley Trail where loop closure matters.

---

## PART 3: LOCALIZATION (AMCL)

### Card 8 — What AMCL Does
**Q: What is AMCL and how does it differ from SLAM?**

A: **Adaptive Monte Carlo Localization** — a particle filter that localizes the robot within a **known, pre-built map**. It does NOT build the map.

Each particle is a pose hypothesis (x, y, theta). AMCL:
1. Predicts particle motion using odometry model
2. Weighs particles by how well the laser scan matches the map at that pose
3. Resamples — likely poses survive, unlikely ones die
4. Adapts particle count (your range: **100–500**) based on confidence

> Key difference from GMapping: AMCL particles are just poses (x,y,theta). GMapping particles each carry an entire map. AMCL is much cheaper.

---

### Card 9 — Likelihood Field Model
**Q: What is the "likelihood_field" laser model in your AMCL config?**

A: Instead of ray-tracing each laser beam through the map (expensive), the likelihood field model:
1. Takes each laser endpoint
2. Looks up the **distance to the nearest obstacle** in the pre-computed map
3. Scores the measurement with a Gaussian — closer to a map obstacle = higher score

Your config: `laser_z_hit: 0.95` (95% weight on real measurements), `laser_z_rand: 0.05` (5% for random noise). Uses **60 beams** out of the full scan.

> This is fast and works well for structured environments. The alternative (`beam` model) does full ray tracing and is more accurate but much slower.

---

### Card 10 — Odometry Noise Model (odom_alpha)
**Q: What do `odom_alpha1` through `odom_alpha4` control in AMCL?**

A: They model how noisy your odometry is, which controls how much particles spread out during motion:

- **alpha1**: Rotation noise from rotation (turning is imprecise)
- **alpha2**: Rotation noise from translation (driving straight wiggles heading)
- **alpha3**: Translation noise from translation (distance is imprecise)
- **alpha4**: Translation noise from rotation (turning causes position slip)

All set to **0.2** in your config. Higher values = more particle spread = more uncertainty = needs more particles to converge. For tank treads (inherently slippery), you may need to increase these.

---

## PART 4: COSTMAPS

### Card 11 — Two Costmaps, Two Purposes
**Q: Why does move_base use two separate costmaps?**

A:
**Global costmap** (your config: frame=`map`, static_map=true, 1 Hz update):
- Covers the entire known map
- Starts from the static SLAM map (static_layer)
- Adds live obstacles + inflation
- Used by the **global planner** to find a path from A to B

**Local costmap** (your config: frame=`odom`, 3m x 3m rolling window, 5 Hz update):
- Small area around the robot
- No static map — purely from live sensor data
- Used by **DWA** for real-time obstacle avoidance

> The global costmap is the "big picture" plan. The local costmap is the "what's in front of me right now" reaction.

---

### Card 12 — Costmap Layers
**Q: What do the three costmap layers (static, obstacle, inflation) each contribute?**

A:
1. **Static layer** (global only): Loads the saved SLAM map. Free/occupied/unknown cells. Doesn't change at runtime.

2. **Obstacle layer** (both): Inserts live LiDAR hits as lethal (cost=254) cells. Also **clears** cells the laser passes through (marking=true, clearing=true in your config). This is how the robot sees new obstacles that weren't in the original map.

3. **Inflation layer** (both): Expands obstacles outward with decaying cost. Your `inflation_radius: 0.15m` means cells within 15cm of any obstacle get elevated cost. `cost_scaling_factor: 3.0` controls how fast cost decays — higher = steeper dropoff = robot can get closer.

> Cost values: 254 = lethal (inside obstacle), 253 = inscribed (robot center would collide), 1-252 = inflated (proximity penalty), 0 = free.

---

### Card 13 — Footprint vs Inflation Radius
**Q: Your robot footprint is 25x20cm and inflation_radius is 0.15m. What's the actual safety margin?**

A: The footprint defines the robot's physical outline. The planner checks if ANY point of the footprint would touch a lethal cell.

The inscribed radius (distance from center to nearest footprint edge) is **0.10m**. The circumscribed radius (center to corner) is ~**0.16m**.

With `inflation_radius: 0.15m`, the inflated zone barely extends past the circumscribed radius. This means the planner will allow the robot very close to obstacles — good for tight corridors, risky for collision.

> If you increase inflation_radius to 0.25m, you'd get ~10cm of extra clearance around corners but might fail to find paths through narrow spaces.

---

## PART 5: PLANNING (move_base + DWA)

### Card 14 — Global vs Local Planner
**Q: What does each planner do and how do they interact?**

A:
**Global planner** (runs at **1 Hz** in your config):
- Runs A* or Dijkstra on the global costmap
- Produces a complete path (sequence of poses) from current position to goal
- Replans every second, or when the local planner reports it's stuck

**DWA local planner** (runs at **5 Hz**):
- Doesn't follow the global path exactly
- Samples possible (vx, vtheta) velocity pairs
- Forward-simulates each for **1.5s** to get candidate trajectories
- Scores each trajectory on: path following + goal reaching + obstacle clearance
- Sends the best velocity as `/cmd_vel`

> The global planner says "go through this hallway then turn left." DWA says "right now, the best velocity to roughly follow that plan while avoiding that new chair is (0.2 m/s, 0.3 rad/s)."

---

### Card 15 — DWA Trajectory Scoring
**Q: How does DWA score trajectories, and what do your bias values mean?**

A: Each candidate trajectory gets a cost:

```
cost = path_distance_bias * (distance to global path)
     + goal_distance_bias * (distance to goal)
     + occdist_scale * (proximity to obstacles)
```

**Lower cost wins.** Your tuning:
- `path_distance_bias: 20.0` — penalty for straying from the global path
- `goal_distance_bias: 32.0` — penalty for not getting closer to goal (**dominant term**)
- `occdist_scale: 0.02` — very small penalty for being near obstacles

> Your config heavily favors goal-reaching over path-following or obstacle clearance. This means the robot will cut corners and squeeze past obstacles to reach the goal. Good for "just get there" behavior on imperfect maps.

---

### Card 16 — DWA Velocity Sampling
**Q: How many trajectories does DWA evaluate per cycle, and what constrains the velocity space?**

A: `vx_samples: 12` x `vtheta_samples: 20` = **240 candidate trajectories** per cycle, evaluated **5 times per second**.

The "dynamic window" limits which velocities are even sampled:
1. **Robot limits**: vx in [-0.15, 0.35], vtheta in [-1.5, 1.5]
2. **Acceleration limits**: From current velocity, can only reach velocities within one timestep of acceleration (`acc_lim_x: 1.5`, `acc_lim_theta: 3.0`)
3. **Obstacle limits**: Velocities that would cause collision within sim_time are excluded

> `min_vel_trans: 0.05` is your creep fix — any trajectory with total translational velocity < 5cm/s is rejected. The robot either moves decisively or stops.

---

### Card 17 — Goal Tolerances and Latching
**Q: What does `latch_xy_goal_tolerance: true` do and why do you need it?**

A: Without latching: the robot must stay within `xy_goal_tolerance: 0.20m` of the goal while ALSO satisfying `yaw_goal_tolerance: 0.3 rad`. If it enters the tolerance zone but overshoots while rotating to the right heading, DWA starts driving back — and oscillates.

With **latching**: once the robot enters the 20cm xy tolerance zone, the position constraint is "latched" (locked as satisfied). Now it only needs to achieve the yaw tolerance, even if it drifts slightly past 20cm while rotating.

> Essential for differential drive robots that can't translate and rotate independently. Without it, goal-reaching becomes a frustrating dance.

---

## PART 6: SENSOR FUSION (EKF)

### Card 18 — Why EKF Exists
**Q: Why fuse wheel odometry and IMU instead of using either alone?**

A:
**Wheel odometry alone**: Knows vx and vy well, but heading drifts because wheel slip (especially tank treads) corrupts angular velocity. Also, no absolute orientation reference.

**IMU alone**: Excellent angular velocity (gyroscope) and orientation, but integrating accelerometers for position causes massive drift within seconds.

**EKF fusion**: Takes vx, vy from wheels + yaw, vyaw from IMU. The wheels provide translation, the IMU provides rotation. Each sensor compensates for the other's weakness.

> Your config: odom0 contributes (vx, vy, vyaw), imu0 contributes (yaw, vyaw). Both in differential mode, so the EKF uses changes rather than absolute values.

---

### Card 19 — The "dummy" Frame Trick
**Q: Why is `base_link_frame` set to `dummy` instead of `base_link` in your EKF config?**

A: The EKF node publishes a TF from `odom_frame` → `base_link_frame`. If set to `base_link`, the EKF would publish `odom→base_link`.

But `robot_state_publisher` (from the URDF) also publishes frames relative to `base_link`. Having two nodes fight over the same TF link causes conflicts.

The workaround: EKF publishes `odom→dummy`, and a separate mechanism maps `dummy` to `base_link`. This keeps the TF tree clean.

> This is a common ROS pattern when using robot_state_publisher alongside robot_localization. It's hacky but standard.

---

## PART 7: RECOVERY AND EDGE CASES

### Card 20 — What Happens When the Robot Gets Stuck
**Q: Describe the recovery behavior sequence in move_base.**

A:
1. DWA fails to find a valid trajectory for a set duration
2. move_base triggers **recovery behaviors** in order:
   - **Conservative reset**: Clears obstacles outside a small region around the robot in both costmaps
   - **Clearing rotation** (`clearing_rotation_allowed: true` in your config): Robot rotates in place 360 degrees, using the laser to rebuild the local costmap from scratch
   - **Aggressive reset**: Clears ALL obstacle data from costmaps
3. If all recovery behaviors fail → move_base **aborts** the goal and publishes a failure status

> You currently only have clearing rotation enabled. You could add back-up behavior or custom recovery plugins for rough terrain.

---

### Card 21 — Map vs Reality Mismatch
**Q: What happens when the real environment has changed since the SLAM map was built?**

A: The **obstacle layer** in both costmaps handles this:
- New obstacles (a moved chair): LiDAR hits mark new lethal cells in the costmap, even though the static map says "free." The global planner replans around them at 1 Hz.
- Removed obstacles (a door opened): LiDAR clearing rays pass through what the static map says is occupied. The obstacle layer clears these cells, but the **static layer still shows them as occupied** in the global costmap.

> This is why `static_map: false` on the local costmap matters — it only uses live data, so removed obstacles disappear immediately in local planning. The global costmap is more conservative.

---

## PART 8: TYING IT ALL TOGETHER

### Card 22 — Your Full System at Runtime
**Q: List every node running during autonomous navigation and what each publishes.**

A:
| Node | Publishes | Purpose |
|---|---|---|
| rplidar_node | `/scan` | Raw laser scans |
| transbot_driver | `/transbot/imu`, `/transbot/get_vel` | Raw IMU + wheel vel |
| imu_filter_madgwick | `/imu/data` | Filtered orientation |
| base_node | `/odom_raw` | Wheel odometry |
| ekf_localization | TF: `odom→dummy` | Fused odometry |
| robot_state_publisher | TF: `base_link→*` | URDF frames |
| static_transform_publisher | TF: `base_link→laser` | LiDAR offset |
| map_server | `/map` | Saved SLAM map |
| amcl | TF: `map→odom` | Global localization |
| move_base | `/cmd_vel` | Velocity commands |

> That's ~10 nodes minimum for autonomous navigation. Each one failing silently can break the whole pipeline — this is why `check_topics.sh` exists.

---

### Card 23 — The Numbers That Matter
**Q: What are the key frequencies and rates in your system?**

A:
- **EKF**: 20 Hz (sensor fusion)
- **Local costmap update**: 5 Hz (obstacle detection)
- **DWA controller**: 5 Hz (velocity commands)
- **Local costmap publish**: 2 Hz (visualization)
- **Global planner**: 1 Hz (path replanning)
- **Global costmap update**: 1 Hz
- **AMCL**: updates every 0.1m or 0.2 rad of motion
- **GMapping** (during mapping only): updates every 0.2m or 0.2 rad, map published every 2s

> The pipeline bottleneck is usually the global planner at 1 Hz. If the robot moves 0.35 m/s, it travels 35cm between replans — nearly 2 body lengths. The local planner at 5 Hz provides the reactive safety net.

---

### Card 24 — What Would Break Navigation
**Q: List the failure modes that would cause navigation to fail, from most to least obvious.**

A:
1. **TF tree broken**: Any missing transform (map→odom→base_link→laser) and move_base can't compute the robot's pose. Instant failure.
2. **No /scan data**: Costmaps go stale, AMCL can't localize, DWA has no obstacles. Robot drives blind.
3. **AMCL delocalized**: Particles converge on wrong location. Robot thinks it's somewhere else, plans impossible paths. Hard to detect.
4. **Odometry wildly wrong**: EKF output makes AMCL's motion model wrong. Particles slowly diverge. Gradual degradation.
5. **Costmap inflation too high**: No valid paths exist through narrow spaces. move_base oscillates or aborts.
6. **Costmap inflation too low**: Paths exist too close to obstacles. Robot clips walls.
7. **DWA sim_time too short**: Robot can't "see" obstacles far enough ahead, makes last-second swerves or collisions.
8. **Goal in unknown/occupied space**: move_base immediately aborts — no valid plan possible.

---
