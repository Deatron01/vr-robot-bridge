# ROS 1 Hub bridge (`bridge_node_ros1.py`)

ROS 1 Noetic port of `vrtelemetry-plugin-ros-unity-bridge`'s `bridge_node.py`
(the ROS 2 plugin that ships with VRTelemetry). Runs inside WSL2 as a plain
`rospy` node — **not** launched by VRTelemetry's `PluginManager`, which is
Windows-side and has no access to WSL2's Python/ROS install.

## Files

| file | what it is |
|---|---|
| `bridge_node_ros1.py` | The bridge: Core Hub websocket → `geometry_msgs/PoseStamped` on `/vrtelemetry/hmd_pose`. |
| `coordinate_convert.py` | OpenXR → ROS/REP-103 axis permutation. Copied unchanged from the ROS 2 plugin (pure math, no ROS imports). |
| `run_bridge.sh` | Sources the ROS environment, then runs the node. **Use this, not the .py directly** — see "The sourcing trap". |
| `mock_hub.py` | Synthetic Core Hub. Emits `telemetry_frame` messages so the whole chain can be tested with no headset, no VRTelemetry, and no WSL2↔Windows networking. |
| `verify_conversion.py` | Task P1.2 check: asserts the published poses match hand-derived REP-103 expectations. |

## The sourcing trap

WSL2 **non-interactive** shells (`wsl -d Ubuntu-20.04 bash -lc ...`, which is
what any automation uses) do not source `~/.bashrc`, so the ROS setup files it
sources never run and `import rospy` fails. Verified 2026-09-13: `ROS_DISTRO`
is empty in such a shell. `run_bridge.sh` exists to source things explicitly.
Anything scripted — including the deferred `wsl.exe`-entrypoint automation —
must do the same.

Related: background processes started from a `wsl.exe` invocation can die when
that invocation ends. Use `setsid nohup … &` to fully detach them.

## Quickstart (all inside WSL2, no headset required)

```bash
# 1. rosbridge + roscore (once; detached so it survives the shell exiting)
mkdir -p ~/p0logs
source /opt/ros/noetic/setup.bash
setsid nohup roslaunch rosbridge_server rosbridge_websocket.launch \
    > ~/p0logs/rosbridge.log 2>&1 &

# 2. synthetic telemetry, stepping through known poses
cd /mnt/c/Users/nipit/Desktop/ROS/vr-robot-bridge/ros_workspace/bridge
setsid nohup python3 -u mock_hub.py --mode known --hold 4 > ~/p0logs/mock.log 2>&1 &

# 3. the bridge
setsid nohup ./run_bridge.sh > ~/p0logs/bridge.log 2>&1 &

# 4. check
source /opt/ros/noetic/setup.bash
rostopic echo /vrtelemetry/hmd_pose
python3 verify_conversion.py --duration 25
```

`mock_hub.py --mode orbit` (the default) gives continuous smooth motion
instead, which is the more useful mode for Unity play-mode work.

## Networking: what actually works

Verified 2026-09-13 on this machine (no `.wslconfig`, so WSL2 is on default
NAT networking):

- **Windows → WSL2 works on `localhost`.** With rosbridge running,
  `Test-NetConnection localhost -Port 9090` succeeds from PowerShell. This is
  the direction Unity needs, so Unity's rosbridge client should point at
  **`ws://localhost:9090`**. (Only the IPv6 `::1` attempt fails; the IPv4 one
  succeeds, which is what matters.)
- **WSL2 → Windows does NOT work.** `localhostForwarding` only covers the
  direction above, not the reverse. Probing a Windows listener bound to
  `0.0.0.0` (Unity's port 7800) from inside WSL2 was refused on both
  `localhost` and the gateway address `172.18.224.1`, with all three Windows
  Firewall profiles enabled.
  **Consequence: `HUB_WS_URL=ws://localhost:8000/...` will not reach the real
  Core Hub.** That's still to be solved (project task P0.3) — likely a Windows
  Firewall inbound rule for the WSL subnet, or switching WSL2 to mirrored
  networking. Until then, use `mock_hub.py`, which runs inside WSL2 and
  sidesteps the boundary entirely.

## Prerequisites (already done on this machine)

- `ros-noetic-rosbridge-server` — installed 2026-09-13 (0.11.17).
- `websockets` 12.0 — installed 2026-09-13 via `pip3 install --user`.
- `rospy` / `geometry_msgs` come from the ROS install, not pip.

## Status

- [x] `coordinate_convert.py` ported (unchanged — pure math)
- [x] `bridge_node_ros1.py` written (rospy substitutions), compiles on the
      distro's Python 3.8.10
- [x] `ros-noetic-rosbridge-server` installed; rosbridge serves
      ws://0.0.0.0:9090 and roscore listens on 11311
- [x] `websockets` installed
- [x] `mock_hub.py` + `run_bridge.sh` written
- [x] **End-to-end run inside WSL2 confirmed**: mock → bridge →
      `/vrtelemetry/hmd_pose`, 1802 messages in 25 s (≈72 Hz, matching the
      mock's configured rate)
- [x] **Coordinate conversion verified** (`verify_conversion.py`): all five
      known poses match hand-derived REP-103 expectations, positions and
      quaternions
- [x] Windows → WSL2 reachability on 9090 confirmed (`ws://localhost:9090`)
- [ ] WSL2 → Windows reachability for the real Hub on :8000 — **blocked**,
      see "Networking" above (project task P0.3)
- [ ] Run against real VRTelemetry telemetry (needs the above)
- [ ] `PluginManager`/`wsl.exe`-entrypoint automation (optional, later)
