"""
PTZ Controller
PTZ(Pan-Tilt-Zoom) 카메라 제어 모듈
"""

import urllib.request
import urllib.error
import urllib.parse
from typing import Optional
from loguru import logger

from core.models import Camera


class PTZController:
    """PTZ 카메라 제어 클래스"""

    def __init__(self, camera: Camera):
        """
        PTZ 컨트롤러 초기화

        Args:
            camera: Camera 모델 (ptz_type, ptz_port, ptz_channel 포함)
        """
        self.camera = camera
        self.ptz_type = camera.ptz_type
        self.ptz_port = camera.ptz_port or "80"
        self.ptz_channel = camera.ptz_channel or "1"

        # RTSP URL에서 IP, username, password 추출
        self.ip, self.username, self.password = self._extract_info_from_rtsp(camera.rtsp_url)

        # Camera 모델에서 username/password가 명시적으로 설정되어 있으면 우선 사용
        if camera.username:
            self.username = camera.username
        if camera.password:
            self.password = camera.password

        # HTTP 타임아웃 설정
        self.timeout = 5

        # 디버그: 비밀번호 길이만 표시 (보안상 전체는 표시 안함)
        pwd_info = f"password_length={len(self.password) if self.password else 0}"
        logger.info(f"PTZ Controller initialized: {self.ptz_type}, IP={self.ip}, Port={self.ptz_port}, Username={self.username}, {pwd_info}")

        if not self.username or not self.password:
            logger.warning(f"PTZ authentication info missing! Username={self.username}, Password={'SET' if self.password else 'NOT_SET'}")

    def _extract_info_from_rtsp(self, rtsp_url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        RTSP URL에서 IP, username, password 추출

        예: rtsp://admin:password123@192.168.0.131:554/stream

        Returns:
            (ip, username, password) tuple
        """
        try:
            parsed = urllib.parse.urlparse(rtsp_url)

            # IP 추출 (포트 제거)
            ip = parsed.hostname

            # Username, Password 추출
            username = parsed.username
            password = parsed.password

            # URL 디코딩 (특수문자 처리)
            if username:
                username = urllib.parse.unquote(username)
            if password:
                password = urllib.parse.unquote(password)

            logger.debug(f"Extracted from RTSP: IP={ip}, Username={username}, Password={'*' * len(password) if password else None}")
            return ip, username, password
        except Exception as e:
            logger.error(f"Failed to extract info from RTSP URL: {e}")
            return None, None, None

    def send_command(self, command: str, speed: int = 5) -> bool:
        """
        PTZ 명령 전송

        Args:
            command: PTZ 명령 (ZOOMIN, ZOOMOUT, ZOOMSTOP, UP, DOWN, LEFT, RIGHT 등)
            speed: 속도 (1-9)

        Returns:
            성공 여부
        """
        if not self.ip:
            logger.error("Camera IP not available")
            return False

        if not self.ptz_type or self.ptz_type.upper() == "NONE":
            logger.warning("PTZ type not configured")
            return False

        try:
            if self.ptz_type.upper() == "HIK":
                return self._send_hik_command(command, speed)
            elif self.ptz_type.upper() == "ONVIF":
                return self._send_onvif_command(command, speed)
            else:
                logger.warning(f"Unsupported PTZ type: {self.ptz_type}")
                return False

        except Exception as e:
            logger.error(f"Failed to send PTZ command: {e}")
            return False

    def _send_hik_command(self, command: str, speed: int) -> bool:
        """
        HIK 카메라용 PTZ 명령 전송 (PUT + XML 방식, Basic/Digest 인증 지원 - opencv_nvr.py와 동일)

        Args:
            command: PTZ 명령
            speed: 속도 (1-9)

        Returns:
            성공 여부
        """
        # XML 데이터 생성
        xml_data = self._generate_hik_xml(command, speed)

        if not xml_data:
            logger.warning(f"Unknown command for HIK: {command}")
            return False

        # URL 구성 (Continuous 경로 사용 - opencv_nvr.py와 동일)
        url = f"http://{self.ip}:{self.ptz_port}/ISAPI/PTZCtrl/channels/{self.ptz_channel}/Continuous"

        # HTTP PUT 요청 전송 (Basic/Digest 인증 모두 지원)
        try:
            logger.debug(f"Sending PTZ command: {command} to {url}, auth=({self.username}, {'***' if self.password else None})")
            logger.debug(f"XML Data: {xml_data}")

            # Basic과 Digest 인증을 모두 지원하는 핸들러 생성
            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, url, self.username, self.password)

            basic_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
            digest_handler = urllib.request.HTTPDigestAuthHandler(password_mgr)
            opener = urllib.request.build_opener(basic_handler, digest_handler)

            request = urllib.request.Request(url, data=xml_data.encode('utf-8'), method='PUT')
            request.add_header('Accept', 'application/xml')
            request.add_header('Content-Type', 'text/xml;charset=utf-8')

            with opener.open(request, timeout=self.timeout) as response:
                result = response.read().decode('utf-8')
                logger.debug(f"PTZ command sent successfully: {command}, Response code: {response.getcode()}")
                logger.debug(f"Response: {result}")
                return True

        except urllib.error.HTTPError as e:
            logger.error(f"HTTP PUT request failed - HTTP {e.code}: {e.reason}")
            if hasattr(e, 'read'):
                error_content = e.read().decode('utf-8', errors='ignore')
                logger.error(f"Error content: {error_content}")
            return False
        except urllib.error.URLError as e:
            logger.error(f"HTTP PUT request failed - URL error: {e.reason}")
            return False
        except Exception as e:
            logger.error(f"HTTP PUT request failed - Other error: {e}")
            return False

    def _generate_hik_xml(self, command: str, speed: int) -> Optional[str]:
        """
        HIK 카메라용 XML 명령 생성 (opencv_nvr.py와 동일)

        Args:
            command: PTZ 명령
            speed: 속도 (1-9)

        Returns:
            XML 문자열
        """
        speed_str = str(speed)

        # 명령어 템플릿 (opencv_nvr.py의 generate_hik_command와 동일)
        command_templates = {
            "UPLEFT": f"<PTZData><pan>-{speed_str}0</pan><tilt>{speed_str}0</tilt><zoom>0</zoom></PTZData>",
            "UP": f"<PTZData><pan>0</pan><tilt>{speed_str}0</tilt><zoom>0</zoom></PTZData>",
            "UPRIGHT": f"<PTZData><pan>{speed_str}0</pan><tilt>{speed_str}0</tilt><zoom>0</zoom></PTZData>",
            "LEFT": f"<PTZData><pan>-{speed_str}0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>",
            "STOP": "<PTZData><pan>0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>",
            "RIGHT": f"<PTZData><pan>{speed_str}0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>",
            "DOWNLEFT": f"<PTZData><pan>-{speed_str}0</pan><tilt>-{speed_str}0</tilt><zoom>0</zoom></PTZData>",
            "DOWN": f"<PTZData><pan>0</pan><tilt>-{speed_str}0</tilt><zoom>0</zoom></PTZData>",
            "DOWNRIGHT": f"<PTZData><pan>{speed_str}0</pan><tilt>-{speed_str}0</tilt><zoom>0</zoom></PTZData>",
            "ZOOMIN": "<PTZData><pan>0</pan><tilt>0</tilt><zoom>1</zoom></PTZData>",
            "ZOOMOUT": "<PTZData><pan>0</pan><tilt>0</tilt><zoom>-1</zoom></PTZData>",
            "ZOOMSTOP": "<PTZData><pan>0</pan><tilt>0</tilt><zoom>0</zoom></PTZData>",
        }

        return command_templates.get(command.upper())

    def _generate_hik_cgi_params(self, command: str, speed: int) -> Optional[str]:
        """
        HIK 카메라용 CGI 파라미터 생성

        Args:
            command: PTZ 명령
            speed: 속도 (1-9)

        Returns:
            CGI 파라미터 문자열
        """
        speed_str = str(speed)
        channel = self.ptz_channel

        # 명령어 매핑 (opencv_nvr.py의 convert_xml_to_cgi_params 참고)
        command_map = {
            "UP": f"action=start&channel={channel}&code=Up&arg1={speed_str}&arg2=0&arg3=0",
            "DOWN": f"action=start&channel={channel}&code=Down&arg1={speed_str}&arg2=0&arg3=0",
            "LEFT": f"action=start&channel={channel}&code=Left&arg1={speed_str}&arg2=0&arg3=0",
            "RIGHT": f"action=start&channel={channel}&code=Right&arg1={speed_str}&arg2=0&arg3=0",
            "UPLEFT": f"action=start&channel={channel}&code=LeftUp&arg1={speed_str}&arg2=0&arg3=0",
            "UPRIGHT": f"action=start&channel={channel}&code=RightUp&arg1={speed_str}&arg2=0&arg3=0",
            "DOWNLEFT": f"action=start&channel={channel}&code=LeftDown&arg1={speed_str}&arg2=0&arg3=0",
            "DOWNRIGHT": f"action=start&channel={channel}&code=RightDown&arg1={speed_str}&arg2=0&arg3=0",
            "ZOOMIN": f"action=start&channel={channel}&code=ZoomTele&arg1={speed_str}&arg2=0&arg3=0",
            "ZOOMOUT": f"action=start&channel={channel}&code=ZoomWide&arg1={speed_str}&arg2=0&arg3=0",
            "STOP": f"action=stop&channel={channel}&code=Stop&arg1=0&arg2=0&arg3=0",
            "ZOOMSTOP": f"action=stop&channel={channel}&code=Stop&arg1=0&arg2=0&arg3=0",
        }

        return command_map.get(command.upper())

    def _send_onvif_command(self, command: str, speed: int) -> bool:
        """
        ONVIF 카메라용 PTZ 명령 전송

        Args:
            command: PTZ 명령
            speed: 속도 (1-9)

        Returns:
            성공 여부
        """
        # TODO: ONVIF 구현 (필요 시)
        logger.warning("ONVIF PTZ control not implemented yet")
        return False

    # 편의 메서드
    def zoom_in(self, speed: int = 5) -> bool:
        """줌 인"""
        return self.send_command("ZOOMIN", speed)

    def zoom_out(self, speed: int = 5) -> bool:
        """줌 아웃"""
        return self.send_command("ZOOMOUT", speed)

    def zoom_stop(self) -> bool:
        """줌 정지"""
        return self.send_command("ZOOMSTOP", 0)

    def move_up(self, speed: int = 5) -> bool:
        """위로 이동"""
        return self.send_command("UP", speed)

    def move_down(self, speed: int = 5) -> bool:
        """아래로 이동"""
        return self.send_command("DOWN", speed)

    def move_left(self, speed: int = 5) -> bool:
        """왼쪽으로 이동"""
        return self.send_command("LEFT", speed)

    def move_right(self, speed: int = 5) -> bool:
        """오른쪽으로 이동"""
        return self.send_command("RIGHT", speed)

    def stop(self) -> bool:
        """정지"""
        return self.send_command("STOP", 0)