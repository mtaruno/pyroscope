#!/usr/bin/env python

"""
Unit tests for coverage_planner.CoveragePlanner.

These tests exercise the target-safety and target-generation logic without
requiring a running ROS graph. A lightweight stub replaces rospy so the
planner class can be imported and tested in a plain Python environment.
"""

import math
import sys
import types
import unittest

# ---------------------------------------------------------------------------
# Minimal rospy stub so coverage_planner.py can be imported outside ROS.
# Only the symbols actually used at import / construction time are provided.
# ---------------------------------------------------------------------------
_rospy = types.ModuleType('rospy')
_rospy.ROSInterruptException = type('ROSInterruptException', (Exception,), {})
_rospy.ROSException = type('ROSException', (Exception,), {})


class _FakeTime(object):
    def __init__(self, secs=0, nsecs=0):
        self._secs = secs

    def to_sec(self):
        return float(self._secs)

    def __sub__(self, other):
        return _FakeDuration(self._secs - other._secs)

    def __add__(self, other):
        return _FakeTime(self._secs + other._secs)

    def __lt__(self, other):
        return self._secs < other._secs

    def __ne__(self, other):
        return self._secs != other._secs

    def __call__(self, secs=0, nsecs=0):
        return _FakeTime(secs)


class _FakeDuration(object):
    def __init__(self, secs=0, nsecs=0):
        self._secs = secs

    def to_sec(self):
        return float(self._secs)


_rospy.Time = _FakeTime
_rospy.Duration = _FakeDuration

_rospy.get_param = lambda name, default=None: default
_rospy.loginfo = lambda *a, **kw: None
_rospy.logwarn = lambda *a, **kw: None
_rospy.logwarn_throttle = lambda *a, **kw: None
_rospy.logfatal = lambda *a, **kw: None
_rospy.is_shutdown = lambda: False
_rospy.signal_shutdown = lambda msg: None
_rospy.sleep = lambda d: None
_rospy.Rate = lambda hz: type('R', (), {'sleep': lambda s: None})()
_rospy.init_node = lambda *a, **kw: None


class _FakePublisher(object):
    def __init__(self, *a, **kw):
        pass

    def publish(self, msg=None):
        pass


class _FakeSubscriber(object):
    def __init__(self, *a, **kw):
        pass


_rospy.Publisher = _FakePublisher
_rospy.Subscriber = _FakeSubscriber


# Stub out every ROS dependency that coverage_planner imports at module level
sys.modules['rospy'] = _rospy
sys.modules['actionlib'] = types.ModuleType('actionlib')

# Fake SimpleActionClient
_sac = type('SimpleActionClient', (), {
    '__init__': lambda self, *a, **kw: None,
    'wait_for_server': lambda self, timeout=None: True,
})
sys.modules['actionlib'].SimpleActionClient = _sac
sys.modules['actionlib'].GoalStatus = type('GoalStatus', (), {'SUCCEEDED': 3})

sys.modules['tf'] = types.ModuleType('tf')
sys.modules['tf'].Exception = Exception
sys.modules['tf'].LookupException = type('LookupException', (Exception,), {})
sys.modules['tf'].ConnectivityException = type('ConnectivityException', (Exception,), {})
sys.modules['tf'].ExtrapolationException = type('ExtrapolationException', (Exception,), {})
sys.modules['tf'].TransformListener = lambda: None
_tf_trans = types.ModuleType('tf.transformations')
_tf_trans.euler_from_quaternion = lambda q: (0, 0, 0)
_tf_trans.quaternion_from_euler = lambda r, p, y: (0, 0, 0, 1)
sys.modules['tf'].transformations = _tf_trans
sys.modules['tf.transformations'] = _tf_trans

sys.modules['geometry_msgs'] = types.ModuleType('geometry_msgs')
sys.modules['geometry_msgs.msg'] = types.ModuleType('geometry_msgs.msg')
sys.modules['geometry_msgs.msg'].PoseStamped = type('PoseStamped', (), {})

sys.modules['move_base_msgs'] = types.ModuleType('move_base_msgs')
sys.modules['move_base_msgs.msg'] = types.ModuleType('move_base_msgs.msg')
sys.modules['move_base_msgs.msg'].MoveBaseAction = type('MoveBaseAction', (), {})
sys.modules['move_base_msgs.msg'].MoveBaseGoal = type('MoveBaseGoal', (), {})

sys.modules['nav_msgs'] = types.ModuleType('nav_msgs')
sys.modules['nav_msgs.msg'] = types.ModuleType('nav_msgs.msg')
sys.modules['nav_msgs.msg'].OccupancyGrid = type('OccupancyGrid', (), {})
sys.modules['nav_msgs.srv'] = types.ModuleType('nav_msgs.srv')
sys.modules['nav_msgs.srv'].GetPlan = type('GetPlan', (), {})

