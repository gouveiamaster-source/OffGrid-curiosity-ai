#!/usr/bin/env python3
"""One-click launcher: start API and open browser automatically."""

from __future__ import annotations

import argparse
import os
import shlex
import socket
import subprocess
import sys
import time
import webbrowser


def _wait_for_port(host: str, port: int, timeout_seconds: float) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _build_uvicorn_command(host: str, port: int, reload_mode: bool) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        host,
        "--port",
        str(port),
    ]
    if reload_mode:
        command.append("--reload")
    return command


def _open_in_browser(url: str) -> None:
    browser_cmd = os.getenv("BROWSER", "").strip()
    if browser_cmd:
        try:
            subprocess.Popen([*shlex.split(browser_cmd), url])
            return
        except Exception:
            pass
    webbrowser.open(url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Alexandria-AI and open it in the browser.")
    parser.add_argument("--host", default=os.getenv("ALEXANDRIA_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("ALEXANDRIA_PORT", "8000")))
    parser.add_argument("--timeout", type=float, default=25.0)
    parser.add_argument(
        "--open-url",
        default=os.getenv("ALEXANDRIA_OPEN_URL", ""),
        help="Explicit URL to open in the browser.",
    )
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload (development mode).",
    )
    args = parser.parse_args()

    server_url = f"http://{args.host}:{args.port}"
    open_url = args.open_url or f"http://127.0.0.1:{args.port}"
    command = _build_uvicorn_command(args.host, args.port, args.reload)

    print(f"Starting API on {server_url}...")
    process = subprocess.Popen(command)

    try:
        wait_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
        if not _wait_for_port(wait_host, args.port, args.timeout):
            print(
                "Server did not become ready in time. "
                "Check logs above and try again.",
                file=sys.stderr,
            )
            process.terminate()
            process.wait(timeout=5)
            return 1

        if not args.no_open:
            print(f"Opening browser: {open_url}")
            _open_in_browser(open_url)

        print("Server is running. Press Ctrl+C to stop.")
        process.wait()
        return process.returncode or 0
    except KeyboardInterrupt:
        print("\nStopping server...")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
