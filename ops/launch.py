#!/usr/bin/python3
"""Launch fixed MCP programs without inheriting transport credentials."""
import os
from pathlib import Path
import sys

ROOT = Path("/home/user")
env = {"HOME": str(ROOT), "USER": "user", "LOGNAME": "user",
       "PATH": "/usr/local/bin:/usr/bin:/bin:/snap/bin", "LANG": "C.UTF-8",
       "PYTHONDONTWRITEBYTECODE": "1"}
for key in ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP"):
    if key in os.environ:
        env[key] = os.environ[key]
mode = sys.argv[1] if len(sys.argv) == 2 else ""
if mode == "bridge":
    env["BRIDGE_WORKSPACE"] = str(ROOT)
    command = [str(ROOT / "chatgpt-local-bridge/.venv/bin/python"), "-B",
               str(ROOT / "chatgpt-local-bridge/mcp_server.py")]
elif mode == "blender":
    env.update({"BLENDER_MCP_DISABLE_TELEMETRY": "1", "BLENDER_HOST": "127.0.0.1", "BLENDER_PORT": "9876"})
    command = [str(ROOT / ".local/share/uv/tools/blender-mcp/bin/python"), "-B",
               str(ROOT / ".local/lib/mcp-integration/blender_entry.py")]
elif mode in {"tunnel-bridge", "tunnel-unity", "tunnel-blender"}:
    profile = {"tunnel-bridge": "chatgpt-local-bridge", "tunnel-unity": "chatgpt-unity",
               "tunnel-blender": "chatgpt-blender"}[mode]
    command = [str(ROOT / ".local/bin/tunnel-client"), "run", "--profile-dir",
               str(ROOT / ".config/tunnel-client"), "--profile", profile]
else:
    raise SystemExit("Usage: launch.py bridge|blender")
os.chdir(ROOT / "chatgpt-local-bridge" if mode == "bridge" else ROOT)
if mode.startswith("tunnel-"):
    from supervise import supervise
    raise SystemExit(supervise(command, env, mode))
os.execve(command[0], command, env)
