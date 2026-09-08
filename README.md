# PC MCP integration

Private backup of the three MCP integrations used to reach this computer from
ChatGPT: Local Dev Bridge, Unity AI Game Developer and Blender MCP.

The repository contains the Bridge source, dependency locks, launchers, process
supervisor, three user systemd services, tunnel profiles with credential file
references, Unity MCP settings/package versions, the installed Blender addon and
global agent instructions. See [RESTORE.md](RESTORE.md) for the installation map
and recovery procedure. The snapshot targets the current `/home/user` layout.

Access keys, login sessions and cloud-side ChatGPT connections must be retained
separately. Unity projects, Blender scenes, editor binaries and virtual environments
are not part of this integration backup. Publishing this repository does not
change the running installation or the account associated with the tunnels.

## Local Development Bridge 0.4.1

Python MCP server for `/home/user`. Code and file operations belong here;
live Blender and Unity state belongs to their respective MCPs.

Start each ChatGPT session with `get_session_context(cwd=<project>)` and inspect
the live tool inventory. Global AGENTS.md is also included in MCP initialization.
Refresh the plugin's tools in ChatGPT after changing the server's tool catalog.

## Boundaries

- `bridge_config.json` lists protected credential paths, read-only control paths,
  application aliases and process signal policy. The remainder of the configured
  workspace stays available for normal project editing.
- File reads/writes validate paths. Recursive search, patches, Git and shell run
  through Bubblewrap; host `/run`, `/tmp`, `/proc` and home mounts are isolated.
- The shell has no network and uses no login/profile scripts. Its HOME is private
  `/tmp`; use explicit project paths. Project dependencies already installed remain
  available. Do not use Blender/Unity Python/C# to bypass a denied operation.
- Global Git `user.name` and `user.email` are copied into an ephemeral, read-only
  config inside the sandbox. Repository-local identity still takes precedence.
  Global credential helpers, hooks and other settings are not forwarded.
- Filesystem policy is loaded on server startup. Restart the bridge tunnel after
  an operator changes it. Missing/invalid configuration or missing/empty required
  path lists refuse startup. This is a development boundary, not containment against
  a hostile local process running under the same OS account. Unlisted project
  secrets are not automatically classified: add their paths to the policy.
- `move(overwrite=true)` supports atomic replacement of files or empty directories;
  it never recursively erases a destination. Overlapping paths are rejected.
- Desktop processes receive only an explicit environment allowlist. `blender`
  uses `snap run blender`; `unity-examplegame` has fixed Editor and project arguments.
  Launching an already-open configured Blender/Unity instance returns its PID instead
  of opening a duplicate. Do not close Editors with unsaved work; use native app state first.
- New applications run in independent `mcp-app-*.service` user units. Tunnel
  restarts cannot stop their process groups. Application launch requires the user
  systemd manager; there is deliberately no tunnel-owned subprocess fallback.
  `app_close` accepts only handles created by the current Bridge process and sends
  TERM unless `force=true` explicitly requests KILL. After a Bridge restart, an
  existing Editor is reused without claiming ownership; inspect its native state.

## Services

The three tunnel profiles retain their existing tunnel IDs and ports:
bridge 8080, Unity 8081, Blender 8082. They are managed by user systemd services.
The independent `codex-chatgpt-web` profile is not managed here.

```sh
mcp-services status
mcp-services restart bridge
mcp-services stop blender
mcp-services start all
journalctl --user -u mcp-tunnel-chatgpt-local-bridge.service -n 100
```

`integration_status` provides read-only diagnostics from ChatGPT. Tunnel readiness
does not prove Editor readiness. Unity diagnostics verify the project endpoint,
tools, Editor state and open scenes; Blender diagnostics query its live addon.
Services start at user login and restart on process failure. A supervisor also
detects when a stdio MCP child dies while its tunnel remains alive, and restarts
that tunnel. They do not start or stop Unity/Blender Editors or discard unsaved work.

Runtime keys are referenced from mode-0600 files under the private operator config
directory; they are not stored in this repository or forwarded to MCP children.
Tunnel logs go to the user journal. Blender INFO argument logging is suppressed;
error diagnostics remain available. Unity maintains its own rotating server logs.

## Versions and upgrades

- `requirements.lock`: exact current bridge distributions (MCP 2.2.0, Python 3.14).
- Blender MCP stays at 1.9.1 in a persistent uv tool environment using copied files.
  `ops/blender-requirements.lock` records its exact dependencies/Python 3.12 runtime.
- Unity plugin 0.90.0 owns GameDev MCP Server 9.2.5; project manifest/lock own its
  extensions. Do not upgrade these independently without compatibility checks.
- Keep Blender server/addon protocols aligned. The local wrapper adds read-only
  `get_context` and paginated `get_scene_objects`; the addon itself is unchanged.
- Detailed and anonymous Blender server telemetry is disabled by the wrapper.
  Arbitrary Python/C# authoring capabilities are retained.
- Stage upgrades separately, keep the preceding installation, verify initialization,
  enabled tools, app identity, a read-only call, and then a small task with final
  app verification. Do not delete the active uv environment/cache during a run.

Read-only Bridge tools and the two local Blender context helpers advertise explicit
read-only/non-destructive metadata; mutation tools retain conservative defaults.
This changes tool classification, not permissions or execution capabilities.

## Validation

```sh
BRIDGE_SANDBOX_TESTS=1 BRIDGE_SYSTEMD_TESTS=1 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m unittest -v
```

Tests use disposable directories and synthetic secrets. The Bubblewrap integration
tests require host user namespaces; do not disable isolation to make a nested
sandbox test pass. Global rules and systemd/profile backups are retained outside
this repository in the private integration state directory.
The systemd regression starts the real application launcher in a disposable service
with the tunnel's KillMode, then stops that service and checks that the application
survives in its own unit. It also checks literal arguments and environment filtering.
The Git regression performs a disposable commit and checks local identity precedence.

## ChatGPT catalog after this update

The running servers advertise Bridge 20 tools, Blender 30 tools and Unity 114
currently enabled tools. A saved ChatGPT connection may retain older metadata.
Open each of the three existing connections in ChatGPT Plugins, select Refresh,
check the tools, and start a new conversation with the connections enabled.
The new Bridge tools are `get_session_context` and `integration_status`; Blender
adds `get_context` and `get_scene_objects`. The five newly enabled Unity state
and screenshot tools must also appear in the refreshed Unity connection.
The existing tunnel IDs, health ports and credentials still work; no replacement
API key or tunnel is required. See the official refresh workflow:
https://developers.openai.com/plugins/deploy/connect-chatgpt#refresh-metadata

Verified on 2026-09-08: all three existing account plugins answered real calls.
The user refreshed the three original ChatGPT connections on the intended account.
The final ChatGPT UI check confirmed all new tools, the five enabled Unity tools,
and refreshed read-only metadata for Bridge/Blender. Fresh local MCP sessions also
see the new tools. The Codex account is independent
and has not been added to the tunnel configuration.
Automatic recovery of a killed Bridge MCP child passed in approximately 7.4s.
A complete OS restart/login and Unity Play Mode were not exercised in this task.

## 0.4.1 acceptance checks

29 tests passed with both host integration flags enabled. A disposable application
survived stopping its launcher service; a real sandbox commit used the configured
Git identity and respected project overrides. Startup with a missing configuration
was refused. A live Bridge MCP child failure recovered in 5.78 seconds while the
original Unity and Blender Editors remained open. Full logout/login, reboot and
hung-process recovery were not exercised or added. Tool names and input schemas
are unchanged, so this patch does not require another ChatGPT catalog refresh.
