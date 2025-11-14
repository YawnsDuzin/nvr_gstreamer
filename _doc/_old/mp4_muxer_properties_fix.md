# MP4 muxer-properties 설정 오류 수정

## 문제 개요

`file_format: "mp4"` 설정 시 splitmuxsink의 muxer-properties 설정에서 TypeError 발생

### 오류 메시지
```
TypeError: could not convert 'fragment-duration=1000,streamable=true' to type 'GstStructure' when setting property 'GstSplitMuxSink.muxer-properties'
```

### 발생 환경
- GStreamer 1.18.4 (Raspberry Pi 4)
- GStreamer 1.26.7 (Windows)
- 모든 GStreamer 버전에서 동일하게 발생

## 원인 분석

### 문제 코드 (이전)

```python
# camera/gst_pipeline.py:826
if self.file_format == 'mp4':
    # ❌ 문자열을 GstStructure 타입 속성에 할당 시도
    self.splitmuxsink.set_property("muxer-properties", "fragment-duration=1000,streamable=true")
```

### 문제 원인

`muxer-properties`는 **GstStructure** 타입을 요구하지만, 문자열을 직접 할당하려고 시도함

```python
# GStreamer 타입 체크
>>> type(splitmuxsink.get_property('muxer-properties'))
<class 'gi.repository.Gst.Structure'>
```

## 해결 방법

### Gst.Structure.new_from_string() 사용

GstStructure 객체를 생성하여 설정해야 함

```python
# camera/gst_pipeline.py:827-832
if self.file_format == 'mp4':
    # ✅ GstStructure 객체로 생성
    muxer_props = Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=true")
    if muxer_props:
        self.splitmuxsink.set_property("muxer-properties", muxer_props)
        logger.debug("[RECORDING DEBUG] MP4 muxer properties set: fragment-duration=1000ms, streamable=true")
    else:
        logger.warning("[RECORDING DEBUG] Failed to create muxer-properties structure, using defaults")
```

### GstStructure 문법

```python
# 기본 형식
Gst.Structure.new_from_string("structure_name,field1=value1,field2=value2")

# mp4mux 속성 예시
Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=true")
```

#### 구조 설명
- **structure_name**: "properties" (필수)
- **fragment-duration**: Fragment 기간 (밀리초)
  - MP4 파일을 여러 fragment로 분할
  - 값이 작을수록 파일 손상 시 복구 가능성 증가
  - 권장값: 1000ms (1초)
- **streamable**: true/false
  - true: 스트리밍 가능한 MP4 생성 (moov atom을 앞에 배치)
  - false: 일반 MP4 (moov atom이 파일 끝에 위치)

## 수정 내용

### 파일: camera/gst_pipeline.py

#### 변경 전 (Line 823-826)
```python
# muxer 속성 설정 (mp4의 경우 fragment 설정)
if self.file_format == 'mp4':
    # mp4mux 속성 설정을 위한 문자열
    self.splitmuxsink.set_property("muxer-properties", "fragment-duration=1000,streamable=true")
```

#### 변경 후 (Line 823-832)
```python
# muxer 속성 설정 (mp4의 경우 fragment 설정)
if self.file_format == 'mp4':
    # mp4mux 속성 설정: GstStructure 객체로 생성
    # fragment-duration: 밀리초 단위, streamable: true로 설정하여 스트리밍 가능한 MP4 생성
    muxer_props = Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=true")
    if muxer_props:
        self.splitmuxsink.set_property("muxer-properties", muxer_props)
        logger.debug("[RECORDING DEBUG] MP4 muxer properties set: fragment-duration=1000ms, streamable=true")
    else:
        logger.warning("[RECORDING DEBUG] Failed to create muxer-properties structure, using defaults")
```

## mp4mux 속성 상세

### fragment-duration (int, 밀리초)
- **기본값**: 0 (fragment 미사용)
- **권장값**: 1000 (1초)
- **효과**:
  - MP4 파일을 시간 기반으로 fragment로 분할
  - 녹화 중 오류 발생 시 마지막 fragment까지 복구 가능
  - 값이 작을수록 복구 가능성 증가, 파일 크기 약간 증가

