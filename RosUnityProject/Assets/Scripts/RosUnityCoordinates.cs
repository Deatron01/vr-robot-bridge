using UnityEngine;

namespace VrRobotBridge
{
    /// <summary>
    /// ROS (REP-103) -> Unity coordinate conversion.
    ///
    /// This is the SECOND conversion in the chain. The first happens in the ROS 1
    /// bridge (ros_workspace/bridge/coordinate_convert.py), which turns the
    /// headset's OpenXR pose into REP-103. This class finishes the job.
    ///
    ///   REP-103 : right-handed, X forward, Y left,  Z up
    ///   Unity   : LEFT-handed,  X right,   Y up,    Z forward
    ///
    /// Position is a straight relabel of axes:
    ///     unity.x = -ros.y     (ROS +Y is left; Unity +X is right)
    ///     unity.y =  ros.z     (up stays up)
    ///     unity.z =  ros.x     (forward stays forward)
    ///
    /// Rotation is NOT the same permutation. Handedness flips between the two
    /// frames, and a quaternion's vector part is a pseudo-vector: it picks up an
    /// extra overall sign change under a handedness flip. Applying the position
    /// permutation and then negating the vector part gives
    ///     unity.q = ( ros.q.y, -ros.q.z, -ros.q.x, ros.q.w )
    /// with the scalar part w unchanged, as it is under any pure change of axes.
    ///
    /// Cross-check against the verified table in ros_workspace/bridge
    /// (verify_conversion.py), composing both conversions end to end:
    ///
    ///   OpenXR +1m X (right)    -> ROS ( 0,-1, 0) -> Unity (+1, 0, 0)  right
    ///   OpenXR +1m Y (up)       -> ROS ( 0, 0, 1) -> Unity ( 0,+1, 0)  up
    ///   OpenXR +1m Z (backward) -> ROS (-1, 0, 0) -> Unity ( 0, 0,-1)  backward
    ///
    /// The composition reduces to "negate Z", which is exactly the textbook
    /// OpenXR (right-handed, -Z forward) -> Unity (left-handed, +Z forward)
    /// mapping. Two independently derived conversions composing into the known
    /// one is the cross-check that neither carries a sign error.
    /// </summary>
    public static class RosUnityCoordinates
    {
        public static Vector3 RosToUnityPosition(double x, double y, double z)
        {
            return new Vector3((float)(-y), (float)z, (float)x);
        }

        public static Quaternion RosToUnityRotation(double x, double y, double z, double w)
        {
            return new Quaternion((float)y, (float)(-z), (float)(-x), (float)w);
        }
    }
}
