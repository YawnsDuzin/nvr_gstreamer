# NVR 시스템 제품 요구사항 정의서 (PRD)

## 1. 제품 개요

### 1.1 제품명
**PyNVR** - Python 기반 네트워크 비디오 레코더 시스템

### 1.2 제품 목적
Raspberry Pi 환경에서 운영 가능한 경량화된 NVR 시스템으로, 최대 4대의 IP 카메라에 대한 실시간 모니터링, 녹화, 재생 및 관리 기능을 제공하는 오픈소스 기반 솔루션

### 1.3 타겟 사용자
- 소규모 사업장 관리자
- 홈 보안 시스템 구축자
- DIY 보안 시스템 개발자

## 2. 기능 요구사항

### 2.1 핵심 기능

#### 2.1.1 카메라 관리
- **카메라 등록/수정/삭제**
  - RTSP URL 자동 검색 (ONVIF Discovery)
  - 수동 URL 입력 지원
  - 카메라 프로파일 관리 (메인/서브 스트림)
  - 카메라 상태 실시간 모니터링
  
- **지원 사양**
  - 최대 동시 연결: 4대
  - 지원 프로토콜: RTSP, RTMP, HTTP
  - 지원 코덱: H.264, H.265, MJPEG
  - 해상도: 최대 4K (3840x2160)
  - 프레임레이트: 최대 30fps

#### 2.1.2 실시간 모니터링
- **화면 레이아웃**
  - 1x1, 2x2, 1+3, 사용자 정의 레이아웃
  - 전체화면 모드
  - 순환 보기 (Sequence Mode)
  
- **스트림 제어**
  - 적응형 비트레이트 조정
  - 버퍼링 최적화 (1-3초)
  - 하드웨어 가속 (GPU 활용)

#### 2.1.3 녹화 기능
- **녹화 모드**
  - 연속 녹화
  - 모션 감지 녹화
  - 스케줄 녹화
  - 수동 녹화
  - 이벤트 기반 녹화 (알람 입력)
  
- **녹화 설정**
  - 코덱 설정 (H.264/H.265)
  - 품질 설정 (비트레이트, 프레임레이트)
  - Pre/Post 녹화 버퍼 (5-30초)
  - 파일 분할 단위 (5분, 10분, 30분, 1시간)

#### 2.1.4 재생 기능
- **타임라인 기반 재생**
  - 달력 뷰 검색
  - 시간축 네비게이션
  - 썸네일 프리뷰
  
- **재생 제어**
  - 배속 재생 (0.25x ~ 16x)
  - 프레임 단위 이동
  - 동기화된 멀티 채널 재생

#### 2.1.5 PTZ 제어
- **기본 제어**
  - Pan/Tilt/Zoom 제어
  - 프리셋 포지션 (최대 255개)
  - 투어/패트롤 기능
  
- **고급 기능**
  - 속도 조절
  - ONVIF 표준 지원

#### 2.1.6 이벤트 관리
- **이벤트 유형**
  - 모션 감지
  - 비디오 손실
  - 디스크 오류
  - 네트워크 단절
  - 시스템 리소스 임계값 초과
  
- **알림 방법**
  - 이메일 알림
  - 웹훅 (HTTP POST)
  - 로컬 알람 출력

#### 2.1.7 저장소 관리
- **저장 정책**
  - 자동 덮어쓰기 (순환 녹화)
  - 저장 기간 설정 (1일 ~ 365일)
  - 채널별 할당량 관리
  - 중요 녹화 보호 (Lock 기능)
  
- **저장소 유형**
  - 로컬 디스크 (SD카드, USB, HDD)
  - 네트워크 저장소 (NAS, SMB/CIFS)
  - 클라우드 저장소 (S3 호환)

#### 2.1.8 백업 및 내보내기
- **백업 옵션**
  - 예약 백업
  - 수동 백업
  - 증분 백업
  
- **내보내기 형식**
  - AVI, MP4, MKV
  - 워터마크 추가
  - 프라이버시 마스킹

### 2.2 보안 기능

#### 2.2.1 사용자 관리
- **인증 체계**
  - 로컬 사용자 관리
  
- **권한 관리**
  - 채널별 권한 설정
  - 기능별 권한 설정

#### 2.2.2 암호화  
- **저장 암호화**
  - AES-256 파일 암호화
  - 설정 파일 암호화

#### 2.2.3 감사 로그
- 사용자 활동 로깅
- 시스템 이벤트 로깅
- 접근 시도 로깅

### 2.3 통합 기능