### streamable (boolean)
- **기본값**: false
- **권장값**: true
- **효과**:
  - true: moov atom을 파일 앞에 배치 → HTTP 스트리밍 가능
  - false: moov atom을 파일 끝에 배치 → 파일 전체 다운로드 필요

### 기타 유용한 mp4mux 속성
```python
# 더 많은 옵션 사용 예시
muxer_props = Gst.Structure.new_from_string(
    "properties,"
    "fragment-duration=1000,"
    "streamable=true,"
    "faststart=true,"          # moov atom을 파일 앞으로 이동 (streamable과 유사)
    "presentation-time=true"   # 프레젠테이션 시간 정보 포함
)
```

## 테스트 방법

### IT_RNVR.json 설정
```json
{
  "recording": {
    "file_format": "mp4",
    "rotation_minutes": 2,
    "codec": "h264"
  }
}
```

### 예상 로그
```
DEBUG | [RECORDING DEBUG] MP4 muxer properties set: fragment-duration=1000ms, streamable=true
DEBUG | [RECORDING DEBUG] splitmuxsink configured with format-location handler
INFO  | Pipeline started for Main Camera (mode: streaming_only, recording: False)
```

### 녹화 파일 확인
```bash
# MP4 파일 구조 확인
ffprobe -v error -show_format -show_streams recording.mp4

# moov atom 위치 확인 (streamable=true인 경우 ftyp 다음에 위치)
ffprobe -v error -show_entries format_tags=major_brand,minor_version,compatible_brands recording.mp4
```

## 관련 GStreamer 요소

### mp4mux
- **역할**: H.264/H.265 스트림을 MP4 컨테이너로 muxing
- **지원 코덱**: H.264, H.265, AAC
- **특징**: fragment 지원, faststart 지원

### splitmuxsink
- **역할**: 자동 파일 분할 (시간 또는 크기 기반)
- **내부 muxer**: mp4mux, matroskamux, avimux 등 선택 가능
- **muxer-factory**: 사용할 muxer 지정
- **muxer-properties**: 내부 muxer에 전달할 속성 (GstStructure)

### 파이프라인 구조
```
tee → record_queue → recording_valve → h264parse → splitmuxsink
                                                      ↓
                                                    mp4mux (internal)
                                                      ↓
                                                    file
```

## 다른 포맷과의 비교

### MKV (Matroska) - 기본 포맷
```python
# muxer-properties 설정 불필요
self.splitmuxsink.set_property("muxer-factory", "matroskamux")
```

### AVI
```python
# muxer-properties 설정 불필요
self.splitmuxsink.set_property("muxer-factory", "avimux")
```

### MP4 (수정 후)
```python
self.splitmuxsink.set_property("muxer-factory", "mp4mux")
muxer_props = Gst.Structure.new_from_string("properties,fragment-duration=1000,streamable=true")
self.splitmuxsink.set_property("muxer-properties", muxer_props)
```

## 주의 사항

1. **GstStructure 생성 실패 시**: 기본값 사용 (fragment 미사용)
2. **fragment-duration=0**: Fragment 기능 비활성화
3. **streamable=false**: 파일 전체를 다운로드해야 재생 가능
4. **MP4 vs MKV**:
   - MP4: 범용성 높음, fragment 지원
   - MKV: 더 유연한 메타데이터, 복구 기능 우수

## 참고 자료

### GStreamer 공식 문서
- [splitmuxsink](https://gstreamer.freedesktop.org/documentation/multifile/splitmuxsink.html)
- [mp4mux](https://gstreamer.freedesktop.org/documentation/isomp4/mp4mux.html)
- [GstStructure](https://gstreamer.freedesktop.org/documentation/gstreamer/gststructure.html)

### 관련 이슈
- GStreamer muxer-properties 타입 오류는 일반적인 실수
- 문자열 대신 GstStructure 객체를 사용해야 함

---

**작성일**: 2025-11-05
**수정 파일**: camera/gst_pipeline.py
**영향 범위**: MP4 포맷 녹화 기능