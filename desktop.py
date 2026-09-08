"""MCP-facing desktop client. Fixed local helper, private pipes, no shell or socket."""
from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time

from security import minimal_environment


class DesktopClient:
    def __init__(self):
        self.process = None
        self.lock = threading.RLock()
        self.sequence = 0

    def close(self):
        with self.lock:
            p, self.process = self.process, None
            if p is None:
                return
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=3)
            for pipe in (p.stdin, p.stdout):
                if pipe:
                    pipe.close()

    def call(self, operation: str, **arguments):
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                self.close()
                self.process = subprocess.Popen(
                    ['/usr/bin/python3', '-B', str(Path(__file__).with_name('desktop_worker.py'))],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    env=minimal_environment(desktop=True), bufsize=0,
                )
            self.sequence += 1
            p = self.process
            payload = json.dumps({'id': self.sequence, 'operation': operation, 'arguments': arguments})
            try:
                p.stdin.write((payload + '\n').encode())
                result = bytearray()
                deadline = time.monotonic() + 25
                with selectors.DefaultSelector() as selector:
                    selector.register(p.stdout, selectors.EVENT_READ)
                    while b'\n' not in result:
                        if not selector.select(max(0, deadline - time.monotonic())):
                            raise TimeoutError('Desktop helper timed out; action outcome may be unknown. Observe before retrying.')
                        chunk = os.read(p.stdout.fileno(), 65536)
                        if not chunk:
                            raise RuntimeError('Desktop helper stopped; observe before retrying any action.')
                        result.extend(chunk)
                        if len(result) > 20_000_000:
                            raise RuntimeError('Desktop observation exceeded the response limit.')
                response = json.loads(result)
                if response['id'] != self.sequence:
                    raise RuntimeError('Desktop response sequence mismatch.')
            except Exception:
                self.close()
                raise
            if not response.get('ok'):
                raise RuntimeError(response.get('error', 'Desktop operation failed'))
            return response['result']


client = DesktopClient()
atexit.register(client.close)
