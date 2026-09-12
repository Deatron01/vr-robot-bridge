# VR-Telemetry → ROS ↔ Unity Bridge

Streams live VR telemetry (joint positions, hand pose, controller input) to a
ROS-based robot-hand simulator and visualises the robot hand in a Unity XR
application, for 1:1 simulation between the user's VR motions and a
Gazebo/MoveIt robot hand.

See `docs/implementation_plan.md` for the full plan (goals, open questions,
proposed layout, verification plan, timeline).

## Status

Environment setup in progress:
- [x] GitHub repo created
- [ ] WSL2 Ubuntu 20.04 installed
- [ ] ROS Noetic installed
- [ ] irob-saf (iROB Surgical Automation Framework) workspace built
- [ ] ROS workspace scaffolded (`ros_workspace/`)
- [ ] Unity XR project scaffolded (`UnityProject/`)

## Related

- Course: [Advanced ROS Course materials](https://abc-irobotics.github.io/advanced_ros_course_materials_hu/)
- Framework: [ABC-iRobotics/irob-saf](https://github.com/ABC-iRobotics/irob-saf)
