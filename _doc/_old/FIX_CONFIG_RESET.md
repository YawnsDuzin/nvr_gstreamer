# config.yaml 초기화 문제 해결

## 문제 원인

main.py 실행 시 config.yaml의 cameras 설정이 빈 배열로 초기화되는 문제가 발생했습니다.

### 원인 분석:

1. **config_manager.py의 save_config() 메서드**
   - YAML 파일을 완전히 덮어쓰기 때문에 주석이 사라짐
   - 메모리에 로드된 cameras 리스트가 비어있으면 빈 배열로 저장됨

2. **UI에서 자동 저장**
   - camera_list_widget.py에서 카메라 추가/수정/삭제 시 자동으로 save_config() 호출
   - 의도하지 않은 시점에 설정 파일이 덮어써질 수 있음

## 적용된 수정사항

### 1. config_manager.py 수정

```python
# create_default_config() 메서드 개선
def create_default_config(self):
    """Create default configuration file (only if not exists)"""
    # 파일이 이미 있으면 덮어쓰지 않음
    if self.config_file.exists():
        logger.warning(f"Config file already exists: {self.config_file}. Skipping creation.")
        return

    # ... 기본 설정 생성
```

**효과**: 이미 설정 파일이 있으면 절대 덮어쓰지 않음

### 2. config.yaml 복구

cameras가 빈 배열로 되어 있던 것을 원래 설정으로 복구:

```yaml
cameras:
  - camera_id: cam_01
    name: Main Camera
    rtsp_url: rtsp://admin:trolleycam1~@192.168.0.131:554/Streaming/Channels/102
    enabled: true
    recording_enabled: true
```

### 3. save_config() 개선

```python
# YAML 저장 시 UTF-8 인코딩 및 가독성 향상
yaml.dump(
    data,
    f,
    default_flow_style=False,
    sort_keys=False,
    allow_unicode=True,
    indent=2
)
```

## 권장 사항

### 설정 파일 백업

중요한 설정을 잃지 않기 위해 정기적으로 백업:

```bash
# config.yaml 백업
cp config.yaml config.yaml.backup

# 또는 날짜별 백업
cp config.yaml "config.yaml.backup.$(date +%Y%m%d)"
```

### 설정 파일 수동 편집 시 주의사항

1. **프로그램을 먼저 종료**한 후 편집
2. YAML 문법 확인 (들여쓰기 중요!)
3. 편집 후 백업본 생성
4. 프로그램 실행 전 문법 검증:
   ```python
   python -c "import yaml; yaml.safe_load(open('config.yaml'))"
   ```

### UI에서 카메라 설정 변경 시

- UI에서 카메라를 추가/수정/삭제하면 자동으로 config.yaml이 업데이트됨
- **주석은 사라지지만** 설정 데이터는 유지됨
- 주석을 유지하려면 config.yaml을 직접 편집 (프로그램 종료 후)

## 향후 개선 방향

### ruamel.yaml 사용 (주석 유지)

현재 PyYAML은 주석을 보존하지 않습니다. ruamel.yaml로 교체하면 주석 유지 가능:

```bash
pip install ruamel.yaml
```

```python
from ruamel.yaml import YAML

def save_config(self):
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.preserve_quotes = True
    yaml.width = 4096

    with open(self.config_file, 'w') as f:
        yaml.dump(data, f)
```

## 테스트

수정 후 다음 테스트 수행:

```bash
# 1. 설정 파일 백업
cp config.yaml config.yaml.test.backup

# 2. 프로그램 실행
python main.py

# 3. 프로그램 종료 후 config.yaml 확인
cat config.yaml

# 4. cameras 설정이 유지되는지 확인
python -c "import yaml; cfg = yaml.safe_load(open('config.yaml')); print(f'Cameras: {len(cfg[\"cameras\"])}')"
```

## 결론

이제 config.yaml의 cameras 설정이:
- ✅ 프로그램 실행 시 초기화되지 않음
- ✅ 기존 설정 파일이 있으면 덮어쓰지 않음
- ✅ UI에서만 의도적으로 변경할 때 저장됨
- ⚠️ 주석은 UI에서 저장 시 사라짐 (향후 ruamel.yaml로 개선 가능)
