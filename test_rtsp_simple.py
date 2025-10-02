#!/usr/bin/env python3
"""
Simple RTSP test with various pipeline configurations
Tests different decoder options to find what works
"""

import sys
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

# Initialize GStreamer
Gst.init(None)


def test_pipeline(pipeline_str, description):
    """Test a specific pipeline configuration"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Pipeline: {pipeline_str}")
    print(f"{'='*60}")

    try:
        pipeline = Gst.parse_launch(pipeline_str)

        bus = pipeline.get_bus()
        bus.add_signal_watch()

        loop = GLib.MainLoop()

        def on_message(bus, msg):
            t = msg.type
            if t == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                print(f"❌ ERROR: {err}")
                print(f"   Debug: {debug}")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif t == Gst.MessageType.EOS:
                print("End of stream")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif t == Gst.MessageType.STATE_CHANGED:
                if msg.src == pipeline:
                    old_state, new_state, pending = msg.parse_state_changed()
                    print(f"✓ State changed: {old_state.value_nick} -> {new_state.value_nick}")
                    if new_state == Gst.State.PLAYING:
                        print("✅ SUCCESS: Pipeline is playing!")

        bus.connect("message", on_message)

        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("❌ Failed to start pipeline")
            return False

        print("Starting pipeline...")

        # Run for 5 seconds
        GLib.timeout_add_seconds(5, lambda: loop.quit())

        try:
            loop.run()
        except KeyboardInterrupt:
            pass

        pipeline.set_state(Gst.State.NULL)
        print("Pipeline stopped")
        return True

    except Exception as e:
        print(f"❌ Exception: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_rtsp_simple.py <RTSP_URL>")
        sys.exit(1)

    rtsp_url = sys.argv[1]
    print(f"Testing RTSP URL: {rtsp_url}")

    # Different pipeline configurations to test
    pipelines = [
        # 1. Simplest - just display without decoding
        (
            f"rtspsrc location={rtsp_url} latency=200 protocols=tcp ! "
            "decodebin ! autovideosink",
            "Decodebin (automatic decoder selection)"
        ),

        # 2. Software decoder with TCP
        (
            f"rtspsrc location={rtsp_url} latency=200 protocols=tcp ! "
            "rtph264depay ! h264parse ! avdec_h264 ! "
            "videoconvert ! autovideosink",
            "Software decoder (avdec_h264) with TCP"
        ),

        # 3. Software decoder with UDP
        (
            f"rtspsrc location={rtsp_url} latency=200 protocols=udp ! "
            "rtph264depay ! h264parse ! avdec_h264 ! "
            "videoconvert ! autovideosink",
            "Software decoder (avdec_h264) with UDP"
        ),

        # 4. V4L2 hardware decoder
        (
            f"rtspsrc location={rtsp_url} latency=200 protocols=tcp ! "
            "rtph264depay ! h264parse ! v4l2h264dec ! "
            "videoconvert ! autovideosink",
            "Hardware decoder (v4l2h264dec)"
        ),

        # 5. Playbin (highest level, automatic everything)
        (
            f"playbin uri={rtsp_url}",
            "Playbin (fully automatic)"
        ),

        # 6. With queue for buffering
        (
            f"rtspsrc location={rtsp_url} latency=200 protocols=tcp ! "
            "queue ! rtph264depay ! h264parse ! avdec_h264 ! "
            "videoconvert ! autovideosink",
            "Software decoder with queue"
        ),
    ]

    successful = []
    failed = []

    for pipeline_str, description in pipelines:
        if test_pipeline(pipeline_str, description):
            successful.append(description)
        else:
            failed.append(description)

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"\n✅ Successful pipelines ({len(successful)}):")
    for desc in successful:
        print(f"  - {desc}")

    print(f"\n❌ Failed pipelines ({len(failed)}):")
    for desc in failed:
        print(f"  - {desc}")

    if successful:
        print(f"\n🎉 Recommended: Use '{successful[0]}'")


if __name__ == "__main__":
    main()