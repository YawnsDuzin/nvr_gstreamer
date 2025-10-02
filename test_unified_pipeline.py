"""
통합 파이프라인 테스트
스트리밍과 녹화를 하나의 파이프라인에서 처리하는 테스트
"""

import sys
import time
from loguru import logger
from streaming.unified_pipeline import UnifiedPipeline, PipelineMode

# 로거 설정
logger.remove()
logger.add(sys.stdout, level="DEBUG", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


def test_streaming_only():
    """스트리밍만 테스트"""
    logger.info("=== Testing Streaming Only Mode ===")

    # RTSP URL (테스트용)
    rtsp_url = "rtsp://admin:admin123@192.168.1.100:554/stream1"

    # 파이프라인 생성
    pipeline = UnifiedPipeline(
        rtsp_url=rtsp_url,
        camera_id="cam01",
        camera_name="Test Camera",
        mode=PipelineMode.STREAMING_ONLY
    )

    # 파이프라인 생성 및 시작
    if pipeline.create_pipeline():
        if pipeline.start():
            logger.success("Streaming started")

            # 30초 동안 스트리밍
            time.sleep(30)

            # 정지
            pipeline.stop()
            logger.info("Streaming stopped")
        else:
            logger.error("Failed to start pipeline")
    else:
        logger.error("Failed to create pipeline")


def test_recording_only():
    """녹화만 테스트"""
    logger.info("=== Testing Recording Only Mode ===")

    # RTSP URL
    rtsp_url = "rtsp://admin:admin123@192.168.1.100:554/stream1"

    # 파이프라인 생성
    pipeline = UnifiedPipeline(
        rtsp_url=rtsp_url,
        camera_id="cam01",
        camera_name="Test Camera",
        mode=PipelineMode.RECORDING_ONLY
    )

    # 파이프라인 생성 및 시작
    if pipeline.create_pipeline():
        if pipeline.start():
            logger.success("Pipeline started")

            # 녹화 시작
            if pipeline.start_recording():
                logger.success("Recording started")

                # 30초 동안 녹화
                time.sleep(30)

                # 녹화 정지
                pipeline.stop_recording()
                logger.info("Recording stopped")
            else:
                logger.error("Failed to start recording")

            # 파이프라인 정지
            pipeline.stop()
        else:
            logger.error("Failed to start pipeline")
    else:
        logger.error("Failed to create pipeline")


def test_both_modes():
    """스트리밍과 녹화 동시 테스트"""
    logger.info("=== Testing Both Streaming and Recording ===")

    # RTSP URL
    rtsp_url = "rtsp://admin:admin123@192.168.1.100:554/stream1"

    # 파이프라인 생성
    pipeline = UnifiedPipeline(
        rtsp_url=rtsp_url,
        camera_id="cam01",
        camera_name="Test Camera",
        mode=PipelineMode.BOTH
    )

    # 파이프라인 생성 및 시작
    if pipeline.create_pipeline():
        if pipeline.start():
            logger.success("Pipeline started with both modes")

            # 상태 확인
            status = pipeline.get_status()
            logger.info(f"Initial status: {status}")

            # 10초 동안 스트리밍만
            logger.info("Streaming only for 10 seconds...")
            time.sleep(10)

            # 녹화 시작
            if pipeline.start_recording():
                logger.success("Recording started while streaming")

                status = pipeline.get_status()
                logger.info(f"Status after recording start: {status}")

                # 20초 동안 스트리밍 + 녹화
                logger.info("Streaming and recording for 20 seconds...")
                time.sleep(20)

                # 녹화 정지
                pipeline.stop_recording()
                logger.info("Recording stopped, streaming continues")

                # 10초 더 스트리밍만
                logger.info("Streaming only for 10 more seconds...")
                time.sleep(10)

            # 파이프라인 정지
            pipeline.stop()
            logger.info("Pipeline stopped")

            # 최종 상태
            final_status = pipeline.get_status()
            logger.info(f"Final status: {final_status}")
        else:
            logger.error("Failed to start pipeline")
    else:
        logger.error("Failed to create pipeline")


def test_file_rotation():
    """파일 회전 테스트"""
    logger.info("=== Testing File Rotation ===")

    # RTSP URL
    rtsp_url = "rtsp://admin:admin123@192.168.1.100:554/stream1"

    # 파이프라인 생성 (짧은 파일 분할 시간 설정)
    pipeline = UnifiedPipeline(
        rtsp_url=rtsp_url,
        camera_id="cam01",
        camera_name="Test Camera",
        mode=PipelineMode.RECORDING_ONLY
    )

    # 파일 분할 시간을 30초로 설정 (테스트용)
    pipeline.file_duration = 30

    # 파이프라인 생성 및 시작
    if pipeline.create_pipeline():
        if pipeline.start():
            logger.success("Pipeline started")

            # 녹화 시작
            if pipeline.start_recording():
                logger.success("Recording started")

                # 70초 동안 녹화 (2번의 파일 회전 발생)
                for i in range(7):
                    time.sleep(10)
                    status = pipeline.get_status()
                    logger.info(f"Recording duration: {status.get('recording_duration', 0)} seconds")
                    logger.info(f"Current file: {status.get('current_file', 'N/A')}")

                # 녹화 정지
                pipeline.stop_recording()

            # 파이프라인 정지
            pipeline.stop()
        else:
            logger.error("Failed to start pipeline")
    else:
        logger.error("Failed to create pipeline")


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description="Test unified pipeline")
    parser.add_argument("--mode", choices=["streaming", "recording", "both", "rotation"],
                       default="both", help="Test mode")
    parser.add_argument("--rtsp", type=str,
                       default="rtsp://admin:admin123@192.168.1.100:554/stream1",
                       help="RTSP URL")

    args = parser.parse_args()

    # 테스트 모드에 따라 실행
    if args.mode == "streaming":
        test_streaming_only()
    elif args.mode == "recording":
        test_recording_only()
    elif args.mode == "both":
        test_both_modes()
    elif args.mode == "rotation":
        test_file_rotation()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()