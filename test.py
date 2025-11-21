import socket
import threading

HOST = "0.0.0.0"   # 모든 IP에서 접속 허용
PORT = 23000        # 서버 포트

def handle_client(conn, addr):
    print(f"[접속] {addr} 클라이언트 연결됨")

    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break

            print(f"[수신 from {addr}] {data.decode().strip()}")
            conn.sendall(b"OK\n")  # 수신 확인 응답
        except ConnectionResetError:
            break

    conn.close()
    print(f"[종료] {addr} 클라이언트 연결 종료")


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()

    print(f"TCP 서버 시작됨 (포트 {PORT})")

    while True:
        conn, addr = server.accept()
        thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        thread.start()


if __name__ == "__main__":
    start_server()
