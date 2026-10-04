"""One public port for Odoo's HTTP and evented workers."""

import os
from pathlib import Path
import signal
import subprocess
import time

HTTP_PORT = 8068
EVENTED_PORT = 8072


def proxy_config(directory, public_port):
    port = int(public_port)
    if not 1024 <= port <= 65535 or port in (HTTP_PORT, EVENTED_PORT):
        raise ValueError("PORT must be an unprivileged port distinct from Odoo's internal ports")
    directory = Path(directory).resolve()
    # The directory comes from mkdtemp, never a request or environment value.
    return f'''
daemon off;
worker_processes 1;
pid {directory}/nginx.pid;
error_log stderr warn;
events {{ worker_connections 1024; }}
http {{
    access_log off;
    client_body_temp_path {directory}/body;
    proxy_temp_path {directory}/proxy;
    map $http_upgrade $connection_upgrade {{ default upgrade; '' close; }}
    map $http_x_forwarded_proto $forwarded_proto {{ default $http_x_forwarded_proto; '' $scheme; }}
    map $http_x_forwarded_for $forwarded_for {{ default $http_x_forwarded_for; '' $remote_addr; }}
    server {{
        listen 0.0.0.0:{port};
        client_max_body_size 0;
        proxy_http_version 1.1;
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
        proxy_request_buffering off;
        proxy_set_header Host $http_host;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_set_header X-Forwarded-Proto $forwarded_proto;
        proxy_set_header X-Forwarded-For $forwarded_for;
        location / {{
            proxy_pass http://127.0.0.1:{HTTP_PORT};
        }}
        location ~ ^/websocket(/|$) {{
            proxy_pass http://127.0.0.1:{EVENTED_PORT};
            proxy_set_header Host $http_host;
            proxy_set_header X-Forwarded-Host $http_host;
            proxy_set_header X-Forwarded-Proto $forwarded_proto;
            proxy_set_header X-Forwarded-For $forwarded_for;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection $connection_upgrade;
            proxy_buffering off;
        }}
    }}
}}
'''


def serve(commands):
    """Stop the entire runtime if either essential process exits or we receive SIGTERM."""
    children = []
    stopped = []
    previous = {}
    try:
        for signum in (signal.SIGTERM, signal.SIGINT):
            previous[signum] = signal.signal(signum, lambda number, _frame: stopped.append(number))
        for command in commands:
            if stopped:
                break
            children.append(subprocess.Popen(command, start_new_session=True))
        while not stopped and all(child.poll() is None for child in children):
            time.sleep(0.2)
        return 128 + stopped[0] if stopped else next(child.returncode or 1 for child in children if child.returncode is not None)
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 25
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