#### 2.3.1 AI 분석 (확장 모듈)
- **객체 감지**
  - 사람/차량/동물 구분
  - 라인 크로싱 감지
  - 영역 침입 감지
  - 배회 감지
  
- **얼굴 인식**
  - 얼굴 감지 및 캡처
  - 블랙리스트/화이트리스트
  - 출입 통계

#### 2.3.2 외부 시스템 연동
- **홈 오토메이션**
  - MQTT 브로커 연동
  
- **알람 시스템**
  - GPIO 입출력
  - 시리얼 통신 (RS-485)

## 3. 비기능 요구사항

### 3.1 성능 요구사항
- **하드웨어 요구사항**
  ```
  최소 사양:
  - Raspberry Pi 4 (4GB RAM)
  - 32GB SD 카드
  - 1TB USB 3.0 HDD
  
  권장 사양:
  - Raspberry Pi 5 (8GB RAM)
  - 64GB SD 카드
  - 2TB USB 3.0 SSD
  ```

- **성능 목표**
  - CPU 사용률: 평균 < 50%, 피크 < 80%
  - 메모리 사용률: < 50% (4GB 기준)
  - 네트워크 대역폭: < 100Mbps (4채널 FHD)
  - 시작 시간: < 30초
  - 카메라 연결 시간: < 5초

### 3.2 신뢰성 요구사항
- **가용성**
  - 24/7 무중단 운영
  - 자동 재시작 (Watchdog)
  - 자동 재연결 (연결 실패 시)
  
- **복구 능력**
  - 데이터베이스 무결성 검사
  - 파일 시스템 복구
  - 설정 백업/복원

### 3.4 사용성
- **UI/UX**
  - PyQt5 를 이용한 반응형 UI
  - 다국어 지원 (한국어, 영어)
  - 다크 모드
  - 모바일 최적화

### 3.5 유지보수성
- **모니터링**
  - 시스템 대시보드
  - 실시간 리소스 모니터링
  - SNMP 지원
  
- **업데이트**
  - 자동 업데이트
  - 롤백 기능


### 4.2 컴포넌트 설계

#### 4.2.1 Core Components
```python
# Singleton 패턴 적용 클래스
- ConfigManager: 전역 설정 관리
- DatabaseManager: DB 연결 관리
- LogManager: 로깅 시스템
- EventBus: 이벤트 통신

# Thread 기반 워커 클래스
- StreamWorker(QThread): 스트림 처리
- RecordingWorker(QThread): 녹화 처리
- AnalyticsWorker(QThread): 분석 처리
- StorageWorker(QThread): 저장소 관리
```

### 4.3 데이터베이스 스키마

```sql
-- 카메라 정보
CREATE TABLE cameras (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    rtsp_url VARCHAR(500),
    username VARCHAR(50),
    password VARCHAR(100),  -- 암호화 저장
    enabled BOOLEAN,
    ptz_supported BOOLEAN,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 녹화 파일 정보
CREATE TABLE recordings (
    id INTEGER PRIMARY KEY,
    camera_id INTEGER,
    file_path VARCHAR(500),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    file_size BIGINT,
    recording_type VARCHAR(20),
    locked BOOLEAN,
    FOREIGN KEY (camera_id) REFERENCES cameras(id)
);

-- 이벤트 로그
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    camera_id INTEGER,
    event_type VARCHAR(50),
    description TEXT,
    severity VARCHAR(20),
    timestamp TIMESTAMP,
    acknowledged BOOLEAN,
    FOREIGN KEY (camera_id) REFERENCES cameras(id)
);

-- 사용자 정보
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password_hash VARCHAR(255),
    role VARCHAR(20),
    created_at TIMESTAMP,
    last_login TIMESTAMP
);

-- 시스템 설정
CREATE TABLE settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    category VARCHAR(50),
    updated_at TIMESTAMP
);
```

## 5. 개발 환경 구성

### 5.1 기술 스택
```yaml
  - Python: 3.9+
  - UI: PyQt5
  - Streaming: GStreamer 1.18+
  - Database: SQLite 3.35+
  - Cache: Redis 6.2+
```

### 5.2 디렉토리 구조
```
pynvr/
├── src/
│   ├── core/           # 핵심 엔진
│   │   ├── streaming/
│   │   ├── recording/
│   │   └── analytics/
│   ├── api/            # REST API
│   ├── ui/             # PyQt5 UI
│   ├── web/            # Web UI
│   ├── config/         # 설정 관리
│   ├── database/       # DB 관리
│   └── utils/          # 유틸리티
├── tests/              # 테스트
├── docs/               # 문서
├── scripts/            # 스크립트
├── docker/             # Docker 설정
└── requirements/       # 의존성
```
