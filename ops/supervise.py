"""Own a single tunnel; fail the unit when its required stdio child disappears."""
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def has_stdio_child(pid: int, marker: bytes) -> bool:
    for process in Path('/proc').iterdir():
        if not process.name.isdigit():
            continue
        try:
            stat = (process / 'stat').read_text()
            ppid = int(stat[stat.rfind(')') + 2:].split()[1])
            if ppid == pid and marker in (process / 'cmdline').read_bytes():
                return True
        except (OSError, ValueError):
            continue
    return False


def supervise(command: list[str], env: dict, mode: str) -> int:
    markers = {'tunnel-bridge': b'/chatgpt-local-bridge/mcp_server.py',
               'tunnel-blender': b'/mcp-integration/blender_entry.py'}
    marker = markers.get(mode)
    stopping = False

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    child = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL)
    started = time.monotonic()
    missing_since = None
    exit_code = 1
    try:
        while not stopping:
            if child.poll() is not None:
                print('Tunnel exited; requesting service restart.', file=sys.stderr, flush=True)
                break
            if marker:
                if has_stdio_child(child.pid, marker):
                    missing_since = None
                elif missing_since is None:
                    missing_since = time.monotonic()
                elif time.monotonic() - started > 20 and time.monotonic() - missing_since > 4:
                    print('Required stdio MCP child disappeared; requesting service restart.', file=sys.stderr, flush=True)
                    break
            time.sleep(1)
        if stopping:
            exit_code = 0
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)
    return exit_code
