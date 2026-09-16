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
    /// Minimal rosbridge_suite v2 protocol client (subscribe only) for
    /// sensor_msgs/JointState, used to drive the imported PSM1 URDF model's
    /// ArticulationBody joints (task P4.3).
    ///
    /// Sibling of RosBridgeClient rather than a generalization of it: each
    /// client class here owns exactly one ROS message type end to end
    /// (connect, subscribe, parse), so adding a new topic never risks the
    /// PoseStamped path that's already verified working. See RosBridgeClient's
    /// own doc comment for the rationale (hand-written vs. ROS#) and the
    /// threading model (background Task + ConcurrentQueue; nothing here
    /// touches the Unity API, exactly like RosBridgeClient).
    /// </summary>
    public class RosJointStateClient
    {
        public readonly ConcurrentQueue<JointStateSample> Samples = new ConcurrentQueue<JointStateSample>();

        public volatile bool Connected;
        public volatile string LastError = "";
        public long ReceivedCount;

        private readonly string _url;
        private readonly string _topic;
        private CancellationTokenSource _cts;
        private Task _worker;

        public RosJointStateClient(string url, string topic)
        {
            _url = url;
            _topic = topic;
        }

        public void Start()
        {
            Stop();
            _cts = new CancellationTokenSource();
            _worker = Task.Run(() => RunAsync(_cts.Token));
        }

        /// <summary>Must be called from OnDisable/OnDestroy -- see RosBridgeClient.Stop().</summary>
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

                    // queue_length 1: only the newest joint configuration matters.
                    string subscribe =
                        "{\"op\":\"subscribe\"," +
                        "\"topic\":\"" + _topic + "\"," +
                        "\"type\":\"sensor_msgs/JointState\"," +
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
            // JointState for a 14-DOF arm is a few hundred bytes -- 32KB is
            // generous headroom, matching RosBridgeClient's sizing philosophy.
            var buffer = new byte[32 * 1024];
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
            // JsonUtility ignores fields it doesn't know about (header,
            // velocity, effort simply fall away), exactly as in RosBridgeClient.
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
            if (envelope.msg.name == null || envelope.msg.position == null) return;

            Samples.Enqueue(new JointStateSample
            {
                Names = envelope.msg.name,
                Positions = envelope.msg.position,
            });
            Interlocked.Increment(ref ReceivedCount);
        }

        public class JointStateSample
        {
            public string[] Names;
            public double[] Positions;
        }

        [Serializable] private class PublishEnvelope
        {
            public string op;
            public string topic;
            public JointStateMsg msg;
        }

        [Serializable] private class JointStateMsg
        {
            public string[] name;
            public double[] position;
        }
    }
}
