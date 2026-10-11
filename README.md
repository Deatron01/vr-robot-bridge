<h1 align="center">vr-robot-bridge</h1>

<p align="center">
  Live VR poses into a ROS robot hand, mirrored in Unity.<br />
  <samp>C# · PYTHON · ROS NOETIC · UNITY 6 · WSL2</samp>
</p>

### <samp>01 — WHAT IT IS</samp>

Streams live VR telemetry (HMD pose, controller poses, controller input) to a
ROS-based robot simulator and visualises it in a Unity XR application, for 1:1
simulation between the user's VR motions and a Gazebo/MoveIt robot hand.

See `docs/implementation_plan.md` for the original plan. The living task
breakdown (with per-task status) is in the ROS claude.ai project docs.

### <samp>02 — LAYOUT</samp>

```
vr-robot-bridge/
├── docs/                       plan, environment log, screenshots
├── ros_workspace/bridge/       the ROS 1 side (runs inside WSL2)
│   ├── bridge_node_ros1.py     Hub websocket -> geometry_msgs/PoseStamped
│   ├── coordinate_convert.py   OpenXR -> ROS/REP-103
│   ├── run_bridge.sh           sources ROS, then runs the node
│   ├── mock_hub.py             synthetic Core Hub (no headset needed)
│   └── verify_conversion.py    asserts the conversion against REP-103
└── RosUnityProject/            the Unity side (Unity 6000.3.23f1, URP)
    └── Assets/Scripts/
        ├── RosBridgeClient.cs      minimal rosbridge websocket client
        ├── RosPoseSubscriber.cs    drives a transform from the topic
        └── RosUnityCoordinates.cs  ROS -> Unity conversion
```

### <samp>03 — ENVIRONMENT</samp>

irob-saf (ROS Noetic + dVRK) needs Linux, so the ROS side runs inside **WSL2,
distro `Ubuntu-20.04`** — see `docs/environment_setup.md`. Unity runs natively
on Windows and reaches rosbridge across the WSL boundary.

- WSL2: Ubuntu 20.04.6, Python 3.8.10, ROS Noetic (`ros-noetic-desktop-full`)
- Catkin workspace `~/catkin_ws`: `cisst-saw`, `crtk`, `dvrk` (2.2.1),
  `ethzasl_icp_mapping`, `irob-saf`
- `ros-noetic-rosbridge-server` 0.11.17, `websockets` 12.0

### <samp>04 — RUNNING THE WHOLE CHAIN (NO HEADSET REQUIRED)</samp>

Inside WSL2:

```bash
mkdir -p ~/p0logs && source /opt/ros/noetic/setup.bash
setsid nohup roslaunch rosbridge_server rosbridge_websocket.launch > ~/p0logs/rosbridge.log 2>&1 &
cd /mnt/c/Users/nipit/Desktop/ROS/vr-robot-bridge/ros_workspace/bridge
setsid nohup python3 -u mock_hub.py --mode orbit > ~/p0logs/mock.log 2>&1 &
setsid nohup ./run_bridge.sh > ~/p0logs/bridge.log 2>&1 &
```

Then press Play in Unity. The `HmdCube` object in `SampleScene` follows the
telemetry. `mock_hub.py --mode known` instead steps through five fixed poses
for verification.

See `ros_workspace/bridge/README.md` for the gotchas (ROS sourcing in
non-interactive shells, `setsid`, the `pkill` self-match trap).

### <samp>05 — NETWORKING</samp>

- **Windows → WSL2 works on `localhost`** — Unity connects to
  `ws://localhost:9090`. Verified.
- **WSL2 → Windows does not.** `localhostForwarding` is one-directional, and a
  Windows listener on `0.0.0.0` is refused from WSL2 on both `localhost` and
  the gateway `172.18.224.1`, with the firewall enabled. This is why the real
  Core Hub (`:8000` on Windows) is not yet reachable from the bridge, and why
  `mock_hub.py` runs inside WSL2.

### <samp>06 — STATUS</samp>

- [x] WSL2 + ROS Noetic + irob-saf/dVRK workspace built (45/45 + 8/8 packages)
- [x] ROS 1 bridge written and running; `/vrtelemetry/hmd_pose` publishes at
      ≈72 Hz from the mock
- [x] OpenXR → ROS conversion verified against hand-derived REP-103 values
      (`verify_conversion.py`, 5/5 poses, position and quaternion)
- [x] Unity project with a minimal rosbridge client; cube driven live through
      mock → bridge → rosbridge → Unity (`docs/p24_unity_cube.png`)
- [x] ROS → Unity **position** conversion verified: all four distinct poses
      land on their expected Unity coordinates
- [ ] ROS → Unity **rotation** conversion not yet empirically verified — the
      yaw test pose sits at the origin, so position alone can't distinguish it
- [ ] Real VRTelemetry telemetry — blocked on WSL2 → Windows networking
- [ ] XR viewing (XR Interaction Toolkit + OpenXR against SteamVR)
- [ ] Robot hand model (dVRK PSM xacro vs simple 6-DOF hand) and Gazebo/MoveIt

### <samp>07 — RELATED</samp>

- Course: [Advanced ROS Course materials](https://abc-irobotics.github.io/advanced_ros_course_materials_hu/)
- Framework: [ABC-iRobotics/irob-saf](https://github.com/ABC-iRobotics/irob-saf)

<br />

<p align="center">
  <a href="https://github.com/Deatron01"><img src="https://raw.githubusercontent.com/Deatron01/Deatron01/main/assets/icon.png" width="56" alt="Dea" /></a><br />
  <sub><i>Little chaos in a quiet mind.</i></sub><br />
  <sub><samp>MORE WORK AT <a href="https://github.com/Deatron01">GITHUB.COM/DEATRON01</a></samp></sub>
</p>
