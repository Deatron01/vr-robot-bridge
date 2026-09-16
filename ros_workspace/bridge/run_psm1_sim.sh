#!/bin/bash
# Bring up the irob-saf / dVRK PSM1 kinematic simulator and rosbridge, then
# enable+home the arm so it starts publishing real poses on /PSM1/measured_cp.
#
# This is "the irob robot simulator" the course provides (see
# https://github.com/ABC-iRobotics/irob-saf and the course's da Vinci module):
# a kinematics-only simulation of a single PSM arm via cisst-saw's
# KIN_SIMULATED console mode -- no Gazebo needed. It also starts
# robot_state_publisher + joint_state_publisher (full TF tree + joint_states,
# useful later for a full URDF-driven Unity visualisation, task P4.2) and
# opens an RViz window on this side as a sanity check independent of Unity.
#
# Usage: run inside the WSL2 Ubuntu-20.04 distro (has ROS + the catkin_ws):
#   bash run_psm1_sim.sh
#
# Idempotent: safe to re-run; kills any previous console/rosbridge first.
#
# Unity side: point a RosPoseSubscriber (RosBridgeUrl=ws://localhost:9090,
# Topic=/PSM1/measured_cp) at this -- geometry_msgs/PoseStamped, so the
# existing component (no new C# needed) drives a GameObject from the robot's
# live end-effector pose, exactly like it does for /vrtelemetry/hmd_pose.
set -uo pipefail

source /opt/ros/noetic/setup.bash
source ~/catkin_ws/devel/setup.bash
source ~/catkin_ws/devel/cisstvars.sh 2>/dev/null || true

echo "--- stopping any previous console/rosbridge ---"
pkill -f '[d]vrk_console_json' 2>/dev/null
pkill -f '[r]osbridge_websocket' 2>/dev/null
sleep 1

echo "--- launching PSM1 KIN_SIMULATED (console + state publishers + rviz) ---"
setsid nohup roslaunch dvrk_robot dvrk_arm_rviz.launch arm:=PSM1 \
  > ~/dvrk_psm1.log 2>&1 < /dev/null &
disown

echo "--- launching rosbridge_websocket on :9090 ---"
setsid nohup roslaunch rosbridge_server rosbridge_websocket.launch \
  > ~/rosbridge.log 2>&1 < /dev/null &
disown

echo "--- waiting for the console to come up ---"
sleep 12

echo "--- enabling + homing PSM1 ---"
rostopic pub /PSM1/state_command crtk_msgs/StringStamped "{string: enable}" -1
sleep 2
rostopic pub /PSM1/state_command crtk_msgs/StringStamped "{string: home}" -1
sleep 6

echo "--- operating_state ---"
timeout 3 rostopic echo -n1 /PSM1/operating_state
echo "--- measured_cp (should now be publishing real values) ---"
timeout 3 rostopic echo -n1 /PSM1/measured_cp
echo "--- done: rosbridge at ws://localhost:9090, arm's live pose on /PSM1/measured_cp ---"
