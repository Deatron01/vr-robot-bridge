#!/usr/bin/env python3
"""Mock VRTelemetry Core Hub -- synthetic `telemetry_frame` publisher.

Stands in for the real Core Hub's Event Router (`/ws/hub/telemetry`) so the
ROS 1 bridge, rosbridge and Unity can be developed and verified without a
headset, without a live VRTelemetry session, and -- because this runs inside
WSL2 alongside the bridge -- without solving WSL2 -> Windows networking
(task P0.3) first.

Serves the same contract the real Hub does (PROTOCOL.md section 4, and
`HubSubscriber` in bridge_node_ros1.py):

    {"type": "telemetry_frame", "session_id": "...", "frame": {...}}

Poses are emitted in the **OpenXR runtime convention** (right-handed, +Y up,
-Z forward), exactly as the real Hub stores them -- the bridge is what
converts to ROS/REP-103.

Modes
-----
known   Steps through a fixed sequence of hand-checkable poses, holding each
        for --hold seconds. This is the fixture for task P1.2: the expected
        ROS-side values are printed at startup so `rostopic echo` can be
        compared against them directly.
orbit   Continuous smooth motion (a circle in the OpenXR XZ plane at eye
        height, yawing to face travel). For "does it move and keep up"
        checks and for Unity play-mode work.

Usage
-----
    python3 mock_hub.py                        # orbit @ 72 Hz on :8000
    python3 mock_hub.py --mode known --hold 3
    python3 mock_hub.py --host 0.0.0.0 --rate 90

Then, in another shell:

    HUB_WS_URL=ws://127.0.0.1:8000/ws/hub/telemetry ./run_bridge.sh
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import time

import websockets

SESSION_ID = "mock-session-0001"

# Fixed poses for task P1.2, in OpenXR convention: (label, position, quat xyzw).
KNOWN_STEPS = [
    ("identity", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR X (right)", (1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR Y (up)", (0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR Z (backward)", (0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    ("yaw +90deg about OpenXR Y", (0.0, 0.0, 0.0), (0.0, 0.70710678, 0.0, 0.70710678)),
]

# Expected values on the ROS side after openxr_pose_to_ros, DERIVED BY HAND
# from REP-103 (x forward, y left, z up) and hardcoded deliberately.
#
# These are NOT computed by importing coordinate_convert: the point of P1.2 is
# to check that module against an independent source of truth. Generating the
# expectations with the very code under test would only prove self-consistency
# and would happily agree with a sign error.
EXPECTED_ROS = [
    ("identity", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR X (right)", (0.0, -1.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR Y (up)", (0.0, 0.0, 1.0), (0.0, 0.0, 0.0, 1.0)),
    ("+1m OpenXR Z (backward)", (-1.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)),
    ("yaw +90deg about OpenXR Y", (0.0, 0.0, 0.0), (0.0, 0.0, 0.70710678, 0.70710678)),
]


def print_expected_table() -> None:
    print("\nExpected ROS values on /vrtelemetry/hmd_pose (hand-derived from REP-103):")
    print(f"  {'step':<28} {'position (x,y,z)':<24} quaternion (x,y,z,w)")
    for label, pos, quat in EXPECTED_ROS:
        pos_s = "(" + ", ".join(f"{v:+.4f}" for v in pos) + ")"
        quat_s = "(" + ", ".join(f"{v:+.4f}" for v in quat) + ")"
        print(f"  {label:<28} {pos_s:<24} {quat_s}")
    print()


def build_frame(index: int, pos, quat) -> dict:
    """One telemetry_frame `frame` object, matching PROTOCOL.md section 4."""
    px, py, pz = pos
    qx, qy, qz, qw = quat
    frame = {
        "frame_index": index,
        "timestamp_ns": time.time_ns(),
        "hmd_pos_x": px,
        "hmd_pos_y": py,
        "hmd_pos_z": pz,
        "hmd_rot_x": qx,
        "hmd_rot_y": qy,
        "hmd_rot_z": qz,
        "hmd_rot_w": qw,
        "hmd_tracking_valid": 1.0,
        # Controllers: offset copies of the HMD pose so the fields exist and
        # move, for task P1.3. Synthetic, not a model of real hand motion.
        "left_tracking_valid": 1.0,
        "right_tracking_valid": 1.0,
        "eye_tracking_valid": 0.0,
    }
    for side, dx in (("left", -0.2), ("right", 0.2)):
        frame[f"{side}_pos_x"] = px + dx
        frame[f"{side}_pos_y"] = py - 0.3
        frame[f"{side}_pos_z"] = pz - 0.3
        frame[f"{side}_rot_x"] = qx
        frame[f"{side}_rot_y"] = qy
        frame[f"{side}_rot_z"] = qz
        frame[f"{side}_rot_w"] = qw
        frame[f"{side}_trigger"] = 0.0
        frame[f"{side}_grip"] = 0.0
        frame[f"{side}_joy_x"] = 0.0
        frame[f"{side}_joy_y"] = 0.0
    return frame


def orbit_pose(t: float, radius: float = 1.0, height: float = 1.6):
    """Circle in the OpenXR XZ plane at eye height, yawing to face travel."""
    angle = (t * 0.5) % (2.0 * math.pi)
    pos = (radius * math.sin(angle), height, -radius * math.cos(angle))
    half = angle / 2.0
    quat = (0.0, math.sin(half), 0.0, math.cos(half))
    return pos, quat


async def stream(websocket, args) -> None:
    peer = getattr(websocket, "remote_address", "?")
    path = getattr(websocket, "path", "?")
    print(f"[mock_hub] client connected: {peer} path={path}")

    index = 0
    period = 1.0 / args.rate
    next_send = time.perf_counter()
    start = time.perf_counter()
    last_step = -1

    try:
        while True:
            now = time.perf_counter() - start
            if args.mode == "known":
                step = int(now // args.hold) % len(KNOWN_STEPS)
                label, pos, quat = KNOWN_STEPS[step]
                if step != last_step:
                    exp_pos = EXPECTED_ROS[step][1]
                    print(
                        f"[mock_hub] step {step}: {label}"
                        f"  -> expect ROS position "
                        f"({exp_pos[0]:+.4f}, {exp_pos[1]:+.4f}, {exp_pos[2]:+.4f})"
                    )
                    last_step = step
            else:
                pos, quat = orbit_pose(now)

            message = {
                "type": "telemetry_frame",
                "session_id": SESSION_ID,
                "frame": build_frame(index, pos, quat),
            }
            await websocket.send(json.dumps(message))
            index += 1

            next_send += period
            delay = next_send - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            else:
                # Fell behind (slow consumer); resync rather than spin.
                next_send = time.perf_counter()
    except websockets.ConnectionClosed:
        print(f"[mock_hub] client disconnected after {index} frames")


async def main_async(args) -> None:
    # Accept any path/query string: the bridge appends ?plugin_id=... (and
    # optionally &token=...), and the real Hub serves this at
    # /ws/hub/telemetry. Signature takes *_ so this works on websockets
    # versions that still pass a `path` argument to the handler.
    async def handler(websocket, *_):
        await stream(websocket, args)

    print(f"[mock_hub] mode={args.mode} rate={args.rate}Hz "
          f"serving ws://{args.host}:{args.port}/<any-path>")
    if args.mode == "known":
        print(f"[mock_hub] holding each step for {args.hold}s")
        print_expected_table()

    async with websockets.serve(handler, args.host, args.port):
        await asyncio.Future()  # run forever


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--rate", type=float, default=72.0, help="frames per second")
    parser.add_argument("--mode", choices=("orbit", "known"), default="orbit")
    parser.add_argument("--hold", type=float, default=3.0,
                        help="seconds to hold each pose in --mode known")
    args = parser.parse_args()

    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\n[mock_hub] stopped")


if __name__ == "__main__":
    main()
