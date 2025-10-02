#!/usr/bin/env python3
"""
Simple RTSP test script without external dependencies
Works with minimal Python installation
"""

import sys
import time

# GStreamer imports
try:
    import gi
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib
    print("✓ GStreamer loaded successfully")
except ImportError as e:
    print(f"✗ Failed to import GStreamer: {e}")
    print("Install with: sudo apt-get install python3-gst-1.0")
    sys.exit(1)

# Initialize GStreamer
Gst.init(None)


def test_rtsp_stream(rtsp_url):
    """
    Simple RTSP stream test

    Args:
        rtsp_url: RTSP stream URL
    """
    print(f"\nTesting RTSP stream: {rtsp_url}")
    print("-" * 50)

    # Create simple pipeline string
    pipeline_str = (
        f"rtspsrc location={rtsp_url} latency=200 ! "
        "rtph264depay ! h264parse ! "
        "avdec_h264 ! "
        "videoconvert ! "
        "autovideosink sync=false"
    )

    print(f"Pipeline: {pipeline_str}\n")

    try:
        # Create pipeline
        pipeline = Gst.parse_launch(pipeline_str)
        print("✓ Pipeline created")

        # Create bus and connect message handler
        bus = pipeline.get_bus()
        bus.add_signal_watch()

        def on_message(bus, message):
            t = message.type
            if t == Gst.MessageType.EOS:
                print("End-of-stream")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print(f"Error: {err}, {debug}")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif t == Gst.MessageType.STATE_CHANGED:
                if message.src == pipeline:
                    old_state, new_state, pending = message.parse_state_changed()
                    print(f"State changed: {old_state.value_nick} -> {new_state.value_nick}")

        bus.connect("message", on_message)

        # Start pipeline
        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("✗ Failed to start pipeline")
            return

        print("✓ Pipeline started")
        print("\nStreaming... Press Ctrl+C to stop\n")

        # Run main loop
        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            print("\n\nStopping stream...")

        # Clean up
        pipeline.set_state(Gst.State.NULL)
        print("✓ Pipeline stopped")

    except GLib.Error as e:
        print(f"✗ Pipeline error: {e}")
        return


def test_with_hardware_acceleration(rtsp_url):
    """
    Test with Raspberry Pi hardware acceleration

    Args:
        rtsp_url: RTSP stream URL
    """
    print(f"\nTesting with hardware acceleration: {rtsp_url}")
    print("-" * 50)

    # Try OMX decoder for Raspberry Pi
    pipeline_str = (
        f"rtspsrc location={rtsp_url} latency=200 ! "
        "rtph264depay ! h264parse ! "
        "omxh264dec ! "
        "videoconvert ! "
        "autovideosink sync=false"
    )

    print(f"Hardware pipeline: {pipeline_str}\n")

    try:
        pipeline = Gst.parse_launch(pipeline_str)
        print("✓ Hardware pipeline created")

        bus = pipeline.get_bus()
        bus.add_signal_watch()

        def on_message(bus, message):
            t = message.type
            if t == Gst.MessageType.ERROR:
                err, debug = message.parse_error()
                print(f"Error: {err}")
                pipeline.set_state(Gst.State.NULL)
                loop.quit()
            elif t == Gst.MessageType.STATE_CHANGED:
                if message.src == pipeline:
                    old_state, new_state, pending = message.parse_state_changed()
                    print(f"State: {old_state.value_nick} -> {new_state.value_nick}")

        bus.connect("message", on_message)

        ret = pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("✗ Hardware acceleration failed, falling back to software")
            return False

        print("✓ Hardware acceleration active")
        print("\nStreaming... Press Ctrl+C to stop\n")

        loop = GLib.MainLoop()
        try:
            loop.run()
        except KeyboardInterrupt:
            print("\n\nStopping stream...")

        pipeline.set_state(Gst.State.NULL)
        return True

    except GLib.Error:
        print("✗ Hardware acceleration not available")
        return False


def check_gstreamer_plugins():
    """Check available GStreamer plugins"""
    print("\nChecking GStreamer plugins...")
    print("-" * 50)

    required_plugins = [
        "rtspsrc",
        "rtph264depay",
        "h264parse",
        "avdec_h264",
        "videoconvert",
        "autovideosink"
    ]

    # Check for hardware decoders
    hw_decoders = ["omxh264dec", "v4l2h264dec"]

    registry = Gst.Registry.get()

    for plugin in required_plugins:
        if registry.find_plugin(plugin) or registry.find_feature(plugin, Gst.ElementFactory.__gtype__):
            print(f"✓ {plugin} available")
        else:
            print(f"✗ {plugin} NOT available")

    print("\nHardware decoders:")
    for decoder in hw_decoders:
        if registry.find_feature(decoder, Gst.ElementFactory.__gtype__):
            print(f"✓ {decoder} available")
        else:
            print(f"✗ {decoder} NOT available")


def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 simple_test.py <RTSP_URL>")
        print("Example: python3 simple_test.py rtsp://192.168.1.100:554/stream")
        sys.exit(1)

    rtsp_url = sys.argv[1]

    print("=" * 50)
    print("PyNVR Simple RTSP Test")
    print("=" * 50)

    # Check plugins first
    check_gstreamer_plugins()

    # Try hardware acceleration first on Raspberry Pi
    import platform
    if platform.machine().startswith('arm'):
        print("\n🔧 Detected ARM platform (likely Raspberry Pi)")
        if not test_with_hardware_acceleration(rtsp_url):
            print("\n🔄 Falling back to software decoding...")
            test_rtsp_stream(rtsp_url)
    else:
        # Use software decoding on non-ARM platforms
        test_rtsp_stream(rtsp_url)

    print("\n✓ Test completed")


if __name__ == "__main__":
    main()