sys.modules['std_msgs'] = types.ModuleType('std_msgs')
sys.modules['std_msgs.msg'] = types.ModuleType('std_msgs.msg')
sys.modules['std_msgs.msg'].Bool = type('Bool', (), {'__init__': lambda s, **kw: None})
sys.modules['std_msgs.msg'].Int32 = type('Int32', (), {'__init__': lambda s, **kw: None})
sys.modules['std_msgs.msg'].String = type('String', (), {'__init__': lambda s, **kw: None})

# ---------------------------------------------------------------------------
# Now we can safely import the module under test.
# ---------------------------------------------------------------------------
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coverage_planner import CoveragePlanner, CoverageTarget  # noqa: E402


# ---------------------------------------------------------------------------
# Helper to build a fake costmap (nav_msgs/OccupancyGrid-like object).
# ---------------------------------------------------------------------------
class FakeCostmapInfo(object):
    def __init__(self, width, height, resolution, origin_x, origin_y):
        self.width = width
        self.height = height
        self.resolution = resolution

        class Pos(object):
            def __init__(self, x, y):
                self.x = x
                self.y = y

        class Origin(object):
            def __init__(self, x, y):
                self.position = Pos(x, y)

        self.origin = Origin(origin_x, origin_y)


class FakeHeader(object):
    def __init__(self):
        self.stamp = _FakeTime(1)


def make_costmap(width_cells, height_cells, resolution, origin_x, origin_y, default_cost=0):
    """Return a fake OccupancyGrid with *default_cost* everywhere."""
    cm = type('OG', (), {})()
    cm.info = FakeCostmapInfo(width_cells, height_cells, resolution, origin_x, origin_y)
    cm.data = [default_cost] * (width_cells * height_cells)
    cm.header = FakeHeader()
    return cm


def set_cell(costmap, mx, my, cost):
    costmap.data[my * costmap.info.width + mx] = cost


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestIsTargetSafe(unittest.TestCase):
    """Verify is_target_safe against various costmap states."""

    def _make_planner(self, threshold=85, check_radius=0.10):
        planner = CoveragePlanner.__new__(CoveragePlanner)
        planner.latest_costmap = None
        planner.latest_costmap_stamp = None
        planner.target_cost_threshold = threshold
        planner.target_check_radius = check_radius
        return planner

    # -- basic cases --

    def test_no_costmap_returns_false(self):
        planner = self._make_planner()
        self.assertFalse(planner.is_target_safe(0, 0))

    def test_target_outside_costmap_returns_false(self):
        planner = self._make_planner()
        # Costmap covers [0, 5) x [0, 5) metres
        planner.latest_costmap = make_costmap(100, 100, 0.05, 0.0, 0.0)
        # Target at (10, 10) is outside
        self.assertFalse(planner.is_target_safe(10.0, 10.0))

    def test_free_space_returns_true(self):
        planner = self._make_planner()
        # 10x10 m costmap, all cost=0 (free)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0)
        self.assertTrue(planner.is_target_safe(0.0, 0.0))

    def test_obstacle_at_target_returns_false(self):
        planner = self._make_planner(threshold=85)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0)
        # Place obstacle (cost=100) at cell corresponding to (0, 0)
        mx, my = planner.world_to_costmap(0.0, 0.0)
        set_cell(planner.latest_costmap, mx, my, 100)
        self.assertFalse(planner.is_target_safe(0.0, 0.0))

    def test_obstacle_near_target_within_radius(self):
        planner = self._make_planner(threshold=85, check_radius=0.10)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0)
        mx, my = planner.world_to_costmap(0.0, 0.0)
        # Place obstacle one cell away (within check_radius of 0.10m = 2 cells at 0.05 res)
        set_cell(planner.latest_costmap, mx + 1, my, 100)
        self.assertFalse(planner.is_target_safe(0.0, 0.0))

    # -- unknown space handling (the key fix) --

    def test_all_unknown_space_is_safe(self):
        """Targets in completely unknown space should be considered safe.

        This is the critical behaviour for mapless rolling-window navigation.
        Unknown cells have cost -1 in the OccupancyGrid encoding.
        """
        planner = self._make_planner()
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0, default_cost=-1)
        self.assertTrue(planner.is_target_safe(0.0, 0.0))

    def test_mixed_unknown_and_free_is_safe(self):
        planner = self._make_planner()
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0, default_cost=-1)
        # Set center cell to free
        mx, my = planner.world_to_costmap(0.0, 0.0)
        set_cell(planner.latest_costmap, mx, my, 0)
        self.assertTrue(planner.is_target_safe(0.0, 0.0))

    def test_unknown_with_obstacle_is_unsafe(self):
        planner = self._make_planner(threshold=85)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0, default_cost=-1)
        mx, my = planner.world_to_costmap(0.0, 0.0)
        set_cell(planner.latest_costmap, mx, my, 100)
        self.assertFalse(planner.is_target_safe(0.0, 0.0))

    # -- edge-of-costmap neighbour handling --

    def test_target_near_costmap_edge_still_safe(self):
        """A target at the edge of the costmap should not fail just because
        some of its radius cells fall outside the grid."""
        planner = self._make_planner(check_radius=0.10)
        # Small costmap: 10x10 cells = 0.5x0.5 m starting at origin
        planner.latest_costmap = make_costmap(10, 10, 0.05, 0.0, 0.0)
        # Target at (0.025, 0.025) — cell (0, 0), edge of the grid
        self.assertTrue(planner.is_target_safe(0.025, 0.025))

    def test_cost_below_threshold_is_safe(self):
        """Inflated cells with cost below the threshold should be safe."""
        planner = self._make_planner(threshold=253)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0)
        mx, my = planner.world_to_costmap(0.0, 0.0)
        # Set cost to 99 (inscribed inflation in OccupancyGrid), below 253
        set_cell(planner.latest_costmap, mx, my, 99)
        self.assertTrue(planner.is_target_safe(0.0, 0.0))


