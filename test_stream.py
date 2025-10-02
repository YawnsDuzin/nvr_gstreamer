#!/usr/bin/env python3
"""
Test script for RTSP streaming
Simple test to verify GStreamer pipeline and RTSP connection
"""

import sys
import time
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from streaming.pipeline_manager import PipelineManager
from streaming.camera_stream import CameraStream, CameraConfig
from loguru import logger


def test_direct_pipeline(rtsp_url: str, use_hardware: bool = False):
    """
    Test direct GStreamer pipeline

    Args:
        rtsp_url: RTSP stream URL
        use_hardware: Use hardware acceleration
    """
    logger.info("Testing direct GStreamer pipeline...")
    logger.info(f"URL: {rtsp_url}")
    logger.info(f"Hardware acceleration: {use_hardware}")

    # Create pipeline manager
    pipeline = PipelineManager(rtsp_url)

    # Create and start pipeline
    if pipeline.create_pipeline(use_hardware_decode=use_hardware):
        logger.success("Pipeline created successfully")

        if pipeline.start():
            logger.success("Pipeline started successfully")
            logger.info("Streaming... Press Ctrl+C to stop")

            try:
                # Keep running
                while True:
                    state = pipeline.get_pipeline_state()
                    logger.debug(f"Pipeline state: {state}")
                    time.sleep(5)
            except KeyboardInterrupt:
                logger.info("Stopping stream...")

        else:
            logger.error("Failed to start pipeline")
    else:
        logger.error("Failed to create pipeline")

    # Clean up
    pipeline.stop()
    logger.info("Test completed")


def test_camera_stream(rtsp_url: str, camera_name: str = "Test Camera", use_hardware: bool = False):
    """
    Test camera stream handler

    Args:
        rtsp_url: RTSP stream URL
        camera_name: Camera name
        use_hardware: Use hardware acceleration
    """
    logger.info("Testing camera stream handler...")

    # Create camera configuration
    config = CameraConfig(
        camera_id="test_cam",
        name=camera_name,
        rtsp_url=rtsp_url,
        use_hardware_decode=use_hardware,
        reconnect_attempts=3,
        reconnect_delay=5
    )

    # Create camera stream
    stream = CameraStream(config)

    # Connect to stream
    if stream.connect():
        logger.success("Connected to camera stream")
        logger.info(f"Stream stats: {stream.get_stats()}")

        try:
            # Monitor stream
            logger.info("Monitoring stream... Press Ctrl+C to stop")
            while True:
                if stream.check_stream_health():
                    logger.debug("Stream is healthy")
                else:
                    logger.warning("Stream health check failed")
                    # Try to reconnect
                    if not stream.reconnect():
                        logger.error("Failed to reconnect")
                        break

                # Print stats
                stats = stream.get_stats()
                logger.info(f"Status: {stats['status']}, Frames: {stats['frames_received']}")

                time.sleep(5)

        except KeyboardInterrupt:
            logger.info("Stopping stream...")

    else:
        logger.error("Failed to connect to camera stream")

    # Disconnect
    stream.disconnect()
    logger.info("Test completed")


def test_frame_capture(rtsp_url: str, use_hardware: bool = False):
    """
    Test frame capture from stream

    Args:
        rtsp_url: RTSP stream URL
        use_hardware: Use hardware acceleration
    """
    logger.info("Testing frame capture...")

    frame_count = 0

    def on_frame(buffer, width, height):
        """Frame callback"""
        nonlocal frame_count
        frame_count += 1
        if frame_count % 30 == 0:  # Log every 30 frames
            logger.info(f"Captured frame #{frame_count}: {width}x{height}")

    # Create pipeline with frame callback
    pipeline = PipelineManager(rtsp_url, on_frame_callback=on_frame)

    if pipeline.create_pipeline_with_appsink(use_hardware_decode=use_hardware):
        logger.success("Pipeline with appsink created")

        if pipeline.start():
            logger.success("Pipeline started")
            logger.info("Capturing frames... Press Ctrl+C to stop")

            try:
                while True:
                    time.sleep(1)
                    logger.info(f"Total frames captured: {frame_count}")

            except KeyboardInterrupt:
                logger.info("Stopping capture...")

        else:
            logger.error("Failed to start pipeline")
    else:
        logger.error("Failed to create pipeline with appsink")

    pipeline.stop()
    logger.info(f"Test completed. Total frames captured: {frame_count}")


def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test RTSP streaming")
    parser.add_argument("url", help="RTSP stream URL")
    parser.add_argument("--mode", choices=["direct", "stream", "capture"], default="direct",
                        help="Test mode: direct pipeline, camera stream, or frame capture")
    parser.add_argument("--hardware", action="store_true",
                        help="Use hardware acceleration")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--name", default="Test Camera",
                        help="Camera name for stream mode")

    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    logger.remove()
    logger.add(sys.stdout, level=log_level, colorize=True)

    logger.info("=" * 50)
    logger.info("PyNVR RTSP Stream Test")
    logger.info("=" * 50)

    # Check GStreamer
    try:
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst
        Gst.init(None)
        logger.success("GStreamer initialized")
    except Exception as e:
        logger.error(f"Failed to initialize GStreamer: {e}")
        sys.exit(1)

    # Run test based on mode
    if args.mode == "direct":
        test_direct_pipeline(args.url, args.hardware)
    elif args.mode == "stream":
        test_camera_stream(args.url, args.name, args.hardware)
    elif args.mode == "capture":
        test_frame_capture(args.url, args.hardware)


if __name__ == "__main__":
    main()