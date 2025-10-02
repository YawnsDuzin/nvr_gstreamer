#!/usr/bin/env python3
"""
비디오 싱크 테스트 스크립트
라즈베리파이에서 사용 가능한 비디오 싱크를 테스트합니다
"""

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

# GStreamer 초기화
Gst.init(None)


def check_available_sinks():
    """사용 가능한 비디오 싱크 확인"""
    print("사용 가능한 비디오 싱크 확인 중...")
    print("-" * 50)

    sinks = [
        "ximagesink",
        "xvimagesink",
        "glimagesink",
        "gtkglsink",
        "gtksink",
        "fbdevsink",
        "eglglessink",
        "waylandsink",
        "autovideosink"
    ] 

    available = []
    for sink_name in sinks:
        element = Gst.ElementFactory.make(sink_name, None)
        if element is not None:
            print(f"✓ {sink_name} - 사용 가능")
            available.append(sink_name)

            # 윈도우 핸들 설정 메서드 확인
            if hasattr(element, 'set_window_handle'):
                print(f"  └─ set_window_handle() 지원")
            if hasattr(element, 'set_xwindow_id'):
                print(f"  └─ set_xwindow_id() 지원")
            if hasattr(element, 'set_property'):
                try:
                    # window-handle 속성 확인
                    props = element.list_properties()
                    for prop in props:
                        if 'window' in prop.name.lower() or 'handle' in prop.name.lower():
                            print(f"  └─ 속성: {prop.name}")
                except:
                    pass
        else:
            print(f"✗ {sink_name} - 사용 불가")

    print("\n" + "=" * 50)
    print(f"총 {len(available)}개 비디오 싱크 사용 가능")

    if available:
        print("\n추천 우선순위:")
        recommended = []

        # 우선순위 결정
        if "xvimagesink" in available:
            recommended.append("xvimagesink")
        if "ximagesink" in available:
            recommended.append("ximagesink")
        if "glimagesink" in available:
            recommended.append("glimagesink")
        if "autovideosink" in available:
            recommended.append("autovideosink")

        for i, sink in enumerate(recommended[:3], 1):
            print(f"{i}. {sink}")

    return available


def test_window_embedding(sink_name):
    """윈도우 임베딩 테스트"""
    print(f"\n{sink_name} 윈도우 임베딩 테스트...")

    try:
        # 테스트 파이프라인 생성
        pipeline_str = f"videotestsrc ! {sink_name} name=sink"
        pipeline = Gst.parse_launch(pipeline_str)

        # 비디오 싱크 가져오기
        sink = pipeline.get_by_name("sink")

        if sink:
            # 테스트 윈도우 ID (임의의 값)
            test_window_id = 12345

            success = False
            methods_tried = []

            # 방법 1: set_window_handle
            if hasattr(sink, 'set_window_handle'):
                try:
                    sink.set_window_handle(test_window_id)
                    methods_tried.append("set_window_handle")
                    success = True
                except Exception as e:
                    methods_tried.append(f"set_window_handle (실패: {e})")

            # 방법 2: set_xwindow_id
            if hasattr(sink, 'set_xwindow_id'):
                try:
                    sink.set_xwindow_id(test_window_id)
                    methods_tried.append("set_xwindow_id")
                    success = True
                except Exception as e:
                    methods_tried.append(f"set_xwindow_id (실패: {e})")

            # 방법 3: set_property
            try:
                sink.set_property("window-handle", test_window_id)
                methods_tried.append("set_property('window-handle')")
                success = True
            except Exception as e:
                pass

            print(f"테스트 결과:")
            for method in methods_tried:
                print(f"  - {method}")

            if success:
                print(f"  ✓ {sink_name}는 윈도우 임베딩 가능")
            else:
                print(f"  ✗ {sink_name}는 윈도우 임베딩 불가능")

        pipeline.set_state(Gst.State.NULL)

    except Exception as e:
        print(f"테스트 실패: {e}")


def main():
    print("=" * 50)
    print("라즈베리파이 비디오 싱크 테스트")
    print("=" * 50)

    # 사용 가능한 싱크 확인
    available = check_available_sinks()

    # 주요 싱크 임베딩 테스트
    print("\n" + "=" * 50)
    print("윈도우 임베딩 테스트")
    print("=" * 50)

    test_sinks = ["ximagesink", "xvimagesink", "glimagesink"]
    for sink in test_sinks:
        if sink in available:
            test_window_embedding(sink)


if __name__ == "__main__":
    main()