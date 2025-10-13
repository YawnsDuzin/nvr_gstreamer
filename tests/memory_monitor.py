#!/usr/bin/env python3
"""
Memory Monitor - 시스템 메모리 사용량 모니터링 프로그램
라즈베리파이 등 리눅스 시스템의 메모리 사용량을 주기적으로 로깅합니다.
"""

import os
import sys
import time
import psutil
import datetime
import logging
from logging.handlers import RotatingFileHandler
import argparse
import signal

from typing import List, Dict, Any

class MemoryMonitor:
    def __init__(self, log_dir="./logs", interval_minutes=60, top_process_count=5, max_log_size_mb=10):
        """
        메모리 모니터 초기화
        
        Args:
            log_dir (str): 로그 파일 저장 경로
            interval_minutes (int): 모니터링 주기 (분 단위)
            top_process_count (int): 기록할 상위 프로세스 개수
            max_log_size_mb (int): 로그 파일 최대 크기 (MB)
        """
        self.log_dir = log_dir
        self.interval_seconds = interval_minutes * 60
        self.top_process_count = top_process_count
        self.max_log_size = max_log_size_mb * 1024 * 1024  # MB to bytes
        self.running = True
        
        # CSV 헤더 작성 여부 추적
        self.csv_header_written = False
        
        # 로그 디렉토리 생성
        os.makedirs(log_dir, exist_ok=True)
        
        # 로거 설정
        self.setup_logger()
        
        # 시그널 핸들러 설정 (graceful shutdown)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def setup_logger(self):
        """로거 설정"""
        log_file = os.path.join(self.log_dir, 'memory_monitor.log')
        
        # 로거 생성
        self.logger = logging.getLogger('MemoryMonitor')
        self.logger.setLevel(logging.INFO)
        
        # 포맷터 설정
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 파일 핸들러 (로테이션 포함)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=self.max_log_size,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
    
    def signal_handler(self, signum, frame):
        """시그널 핸들러 (Ctrl+C 등)"""
        self.logger.info("모니터링 종료 신호를 받았습니다.")
        self.running = False
    
    def get_memory_info(self):
        """시스템 메모리 정보 수집"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            'total_mb': mem.total / (1024 * 1024),
            'used_mb': mem.used / (1024 * 1024),
            'free_mb': mem.free / (1024 * 1024),
            'available_mb': mem.available / (1024 * 1024),
            'percent': mem.percent,
            'swap_total_mb': swap.total / (1024 * 1024),
            'swap_used_mb': swap.used / (1024 * 1024),
            'swap_free_mb': swap.free / (1024 * 1024),
            'swap_percent': swap.percent
        }
    
    def get_top_processes(self):
        """메모리 사용량 상위 프로세스 정보 수집"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'memory_info']):
            try:
                proc_info = proc.info
                memory_mb = proc_info['memory_info'].rss / (1024 * 1024)
                memory_percent = proc.memory_percent()
                
                processes.append({
                    'pid': proc_info['pid'],
                    'name': proc_info['name'],
                    'username': proc_info['username'],
                    'memory_mb': memory_mb,
                    'memory_percent': memory_percent
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # 메모리 사용량 기준 정렬
        processes.sort(key=lambda x: x['memory_mb'], reverse=True)
        
        return processes[:self.top_process_count]
    
    def log_memory_status(self):
        """메모리 상태를 로그에 기록"""
        try:
            # 메모리 정보 수집
            mem_info = self.get_memory_info()
            top_processes = self.get_top_processes()
            
            # 구분선 및 타임스탬프
            self.logger.info("=" * 70)
            self.logger.info(f"메모리 모니터링 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info("-" * 70)
            
            # 시스템 메모리 정보
            self.logger.info("【시스템 메모리 정보】")
            self.logger.info(f"  총 메모리: {mem_info['total_mb']:.1f} MB, 사용 중: {mem_info['used_mb']:.1f} MB ({mem_info['percent']:.1f}%), 여유: {mem_info['free_mb']:.1f} MB, 가용: {mem_info['available_mb']:.1f} MB")

            # Swap 정보
            self.logger.info("【Swap 정보】")
            self.logger.info(f"  총 Swap: {mem_info['swap_total_mb']:.1f} MB, 사용 중: {mem_info['swap_used_mb']:.1f} MB ({mem_info['swap_percent']:.1f}%), 여유: {mem_info['swap_free_mb']:.1f} MB")

            # 경고 메시지
            if mem_info['percent'] > 80:
                self.logger.warning("⚠️  메모리 사용률이 80%를 초과했습니다!")
            if mem_info['percent'] > 90:
                self.logger.error("⚠️  메모리 사용률이 90%를 초과했습니다!")
            if mem_info['swap_percent'] > 80:
                self.logger.warning("⚠️  Swap 사용률이 80%를 초과했습니다!")
            
            # 상위 프로세스 정보
            self.logger.info(f"【메모리 사용 상위 {self.top_process_count}개 프로세스】")
            s_top_processes = ""
            for i, proc in enumerate(top_processes, 1):
                if i > 1:
                    s_top_processes += ", "
                
                s_top_processes += f"{i}.({proc['name']} | {proc['memory_mb']:.1f} MB | {proc['memory_percent']:.1f}%)"
            
            if s_top_processes:
                self.logger.info(f"  {s_top_processes}")
            else:
                self.logger.info("  프로세스 정보를 가져올 수 없습니다.")
            
            # CSV 형식으로도 저장 (데이터 분석용)
            self.save_csv_data(mem_info, top_processes)
            
        except Exception as e:
            self.logger.error(f"메모리 정보 수집 중 오류 발생: {e}")
    
    def save_csv_data(self, mem_info: Dict[str, Any], top_processes: List[Dict[str, Any]]):
        """CSV 형식으로 데이터 저장 (동적 프로세스 개수 지원)"""
        csv_file = os.path.join(self.log_dir, 'memory_data.csv')
        
        # CSV 파일이 없거나 헤더가 아직 작성되지 않은 경우
        if not os.path.exists(csv_file) or not self.csv_header_written:
            # 새로운 헤더 작성 (top_process_count에 맞춤)
            with open(csv_file, 'w', encoding='utf-8') as f:
                # 기본 헤더
                header = "timestamp,total_mb,used_mb,percent,swap_total_mb,swap_used_mb,swap_percent"
                
                # 동적으로 프로세스 헤더 추가
                for i in range(1, self.top_process_count + 1):
                    header += f",top_process_{i}"
                
                f.write(header + "\n")
                self.csv_header_written = True
        
        # 데이터 추가
        with open(csv_file, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 기본 데이터
            row_data = [
                timestamp,
                f"{mem_info['total_mb']:.1f}",
                f"{mem_info['used_mb']:.1f}",
                f"{mem_info['percent']:.1f}",
                f"{mem_info['swap_total_mb']:.1f}",
                f"{mem_info['swap_used_mb']:.1f}",
                f"{mem_info['swap_percent']:.1f}"
            ]
            
            # 프로세스 데이터 추가 (동적 개수)
            for i in range(self.top_process_count):
                if i < len(top_processes):
                    proc = top_processes[i]
                    row_data.extend([
                        # proc['name'],
                        # f"{proc['memory_mb']:.1f}",
                        # f"{proc['memory_percent']:.1f}",
                        # str(proc['pid'])
                        f" ({proc['name']} | {proc['memory_mb']:.1f} MB | {proc['memory_percent']:.1f}% | PID:{proc['pid']})"
                    ])
                else:
                    # 프로세스가 없는 경우 빈 값
                    row_data.extend(['N/A', '0.0', '0.0', '0'])
            
            f.write(",".join(row_data) + "\n")
    
    def save_summary_txt(self, mem_info: Dict[str, Any], top_processes: List[Dict[str, Any]]):
        """요약 정보를 텍스트 파일로 저장 (선택사항)"""
        txt_file = os.path.join(self.log_dir, 'memory_summary.txt')
        
        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"메모리 모니터링 요약 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")
            
            f.write("【시스템 메모리 정보】\n")
            f.write(f"총 메모리: {mem_info['total_mb']:.1f} MB\n")
            f.write(f"사용 중: {mem_info['used_mb']:.1f} MB ({mem_info['percent']:.1f}%)\n")
            f.write(f"여유: {mem_info['free_mb']:.1f} MB\n")
            f.write(f"가용: {mem_info['available_mb']:.1f} MB\n\n")
            
            f.write("【Swap 정보】\n")
            f.write(f"총 Swap: {mem_info['swap_total_mb']:.1f} MB\n")
            f.write(f"사용 중: {mem_info['swap_used_mb']:.1f} MB ({mem_info['swap_percent']:.1f}%)\n")
            f.write(f"여유: {mem_info['swap_free_mb']:.1f} MB\n\n")
            
            f.write(f"【메모리 사용 상위 {self.top_process_count}개 프로세스】\n")
            for i, proc in enumerate(top_processes, 1):
                f.write(f"{i}. {proc['name']}\n")
                f.write(f"   PID: {proc['pid']}\n")
                f.write(f"   메모리: {proc['memory_mb']:.1f} MB ({proc['memory_percent']:.1f}%)\n")
                f.write(f"   사용자: {proc['username']}\n\n")
    
    def run(self):
        """메인 실행 루프"""
        self.logger.info(f"메모리 모니터링 시작 (주기: {self.interval_seconds//60}분, 상위 프로세스: {self.top_process_count}개)")
        
        # 시작 시 즉시 한 번 실행
        self.log_memory_status()
        
        while self.running:
            # 다음 실행까지 대기
            if self.running:
                next_run = datetime.datetime.now() + datetime.timedelta(seconds=self.interval_seconds)
                self.logger.info(f"다음 모니터링: {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({self.interval_seconds//60}분 후)\n")
                
                # interval_seconds 동안 대기 (1초씩 체크하면서 종료 신호 확인)
                for _ in range(self.interval_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
                
                if self.running:
                    self.log_memory_status()
        
        self.logger.info("메모리 모니터링이 종료되었습니다.")

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='시스템 메모리 사용량 모니터링 프로그램',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예제:
  # 기본 설정으로 실행 (60분 주기, 상위 5개 프로세스)
  python3 memory_monitor.py
  
  # 10분마다 모니터링, 상위 10개 프로세스 기록
  python3 memory_monitor.py -i 10 -t 10
  
  # 1분마다 모니터링, 상위 20개 프로세스 기록
  python3 memory_monitor.py -i 1 -t 20
  
  # 로그 디렉토리 지정
  python3 memory_monitor.py -d /var/log/memory_monitor
  
  # 백그라운드 실행 (nohup 사용)
  nohup python3 memory_monitor.py -i 10 -t 10 -d ./memory_logs > /dev/null 2>&1 &
        """
    )
    
    parser.add_argument('-i', '--interval', type=int, default=60,
                       help='모니터링 주기 (분 단위, 기본값: 60분)')
    parser.add_argument('-t', '--top', type=int, default=5,
                       help='기록할 상위 프로세스 개수 (기본값: 5개)')
    parser.add_argument('-d', '--dir', type=str, default='./logs',
                       help='로그 파일 저장 경로 (기본값: ./logs)')
    parser.add_argument('-s', '--size', type=int, default=10,
                       help='로그 파일 최대 크기 MB (기본값: 10MB)')
    parser.add_argument('--txt', action='store_true',
                       help='요약 텍스트 파일도 생성')
    
    args = parser.parse_args()
    
    # 유효성 검사
    if args.interval < 1:
        print("오류: 모니터링 주기는 1분 이상이어야 합니다.")
        sys.exit(1)
    
    if args.top < 1:
        print("오류: 프로세스 개수는 1개 이상이어야 합니다.")
        sys.exit(1)
    
    if args.top > 50:
        print("경고: 프로세스 개수가 50개를 초과합니다. CSV 파일이 매우 커질 수 있습니다.")
        response = input("계속 진행하시겠습니까? (y/n): ")
        if response.lower() != 'y':
            sys.exit(0)
    
    # 모니터 실행
    monitor = MemoryMonitor(
        log_dir=args.dir,
        interval_minutes=args.interval,
        top_process_count=args.top,
        max_log_size_mb=args.size
    )
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()