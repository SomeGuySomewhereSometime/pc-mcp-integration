"""Read bounded video samples in an isolated decoder, returning native MCP images."""
from __future__ import annotations

import base64
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import time

from obs_control import OBSError

_lock = threading.Lock()
_LIMIT = 2 * 1024 * 1024


def _decode(fd: int, arguments: list[str], timeout: float) -> bytes:
    """Only the selected open file, system libraries and temporary storage are visible."""
    if not all(Path(p).is_file() for p in ('/usr/bin/bwrap', '/usr/bin/prlimit', arguments[0])):
        raise OBSError('decoder_unavailable', 'Video extraction requires Bubblewrap, prlimit and FFmpeg')
    argv = ['/usr/bin/prlimit', '--as=2147483648', '--cpu=8', f'--fsize={_LIMIT}', '--',
            '/usr/bin/bwrap', '--die-with-parent', '--new-session', '--unshare-all',
            '--cap-drop', 'ALL', '--ro-bind', '/usr', '/usr']
    for name in ('lib', 'lib64', 'bin'):
        path = Path('/') / name
        if path.is_symlink():
            argv += ['--symlink', os.readlink(path), str(path)]
        elif path.exists():
            argv += ['--ro-bind', str(path), str(path)]
    argv += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/input',
             '--ro-bind-fd', str(fd), '/input/video', '--chdir', '/tmp',
             '--clearenv', '--setenv', 'PATH', '/usr/bin', '--setenv', 'HOME', '/tmp',
             '--setenv', 'LANG', 'C.UTF-8', '--', *arguments]
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        try:
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=output,
                                    stderr=errors, pass_fds=(fd,),
                                    env={'PATH': '/usr/bin', 'LANG': 'C.UTF-8'},
                                    timeout=max(0.1, min(8, timeout)))
        except subprocess.TimeoutExpired:
            raise OBSError('decode_timeout', 'Video decoding exceeded the time limit') from None
        if result.returncode:
            # Decoder errors can quote file contents; never expose them to the agent.
            raise OBSError('decode_failed', 'Video could not be decoded in the isolated decoder')
        output.seek(0)
        data = output.read(_LIMIT + 1)
        if not data or len(data) > _LIMIT:
            raise OBSError('decode_failed', 'Decoder output is empty or exceeds the limit')
        return data


def extract_frames(path: str, path_check, start_seconds: float = 0,
                   interval_seconds: float = 1, count: int = 3) -> dict:
    started = time.monotonic()
    if type(count) is not int or not 1 <= count <= 6:
        raise OBSError('invalid_arguments', 'count must be an integer from 1 to 6')
    for value, low, high, label in ((start_seconds, 0, 86400, 'start_seconds'),
                                  (interval_seconds, 0.1, 60, 'interval_seconds')):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise OBSError('invalid_arguments', f'{label} must be finite and between {low} and {high}')
    source = Path(path_check(path))
    if source.suffix.lower() not in ('.mkv', '.mp4', '.webm', '.mov'):
        raise OBSError('invalid_video', 'Use a completed MKV, MP4, WebM or MOV recording')
    if not _lock.acquire(timeout=1):
        raise OBSError('busy', 'Another video extraction is running')
    fd = None
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        # Verify the actual opened target, including concurrent parent-symlink changes.
        path_check(str(Path(f'/proc/self/fd/{fd}').resolve()))
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= 8 * 1024**3:
            raise OBSError('invalid_video', 'Video must be a regular file of at most 8 GiB')
        common = ['-v', 'error', '-max_alloc', '134217728',
                  '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'matroska,webm,mov',
                  '-probesize', '5000000', '-analyzeduration', '3000000']
        probe = json.loads(_decode(fd, ['/usr/bin/ffprobe', *common,
                         '-select_streams', 'v:0', '-show_entries',
                         'format=duration:stream=width,height', '-of', 'json', '/input/video'], 5))
        duration = float(probe.get('format', {}).get('duration', 0))
        streams = probe.get('streams', [])
        if not math.isfinite(duration) or duration <= 0 or not streams:
            raise OBSError('invalid_video', 'Video must have a finalized duration and a video stream')
        width, height = streams[0].get('width', 0), streams[0].get('height', 0)
        if not 0 < width <= 16384 or not 0 < height <= 16384:
            raise OBSError('invalid_video', 'Video dimensions exceed supported limits')
        times = [round(start_seconds + i * interval_seconds, 6) for i in range(count)]
        if times[-1] >= duration:
            raise OBSError('invalid_arguments', f'Last requested frame must be before duration {duration:.3f}s')
        frames = []
        for timestamp in times:
            remaining = 20 - (time.monotonic() - started)
            if remaining <= 0:
                raise OBSError('decode_timeout', 'Video sampling exceeded 20 seconds')
            encoded = _decode(fd, ['/usr/bin/ffmpeg', *common, '-nostdin', '-threads', '1',
                            '-ss', str(timestamp), '-i', '/input/video', '-map', '0:v:0',
                            '-an', '-sn', '-dn', '-frames:v', '1', '-filter_threads', '1',
                            '-vf', 'scale=w=min(960\\,iw):h=min(540\\,ih):force_original_aspect_ratio=decrease',
                            '-c:v', 'mjpeg', '-q:v', '4', '-threads', '1',
                            '-f', 'image2pipe', 'pipe:1'], remaining)
            if not encoded.startswith(b'\xff\xd8') or not encoded.endswith(b'\xff\xd9'):
                raise OBSError('decode_failed', 'Decoder did not return a complete JPEG frame')
            frames.append({'requested_time_seconds': timestamp,
                           'data': base64.b64encode(encoded).decode(), 'mime_type': 'image/jpeg'})
        after = os.fstat(fd)
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise OBSError('video_changed', 'Recording changed during extraction; stop recording before sampling')
        return {'ok': True, 'path': str(source), 'duration_seconds': duration,
                'source_width': width, 'source_height': height,
                'elapsed_ms': round((time.monotonic() - started) * 1000, 1),
                'sampled_only': True, 'audio_analyzed': False, 'frames': frames}
    finally:
        if fd is not None:
            os.close(fd)
        _lock.release()
