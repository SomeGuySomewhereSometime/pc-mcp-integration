from __future__ import annotations

import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from security import (checked_path, minimal_environment, run_sandbox, sandbox_network_enabled,
                      validate_filesystem_policy)
from applications import Application, launch_application


# Toda esta árvore fica disponível para a bridge.
WORKSPACE = Path(
    os.environ.get(
        "BRIDGE_WORKSPACE",
        "/home/user/Projects",
    )
).expanduser().resolve()

# run_command uses the same configured workspace as the rest of the bridge.
# Bubblewrap remains enabled; only the mounted home subtree follows WORKSPACE.
COMMAND_WORKSPACE = WORKSPACE

CONFIG_PATH = Path(
    os.environ.get(
        "BRIDGE_CONFIG",
        str(Path(__file__).with_name("bridge_config.json")),
    )
).expanduser().resolve()


def load_bridge_config() -> dict:
    """Load host-control policy once at startup."""
    if not CONFIG_PATH.exists():
        raise RuntimeError(f"Required bridge config is missing: {CONFIG_PATH}")
    try:
        payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid bridge config {CONFIG_PATH}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Invalid bridge config {CONFIG_PATH}: root must be an object"
        )
    validate_filesystem_policy(payload)
    return payload


BRIDGE_CONFIG = load_bridge_config()

app = FastAPI(
    title="ChatGPT Local Bridge",
    version="0.6.5",
)


# ---------------------------------------------------------------------------
# Segurança de caminhos
# ---------------------------------------------------------------------------

def safe_path(path: str = ".", *, write: bool = False,
              follow_leaf: bool = True, tree: bool = False) -> Path:
    return checked_path(WORKSPACE, BRIDGE_CONFIG, path, write=write,
                        follow_leaf=follow_leaf, tree=tree)


def relative(path: Path) -> str:
    return str(path.relative_to(WORKSPACE)) or "."


def safe_command_path(path: str = ".") -> Path:
    return checked_path(COMMAND_WORKSPACE, BRIDGE_CONFIG, path)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class PathRequest(BaseModel):
    path: str = "."


class SearchRequest(BaseModel):
    query: str
    path: str = "."


class WriteRequest(BaseModel):
    path: str
    content: str


class PatchRequest(BaseModel):
    patch: str
    cwd: str = "."


class CommandRequest(BaseModel):
    command: str
    cwd: str = "."
    timeout: int = 60


class GitRequest(BaseModel):
    cwd: str = "."


class ProcessListRequest(BaseModel):
    query: str = ""
    limit: int = 200
    include_args: bool = False


class ProcessKillRequest(BaseModel):
    pid: int
    signal: str = "TERM"


class ProcessInfoRequest(BaseModel):
    pid: int


class JournalQueryRequest(BaseModel):
    query: str = ""
    since_minutes: int = 60
    limit: int = 200
    kernel_only: bool = False


class ScreenCaptureRequest(BaseModel):
    path: str = ""
    interactive: bool = False
    include_cursor: bool = True


class AppLaunchRequest(BaseModel):
    app: str
    args: list[str] = []
    cwd: str = "."


class AppCloseRequest(BaseModel):
    handle: str
    force: bool = False


class MkdirRequest(BaseModel):
    path: str
    parents: bool = True
    exist_ok: bool = True


class MoveRequest(BaseModel):
    source: str
    destination: str
    overwrite: bool = False


class DeleteRequest(BaseModel):
    path: str
    recursive: bool = False


# ---------------------------------------------------------------------------
# Proteção básica contra comandos destrutivos
# ---------------------------------------------------------------------------

BLOCKED_PATTERNS = [
    r"(^|\s)sudo(\s|$)",
    r"(^|\s)su(\s|$)",
    r"(^|\s)shutdown(\s|$)",
    r"(^|\s)reboot(\s|$)",
    r"(^|\s)poweroff(\s|$)",
    r"(^|\s)mkfs",
    r"(^|\s)mount(\s|$)",
    r"(^|\s)umount(\s|$)",
    r"(^|\s)rm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-rf|-fr)\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-[a-zA-Z]*f",
    r"\bgit\s+checkout\s+--\s+\.",
    r"\bgit\s+restore\s+\.",
    r"\bdd\s+if=",
]


