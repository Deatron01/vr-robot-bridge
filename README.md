# VR-Telemetry → ROS ↔ Unity Bridge

Streams live VR telemetry (joint positions, hand pose, controller input) to a
ROS-based robot-hand simulator and visualises the robot hand in a Unity XR
application, for 1:1 simulation between the user's VR motions and a
Gazebo/MoveIt robot hand.

See `docs/implementation_plan.md` for the full plan (goals, open questions,
proposed layout, verification plan, timeline).

## Environment

irob-saf (ROS Noetic + dVRK) needs Linux; there is no supported native-Windows
build. This project runs it inside **WSL2, distro `Ubuntu-20.04`** on this PC
(imported manually since Ubuntu 20.04 was dropped from the WSL online catalog —
see `docs/environment_setup.md`).

- WSL2 distro: `Ubuntu-20.04` (Ubuntu 20.04.6 LTS), default user `nipit`
- ROS Noetic (`ros-noetic-desktop-full`) installed and sourced by default
- Catkin workspace: `~/catkin_ws` inside the distro, containing:
  - `cisst-saw`, `crtk`, `dvrk` (dVRK 2.2.1, via jhu-saw vcs import)
  - `ethzasl_icp_mapping` (+ libnabo, libpointmatcher built from source)
  - `irob-saf` (this framework — all 8 packages build clean)
  - OE-daVinci config files under `sawIntuitiveResearchKit/share/`

To work in it: `wsl -d Ubuntu-20.04`, then `~/catkin_ws` is the workspace
(`devel/setup.bash` and `devel/cisstvars.sh` are sourced automatically by
`.bashrc`).

## Status

- [x] GitHub repo created
- [x] WSL2 Ubuntu 20.04 installed
- [x] ROS Noetic installed
- [x] irob-saf (iROB Surgical Automation Framework) workspace built
- [ ] ROS workspace scaffolded (`ros_workspace/`) — the VR-telemetry bridge itself
- [ ] Unity XR project scaffolded (`UnityProject/`)

## Related

- Course: [Advanced ROS Course materials](https://abc-irobotics.github.io/advanced_ros_course_materials_hu/)
- Framework: [ABC-iRobotics/irob-saf](https://github.com/ABC-iRobotics/irob-saf)
