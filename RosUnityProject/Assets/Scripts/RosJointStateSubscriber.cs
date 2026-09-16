using System.Collections.Generic;
using Unity.Robotics.UrdfImporter;
using UnityEngine;

namespace VrRobotBridge
{
    /// <summary>
    /// Drives the imported PSM1 URDF model's ArticulationBody joints from a
    /// sensor_msgs/JointState topic published through rosbridge (task P4.3).
    ///
    /// Chain: dvrk_console_json (PSM1 KIN_SIMULATED)
    ///          -> joint_state_publisher / robot_state_publisher
    ///          -> rosbridge_suite :9090
    ///          -> this component
    ///
    /// Unlike RosPoseSubscriber (one Transform), this drives many joints at
    /// once: on enable it walks RobotRoot's hierarchy exactly once, indexing
    /// every Unity.Robotics.UrdfImporter.UrdfJoint by its jointName field --
    /// confirmed live (2026-09-16) to equal the URDF's <joint name="..."> for
    /// every actuated joint (e.g. "outer_yaw", "outer_pitch", "jaw", ...) --
    /// and on each incoming message looks up each published joint by name in
    /// that map, so no assumption about GameObject naming is needed.
    ///
    /// Mimic joints: the URDF's outer_pitch_1..5 and jaw_mimic_1/2 are not
    /// independently actuated in the URDF (they carry a &lt;mimic&gt; tag), but
    /// dVRK's own joint_state_publisher already resolves them into real,
    /// independent values before publishing -- verified live against
    /// /PSM1/joint_states on 2026-09-16 (all 14 names appear with distinct
    /// values, not just the 7 "primary" joints). So this component does no
    /// mimic/multiplier math of its own: every name in the message maps
    /// straight onto one ArticulationBody.
    ///
    /// Kinematic playback, not a physics simulation: the URDF importer leaves
    /// every joint's drive at stiffness=0/damping=0/forceLimit=0 (there's no
    /// <dynamics>/effort data in this URDF to seed them from), and the base
    /// link isn't anchored -- so left alone, the whole chain free-falls under
    /// gravity the instant Play starts (observed live 2026-09-16: every
    /// jointPosition drifted to ~0 regardless of the ROS-reported angle). This
    /// component's job is to faithfully mirror dVRK's ground-truth joint
    /// values, not to simulate the arm's dynamics, so on enable it disables
    /// gravity on every body in the chain and anchors the root (immovable),
    /// and every Update() writes each joint's ArticulationBody.jointPosition
    /// directly rather than nudging an unconfigured drive toward a target --
    /// this guarantees the rendered pose always equals the latest ROS sample,
    /// with no lag, sag, or dependency on drive tuning. The xDrive.target is
    /// still set alongside it (harmless, and keeps the Inspector's drive
    /// fields consistent) in case stiffness/damping are configured later.
    ///
    /// Units: ROS/REP-103 publishes radians for revolute/continuous joints and
    /// metres for prismatic joints -- exactly the units ArticulationBody's
    /// native jointPosition uses internally, so no conversion is needed there.
    /// xDrive.target is the one place Unity uses degrees for angular drives,
    /// so only that field is converted with Mathf.Rad2Deg; the one prismatic
    /// joint (outer_insertion) is passed straight through in both places.
    /// </summary>
    public class RosJointStateSubscriber : MonoBehaviour
    {
        [Header("Connection")]
        public string RosBridgeUrl = "ws://localhost:9090";
        public string Topic = "/PSM1/joint_states";

        [Header("Target")]
        [Tooltip("Root of the imported URDF robot (e.g. the dvrk_psm GameObject). " +
                 "Leave empty to use this GameObject.")]
        public Transform RobotRoot;

        [Tooltip("Keep updating while the window is unfocused, same rationale as " +
                 "RosPoseSubscriber: the operator is rarely looking at this Editor window.")]
        public bool RunInBackground = true;

        [Header("Status (read-only)")]
        public bool Connected;
        public long MessagesReceived;
        public long UpdatesApplied;
        public int JointsMapped;
        public string LastError = "";

        private RosJointStateClient _client;
        private readonly Dictionary<string, ArticulationBody> _jointMap =
            new Dictionary<string, ArticulationBody>();
        private readonly Dictionary<string, bool> _jointIsLinear =
            new Dictionary<string, bool>();

        private void OnEnable()
        {
            if (RunInBackground) Application.runInBackground = true;

            Transform root = RobotRoot != null ? RobotRoot : transform;
            BuildJointMap(root);
            ConfigureForKinematicPlayback(root);

            _client = new RosJointStateClient(RosBridgeUrl, Topic);
            _client.Start();
            Debug.Log($"[RosJointStateSubscriber] connecting to {RosBridgeUrl} topic {Topic}, " +
                      $"{_jointMap.Count} joints mapped under {root.name}");
        }

        private void OnDisable()
        {
            _client?.Stop();
            _client = null;
            Connected = false;
        }

        private void BuildJointMap(Transform root)
        {
            _jointMap.Clear();
            _jointIsLinear.Clear();

            var urdfJoints = root.GetComponentsInChildren<UrdfJoint>(true);
            foreach (var uj in urdfJoints)
            {
                var ab = uj.GetComponent<ArticulationBody>();
                if (ab == null) continue;
                if (ab.jointType == ArticulationJointType.FixedJoint) continue;
                if (string.IsNullOrEmpty(uj.jointName)) continue;

                _jointMap[uj.jointName] = ab;
                _jointIsLinear[uj.jointName] = ab.jointType == ArticulationJointType.PrismaticJoint;
            }
            JointsMapped = _jointMap.Count;
        }

        /// <summary>
        /// See the class doc comment: this display mirrors ROS ground truth
        /// rather than simulating dynamics, so gravity is off everywhere and
        /// the base is anchored to stop the whole chain drifting/falling.
        /// </summary>
        private void ConfigureForKinematicPlayback(Transform root)
        {
            var bodies = root.GetComponentsInChildren<ArticulationBody>(true);
            foreach (var ab in bodies)
            {
                ab.useGravity = false;
                if (ab.isRoot) ab.immovable = true;
            }
        }

        private void Update()
        {
            if (_client == null) return;

            Connected = _client.Connected;
            MessagesReceived = _client.ReceivedCount;
            LastError = _client.LastError;

            // Drain the queue and keep only the newest sample, same latency
            // rationale as RosPoseSubscriber (ROS side can outpace Unity's frame rate).
            bool got = false;
            RosJointStateClient.JointStateSample latest = null;
            while (_client.Samples.TryDequeue(out var sample))
            {
                latest = sample;
                got = true;
            }
            if (!got || latest == null) return;

            int n = Mathf.Min(latest.Names.Length, latest.Positions.Length);
            for (int i = 0; i < n; i++)
            {
                string name = latest.Names[i];
                if (!_jointMap.TryGetValue(name, out var ab)) continue;

                float valueNative = (float)latest.Positions[i]; // radians or metres, matches ArticulationBody's own units.
                ab.jointPosition = new ArticulationReducedSpace(valueNative);

                var drive = ab.xDrive;
                drive.target = _jointIsLinear[name] ? valueNative : valueNative * Mathf.Rad2Deg;
                ab.xDrive = drive;
            }
            UpdatesApplied++;
        }
    }
}
