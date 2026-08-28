#!/usr/bin/env python3
"""
Railway entrypoint for DEV X CORE.
Keeps a health HTTP server on $PORT (Railway requirement) and
runs the music userbot in the same process.
"""
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = int(os.environ.get("PORT", "8080"))
DATA_DIR = "/data" if os.path.isdir("/data") else os.path.abspath(".")


def ensure_dirs():
    for name in ("logs", "temp", "banner", "backups"):
        os.makedirs(os.path.join(DATA_DIR, name), exist_ok=True)
        os.makedirs(os.path.join(".", name), exist_ok=True)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"DEV X CORE online")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_health():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"  Health check listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    ensure_dirs()
    os.environ.setdefault("DATA_DIR", DATA_DIR)
    threading.Thread(target=run_health, daemon=True, name="railway-health").start()

    import runpy

    runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.py"), run_name="__main__")
