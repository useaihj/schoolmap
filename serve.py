"""간단한 로컬 서버 - python serve.py 로 실행 후 http://localhost:8080 접속"""
import http.server
import socketserver

PORT = 8080
Handler = http.server.SimpleHTTPServer if hasattr(http.server, 'SimpleHTTPServer') else http.server.SimpleHTTPRequestHandler

with socketserver.TCPServer(("", PORT), http.server.SimpleHTTPRequestHandler) as httpd:
    print(f"서버 시작: http://localhost:{PORT}")
    print("종료: Ctrl+C")
    httpd.serve_forever()
