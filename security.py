"""Shared filesystem and process boundaries for the local development bridge."""
from __future__ import annotations

import os
import pwd
import subprocess
import threading
from pathlib import Path

from fastapi import HTTPException


def policy_paths(config: dict, section: str) -> list[Path]:
    values = config.get("filesystem", {}).get(section, [])
    if not isinstance(values, list) or any(not isinstance(x, str) or not Path(x).is_absolute() for x in values):
        raise RuntimeError(f"filesystem.{section} must contain absolute paths")
    return sorted({Path(x).resolve() for x in values}, key=lambda x: (len(x.parts), str(x)))


def validate_filesystem_policy(config: dict) -> None:
    filesystem = config.get("filesystem")
    if not isinstance(filesystem, dict):
        raise RuntimeError("Required filesystem policy is missing or invalid")
    for section in ("denied_paths", "read_only_paths"):
        if section not in filesystem or not policy_paths(config, section):
            raise RuntimeError(f"Required filesystem.{section} must be a nonempty list")


def checked_path(workspace: Path, config: dict, value: str, *, write: bool = False,
                 follow_leaf: bool = True, tree: bool = False) -> Path:
    raw = workspace / value
    candidate = raw.resolve() if follow_leaf or raw.name in {"", ".", ".."} else raw.parent.resolve() / raw.name
    if not candidate.is_relative_to(workspace):
        raise HTTPException(403, "DENIED: path outside workspace")
    denied = policy_paths(config, "denied_paths")
    protected = denied + (policy_paths(config, "read_only_paths") if write else [])
    for root in protected:
        if candidate.is_relative_to(root) or (tree and root.is_relative_to(candidate)):
            raise HTTPException(403, "DENIED: protected filesystem path")
    if write and candidate == workspace:
        raise HTTPException(403, "DENIED: cannot modify workspace root")
    return candidate


def minimal_environment(*, desktop: bool = False) -> dict[str, str]:
    account = pwd.getpwuid(os.getuid())
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin:/snap/bin",
        "HOME": account.pw_dir,
        "USER": account.pw_name,
        "LOGNAME": account.pw_name,
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if desktop:
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR",
                    "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP"):
            if key in os.environ:
                env[key] = os.environ[key]
    return env


def sandbox_network_enabled(config: dict) -> bool:
    """Return whether development commands may use the host network stack."""
    section = config.get("sandbox", {})
    return isinstance(section, dict) and section.get("network") is True


def sandbox_argv(workspace: Path, cwd: Path, config: dict, argv: list[str], *, read_only: bool = False,
                 git_config_fd: int | None = None) -> list[str]:
    """Hide host IPC and credentials; optionally retain host networking."""
    if not Path("/usr/bin/bwrap").exists():
        raise HTTPException(500, "bubblewrap is not installed")
    args = ["/usr/bin/bwrap", "--die-with-parent", "--new-session", "--unshare-all",
            "--cap-drop", "ALL"]
    if sandbox_network_enabled(config):
        # Keep mount/PID/IPC/user isolation but allow normal development traffic.
        # Credentials remain withheld because HOME and Git config stay private.
        args += ["--share-net"]
    args += ["--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev",
             "--tmpfs", "/tmp", "--tmpfs", "/run", "--tmpfs", "/home",
             "--dir", str(workspace), "--ro-bind" if read_only else "--bind", str(workspace), str(workspace)]
    if sandbox_network_enabled(config):
        # Ubuntu commonly points /etc/resolv.conf into /run/systemd/resolve.
        # Re-expose only resolver metadata needed for DNS, not the rest of /run.
        resolver = Path("/run/systemd/resolve")
        if resolver.is_dir():
            args += ["--dir", "/run/systemd", "--ro-bind", str(resolver), str(resolver)]
    # Optional tools outside a smaller workspace remain readable, never writable.
    node = Path("/home/user/.hermes/node")
    if node.exists() and not node.is_relative_to(workspace):
        args += ["--ro-bind", str(node), str(node)]
    denied = policy_paths(config, "denied_paths")
    for root in policy_paths(config, "read_only_paths"):
        if root.exists() and root.is_relative_to(workspace) and not any(root.is_relative_to(p) for p in denied):
            args += ["--ro-bind", str(root), str(root)]
    for root in denied:
        if not root.exists() or not root.is_relative_to(workspace):
            continue
        # An empty, read-only mount also prevents creating a replacement secret.
        if root.is_dir():
            args += ["--tmpfs", str(root), "--remount-ro", str(root)]
        else:
            args += ["--ro-bind", "/dev/null", str(root)]
    git_config = "/dev/null"
    if git_config_fd is not None:
        git_config = "/tmp/bridge-gitconfig"
        args += ["--ro-bind-data", str(git_config_fd), git_config]
    args += ["--chdir", str(cwd), "--setenv", "HOME", "/tmp",
             "--setenv", "TMPDIR", "/tmp", "--setenv", "GIT_CONFIG_GLOBAL", git_config,
             "--setenv", "GIT_CONFIG_SYSTEM", "/dev/null", "--", *argv]
    return args