class TestRefreshTargets(unittest.TestCase):
    """Verify target generation from costmap."""

    def _make_planner(self, width=2.0, height=2.0, spacing=0.5, margin=0.3):
        planner = CoveragePlanner.__new__(CoveragePlanner)
        planner.area_width = width
        planner.area_height = height
        planner.row_spacing = spacing
        planner.waypoint_spacing = spacing
        planner.origin_x = 0.0
        planner.origin_y = 0.0
        planner.wall_margin = margin
        planner.target_cost_threshold = 253
        planner.target_check_radius = 0.05
        planner.targets = []
        planner.target_lookup = {}
        planner.next_target_id = 0
        planner.sweep_target_ids = []
        planner.sweep_cursor = 0
        planner.sequence_initialized = False
        planner.latest_costmap = None
        planner.latest_costmap_stamp = None
        return planner

    def test_generates_targets_in_free_space(self):
        planner = self._make_planner(width=2.0, height=2.0, spacing=0.5, margin=0.3)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0)
        planner.refresh_targets_from_costmap()
        self.assertGreater(len(planner.targets), 0)
        # All targets should be safe (no obstacles in the costmap)
        for t in planner.targets:
            self.assertTrue(t.currently_safe, "Target at (%.2f, %.2f) should be safe" % (t.x, t.y))

    def test_generates_targets_in_unknown_space(self):
        """Targets in unknown space should still be generated and marked safe."""
        planner = self._make_planner(width=2.0, height=2.0, spacing=0.5, margin=0.3)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0, default_cost=-1)
        planner.refresh_targets_from_costmap()
        self.assertGreater(len(planner.targets), 0)
        safe_count = sum(1 for t in planner.targets if t.currently_safe)
        self.assertEqual(safe_count, len(planner.targets),
                         "All targets should be safe when space is unknown")

    def test_targets_near_obstacle_are_unsafe(self):
        planner = self._make_planner(width=2.0, height=2.0, spacing=0.5, margin=0.3)
        planner.latest_costmap = make_costmap(200, 200, 0.05, -5.0, -5.0)
        planner.target_cost_threshold = 85
        # Place obstacle at origin
        mx, my = planner.world_to_costmap(0.0, 0.0)
        set_cell(planner.latest_costmap, mx, my, 100)
        planner.refresh_targets_from_costmap()
        # The target at (0, 0) should be unsafe
        origin_target = None
        for t in planner.targets:
            if abs(t.x) < 0.01 and abs(t.y) < 0.01:
                origin_target = t
                break
        if origin_target is not None:
            self.assertFalse(origin_target.currently_safe)


class TestSweepSequence(unittest.TestCase):
    """Verify the lawnmower sweep ordering."""

    def test_alternating_row_direction(self):
        planner = CoveragePlanner.__new__(CoveragePlanner)
        planner.targets = [
            CoverageTarget(0, 0, 0, 0, 0),
            CoverageTarget(1, 1, 0, 0, 1),
            CoverageTarget(2, 2, 0, 0, 2),
            CoverageTarget(3, 0, 1, 1, 0),
            CoverageTarget(4, 1, 1, 1, 1),
            CoverageTarget(5, 2, 1, 1, 2),
        ]
        planner.build_sweep_target_ids()
        # Row 0 (even): left to right → ids 0, 1, 2
        # Row 1 (odd):  right to left → ids 5, 4, 3
        self.assertEqual(planner.sweep_target_ids, [0, 1, 2, 5, 4, 3])


if __name__ == '__main__':
    unittest.main()
