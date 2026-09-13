using UnityEngine;

namespace VrRobotBridge
{
    /// <summary>
    /// Drives this GameObject's transform from a geometry_msgs/PoseStamped topic
    /// published through rosbridge (task P2.3).
    ///
    /// Chain: VRTelemetry Core Hub (or mock_hub.py)
    ///          -> bridge_node_ros1.py  [OpenXR -> ROS/REP-103]
    ///          -> rosbridge_suite :9090
    ///          -> this component      [ROS -> Unity]
    ///
    /// Default URL is ws://localhost:9090 because rosbridge runs inside WSL2 and
    /// WSL's localhostForwarding covers the Windows -> WSL2 direction. Verified
    /// working 2026-09-13. (The reverse direction does NOT work, which is why
    /// the mock publisher runs inside WSL2 rather than on Windows.)
    /// </summary>
    public class RosPoseSubscriber : MonoBehaviour
    {
        [Header("Connection")]
        public string RosBridgeUrl = "ws://localhost:9090";
        public string Topic = "/vrtelemetry/hmd_pose";

        [Header("Behaviour")]
        [Tooltip("Apply incoming poses to this transform. Leave empty to use this GameObject.")]
        public Transform Target;

        [Tooltip("Apply position as well as rotation.")]
        public bool ApplyPosition = true;

        [Tooltip("Apply rotation as well as position.")]
        public bool ApplyRotation = true;

        [Tooltip("Keep updating while the window is unfocused. Required here: the operator is " +
                 "wearing a headset or driving VRTelemetry, so this view is almost never the " +
                 "focused window. Without it Unity throttles Update() to near zero and the " +
                 "visualisation freezes on the last pose.")]
        public bool RunInBackground = true;

        [Header("Status (read-only)")]
        [Tooltip("Note: these are refreshed in Update(); reading them through tooling that " +
                 "inspects serialized fields can show a stale snapshot.")]
        public bool Connected;
        public long MessagesReceived;
        public long PosesApplied;
        public string LastError = "";

        private RosBridgeClient _client;

        private void OnEnable()
        {
            if (RunInBackground) Application.runInBackground = true;
            if (Target == null) Target = transform;
            _client = new RosBridgeClient(RosBridgeUrl, Topic, "geometry_msgs/PoseStamped");
            _client.Start();
            Debug.Log($"[RosPoseSubscriber] connecting to {RosBridgeUrl} topic {Topic}");
        }

        private void OnDisable()
        {
            _client?.Stop();
            _client = null;
            Connected = false;
        }

        private void Update()
        {
            if (_client == null) return;

            Connected = _client.Connected;
            MessagesReceived = _client.ReceivedCount;
            LastError = _client.LastError;

            // Drain the queue and keep only the newest pose. Rendering an older
            // frame would add latency for no benefit -- and the ROS side runs at
            // ~72 Hz, which can exceed the Unity frame rate.
            bool got = false;
            RosBridgeClient.RosPose latest = default;
            while (_client.Poses.TryDequeue(out var pose))
            {
                latest = pose;
                got = true;
            }
            if (!got) return;

            if (ApplyPosition)
            {
                Target.localPosition =
                    RosUnityCoordinates.RosToUnityPosition(latest.Px, latest.Py, latest.Pz);
            }
            if (ApplyRotation)
            {
                Target.localRotation =
                    RosUnityCoordinates.RosToUnityRotation(latest.Qx, latest.Qy, latest.Qz, latest.Qw);
            }
            PosesApplied++;
        }
    }
}
