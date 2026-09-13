using System;
using System.Collections.Concurrent;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace VrRobotBridge
{
    /// <summary>
    /// Minimal rosbridge_suite v2 protocol client (subscribe only).
    ///
    /// Why hand-written instead of ROS#: the Unity side needs exactly one
    /// message type today (geometry_msgs/PoseStamped over a websocket), and
    /// rosbridge's wire format is plain JSON. ClientWebSocket ships with the
    /// runtime, so this adds no dependency and nothing to break on a Unity
    /// upgrade. The transport is deliberately isolated in this one class: if the
    /// project later wants ROS# (for its message library, TF or URDF support),
    /// only this file is replaced -- RosPoseSubscriber and RosUnityCoordinates
    /// stay as they are.
    ///
    /// Threading: the receive loop runs on a background Task, because Unity's
    /// main thread must not block on network I/O. Received poses are handed over
    /// through a ConcurrentQueue and applied by the MonoBehaviour in Update().
    /// Nothing here touches the Unity API.
    /// </summary>
    public class RosBridgeClient
    {
        public readonly ConcurrentQueue<RosPose> Poses = new ConcurrentQueue<RosPose>();

        public volatile bool Connected;
        public volatile string LastError = "";
        public long ReceivedCount;

        private readonly string _url;
        private readonly string _topic;
        private readonly string _messageType;
        private CancellationTokenSource _cts;
        private Task _worker;

        public RosBridgeClient(string url, string topic, string messageType)
        {
            _url = url;
            _topic = topic;
            _messageType = messageType;
        }

        public void Start()
        {
            Stop();
            _cts = new CancellationTokenSource();
            _worker = Task.Run(() => RunAsync(_cts.Token));
        }

        /// <summary>
        /// Must be called from OnDisable/OnDestroy. A background Task that keeps
        /// running after play mode exits survives into the next play session in
        /// the Editor and is a classic source of phantom connections.
        /// </summary>
        public void Stop()
        {
            try { _cts?.Cancel(); } catch { /* already disposed */ }
            _cts = null;
            _worker = null;
            Connected = false;
        }

        private async Task RunAsync(CancellationToken token)
        {
            var backoff = TimeSpan.FromSeconds(1);

            while (!token.IsCancellationRequested)
            {
                ClientWebSocket socket = null;
                try
                {
                    socket = new ClientWebSocket();
                    await socket.ConnectAsync(new Uri(_url), token);
                    Connected = true;
                    LastError = "";
                    backoff = TimeSpan.FromSeconds(1);

                    // queue_length 1: we only ever care about the newest pose, so
                    // let rosbridge drop backlog rather than build latency.
                    string subscribe =
                        "{\"op\":\"subscribe\"," +
                        "\"topic\":\"" + _topic + "\"," +
                        "\"type\":\"" + _messageType + "\"," +
                        "\"queue_length\":1}";
                    await SendAsync(socket, subscribe, token);

                    await ReceiveLoopAsync(socket, token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    LastError = ex.Message;
                }
                finally
                {
                    Connected = false;
                    socket?.Dispose();
                }

                if (token.IsCancellationRequested) break;

                try { await Task.Delay(backoff, token); }
                catch (OperationCanceledException) { break; }

                // Same escalating backoff the Python bridge uses, capped at 30s.
                double next = Math.Min(30.0, backoff.TotalSeconds * 2.0);
                backoff = TimeSpan.FromSeconds(next);
            }

            Connected = false;
        }

        private static async Task SendAsync(ClientWebSocket socket, string json, CancellationToken token)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(json);
            await socket.SendAsync(new ArraySegment<byte>(bytes),
                WebSocketMessageType.Text, true, token);
        }

        private async Task ReceiveLoopAsync(ClientWebSocket socket, CancellationToken token)
        {
            var buffer = new byte[16 * 1024];
            var builder = new StringBuilder();

            while (!token.IsCancellationRequested && socket.State == WebSocketState.Open)
            {
                builder.Length = 0;
                WebSocketReceiveResult result;
                do
                {
                    result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                    if (result.MessageType == WebSocketMessageType.Close) return;
                    builder.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                } while (!result.EndOfMessage);

                HandleMessage(builder.ToString());
            }
        }

        private void HandleMessage(string json)
        {
            // JsonUtility ignores fields it doesn't know about, so the header and
            // any rosbridge bookkeeping simply fall away.
            PublishEnvelope envelope;
            try
            {
                envelope = JsonUtility.FromJson<PublishEnvelope>(json);
            }
            catch (Exception ex)
            {
                LastError = "parse: " + ex.Message;
                return;
            }

            if (envelope == null || envelope.op != "publish" || envelope.msg == null) return;
            if (envelope.msg.pose == null) return;

            var p = envelope.msg.pose.position;
            var o = envelope.msg.pose.orientation;
            if (p == null || o == null) return;

            Poses.Enqueue(new RosPose
            {
                Px = p.x, Py = p.y, Pz = p.z,
                Qx = o.x, Qy = o.y, Qz = o.z, Qw = o.w,
            });
            Interlocked.Increment(ref ReceivedCount);
        }

        public struct RosPose
        {
            public double Px, Py, Pz;
            public double Qx, Qy, Qz, Qw;
        }

        [Serializable] private class PublishEnvelope
        {
            public string op;
            public string topic;
            public PoseStampedMsg msg;
        }

        [Serializable] private class PoseStampedMsg { public PoseMsg pose; }
        [Serializable] private class PoseMsg { public Vec3Msg position; public QuatMsg orientation; }
        [Serializable] private class Vec3Msg { public double x, y, z; }
        [Serializable] private class QuatMsg { public double x, y, z, w; }
    }
}