def command_is_blocked(command: str) -> bool:
    return any(
        re.search(pattern, command, flags=re.IGNORECASE)
        for pattern in BLOCKED_PATTERNS
    )


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "ok": True,
        "version": "0.6.5",
        "workspace": str(WORKSPACE),
        "workspace_exists": WORKSPACE.exists(),
        "command_workspace": str(COMMAND_WORKSPACE),
        "bubblewrap": Path("/usr/bin/bwrap").exists(),
    }


# ---------------------------------------------------------------------------
# Ficheiros
# ---------------------------------------------------------------------------

@app.post("/list_directory")
def list_directory(req: PathRequest):
    path = safe_path(req.path)

    if not path.exists():
        raise HTTPException(404, "Path does not exist")

    if not path.is_dir():
        raise HTTPException(400, "Path is not a directory")

    entries = []

    for item in sorted(
        path.iterdir(),
        key=lambda p: (not p.is_dir(), p.name.lower()),
    ):
        try:
            safe_path(str(item))
        except HTTPException:
            continue
        entries.append(
            {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            }
        )

    return {
        "path": relative(path),
        "entries": entries,
    }


@app.post("/read_file")
def read_file(req: PathRequest):
    path = safe_path(req.path)

    if not path.exists():
        raise HTTPException(404, "File does not exist")

    if not path.is_file():
        raise HTTPException(400, "Path is not a file")

    if path.stat().st_size > 2_000_000:
        raise HTTPException(
            413,
            "File too large for read_file (>2 MB)",
        )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File is not UTF-8 text")

    return {
        "path": relative(path),
        "content": content,
    }


@app.post("/search")
def search(req: SearchRequest):
    root = safe_path(req.path)

    if not root.exists():
        raise HTTPException(404, "Search path does not exist")

    result = run_sandbox(WORKSPACE, root if root.is_dir() else root.parent, BRIDGE_CONFIG,
        ["/usr/bin/grep", "-rInI", "--exclude-dir=.git", "--exclude-dir=node_modules",
         "--exclude-dir=.venv", "--", req.query, str(root)], timeout=30, read_only=True)

    # grep:
    # 0 = encontrou
    # 1 = não encontrou
    if result.returncode not in (0, 1):
        raise HTTPException(
            500,
            result.stderr.strip(),
        )

    output = result.stdout

    if len(output) > 100_000:
        output = output[:100_000] + "\n...[truncated]"

    return {
        "matches": output,
    }


@app.post("/write_file")
def write_file(req: WriteRequest):
    path = safe_path(req.path, write=True)

    if len(req.content.encode("utf-8")) > 5_000_000:
        raise HTTPException(
            413,
            "Content too large (>5 MB)",
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        req.content,
        encoding="utf-8",
    )

    return {
        "ok": True,
        "path": relative(path),
    }


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

