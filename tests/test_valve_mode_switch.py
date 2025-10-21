#!/usr/bin/env python3
"""
Valve 기반 모드 전환 테스트
런타임 중 PipelineMode 변경이 제대로 동작하는지 확인
"""

import sys
import time
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from streaming.unified_pipeline import UnifiedPipeline, PipelineMode
from loguru import logger


def test_runtime_mode_switch():
    """런타임 모드 전환 테스트"""

    # 테스트용 RTSP URL (실제 카메라 또는 테스트 스트림)
    rtsp_url = "rtsp://admin:trolleycam1~@192.168.0.131:554/Streaming/Channels/102"

    logger.info("=" * 50)
    logger.info("Valve 기반 런타임 모드 전환 테스트 시작")
    logger.info("=" * 50)

    # 파이프라인 생성 (초기 모드: STREAMING_ONLY)
    pipeline = UnifiedPipeline(
        rtsp_url=rtsp_url,
        camera_id="test_cam",
        camera_name="Test Camera",
        mode=PipelineMode.STREAMING_ONLY
    )

    # 파이프라인 생성 및 시작
    logger.info("\n1. 파이프라인 생성 (초기 모드: STREAMING_ONLY)")
    if not pipeline.create_pipeline():
        logger.error("Failed to create pipeline")
        return False

    if not pipeline.start():
        logger.error("Failed to start pipeline")
        return False

    logger.success("파이프라인 시작 완료")
    time.sleep(3)

    # 테스트 1: STREAMING_ONLY → BOTH (런타임 전환)
    logger.info("\n2. 모드 전환 테스트: STREAMING_ONLY → BOTH")
    if pipeline.set_mode(PipelineMode.BOTH):
        logger.success("모드 전환 성공: BOTH")
        status = pipeline.get_status()
        logger.info(f"현재 상태: {status}")
    else:
        logger.error("모드 전환 실패")

    time.sleep(3)

    # 테스트 2: 녹화 시작 (BOTH 모드에서)
    logger.info("\n3. 녹화 시작 (BOTH 모드)")
    if pipeline.start_recording():
        logger.success("녹화 시작 성공")
        status = pipeline.get_status()
        logger.info(f"녹화 상태: {status}")
    else:
        logger.error("녹화 시작 실패")

    time.sleep(5)

    # 테스트 3: BOTH → RECORDING_ONLY (녹화 중 모드 전환)
    logger.info("\n4. 모드 전환 테스트: BOTH → RECORDING_ONLY (녹화 유지)")
    if pipeline.set_mode(PipelineMode.RECORDING_ONLY):
        logger.success("모드 전환 성공: RECORDING_ONLY")
        logger.info("스트리밍은 중단되고 녹화만 계속됨")
        status = pipeline.get_status()
        logger.info(f"현재 상태: {status}")
    else:
        logger.error("모드 전환 실패")

    time.sleep(3)

    # 테스트 4: RECORDING_ONLY → STREAMING_ONLY (녹화 중지, 스트리밍만)
    logger.info("\n5. 녹화 중지")
    if pipeline.stop_recording():
        logger.success("녹화 중지 성공")

    logger.info("\n6. 모드 전환 테스트: RECORDING_ONLY → STREAMING_ONLY")
    if pipeline.set_mode(PipelineMode.STREAMING_ONLY):
        logger.success("모드 전환 성공: STREAMING_ONLY")
        logger.info("스트리밍만 활성화됨")
        status = pipeline.get_status()
        logger.info(f"현재 상태: {status}")
    else:
        logger.error("모드 전환 실패")

    time.sleep(3)

    # 테스트 5: 빠른 모드 전환 (스트레스 테스트)
    logger.info("\n7. 빠른 모드 전환 테스트 (스트레스)")
    modes = [PipelineMode.STREAMING_ONLY, PipelineMode.BOTH, PipelineMode.RECORDING_ONLY]
    for i in range(3):
        for mode in modes:
            logger.info(f"  전환 → {mode.value}")
            pipeline.set_mode(mode)
            time.sleep(0.5)

    logger.success("빠른 모드 전환 테스트 완료")

    # 정리
    logger.info("\n8. 파이프라인 정지")
    pipeline.stop()

    logger.success("\n✅ 모든 테스트 완료!")
    return True


def test_valve_performance():
    """Valve 성능 테스트 - 전환 시 지연 측정"""

    rtsp_url = "rtsp://admin:trolleycam1~@192.168.0.131:554/Streaming/Channels/102"

    logger.info("\n" + "=" * 50)
    logger.info("Valve 전환 성능 테스트")
    logger.info("=" * 50)

    pipeline = UnifiedPipeline(
        rtsp_url=rtsp_url,
        camera_id="perf_test",
        camera_name="Performance Test",
        mode=PipelineMode.BOTH
    )

    if not pipeline.create_pipeline() or not pipeline.start():
        logger.error("Failed to start pipeline")
        return False

    time.sleep(2)

    # 모드 전환 시간 측정
    switch_times = []

    for i in range(10):
        start_time = time.time()

        # 모드 전환
        new_mode = PipelineMode.STREAMING_ONLY if i % 2 == 0 else PipelineMode.BOTH
        pipeline.set_mode(new_mode)

        switch_time = (time.time() - start_time) * 1000  # ms
        switch_times.append(switch_time)

        logger.info(f"전환 #{i+1}: {new_mode.value} - {switch_time:.2f}ms")
        time.sleep(0.5)

    # 통계
    avg_time = sum(switch_times) / len(switch_times)
    max_time = max(switch_times)
    min_time = min(switch_times)

    logger.info("\n📊 성능 통계:")
    logger.info(f"  평균 전환 시간: {avg_time:.2f}ms")
    logger.info(f"  최대 전환 시간: {max_time:.2f}ms")
    logger.info(f"  최소 전환 시간: {min_time:.2f}ms")

    pipeline.stop()

    # 성능 기준 체크
    if avg_time < 10:  # 10ms 이하면 우수
        logger.success("✅ 우수한 전환 성능!")
    elif avg_time < 50:  # 50ms 이하면 양호
        logger.info("✓ 양호한 전환 성능")
    else:
        logger.warning("⚠ 전환 성능 개선 필요")

    return True


def main():
    parser = argparse.ArgumentParser(description="Valve 기반 모드 전환 테스트")
    parser.add_argument("--test", choices=["switch", "performance", "all"],
                       default="all", help="테스트 유형 선택")
    parser.add_argument("--rtsp", help="RTSP URL (선택사항)")
    args = parser.parse_args()

    # 로깅 설정
    logger.remove()
    logger.add(sys.stdout, level="DEBUG", colorize=True)

    try:
        if args.test in ["switch", "all"]:
            test_runtime_mode_switch()

        if args.test in ["performance", "all"]:
            test_valve_performance()

    except KeyboardInterrupt:
        logger.info("\n테스트 중단됨")
    except Exception as e:
        logger.exception(f"테스트 실패: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())