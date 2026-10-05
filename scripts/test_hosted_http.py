"""Real hosted launcher, HTTP authentication and WebSocket round trip in disposable CI."""
import base64
import hashlib
from http.client import HTTPConnection
import json
import os
import socket
import subprocess
import sys
import time

from odoo.addons.bus.websocket import WebsocketConnectionHandler


def main():
    database = os.environ.get("PGDATABASE", "")
    if not database.startswith("tcsi_orvexa_") or os.environ.get("PGHOST") != "127.0.0.1":
        raise SystemExit("Refusing hosted runtime tests outside local disposable CI")
    port = int(os.environ["PORT"])
    process = subprocess.Popen([sys.executable, "/opt/tcsi/cloud_start.py"])
    try:
        deadline = time.monotonic() + 180
        while True:
            if process.poll() is not None:
                raise AssertionError(f"Hosted runtime exited before readiness: {process.returncode}")
            try:
                http = HTTPConnection("127.0.0.1", port, timeout=5)
                http.request("GET", "/web/login")
                response = http.getresponse()
                response.read()
                if response.status == 200:
                    break
            except OSError:
                pass
            finally:
                http.close()
            if time.monotonic() > deadline:
                raise AssertionError("Hosted runtime did not become ready")
            time.sleep(1)
        http = HTTPConnection("127.0.0.1", port, timeout=30)
        body = json.dumps({"jsonrpc": "2.0", "params": {"db": database,
            "login": os.environ["TCSI_ADMIN_LOGIN"], "password": os.environ["TCSI_ADMIN_PASSWORD"]}})
        http.request("POST", "/web/session/authenticate", body,
                     {"Content-Type": "application/json", "X-Forwarded-Proto": "https"})
        response = http.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["result"]["uid"], "HTTP authentication failed"
        cookie = response.getheader("Set-Cookie")
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie
        assert response.getheader("Strict-Transport-Security")
        http.close()
        version = WebsocketConnectionHandler._VERSION
        for protocol, expected in (("999", 426), ("13", 101)):
            with socket.create_connection(("127.0.0.1", port), timeout=20) as connection:
                key = base64.b64encode(os.urandom(16)).decode()
                request = (f"GET /websocket?version={version} HTTP/1.1\r\nHost: localhost:{port}\r\n"
                           f"Origin: https://localhost:{port}\r\nX-Forwarded-Proto: https\r\n"
                           f"Cookie: {cookie.split(';', 1)[0]}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: {protocol}\r\n\r\n")
                connection.sendall(request.encode())
                stream = connection.makefile("rb")
                status = stream.readline().decode()
                assert int(status.split()[1]) == expected, status
                headers = {}
                while (line := stream.readline()) != b"\r\n":
                    assert line, "Connection closed before response headers"
                    name, value = line.decode().split(":", 1)
                    headers[name.lower()] = value.strip()
                assert headers["x-content-type-options"] == "nosniff"
                if expected == 426:
                    assert headers["sec-websocket-version"] == "13"
                else:
                    expected_accept = base64.b64encode(hashlib.sha1((key + WebsocketConnectionHandler._HANDSHAKE_GUID).encode()).digest()).decode()
                    assert headers["sec-websocket-accept"] == expected_accept
                    # Masked ping verifies both directions after the HTTP upgrade.
                    connection.sendall(b"\x89\x84\x00\x00\x00\x00tcsi")
                    assert stream.read(6) == b"\x8a\x04tcsi", "WebSocket ping/pong failed"
                    connection.sendall(b"\x88\x82\x00\x00\x00\x00\x03\xe8")
                    assert stream.read(4) == b"\x88\x02\x03\xe8", "WebSocket close failed"
                stream.close()
        print("Hosted runtime: HTTP login, secure headers/cookie, 426 error, WebSocket 101/ping/pong/close passed")
    finally:
        process.terminate()
        try:
            process.wait(timeout=35)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise AssertionError("Hosted runtime failed to shut down")


if __name__ == "__main__":
    main()
