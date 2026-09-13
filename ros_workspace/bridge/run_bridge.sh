#!/usr/bin/env bash
# Source the ROS 1 environment, then run the Hub->ROS bridge node.
#
# Why this exists (task P0.6): WSL2 non-interactive shells -- which is what
# `wsl -d Ubuntu-20.04 bash -lc ...` gives you, and therefore what any
# automation uses -- do NOT source ~/.bashrc, so the ROS setup files it
# sources are never run and `import rospy` fails. Verified 2026-09-13:
# ROS_DISTRO comes back empty in such a shell. Start the node through this
# script rather than calling bridge_node_ros1.py directly.

source /opt/ros/noetic/setup.bash
if [ -f "$HOME/catkin_ws/devel/setup.bash" ]; then
    source "$HOME/catkin_ws/devel/setup.bash"
fi

cd "$(dirname "$0")" || exit 1

if ! timeout 2 rostopic list >/dev/null 2>&1; then
    echo "run_bridge.sh: WARNING - no ROS master reachable at ${ROS_MASTER_URI:-<unset>}." >&2
    echo "run_bridge.sh:           start one first, e.g." >&2
    echo "run_bridge.sh:             roslaunch rosbridge_server rosbridge_websocket.launch" >&2
fi

: "${HUB_WS_URL:=ws://127.0.0.1:8000/ws/hub/telemetry}"
export HUB_WS_URL
echo "run_bridge.sh: HUB_WS_URL=$HUB_WS_URL"

exec python3 bridge_node_ros1.py "$@"
