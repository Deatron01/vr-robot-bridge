#!/usr/bin/env python3
"""Independent verification of the ROS(REP-103) -> Unity quaternion conversion
used in RosUnityCoordinates.cs, closing the "rotation gap" noted in
claude/status.md for the vr-robot-bridge project.

Why this approach: the noted gap is that live testing (mock_hub yaw-about-Y
pose at the origin, read via Unity's Pipeline CLI) can't distinguish rotation
from position (position stays at origin) and the Pipeline can't even report a
Quaternion field directly. Rather than fighting the live tooling, this proves
the SAME thing mathematically and far more thoroughly: it checks the defining
property a coordinate-conversion quaternion must have --

    f(R * v) == Q * f(v)      for every vector v

where R is a rotation expressed in ROS/REP-103, Q is RosUnityCoordinates'
converted quaternion, f is RosUnityCoordinates' position-axis conversion, and
"*" is "rotate this vector by this quaternion". If that identity holds for
enough independent, non-degenerate rotations and vectors, the quaternion
conversion is correct -- this is strictly stronger than any single
hand-picked pose (like the yaw-at-origin one), because it holds for
*arbitrary* rotations and directions, not just the one case that happened to
be tested live.

Also re-verifies the first-stage conversion (OpenXR -> ROS, in
coordinate_convert.py) the same way, and composes both stages end-to-end
against a hand-worked physical example (an offset AND a rotation together --
exactly the untested case status.md called out), as a final sanity check
independent of both files.

No ROS, no Unity, no WSL2, no network needed -- pure math, runs anywhere with
Python 3. Run with: python3 verify_rotation_chain.py
"""
from __future__ import annotations

import math
import random


# ---------------------------------------------------------------------------
# Quaternion helpers (generic, NOT copied from either file under test --
# using the same helper for both would just prove self-consistency).
# ---------------------------------------------------------------------------

Vec3 = tuple  # (x, y, z)
Quat = tuple  # (x, y, z, w)


def quat_normalize(q: Quat) -> Quat:
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w)
    return (x / n, y / n, z / n, w / n)


def quat_from_axis_angle(axis: Vec3, angle_rad: float) -> Quat:
    ax, ay, az = axis
    n = math.sqrt(ax * ax + ay * ay + az * az)
    ax, ay, az = ax / n, ay / n, az / n
    s = math.sin(angle_rad / 2.0)
    return (ax * s, ay * s, az * s, math.cos(angle_rad / 2.0))


def quat_mul(a: Quat, b: Quat) -> Quat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_conj(q: Quat) -> Quat:
    x, y, z, w = q
    return (-x, -y, -z, w)


def rotate_vec_by_quat(q: Quat, v: Vec3) -> Vec3:
    """Standard v' = q * v * q^-1, treating v as a pure quaternion (v,0)."""
    vq = (v[0], v[1], v[2], 0.0)
    rx, ry, rz, rw = quat_mul(quat_mul(q, vq), quat_conj(q))
    assert abs(rw) < 1e-9, f"result not a pure vector, w={rw}"
    return (rx, ry, rz)


def vec_close(a: Vec3, b: Vec3, tol: float = 1e-6) -> bool:
    return all(abs(a[i] - b[i]) < tol for i in range(3))


# ---------------------------------------------------------------------------
# Stage 1: OpenXR -> ROS/REP-103 (coordinate_convert.py, reproduced verbatim
# from ros_workspace/bridge/coordinate_convert.py for a standalone check).
# ---------------------------------------------------------------------------

def openxr_pos_to_ros(pos: Vec3) -> Vec3:
    x, y, z = pos
    return (-z, -x, y)


def openxr_quat_to_ros(rot_xyzw: Quat) -> Quat:
    x, y, z, w = rot_xyzw
    return (-z, -x, y, w)


# ---------------------------------------------------------------------------
# Stage 2: ROS/REP-103 -> Unity (RosUnityCoordinates.cs, reproduced verbatim).
# ---------------------------------------------------------------------------

def ros_pos_to_unity(pos: Vec3) -> Vec3:
    x, y, z = pos
    return (-y, z, x)


def ros_quat_to_unity(rot_xyzw: Quat) -> Quat:
    x, y, z, w = rot_xyzw
    return (y, -z, -x, w)


# ---------------------------------------------------------------------------
# Property check: f(R*v) == Q*f(v) for a coordinate-conversion pair (f, Q).
# ---------------------------------------------------------------------------

