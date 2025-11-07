#!/usr/bin/env python3
"""
녹화 중지 시 스트리밍 영향 테스트
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

import time
from loguru import logger
from core.models import Camera
from camera.gst_pipeline import GstPipeline

# 로그 설정
logger.remove()
logger.add(sys.stdout, level="DEBUG")

def main():
    """테스트 메인 함수"""
    Gst.init(None)

    # 테스트 카메라 설정
    rtsp_url = "rtsp://admin:trolleycam1~@192.168.0.131:554/Streaming/Channels/102"
    camera_id = "test_cam"
    camera_name = "Test Camera"

    # 파이프라인 생성
    logger.info("Creating pipeline...")
    pipeline = GstPipeline(
        rtsp_url=rtsp_url,
        camera_id=camera_id,
        camera_name=camera_name,
        window_handle=None
    )

    # 파이프라인 생성 (실제 GStreamer 엘리먼트 생성)
    logger.info("Building GStreamer pipeline...")
    if not pipeline.create():
        logger.error("Failed to create GStreamer pipeline")
        return False

    # 파이프라인 시작 (스트리밍만)
    logger.info("Starting pipeline (streaming only)...")
    if not pipeline.start():
        logger.error("Failed to start pipeline")
        return False

    # 5초 대기
    logger.info("Streaming for 5 seconds...")
    time.sleep(5)

    # 녹화 시작
    logger.info("Starting recording...")
    if not pipeline.start_recording():
        logger.error("Failed to start recording")
        return False

    # 10초 녹화
    logger.info("Recording for 10 seconds...")
    time.sleep(10)

    # 녹화 중지
    logger.info("Stopping recording...")
    pipeline.stop_recording()

    # 5초 더 스트리밍 (문제가 있으면 여기서 화면이 검게 변함)
    logger.info("Continuing streaming for 5 seconds after stopping recording...")
    time.sleep(5)

    # 파이프라인 상태 확인
    state = pipeline.get_status()
    logger.info(f"Pipeline status after stopping recording: {state}")

    if state.get("streaming_mode") == "STREAMING_ONLY":
        logger.success("✓ Streaming is still active after stopping recording!")
    else:
        logger.error("✗ Streaming stopped when recording stopped!")

    # 파이프라인 정지
    logger.info("Stopping pipeline...")
    pipeline.stop()

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)