def git_identity_config(cwd: Path, env: dict[str, str]) -> bytes:
    """Copy only global author defaults; repository-local identity keeps precedence."""
    result = subprocess.run(
        ["/usr/bin/git", "config", "--global", "--includes", "--null",
         "--get-regexp", r"^user\.(name|email)$"],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=5)
    if result.returncode not in (0, 1):
        raise HTTPException(500, "Cannot read Git author defaults")
    values = {}
    for item in result.stdout.split("\0"):
        if not item:
            continue
        key, value = item.split("\n", 1)
        if key not in {"user.name", "user.email"}:
            continue
        if len(value) > 512 or any(ord(c) < 32 for c in value):
            raise HTTPException(500, "Invalid Git author default")
        values[key] = value
    lines = ["[user]"]
    for key, value in values.items():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'\t{key.split(".")[1]} = "{escaped}"')
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_sandbox(workspace: Path, cwd: Path, config: dict, argv: list[str], *,
                timeout: int = 60, input_text: str | None = None, read_only: bool = False) -> subprocess.CompletedProcess:
    env = minimal_environment()
    env["PATH"] = "/home/user/.hermes/node/bin:/usr/local/bin:/usr/bin:/bin"
    fd = None
    try:
        identity = git_identity_config(cwd, env)
        fd = os.memfd_create("bridge-git-identity", os.MFD_CLOEXEC)
        os.write(fd, identity)
        os.lseek(fd, 0, os.SEEK_SET)
        # Reuse the bounded pipe reader for synchronous calls too. Import here avoids
        # the command-session launcher's dependency on these sandbox helpers.
        from command_sessions import Job
        command = sandbox_argv(workspace, cwd, config, argv, read_only=read_only, git_config_fd=fd)
        process = subprocess.Popen(command, stdin=subprocess.PIPE if input_text is not None else subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                   pass_fds=(fd,), start_new_session=True)
        job = Job(process, max(1, min(timeout, 300)), cwd)
        if input_text is not None:
            def feed():
                try:
                    process.stdin.write(input_text.encode())
                    process.stdin.flush()
                except BrokenPipeError:
                    pass
                finally:
                    process.stdin.close()
            threading.Thread(target=feed, daemon=True).start()
        job.done.wait()
        result = job.read(limit=262144)
        if job.timed_out:
            raise HTTPException(408, {'error': 'Operation exceeded its execution deadline',
                                     'stdout':result['stdout'], 'stderr':result['stderr']})
        out, err = result['stdout'], result['stderr']
        if result['output_truncated']:
            out = '[earlier output truncated]\n' + out
        return subprocess.CompletedProcess(command, process.returncode, out, err)
    finally:
        if fd is not None:
            os.close(fd)
