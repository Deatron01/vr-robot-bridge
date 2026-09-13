# ros_workspace/bridge/bridge_node_ros1.py
"""ROS 1 (Noetic) bridge: Core Hub telemetry -> geometry_msgs/PoseStamped -> Unity.

ROS 1 port of ``vrtelemetry-plugin-ros-unity-bridge``'s ``bridge_node.py``,
per ``ros1-noetic-wsl2-bridge-port-todo.md`` section 3 (rospy substitutions).
Subscribes to the Core Hub's Event Router (``/ws/hub/telemetry``), converts
the HMD's live OpenXR pose to ROS's REP-103 convention (``coordinate_convert.py``,
copied unchanged from the ROS 2 plugin -- pure math, no ROS imports), and
publishes ``geometry_msgs/PoseStamped`` on a normal ROS 1 topic. From there,
``rosbridge_suite`` (``roslaunch rosbridge_server rosbridge_websocket.launch``)
exposes that topic over its own WebSocket port (default 9090) for the Unity
side -- ROS# (or any other rosbridge-JSON client) subscribes to it exactly
like any other ROS 1 topic. This node does not talk to Unity or
rosbridge_suite directly; it talks to ROS 1's normal pub/sub, and
rosbridge_suite is what makes that reachable from Unity.

This node is a subscriber to the Core Hub, never a dependency of it: if ROS 1
is not installed/sourced, rosbridge_suite is not running, or this process
crashes, telemetry recording on the Windows side is completely unaffected.

## Requires ROS 1 Noetic sourced in this shell

Run this from inside WSL2, in the same shell environment ``~/catkin_ws`` is
built in, i.e. after:

    source /opt/ros/noetic/setup.bash
    source ~/catkin_ws/devel/setup.bash

`rospy` and `geometry_msgs` come from that install, not pip --
``requirements.txt`` here covers only the WebSocket client (``websockets``).

## Running

    roslaunch rosbridge_server rosbridge_websocket.launch   # once, separately
    export HUB_WS_URL=ws://localhost:8000/ws/hub/telemetry  # Windows host, via WSL2 localhost forwarding
    python3 bridge_node_ros1.py

    # Inspect the published topic from another WSL2 terminal:
    rostopic echo /vrtelemetry/hmd_pose

If ``ws://localhost:8000/...`` doesn't connect from inside WSL2, fall back to
the WSL2 host IP (see the parent TODO doc, section 4) for ``HUB_WS_URL``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any

import rospy
import websockets
from coordinate_convert import openxr_pose_to_ros
from geometry_msgs.msg import PoseStamped

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s ros-unity-bridge %(levelname)s %(message)s"
)
logger = logging.getLogger("ros_unity_bridge")


class HubToRosBridge:
    """Owns the ROS 1 publisher. `publish_hmd_pose` is called from the
    WebSocket thread below, not from rospy's own spin thread --
    `rospy.Publisher.publish()` is documented thread-safe, so no additional
    locking is needed here."""

    def __init__(self, frame_id: str, topic: str) -> None:
        self._publisher = rospy.Publisher(topic, PoseStamped, queue_size=10)
        self._frame_id = frame_id
        rospy.loginfo(f"Publishing HMD pose on '{topic}' (frame_id='{frame_id}').")

    def publish_hmd_pose(self, frame: dict[str, Any]) -> None:
        # Same validity rule the Core Hub applies before it records a frame
        # at all -- a stub/zeroed pose from a session that isn't tracking
        # yet must not drive the simulated arm.
        if not frame.get("hmd_tracking_valid", 0):
            return

        msg = PoseStamped()
        msg.header.stamp = rospy.Time.now()
        msg.header.frame_id = self._frame_id

        position, orientation = openxr_pose_to_ros(
            pos=(frame["hmd_pos_x"], frame["hmd_pos_y"], frame["hmd_pos_z"]),
            rot_xyzw=(
                frame["hmd_rot_x"],
                frame["hmd_rot_y"],
                frame["hmd_rot_z"],
                frame["hmd_rot_w"],
            ),
        )
        msg.pose.position.x, msg.pose.position.y, msg.pose.position.z = position
        (
            msg.pose.orientation.x,
            msg.pose.orientation.y,
            msg.pose.orientation.z,
            msg.pose.orientation.w,
        ) = orientation

        self._publisher.publish(msg)


class HubSubscriber:
    """The WebSocket half, on its own asyncio loop and thread -- rospy's own
    spin (`rospy.spin()`) owns the main thread, and the two must not block
    each other. Unchanged from the ROS 2 version: this half is pure asyncio
    + websockets, no ROS API in it at all."""

    def __init__(self, hub_ws_url: str, token: str | None, on_frame) -> None:
        self._hub_ws_url = hub_ws_url
        self._token = token
        self._on_frame = on_frame

    def _connect_url(self) -> str:
        url = self._hub_ws_url
        params = []
        if self._token:
            params.append(f"token={self._token}")
        params.append("plugin_id=ros-unity-bridge")
        sep = "&" if "?" in url else "?"
        return url + sep + "&".join(params)

    async def run(self) -> None:
        url = self._connect_url()
        backoff = 1.0
        while True:
            try:
                logger.info(f"Connecting to Core Hub at {self._hub_ws_url}...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                    logger.info("Connected. Streaming HMD pose to ROS 1.")
                    backoff = 1.0
                    async for raw in ws:
                        message = json.loads(raw)
                        if message.get("type") == "telemetry_frame":
                            self._on_frame(message["frame"])
            except (websockets.WebSocketException, OSError) as exc:
                logger.warning(f"Hub connection lost ({exc}); reconnecting in {backoff:.0f}s.")
                await asyncio.sleep(backoff)
                backoff = min(30.0, backoff * 2)


def main() -> None:
    hub_ws_url = os.environ.get("HUB_WS_URL", "ws://localhost:8000/ws/hub/telemetry")
    token = os.environ.get("HUB_PLUGIN_TOKEN")
    topic = os.environ.get("ROS_POSE_TOPIC", "/vrtelemetry/hmd_pose")
    frame_id = os.environ.get("ROS_FRAME_ID", "vr_play_area")

    rospy.init_node("vrtelemetry_hub_bridge")
    bridge = HubToRosBridge(frame_id=frame_id, topic=topic)

    subscriber = HubSubscriber(hub_ws_url, token, on_frame=bridge.publish_hmd_pose)
    ws_loop = asyncio.new_event_loop()
    ws_thread = threading.Thread(
        target=lambda: ws_loop.run_until_complete(subscriber.run()),
        daemon=True,
        name="hub-subscriber",
    )
    ws_thread.start()

    rospy.spin()


if __name__ == "__main__":
    main()