@app.post("/apply_patch")
def apply_patch(req: PatchRequest):
    cwd = safe_path(req.cwd)

    if not cwd.is_dir():
        raise HTTPException(
            400,
            "cwd is not a directory",
        )

    result = run_sandbox(WORKSPACE, cwd, BRIDGE_CONFIG,
                         ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "apply", "--whitespace=nowarn", "-"],
                         input_text=req.patch, timeout=30)

    if result.returncode != 0:
        raise HTTPException(
            400,
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )

    return {
        "ok": True,
        "cwd": relative(cwd),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


# ---------------------------------------------------------------------------
# Shell isolada com Bubblewrap
# ---------------------------------------------------------------------------

@app.post("/run_command")
def run_command(req: CommandRequest):
    cwd = safe_command_path(req.cwd)

    if not cwd.is_dir():
        raise HTTPException(
            400,
            "cwd is not a directory",
        )

    command = req.command.strip()

    if not command:
        raise HTTPException(
            400,
            "Empty command",
        )

    if command_is_blocked(command):
        raise HTTPException(
            403,
            "DENIED: potentially destructive command",
        )

    timeout = max(
        1,
        min(req.timeout, 300),
    )

    result = run_sandbox(COMMAND_WORKSPACE, cwd, BRIDGE_CONFIG,
                         ["/bin/bash", "--noprofile", "--norc", "-c", command], timeout=timeout)

    stdout = result.stdout
    stderr = result.stderr

    if len(stdout) > 200_000:
        stdout = (
            stdout[:200_000]
            + "\n...[truncated]"
        )

    if len(stderr) > 200_000:
        stderr = (
            stderr[:200_000]
            + "\n...[truncated]"
        )

    return {
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "cwd": str(cwd.relative_to(COMMAND_WORKSPACE)) or ".",
        "sandboxed": True,
        "network": sandbox_network_enabled(BRIDGE_CONFIG),
    }


# ---------------------------------------------------------------------------
# Development / computer bridge
# ---------------------------------------------------------------------------

# Host-control tools are deny-by-default and use bridge_config.json.
LAUNCHED_APPS: dict[str, Application] = {}
LAUNCHED_APP_META: dict[str, dict[str, str | int]] = {}


def _config_section(name: str) -> dict:
    value = BRIDGE_CONFIG.get(name, {})
    return value if isinstance(value, dict) else {}


def _application_policy(name: str) -> dict:
    apps = _config_section("applications")
    value = apps.get(name)
    if not isinstance(value, dict):
        raise HTTPException(403, f"DENIED: application is not allowlisted: {name}")
    return value


def _configured_executable(policy: dict) -> Path:
    raw = str(policy.get("executable", "")).strip()
    if not raw or not Path(raw).is_absolute():
        raise HTTPException(500, "Configured application executable must be an absolute path")
    executable = Path(raw).resolve()
    if not executable.exists() or not executable.is_file():
        raise HTTPException(500, f"Configured application executable does not exist: {raw}")
    if not os.access(executable, os.X_OK):
        raise HTTPException(500, f"Configured application is not executable: {raw}")
    return executable


def _existing_application(policy: dict) -> int | None:
    """Find a configured Editor without launching a duplicate or taking ownership."""
    executables = {str(Path(x).resolve()) for x in policy.get("running_executables", [])}
    prefixes = [str(Path(x).resolve()) + os.sep for x in policy.get("running_executable_prefixes", [])]
    required_args = policy.get("running_required_args", [])
    if not executables and not prefixes:
        return None
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            exe = str((process / "exe").resolve(strict=True))
            if exe not in executables and not any(exe.startswith(x) for x in prefixes):
                continue
            argv = (process / "cmdline").read_bytes().decode(errors="replace").split("\0")
            if required_args and not any(argv[i:i + len(required_args)] == required_args for i in range(len(argv))):
                continue
            return int(process.name)
        except (OSError, ValueError):
            continue
    return None


def desktop_environment() -> dict[str, str]:
    """Return an environment capable of joining the user's desktop session."""
    env = minimal_environment(desktop=True)
    uid = os.getuid()
    runtime_dir = env.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env.setdefault("XDG_RUNTIME_DIR", runtime_dir)
    bus = Path(runtime_dir) / "bus"
    if bus.exists():
        env.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={bus}")
    if not env.get("WAYLAND_DISPLAY"):
        sockets = [
            item for item in sorted(Path(runtime_dir).glob("wayland-*"))
            if not item.name.endswith(".lock")
        ]
        if sockets:
            env["WAYLAND_DISPLAY"] = sockets[0].name
    return env


def _process_executable(pid: int) -> Path | None:
    try:
        return Path(f"/proc/{pid}/exe").resolve(strict=True)
    except (FileNotFoundError, PermissionError, OSError):
        return None


def ensure_killable_pid(pid: int) -> Path:
    if pid <= 1:
        raise HTTPException(403, "DENIED: refusing to signal PID 1 or lower")
    if pid in {os.getpid(), os.getppid()}:
        raise HTTPException(403, "DENIED: refusing to signal the bridge process")
    proc = Path(f"/proc/{pid}")
    if not proc.exists():
        raise HTTPException(404, f"Process {pid} does not exist")
    try:
        owner_uid = proc.stat().st_uid
    except OSError as exc:
        raise HTTPException(400, f"Cannot inspect process {pid}: {exc}") from exc
    if owner_uid != os.getuid():
        raise HTTPException(403, "DENIED: process is owned by another user")
    executable = _process_executable(pid)
    if executable is None:
        raise HTTPException(403, "DENIED: cannot verify process executable")
    policy = _config_section("process_kill")
    configured = policy.get("allowed_executables", [])
    allowed = {
        str(Path(item).expanduser().resolve())
        for item in configured
        if isinstance(item, str) and Path(item).is_absolute()
    }
    prefixes = [
        str(Path(item).expanduser().resolve()) + os.sep
        for item in policy.get("allowed_executable_prefixes", [])
        if isinstance(item, str) and Path(item).is_absolute()
    ]
    executable_text = str(executable)
    if executable_text not in allowed and not any(
        executable_text.startswith(prefix) for prefix in prefixes
    ):
        raise HTTPException(403, f"DENIED: process executable is not allowlisted: {executable}")
    return executable


def _signal_number(name: str) -> int:
    normalized = name.upper().removeprefix("SIG")
    mapping = {
        "TERM": signal.SIGTERM,
        "KILL": signal.SIGKILL,
        "INT": signal.SIGINT,
        "HUP": signal.SIGHUP,
    }
    configured = _config_section("process_kill").get("allowed_signals", ["TERM", "INT"])
    allowed_names = {
        str(item).upper().removeprefix("SIG")
        for item in configured
        if isinstance(item, str)
    }
    if normalized not in mapping or normalized not in allowed_names:
        allowed_display = ", ".join(sorted(allowed_names)) or "none"
        raise HTTPException(403, f"DENIED: signal is not allowlisted (allowed: {allowed_display})")
    return mapping[normalized]


def _default_capture_path() -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return safe_path(
        f".chatgpt-bridge/screenshots/screenshot-{stamp}-{uuid.uuid4().hex[:6]}.png"
    )


def _portal_capture(interactive: bool, timeout: int = 30) -> str:
    """Capture through xdg-desktop-portal using system D-Bus bindings."""
    helper = r'''
import json, sys, uuid
import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

DBusGMainLoop(set_as_default=True)
interactive = sys.argv[1] == "1"
timeout = int(sys.argv[2])
loop = GLib.MainLoop()
bus = dbus.SessionBus()
token = "chatgpt" + uuid.uuid4().hex
state = {"done": False}

def on_response(code, results, path=None):
    if path and not str(path).endswith("/" + token):
        return
    state["done"] = True
    state["code"] = int(code)
    state["results"] = {str(k): str(v) for k, v in dict(results).items()}
    loop.quit()

bus.add_signal_receiver(
    on_response,
    signal_name="Response",
    dbus_interface="org.freedesktop.portal.Request",
    path_keyword="path",
)
portal = bus.get_object(
    "org.freedesktop.portal.Desktop",
    "/org/freedesktop/portal/desktop",
)
iface = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
request_path = iface.Screenshot(
    "",
    {
        "handle_token": dbus.String(token),
        "interactive": dbus.Boolean(interactive),
    },
)

def timed_out():
    if not state["done"]:
        state["error"] = "portal screenshot timed out"
        loop.quit()
    return False

GLib.timeout_add_seconds(timeout, timed_out)
loop.run()
if state.get("code") == 0 and state.get("results", {}).get("uri"):
    print(json.dumps({
        "ok": True,
        "uri": state["results"]["uri"],
        "request": str(request_path),
    }))
else:
    print(json.dumps({"ok": False, **state, "request": str(request_path)}))
    sys.exit(2)
'''
    env = desktop_environment()
    system_python = "/usr/bin/python3"
    if not Path(system_python).exists():
        raise RuntimeError("/usr/bin/python3 is unavailable for portal D-Bus helper")
    result = subprocess.run(
        [system_python, "-c", helper, "1" if interactive else "0", str(timeout)],
        capture_output=True,
        text=True,
        timeout=timeout + 5,
        env=env,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "portal capture failed"
        raise RuntimeError(detail)
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError(f"Invalid portal response: {result.stdout!r}") from exc
    uri = payload.get("uri")
    if not uri:
        raise RuntimeError(f"Portal did not return a screenshot URI: {payload}")
    return str(uri)


def _gnome_screenshot_cli(destination: Path, include_cursor: bool) -> None:
    executable = shutil.which("gnome-screenshot")
    if not executable:
        raise RuntimeError("gnome-screenshot is not installed")
    args = [executable, "--file", str(destination)]
    if include_cursor:
        args.insert(1, "--include-pointer")
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=20,
        env=desktop_environment(),
    )
    if result.returncode != 0 or not destination.exists():
        detail = result.stderr.strip() or result.stdout.strip() or "gnome-screenshot failed"
        raise RuntimeError(detail)


def _gnome_capture(destination: Path, include_cursor: bool) -> None:
    """Fallback for GNOME sessions where Shell grants Screenshot access."""
    env = desktop_environment()
    result = subprocess.run(
        [
            "/usr/bin/gdbus", "call", "--session",
            "--dest", "org.gnome.Shell.Screenshot",
            "--object-path", "/org/gnome/Shell/Screenshot",
            "--method", "org.gnome.Shell.Screenshot.Screenshot",
            "true" if include_cursor else "false",
            "false",
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
    )
    if result.returncode != 0 or not destination.exists():
        detail = result.stderr.strip() or result.stdout.strip() or "GNOME screenshot failed"
        raise RuntimeError(detail)


@app.get("/system_info")
def system_info():
    os_release = {}
    release_path = Path("/etc/os-release")
    if release_path.exists():
        for line in release_path.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                os_release[key] = value.strip().strip('"')
    uptime_seconds = None
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    env = desktop_environment()
    return {
        "hostname": socket.gethostname(),
        "os": os_release.get("PRETTY_NAME", platform.platform()),
        "kernel": platform.release(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "uid": os.getuid(),
        "workspace": str(WORKSPACE),
        "command_workspace": str(COMMAND_WORKSPACE),
        "config": str(CONFIG_PATH),
        "uptime_seconds": uptime_seconds,
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "session_type": os.environ.get("XDG_SESSION_TYPE", ""),
        "wayland_display": env.get("WAYLAND_DISPLAY", ""),
        "dbus_session": bool(env.get("DBUS_SESSION_BUS_ADDRESS")),
        "bubblewrap": Path("/usr/bin/bwrap").exists(),
    }


@app.post("/process_list")
def process_list(req: ProcessListRequest):
    limit = max(1, min(req.limit, 1000))
    fields = (
        "pid=,ppid=,user=,stat=,etime=,comm=,args="
        if req.include_args
        else "pid=,ppid=,user=,stat=,etime=,comm="
    )
    result = subprocess.run(
        ["ps", "-eo", fields],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise HTTPException(500, result.stderr.strip() or "ps failed")
    query = req.query.casefold().strip()
    processes = []
    maxsplit = 6 if req.include_args else 5
    for line in result.stdout.splitlines():
        parts = line.strip().split(None, maxsplit)
        if len(parts) < 6:
            continue
        pid, ppid, user, stat, elapsed, command = parts[:6]
        item = {
            "pid": int(pid),
            "ppid": int(ppid),
            "user": user,
            "state": stat,
            "elapsed": elapsed,
            "command": command,
        }
        if req.include_args:
            item["args"] = parts[6] if len(parts) > 6 else ""
        if query and query not in " ".join(map(str, item.values())).casefold():
            continue
        processes.append(item)
        if len(processes) >= limit:
            break
    return {
        "processes": processes,
        "count": len(processes),
        "limit": limit,
        "include_args": req.include_args,
    }


def _read_proc_text(proc: Path, name: str, *, limit: int = 64_000) -> str:
    try:
        data = (proc / name).read_bytes()[:limit]
    except (FileNotFoundError, PermissionError, OSError):
        return ""
    return data.decode(errors="replace").rstrip("\n")


@app.post("/process_info")
def process_info(req: ProcessInfoRequest):
    if req.pid <= 0:
        raise HTTPException(400, "PID must be positive")
    proc = Path(f"/proc/{req.pid}")
    if not proc.exists():
        raise HTTPException(404, f"Process {req.pid} does not exist")
    try:
        owner_uid = proc.stat().st_uid
    except OSError as exc:
        raise HTTPException(400, f"Cannot inspect process {req.pid}: {exc}") from exc
    if owner_uid != os.getuid():
        raise HTTPException(403, "DENIED: process is owned by another user")

    status = {}
    for line in _read_proc_text(proc, "status").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in {"Name", "State", "Pid", "PPid", "Threads", "Uid", "Gid"}:
                status[key.lower()] = value.strip()

    executable = _process_executable(req.pid)
    try:
        cwd = str((proc / "cwd").resolve(strict=True))
    except (FileNotFoundError, PermissionError, OSError):
        cwd = ""
    cmdline = _read_proc_text(proc, "cmdline").replace("\x00", " ").strip()
    apparmor_label = _read_proc_text(proc, "attr/current", limit=4096)
    cgroup = _read_proc_text(proc, "cgroup", limit=16_000)
    namespaces = {}
    for name in ("pid", "mnt", "net", "ipc", "user"):
        try:
            namespaces[name] = os.readlink(proc / "ns" / name)
        except OSError:
            pass
    return {
        "pid": req.pid,
        "owner_uid": owner_uid,
        "status": status,
        "executable": str(executable) if executable else "",
        "cwd": cwd,
        "cmdline": cmdline,
        "apparmor_label": apparmor_label,
        "cgroup": cgroup,
        "namespaces": namespaces,
    }


@app.post("/journal_query")
def journal_query(req: JournalQueryRequest):
    query = req.query.strip()
    if len(query) > 200:
        raise HTTPException(400, "Query is too long")
    since_minutes = max(1, min(req.since_minutes, 1440))
    limit = max(1, min(req.limit, 500))
    argv = [
        "/usr/bin/journalctl", "--no-pager", "--output=short-iso",
        "--since", f"{since_minutes} minutes ago", "-n", "2000",
    ]
    if req.kernel_only:
        argv.append("--dmesg")
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=20, env=minimal_environment())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(500, f"journalctl failed: {exc}") from exc
    if result.returncode != 0:
        raise HTTPException(500, result.stderr.strip() or "journalctl failed")
    lines = result.stdout.splitlines()
    if query:
        folded = query.casefold()
        lines = [line for line in lines if folded in line.casefold()]
    lines = lines[-limit:]
    return {
        "query": query,
        "since_minutes": since_minutes,
        "kernel_only": req.kernel_only,
        "count": len(lines),
        "lines": lines,
    }


@app.post("/process_kill")
def process_kill(req: ProcessKillRequest):
    executable = ensure_killable_pid(req.pid)
    sig = _signal_number(req.signal)
    try:
        os.kill(req.pid, sig)
    except ProcessLookupError:
        raise HTTPException(404, f"Process {req.pid} no longer exists")
    except PermissionError as exc:
        raise HTTPException(403, f"Permission denied signalling process {req.pid}") from exc
    return {
        "ok": True,
        "pid": req.pid,
        "executable": str(executable),
        "signal": signal.Signals(sig).name,
    }


@app.post("/screen_capture")
def screen_capture(req: ScreenCaptureRequest):
    destination = safe_path(req.path, write=True) if req.path.strip() else _default_capture_path()
    destination = safe_path(str(destination), write=True)
    if destination.suffix.lower() != ".png":
        raise HTTPException(400, "Screenshot path must end in .png")
    if destination.exists() and destination.is_dir():
        raise HTTPException(400, "Screenshot path is a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    backend = ""

    # xdg-desktop-portal is the supported Wayland path on Ubuntu/GNOME.
    # It may show the compositor's consent UI. GNOME Shell D-Bus and the
    # legacy CLI remain fallbacks for sessions where they are permitted.
    try:
        uri = _portal_capture(req.interactive)
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise RuntimeError(f"Unsupported portal URI: {uri}")
        source = Path(unquote(parsed.path))
        if not source.exists():
            raise RuntimeError(f"Portal screenshot file does not exist: {source}")
        shutil.copy2(source, destination)
        backend = "xdg-desktop-portal"
    except Exception as exc:
        errors.append(f"portal: {exc}")

    if not backend:
        try:
            _gnome_capture(destination, req.include_cursor)
            backend = "org.gnome.Shell.Screenshot"
        except Exception as exc:
            errors.append(f"gnome-shell: {exc}")

    if not backend:
        try:
            _gnome_screenshot_cli(destination, req.include_cursor)
            backend = "gnome-screenshot"
        except Exception as exc:
            errors.append(f"gnome-screenshot: {exc}")
            raise HTTPException(
                500,
                {
                    "message": "Screen capture failed",
                    "attempts": errors,
                    "hint": "Approve the xdg-desktop-portal screenshot request on GNOME/Wayland.",
                },
            ) from exc
    return {
        "ok": True,
        "path": relative(destination),
        "absolute_path": str(destination),
        "backend": backend,
        "bytes": destination.stat().st_size,
        "mime_type": "image/png",
    }


@app.post("/app_launch")
def app_launch(req: AppLaunchRequest):
    policy = _application_policy(req.app)
    executable = _configured_executable(policy)
    allow_args = bool(policy.get("allow_args", False))
    if req.args and not allow_args:
        raise HTTPException(403, f"DENIED: arguments are disabled for application: {req.app}")
    max_args = max(0, min(int(policy.get("max_args", 20)), 100))
    if len(req.args) > max_args:
        raise HTTPException(400, "Too many application arguments")
    if any("\x00" in arg or len(arg) > 4096 for arg in req.args):
        raise HTTPException(400, "Invalid application argument")
    existing = _existing_application(policy)
    if existing is not None:
        return {"ok": True, "app": req.app, "pid": existing, "already_running": True,
                "note": "Existing application reused; no close handle issued. Verify native MCP state."}
    fixed_args = policy.get("fixed_args", [])
    if not isinstance(fixed_args, list) or any(not isinstance(x, str) or "\x00" in x for x in fixed_args):
        raise HTTPException(500, "Invalid configured application arguments")
    cwd = safe_path(policy.get("cwd", req.cwd))
    if not cwd.is_dir():
        raise HTTPException(400, "cwd is not a directory")
    try:
        proc = launch_application(
            [str(executable), *fixed_args, *req.args],
            cwd=cwd,
            environment=desktop_environment(),
        )
    except OSError as exc:
        raise HTTPException(500, f"Failed to launch {req.app}: {exc}") from exc
    handle = uuid.uuid4().hex
    LAUNCHED_APPS[handle] = proc
    LAUNCHED_APP_META[handle] = {
        "app": req.app,
        "executable": str(executable),
        "pid": proc.pid,
    }
    return {
        "ok": True,
        "handle": handle,
        "pid": proc.pid,
        "app": req.app,
        "executable": str(executable),
        "cwd": relative(cwd),
        "unit": proc.unit,
    }


@app.post("/app_close")
def app_close(req: AppCloseRequest):
    proc = LAUNCHED_APPS.get(req.handle)
    meta = LAUNCHED_APP_META.get(req.handle, {})
    if proc is None:
        raise HTTPException(404, "Unknown app handle; app_close only accepts handles from app_launch")
    if proc.poll() is not None:
        LAUNCHED_APPS.pop(req.handle, None)
        LAUNCHED_APP_META.pop(req.handle, None)
        return {
            "ok": True,
            "handle": req.handle,
            "pid": proc.pid,
            "already_exited": True,
            "returncode": proc.returncode,
        }
    try:
        if req.force:
            proc.kill()
        else:
            proc.terminate()
    except ProcessLookupError:
        pass
    return {
        "ok": True,
        "handle": req.handle,
        "pid": proc.pid,
        "app": meta.get("app", ""),
        "signal": "SIGKILL" if req.force else "SIGTERM",
    }


@app.post("/mkdir")
def mkdir(req: MkdirRequest):
    path = safe_path(req.path, write=True)
    try:
        path.mkdir(parents=req.parents, exist_ok=req.exist_ok)
    except FileExistsError as exc:
        raise HTTPException(409, "Path already exists") from exc
    except OSError as exc:
        raise HTTPException(400, f"mkdir failed: {exc}") from exc
    return {"ok": True, "path": relative(path)}


@app.post("/move")
def move(req: MoveRequest):
    source = safe_path(req.source, write=True, follow_leaf=False, tree=True)
    destination = safe_path(req.destination, write=True, follow_leaf=False, tree=True)
    if source == destination or source.is_relative_to(destination) or destination.is_relative_to(source):
        raise HTTPException(403, "DENIED: source and destination must not overlap")
    if not source.exists() and not source.is_symlink():
        raise HTTPException(404, "Source does not exist")
    replacing = destination.exists() or destination.is_symlink()
    if replacing:
        if not req.overwrite:
            raise HTTPException(409, "Destination already exists; set overwrite=true to replace it")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if replacing:
            # Atomic replacement; a nonempty directory is never recursively erased.
            os.replace(source, destination)
            result = destination
        else:
            result = Path(shutil.move(str(source), str(destination)))
    except OSError as exc:
        raise HTTPException(400, f"move failed: {exc}") from exc
    return {
        "ok": True,
        "source": req.source,
        "destination": relative(result),
    }


@app.post("/delete")
def delete(req: DeleteRequest):
    path = safe_path(req.path, write=True, follow_leaf=False, tree=req.recursive)
    if path == WORKSPACE:
        raise HTTPException(403, "DENIED: cannot delete workspace root")
    if not path.exists() and not path.is_symlink():
        raise HTTPException(404, "Path does not exist")
    try:
        if path.is_dir() and not path.is_symlink():
            if req.recursive:
                shutil.rmtree(path)
            else:
                path.rmdir()
        else:
            path.unlink()
    except OSError as exc:
        raise HTTPException(400, f"delete failed: {exc}") from exc
    return {"ok": True, "path": req.path, "recursive": req.recursive}


# ---------------------------------------------------------------------------
# AI change log
# ---------------------------------------------------------------------------

class AIChangeRequest(BaseModel):
    cwd: str
    task: str
    files_changed: list[str] = []
    summary: str
    reason: str = ""
    tests: list[str] = []
    status: str = ""
    notes: str = ""
    agent: str = "ChatGPT"


@app.post("/append_ai_change")
def append_ai_change(req: AIChangeRequest):
    project = safe_path(req.cwd)

    if not project.exists() or not project.is_dir():
        raise HTTPException(
            400,
            "cwd is not a valid project directory",
        )

    log_path = safe_path(
        str(Path(req.cwd) / "AI_CHANGES.md"), write=True
    )

    from datetime import datetime

    timestamp = datetime.now().astimezone().strftime(
        "%Y-%m-%d %H:%M %Z"
    )

    lines = [
        "",
        f"## {timestamp} — {req.agent}",
        "",
        "### Tarefa",
        req.task.strip(),
        "",
    ]

    if req.files_changed:
        lines += [
            "### Ficheiros alterados",
            *[f"- `{item}`" for item in req.files_changed],
            "",
        ]

    lines += [
        "### Alterações",
        req.summary.strip(),
        "",
    ]

    if req.reason.strip():
        lines += [
            "### Motivo",
            req.reason.strip(),
            "",
        ]

    if req.tests:
        lines += [
            "### Testes",
            *[f"- {item}" for item in req.tests],
            "",
        ]

    if req.status.strip():
        lines += [
            "### Estado",
            req.status.strip(),
            "",
        ]

    if req.notes.strip():
        lines += [
            "### Observações",
            req.notes.strip(),
            "",
        ]

    entry = "\n".join(lines).rstrip() + "\n"

    if not log_path.exists():
        log_path.write_text(
            "# AI Changes\n",
            encoding="utf-8",
        )

    with log_path.open(
        "a",
        encoding="utf-8",
    ) as f:
        f.write(entry)

    return {
        "ok": True,
        "project": relative(project),
        "path": relative(log_path),
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

@app.post("/git_status")
def git_status(req: GitRequest):
    cwd = safe_path(req.cwd)

    result = run_sandbox(WORKSPACE, cwd, BRIDGE_CONFIG,
                         ["/usr/bin/git", "--no-optional-locks", "-c", "core.fsmonitor=false", "status", "--short"], timeout=30, read_only=True)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "cwd": relative(cwd),
    }


@app.post("/git_diff")
def git_diff(req: GitRequest):
    cwd = safe_path(req.cwd)

    result = run_sandbox(WORKSPACE, cwd, BRIDGE_CONFIG,
                         ["/usr/bin/git", "--no-optional-locks", "-c", "core.fsmonitor=false", "diff", "--no-ext-diff", "--no-textconv", "--"], timeout=30, read_only=True)

    output = result.stdout

    if len(output) > 200_000:
        output = (
            output[:200_000]
            + "\n...[truncated]"
        )

    return {
        "returncode": result.returncode,
        "diff": output,
        "stderr": result.stderr,
        "cwd": relative(cwd),
    }
