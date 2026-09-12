# VR‑Telemetry → ROS ↔ Unity Bridge

## Goal Description

Create a semester‑level project that streams live VR telemetry (joint positions, hand pose, controller input) to a ROS‑based robot‑hand simulator and visualises the robot hand in a Unity XR application. The system will enable 1:1 simulation: the user sees their own motions in VR while the robot hand in Gazebo/MoveIt follows exactly the same commands.

## User Review Required

[!IMPORTANT]  
**Platform choice** – Decide whether to target **ROS 1 (Melodic/Noetic)** or **ROS 2 (Foxy/Humble)**. This determines which ROS‑Unity package you will use (ROS# for ROS 1, ROS‑Unity for ROS 2) and the bridge implementation language.

[!IMPORTANT]  
**Telemetry transport** – Choose how the VR telemetry will be emitted (WebSocket, UDP, TCP, or directly from Unity). The plan assumes a **UDP JSON** stream, but it can be swapped with a custom Unity‑side publisher.

[!IMPORTANT]  
**Robot‑hand model** – Provide the URDF (or SDF) of the robot hand that will be used in both Unity (via URDF‑Importer) and Gazebo. If you lack one, a simple 6‑DOF hand model must be created.

## Open Questions

- Which ROS distribution is already installed on the lab machines?  
- Does the VR telemetry SDK currently expose joint data in a format that can be directly mapped to `sensor_msgs/JointState`?
- Do you need **haptic feedback** from the simulator back into the VR controllers, or is visual synchronisation sufficient?
- Will the Unity project run on the same PC as the ROS bridge, or on a separate workstation? (Network topology affects firewall / latency considerations.)

## Proposed Changes

**Top‑level layout** (new project under the scratch workspace `C:\Users\nipit\.gemini\antigravity\scratch\vr_robot_bridge`):

---
### ROS Workspace

#### [NEW] `vr_robot_bridge/ros_workspace/`
- `src/vr_telemetry_bridge/` – Python package that receives telemetry and publishes ROS messages.
- `src/vr_telemetry_bridge/package.xml` – ROS package metadata.
- `src/vr_telemetry_bridge/setup.py` – Install script.
- `src/vr_telemetry_bridge/vr_bridge_node.py` – Main node (UDP listener → `sensor_msgs/JointState` publisher).
- `src/vr_hand_simulation/` – Gazebo/MoveIt launch files.
- `src/vr_hand_simulation/hand.urdf.xacro` – Robot hand description.
- `src/vr_hand_simulation/launch/hand_sim.launch.xml` – Launch Gazebo with the hand model and subscribe to `/vr/joint_states`.
- `launch/rosbridge_websocket.launch` – Starts `rosbridge_server` (ROS 1) or `ros2-web-bridge` (ROS 2).

---
### Unity XR Project

#### [NEW] `vr_robot_bridge/UnityProject/`
- `Assets/Scenes/VRHandScene.unity` – Main scene containing the XR rig and robot‑hand model.
- `Assets/Scripts/VRRosSubscriber.cs` – C# script using **ROS#** (ROS 1) or **ROS‑Unity** (ROS 2) to subscribe to `/vr/joint_states` and drive the hand model.
- `Assets/ROS/` – ROS# (or ROS‑Unity) prefab and configuration files.
- `Assets/Models/hand/` – Unity‑imported meshes generated from the URDF (via *Unity‑URDF‑Importer*).
- `ProjectSettings/` – XR Interaction Toolkit configuration.

---
### Documentation & Automation

#### [NEW] `vr_robot_bridge/README.md`
- Project overview, architecture diagram, and step‑by‑step build instructions.
- Dependency list (ROS, Unity version, XR SDK, Python packages).
- Quick‑start commands (`./run_bridge.sh`, `Unity.exe -projectPath ...`).

#### [NEW] `vr_robot_bridge/scripts/setup_env.ps1`
- PowerShell script that installs required Python packages, builds the ROS workspace, and launches rosbridge.

#### [NEW] `vr_robot_bridge/scripts/run_all.ps1`
- Starts: ROS bridge → ROS telemetry node → Unity editor (optional headless mode) → Gazebo.

---
### Tests

#### [NEW] `vr_robot_bridge/tests/`
- `test_bridge.py` – verifies that a synthetic UDP packet results in a correctly formed `JointState` message on the ROS topic.
- Unity integration test stub (requires Unity Test Runner) that checks the hand model receives updates.

---
## Verification Plan

### Automated Tests
- **Python bridge unit test**: `pytest tests/test_bridge.py` – inject a mock UDP packet, assert topic publication.
- **ROS topic sanity**: `rostopic hz /vr/joint_states` should report ≥ 60 Hz.
- **Unity Play‑Mode test**: Verify that `VRRosSubscriber` updates a dummy Transform.

### Manual Verification
1. **Latency measurement** – Run `rostopic echo /vr/joint_states` while moving the VR controller; use a high‑speed webcam to record the VR display and the Gazebo window, then compute frame‑to‑frame lag (< 20 ms preferred).
2. **1:1 visual check** – Observe the robot hand in Gazebo mirroring the Unity hand in real time.
3. **Optional haptic loop** – If feedback is implemented, enable controller vibration on contact events and confirm perceived sync.

### Acceptance Criteria
- Telemetry is streamed from VR to ROS at ≥ 60 Hz with ≤ 20 ms end‑to‑end latency.
- Unity visualisation accurately reflects joint angles (≤ 1° error).
- Gazebo robot hand follows the same joint commands without jitter.
- All scripts run on a single Windows machine (or with clearly documented multi‑machine networking).

---
## Timeline (10 weeks typical semester)
| Week | Milestone |
|------|-----------|
| 1‑2 | ROS workspace, rosbridge, and UDP bridge skeleton. |
| 3‑4 | Create / import robot‑hand URDF; set up Gazebo launch. |
| 5‑6 | Initialise Unity project, import XR Interaction Toolkit and ROS#/ROS‑Unity. |
| 7   | Connect Unity subscriber to ROS topic; visual test of hand movement. |
| 8   | Full integration: VR ↔ ROS ↔ Unity ↔ Gazebo. |
| 9   | Latency testing, optimisation (reduce network buffering, adjust publish rates). |
|10   | Documentation, final demo video, project report. |

---
## Risks & Mitigations
- **Network firewall** – Open port 9090 (rosbridge) and the UDP port used by the telemetry node.
- **ROS version mismatch** – Choose one version early; keep both ROS‑Unity and ROS# packages ready for switch.
- **Unity‑ROS serialization bugs** – Use the latest stable ROS# release; add sanity checks in C# (log received message length).
- **Latency spikes** – Buffer telemetry at the bridge with a small queue; drop oldest frames if the queue exceeds a threshold.

---
## Deliverables
- Source code repository (Git) with the full layout described above.
- A concise 5‑minute video demo showing the VR controller moving the robot hand in both Unity and Gazebo.
- A written report (≈ 5 pages) covering architecture, implementation details, latency results, and future extensions.

---
*End of implementation plan.*
