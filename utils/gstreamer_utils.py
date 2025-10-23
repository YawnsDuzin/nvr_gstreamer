"""
GStreamer 유틸리티 함수들
GStreamer 파이프라인에서 공통으로 사용되는 기능들
"""

import platform
from typing import Optional
from loguru import logger

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# GStreamer 초기화
Gst.init(None)


def get_video_sink() -> str:
    """
    플랫폼에 맞는 최적의 비디오 싱크 선택

    Returns:
        비디오 싱크 엘리먼트 이름
    """
    registry = Gst.Registry.get()
    system = platform.system()

    # 플랫폼별 비디오 싱크 우선순위
    if system == "Windows":
        sinks = [
            "d3d11videosink",     # Direct3D 11 (Windows 10+)
            "d3dvideosink",       # Direct3D 9 (older Windows)
            "autovideosink",      # 자동 선택
            "glimagesink",        # OpenGL (fallback)
        ]
    elif system == "Darwin":  # macOS
        sinks = [
            "osxvideosink",       # macOS 네이티브
            "autovideosink",      # 자동 선택
            "glimagesink",        # OpenGL
        ]
    else:  # Linux 및 기타
        sinks = [
            "glimagesink",        # OpenGL (라즈베리파이에서 효율적)
            "xvimagesink",        # X11 with XVideo extension
            "ximagesink",         # X11 기본
            "waylandsink",        # Wayland
            "autovideosink",      # 자동 선택
        ]

    # 사용 가능한 싱크 찾기
    for sink in sinks:
        if registry.find_feature(sink, Gst.ElementFactory.__gtype__):
            logger.info(f"Using video sink: {sink} (platform: {system})")
            return sink

    # 최종 폴백
    logger.warning(f"No platform-specific video sink found for {system}, using fakesink")
    return "fakesink"


def get_available_h264_decoder(prefer_hardware: bool = True, decoder_preference: list = None) -> str:
    """
    사용 가능한 최적의 H264 디코더 선택

    Args:
        prefer_hardware: 하드웨어 디코더 우선 여부
        decoder_preference: 선호 디코더 목록 (우선순위 순)

    Returns:
        디코더 엘리먼트 이름
    """
    registry = Gst.Registry.get()

    # 설정에서 제공된 우선순위가 있으면 사용
    if decoder_preference:
        decoders = decoder_preference
        logger.debug(f"Using custom decoder preference: {decoders}")
    elif prefer_hardware:
        # 하드웨어 디코더 우선 (라즈베리파이 최적화)
        decoders = [
            "v4l2h264dec",     # V4L2 hardware decoder (newer Raspberry Pi)
            "omxh264dec",      # OpenMAX hardware decoder (older Raspberry Pi)
            "avdec_h264",      # Software decoder (libav) - fallback
            "openh264dec",     # OpenH264 software decoder
            "h264parse"        # Last resort - just parse without decode
        ]
    else:
        # 소프트웨어 디코더 우선 (호환성 우선)
        decoders = [
            "avdec_h264",      # Software decoder (libav) - most compatible
            "openh264dec",     # OpenH264 software decoder
            "v4l2h264dec",     # V4L2 hardware decoder (newer Raspberry Pi)
            "omxh264dec",      # OpenMAX hardware decoder (older Raspberry Pi)
            "h264parse"        # Last resort - just parse without decode
        ]

    for decoder in decoders:
        if registry.find_feature(decoder, Gst.ElementFactory.__gtype__):
            logger.info(f"Using H264 decoder: {decoder}")
            return decoder

    logger.warning("No H264 decoder found, using h264parse only")
    return "h264parse"


def create_video_sink_with_properties(sink_name: str, sync: bool = True,
                                     force_aspect_ratio: bool = True) -> Optional[Gst.Element]:
    """
    속성이 설정된 비디오 싱크 엘리먼트 생성

    Args:
        sink_name: 비디오 싱크 이름
        sync: 동기화 여부
        force_aspect_ratio: 종횡비 유지 여부

    Returns:
        생성된 비디오 싱크 엘리먼트 또는 None
    """
    try:
        video_sink = Gst.ElementFactory.make(sink_name, "videosink")

        if not video_sink:
            logger.error(f"Failed to create video sink: {sink_name}")
            return None

        # 공통 속성 설정
        video_sink.set_property("sync", sync)

        # async 속성이 있는 경우 설정
        try:
            video_sink.set_property("async", not sync)
        except:
            pass  # 속성이 없으면 무시

        # force-aspect-ratio 속성이 있는 경우 설정
        if force_aspect_ratio:
            try:
                video_sink.set_property("force-aspect-ratio", True)
            except:
                pass  # 속성이 없으면 무시

        # Windows D3D 싱크들의 추가 속성
        if sink_name in ["d3dvideosink", "d3d11videosink"]:
            try:
                # 전체 화면 모드 비활성화
                video_sink.set_property("fullscreen", False)
                # 렌더링 모드 설정 (있는 경우)
                video_sink.set_property("render-mode", 0)  # 0 = normal
            except:
                pass  # 속성이 없으면 무시

        return video_sink

    except Exception as e:
        logger.error(f"Error creating video sink {sink_name}: {e}")
        return None


def is_hardware_decoder(decoder_name: str) -> bool:
    """
    하드웨어 디코더인지 확인

    Args:
        decoder_name: 디코더 이름

    Returns:
        하드웨어 디코더 여부
    """
    hardware_decoders = [
        "v4l2h264dec",     # V4L2 hardware decoder
        "omxh264dec",      # OpenMAX hardware decoder
        "nvh264dec",       # NVIDIA hardware decoder
        "vaapih264dec",    # VA-API hardware decoder
        "vtdec",           # VideoToolbox (macOS)
        "d3d11h264dec",    # Direct3D 11 decoder (Windows)
    ]
    return decoder_name in hardware_decoders


def get_platform_info() -> dict:
    """
    플랫폼 정보 반환

    Returns:
        플랫폼 정보 딕셔너리
    """
    import os

    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "is_raspberry_pi": False,
        "is_windows": platform.system() == "Windows",
        "is_linux": platform.system() == "Linux",
        "is_macos": platform.system() == "Darwin",
    }

    # 라즈베리파이 감지
    if info["is_linux"]:
        try:
            with open("/proc/device-tree/model", "r") as f:
                model = f.read()
                if "Raspberry Pi" in model:
                    info["is_raspberry_pi"] = True
                    info["pi_model"] = model.strip()
        except:
            pass

    return info