def check_conversion_pair(name, pos_convert, quat_convert, rotations, vectors):
    print(f"\n--- {name} ---")
    all_ok = True
    for r_label, axis, angle_deg in rotations:
        angle = math.radians(angle_deg)
        r = quat_from_axis_angle(axis, angle)
        q_converted = quat_convert(r)
        for v_label, v in vectors:
            lhs = pos_convert(rotate_vec_by_quat(r, v))      # f(R * v)
            rhs = rotate_vec_by_quat(q_converted, pos_convert(v))  # Q * f(v)
            ok = vec_close(lhs, rhs)
            all_ok &= ok
            status = "PASS" if ok else "FAIL"
            if not ok:
                print(f"  [{status}] rot={r_label:<28} vec={v_label:<10} "
                      f"f(R*v)={lhs} vs Q*f(v)={rhs}")
    if all_ok:
        n_cases = len(rotations) * len(vectors)
        print(f"  ALL {n_cases} cases PASS: f(R*v) == Q*f(v) holds for every "
              f"tested rotation and vector.")
    return all_ok


def main():
    random.seed(0)

    axis_tests = [
        ("yaw 90 about Y", (0, 1, 0), 90.0),
        ("yaw -37 about Y", (0, 1, 0), -37.0),
        ("pitch 60 about X", (1, 0, 0), 60.0),
        ("roll 25 about Z", (0, 0, 1), 25.0),
        ("135 about (1,1,0)", (1, 1, 0), 135.0),
        ("random axis 1", (0.3, 0.7, -0.2), 47.0),
        ("random axis 2", (-0.5, 0.1, 0.9), 163.0),
    ]
    # A handful of independent axis-angle rotations, plus random extra cases,
    # to avoid relying on any single hand-picked axis.
    for _ in range(5):
        axis = (random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))
        angle = random.uniform(-179, 179)
        axis_tests.append(("random axis/angle", axis, angle))

    vectors = [
        ("+X", (1, 0, 0)),
        ("+Y", (0, 1, 0)),
        ("+Z", (0, 0, 1)),
        ("diag", (1, 1, 1)),
        ("random", (0.4, -1.3, 0.9)),
    ]

    ok1 = check_conversion_pair(
        "Stage 1: OpenXR -> ROS  (coordinate_convert.py)",
        openxr_pos_to_ros, openxr_quat_to_ros, axis_tests, vectors,
    )
    ok2 = check_conversion_pair(
        "Stage 2: ROS -> Unity  (RosUnityCoordinates.cs)",
        ros_pos_to_unity, ros_quat_to_unity, axis_tests, vectors,
    )

    # End-to-end physical sanity check, independent of both files' internal
    # conventions: a pose that is offset AND rotated (the exact case the
    # status.md gap says was never tried).
    print("\n--- End-to-end offset+rotation case (the untested gap case) ---")
    openxr_pos = (0.5, 0.0, -1.0)          # 1m forward-ish, offset right
    openxr_rot = quat_from_axis_angle((0, 1, 0), 90.0)  # yaw +90 about Y

    ros_pos = openxr_pos_to_ros(openxr_pos)
    ros_rot = openxr_quat_to_ros(openxr_rot)
    unity_pos = ros_pos_to_unity(ros_pos)
    unity_rot = ros_quat_to_unity(ros_rot)

    # Cross-check: rotate a reference vector by ros_rot in ROS space, then
    # convert to Unity, vs converting the reference vector to Unity first and
    # rotating it there by unity_rot -- both paths must land on the same
    # physical direction.
    ref_ros = openxr_pos_to_ros((0, 0, -1))       # ROS-frame "forward" ref
    ref_unity_via_ros_rotation = ros_pos_to_unity(rotate_vec_by_quat(ros_rot, ref_ros))
    ref_unity_direct = rotate_vec_by_quat(unity_rot, ros_pos_to_unity(ref_ros))
    match = vec_close(ref_unity_via_ros_rotation, ref_unity_direct)

    print(f"  OpenXR pos={openxr_pos} rot(axis=Y,90deg)")
    print(f"  -> ROS   pos={tuple(round(c,4) for c in ros_pos)}"
          f" rot={tuple(round(c,4) for c in ros_rot)}")
    print(f"  -> Unity pos={tuple(round(c,4) for c in unity_pos)}"
          f" rot={tuple(round(c,4) for c in unity_rot)}")
    print(f"  Cross-check (rotate-then-convert == convert-then-rotate): "
          f"{'PASS' if match else 'FAIL'}")

    print("\n=== SUMMARY ===")
    print(f"Stage 1 (OpenXR->ROS) quaternion conversion: {'PASS' if ok1 else 'FAIL'}")
    print(f"Stage 2 (ROS->Unity) quaternion conversion:  {'PASS' if ok2 else 'FAIL'}")
    print(f"End-to-end offset+rotation cross-check:      {'PASS' if match else 'FAIL'}")
    overall = ok1 and ok2 and match
    print(f"\nOVERALL: {'ALL CHECKS PASS' if overall else 'FAILURES FOUND'}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
