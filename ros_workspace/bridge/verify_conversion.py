#!/usr/bin/env python3
"""Task P1.2 -- verify the OpenXR -> ROS/REP-103 conversion end to end.

Subscribes to the bridge's output topic while `mock_hub.py --mode known` is
feeding it the fixed pose sequence, collects the distinct poses that actually
arrive, and compares them against expectations **derived by hand from REP-103**
(x forward, y left, z up).

The expected table is hardcoded here and in mock_hub.py rather than computed by
importing coordinate_convert, on purpose: the point is to test that module
against an independent source of truth. Deriving the expectations from the code
under test would only prove self-consistency and would agree with a sign error
just as happily.

Usage (with rosbridge/roscore, mock_hub --mode known, and the bridge running):

    source /opt/ros/noetic/setup.bash
    python3 verify_conversion.py --duration 25

Exit code 0 if every expected pose was observed and matched; 1 otherwise.
"""

from __future__ import annotations

import argparse
import collections
import sys

import rospy
from geometry_msgs.msg import PoseStamped

# (label, expected ROS position xyz, expected ROS quaternion xyzw)
EXPECTED = [
    ("identity", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR X (right)", (0.0, -1.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR Y (up)", (0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR Z (backward)", (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("yaw +90deg about OpenXR Y", (0.0, 0.0, 0.0), (0.0, 0.0, 0.70710678, 0.70710678)),
]

TOL = 1e-4
MIN_SAMPLES = 5  # ignore transient/partial poses seen only once or twice


def key_of(msg: PoseStamped):
    p, o = msg.pose.position, msg.pose.orientation
    return (
        round(p.x, 4), round(p.y, 4), round(p.z, 4),
        round(o.x, 4), round(o.y, 4), round(o.z, 4), round(o.w, 4),
    )


def matches(observed, pos, quat) -> bool:
    want = tuple(pos) + tuple(quat)
    return all(abs(a - b) <= TOL for a, b in zip(observed, want))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="/vrtelemetry/hmd_pose")
    parser.add_argument("--duration", type=float, default=25.0,
                        help="seconds to collect (mock cycle is 5 steps x --hold)")
    args = parser.parse_args()

    counts: collections.Counter = collections.Counter()
    rospy.init_node("verify_conversion", anonymous=True, disable_signals=True)
    rospy.Subscriber(args.topic, PoseStamped, lambda m: counts.update([key_of(m)]))

    print(f"collecting from {args.topic} for {args.duration:.0f}s ...")
    rospy.sleep(args.duration)

    total = sum(counts.values())
    if total == 0:
        print(f"FAIL: no messages received on {args.topic}")
        return 1
    distinct = [k for k, n in counts.items() if n >= MIN_SAMPLES]
    print(f"received {total} messages, {len(distinct)} distinct poses "
          f"(>= {MIN_SAMPLES} samples)\n")

    all_ok = True
    for label, pos, quat in EXPECTED:
        hit = next((d for d in distinct if matches(d, pos, quat)), None)
        want = "pos(" + ", ".join(f"{v:+.4f}" for v in pos) + ")"
        if hit is None:
            print(f"  FAIL  {label:<28} expected {want} -- not observed")
            all_ok = False
        else:
            print(f"  PASS  {label:<28} {want} x{counts[hit]}")

    unexplained = [
        d for d in distinct
        if not any(matches(d, p, q) for _, p, q in EXPECTED)
    ]
    for d in unexplained:
        print(f"  ????  unexpected pose observed: "
              f"pos({d[0]:+.4f}, {d[1]:+.4f}, {d[2]:+.4f}) "
              f"quat({d[3]:+.4f}, {d[4]:+.4f}, {d[5]:+.4f}, {d[6]:+.4f})")
        all_ok = False

    print("\nRESULT:", "PASS -- conversion matches REP-103" if all_ok else "FAIL")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
