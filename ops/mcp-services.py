#!/home/user/.local/share/uv/tools/blender-mcp/bin/python
"""Bounded local service operations and read-only readiness checks."""
import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import socket
import subprocess
import urllib.request

PROFILES = {"bridge": ("chatgpt-local-bridge", 8080),
            "unity": ("chatgpt-unity", 8081), "blender": ("chatgpt-blender", 8082)}
PROJECT = Path("/home/user/Projects/ExampleGame")


def probe(url):
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return {"ok": response.status == 200, "status": response.status}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


async def unity_probe():
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    cfg = json.loads((PROJECT / "UserSettings/AI-Game-Developer-Config.json").read_text())
    # Only derive routing from non-secret fields. Never return the full config.
    pin = hashlib.sha256(str(PROJECT).rstrip("/\\").lower().encode()).hexdigest()[:8]
    url = cfg["host"].rstrip("/") + "/p/" + pin
    async with streamablehttp_client(url, timeout=5) as (read, write, _):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            if "editor-application-get-state" not in names:
                return {"mcp": True, "application": False, "reason": "editor state tool disabled", "tools": len(names)}
            state = await session.call_tool("editor-application-get-state", {})
            scenes = await session.call_tool("scene-list-opened", {})
            return {"mcp": True, "application": not state.isError and not scenes.isError,
                    "server_version": init.serverInfo.version, "tools": len(names), "endpoint": url,
                    "editor_state": state.structuredContent, "scenes": scenes.structuredContent}


def blender_probe():
    with socket.create_connection(("127.0.0.1", 9876), timeout=3) as sock:
        sock.settimeout(4)
        sock.sendall(json.dumps({"type": "get_addon_info", "params": {}}).encode())
        data = b""
        while len(data) < 65536:
            chunk = sock.recv(8192)
            if not chunk:
                raise RuntimeError("addon disconnected")
            data += chunk
            try:
                reply = json.loads(data)
                result = reply.get("result", {})
                return {"application": reply.get("status") == "success",
                        "blender_version": result.get("blender_version"),
                        "protocol": result.get("protocol_version"),
                        "addon_version": result.get("addon_version")}
            except json.JSONDecodeError:
                continue
        raise RuntimeError("addon response too large")


def status(selected):
    result = {}
    for name in selected:
        profile, port = PROFILES[name]
        unit = "mcp-tunnel-" + profile + ".service"
        service = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=5)
        item = {"service": service.stdout.strip(), "tunnel_live": probe(f"http://127.0.0.1:{port}/healthz"),
                "tunnel_ready": probe(f"http://127.0.0.1:{port}/readyz")}
        if name in {"bridge", "blender"}:
            from supervise import has_stdio_child
            marker = b'/chatgpt-local-bridge/mcp_server.py' if name == 'bridge' else b'/mcp-integration/blender_entry.py'
            backend = False
            for proc in Path('/proc').iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    argv = (proc / 'cmdline').read_bytes().split(b'\0')
                    if argv[0] and Path(os.fsdecode(argv[0])).name == 'tunnel-client' and profile.encode() in argv:
                        backend = has_stdio_child(int(proc.name), marker)
                        break
                except OSError:
                    continue
            item['mcp_process_present'] = backend
        try:
            if name == "unity":
                item.update(asyncio.run(asyncio.wait_for(unity_probe(), 15)))
            elif name == "blender":
                item.update(blender_probe())
            else:
                item["application"] = "filesystem backend; use system_info/get_session_context in ChatGPT for end-to-end verification"
        except Exception as exc:
            item.update({"application": False, "probe_error": type(exc).__name__})
        if name == "unity":
            profile_text = (Path("/home/user/.config/tunnel-client") / (profile + ".yaml")).read_text()
            pin = hashlib.sha256(str(PROJECT).lower().encode()).hexdigest()[:8]
            item["profile_pin_matches_project"] = "/p/" + pin in profile_text
        result[name] = item
    return result


def main():
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "start", "stop", "restart"])
    parser.add_argument("component", nargs="?", choices=["all", *PROFILES], default="all")
    args = parser.parse_args()
    selected = list(PROFILES) if args.component == "all" else [args.component]
    if args.action != "status":
        units = ["mcp-tunnel-" + PROFILES[n][0] + ".service" for n in selected]
        subprocess.run(["systemctl", "--user", args.action, *units], check=True, timeout=45)
    print(json.dumps(status(selected), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
