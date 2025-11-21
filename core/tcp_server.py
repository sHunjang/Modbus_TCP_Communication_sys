#!/usr/bin/env python3
# core/tcp_server.py

"""
중앙 TCP 서버 (HMI 직접 전송 방식)
- HMI가 connect → send → close 반복
- 짧은 연결(Short-lived connection) 최적화
"""

import socket
import threading
import json


class TCPServerThread(threading.Thread):
    """중앙 모니터링 TCP 서버"""

    def __init__(self, host: str, port: int, allowed_tokens: dict, on_data_callback):
        """
        Args:
            host: 바인드 주소 (예: '0.0.0.0')
            port: 수신 포트
            allowed_tokens: {병원명: 토큰} 매핑
            on_data_callback: (addr, payload) -> None
        """
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.allowed_tokens = allowed_tokens
        self.on_data_callback = on_data_callback

        self._running = False
        self._server_sock = None

    def run(self):
        """서버 메인 루프"""
        self._running = True
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind((self.host, self.port))
            self._server_sock.listen(20)  # HMI 여러 대 동시 접속 대비

            print(f"✅ TCP 서버 시작: {self.host}:{self.port}")

            while self._running:
                try:
                    client_sock, addr = self._server_sock.accept()
                    # 각 HMI 연결마다 별도 스레드
                    threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, addr),
                        daemon=True,
                    ).start()
                except OSError:
                    break

        except Exception as e:
            print(f"❌ TCP 서버 오류: {e}")
        finally:
            self._close_server()
            print("🛑 TCP 서버 종료")

    def _handle_client(self, client_sock, addr):
        """HMI별 수신 처리 (짧은 연결)"""
        buffer = b""
        try:
            # HMI는 보통 한 번에 1줄 보내고 바로 닫음
            # 하지만 여러 줄을 보낼 수도 있으니 루프 유지
            while True:
                data = client_sock.recv(4096)
                if not data:
                    break
                buffer += data

                # 줄 단위(\n) 파싱
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        payload = json.loads(line.decode("utf-8"))
                        
                        # 인증 체크
                        hospital = payload.get("hospital", "")
                        token = payload.get("auth_token", "")
                        
                        if not self._verify_auth(hospital, token):
                            print(f"⚠️ 인증 실패: {addr} / {hospital}")
                            continue
                        
                        # 데이터 처리
                        self.on_data_callback(addr, payload)

                    except json.JSONDecodeError as e:
                        print(f"⚠️ JSON 파싱 오류 from {addr}: {e}")
                    except Exception as e:
                        print(f"❌ 데이터 처리 오류 from {addr}: {e}")

        except Exception as e:
            print(f"⚠️ 클라이언트 수신 오류 {addr}: {e}")
        finally:
            try:
                client_sock.close()
            except:
                pass
            # 짧은 연결이라 매번 종료 로그는 생략

    def _verify_auth(self, hospital: str, token: str) -> bool:
        """인증 확인"""
        expected_token = self.allowed_tokens.get(hospital, "")
        return token == expected_token and token != ""

    def _close_server(self):
        """서버 소켓 닫기"""
        if self._server_sock:
            try:
                self._server_sock.close()
            except:
                pass
            self._server_sock = None

    def stop(self):
        """서버 중지"""
        self._running = False
        self._close_server()
