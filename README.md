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

## Local Development Bridge 0.6.5

Python MCP server for `/home/user`. Code and file operations belong here;
live Blender and Unity state belongs to their respective MCPs.

### 0.6.0: less restrictive where it helps development

This revision keeps the important destructive boundaries but removes two practical bottlenecks. `sandbox.network` can retain the host network namespace for normal development commands while Bubblewrap still isolates host IPC, PID visibility, private runtime mounts, home credentials and capabilities. The operator configuration in this repository enables network access. Git author identity is still the only global Git configuration forwarded into the shell; credential helpers and login profiles remain hidden.

Two read-only host diagnostics avoid forcing legitimate inspection through the shell sandbox: `process_info(pid)` reports one current-user process including executable, cwd, command line, AppArmor label, cgroup and namespace IDs; `journal_query(...)` returns a bounded host-journal slice and can restrict it to kernel events. This supports cases such as diagnosing Snap/AppArmor/Firefox without exposing host `/proc` wholesale inside arbitrary shell commands.

The version immediately before this change is tagged `backup/pre-relaxed-security-20260909T004258Z` at commit `d4d9679`.

## 0.6.5 rich-editor semantic descendant input

When a focused web editor exposes an unreliable text/caret model on its outer AT-SPI wrapper, the Bridge now searches only within that focused editor for a single visible editable descendant with a sane Text/EditableText caret model. If exactly one exists, `type_text` inserts through that descendant and verifies the result by readback; ambiguous descendants still fall back to the consented portal keyboard path. This specifically targets contenteditable/rich-editor structures without introducing DOM scripting, clipboard access, pointer coordinates or new MCP permissions. Unicode AT-SPI insertion now passes a character count rather than UTF-8 byte length.

## 0.6.4 GNOME portal parent window

GNOME/Wayland can refuse or fail to present RemoteDesktop/ScreenCast permission dialogs when `parent_window` is empty. The desktop worker now creates a 1x1 transparent GTK4 toplevel, exports its xdg-foreign handle with GdkWayland, passes `wayland:<handle>` to `RemoteDesktop.Start`, and destroys the helper parent when the session closes. This keeps the user-consent portal while fixing the previously invisible/pending dialog.

## 0.6.3 rich web editor fallback

Firefox can expose rich `contenteditable` editors with a valid semantic focus but an invalid AT-SPI caret, or accept `EditableText.set_text_contents` without changing the DOM-backed editor. `type_text` now inspects caret/selection state before mutation. When AT-SPI insertion is reliable it keeps verified semantic insertion; when the unique focused editor has an unreliable caret it does not mutate through AT-SPI and instead uses the already-authorized RemoteDesktop keyboard path. Because the target is already identified and focused semantically, this fallback needs no screenshot and no pointer coordinates. The GNOME portal session is still mandatory for injected key events.

Portal `type_text` now emits standard Unicode X11 keysyms, so accented PT-PT text and other printable Unicode characters are not restricted to ASCII. Visual pointer actions retain the existing screenshot/session requirement. No tool names or schemas changed.

## 0.6.2 desktop usability

Firefox/AT-SPI was verified to expose a rich semantic tree, including browser chrome, tabs, links, buttons and ChatGPT navigation. The remaining friction was in the Bridge traversal and input policy rather than an inherent Firefox limitation. Observation now traverses through up to two non-showing intermediary wrappers while still returning only showing/useful elements, which helps modern web apps whose visible controls sit below generic accessibility containers.

`type_text` no longer requires a GNOME RemoteDesktop session or screenshot when exactly one observed editable element already has accessibility focus in the active window. In that case insertion uses AT-SPI `EditableText` and keeps readback verification. Raw keyboard fallback still requires the authorized portal session and screenshot, and ambiguous multiple focused editable fields are refused. No MCP tool names or schemas changed in this revision, so a ChatGPT catalog refresh is not required.

## Desktop observation and control

This extension runs inside the existing Bridge MCP, using the same tunnel and
ChatGPT connection. No installer or other MCP is replaced. The Sol model in
ChatGPT calls structured tools; it does not need to generate input scripts or
use a second model. Refresh the existing connection's tool catalog after deployment.

Four additional tools are available when `desktop.enabled` is true in the local
configuration:

- `desktop_status`: capabilities, limits and session state, without starting control.
- `desktop_observe`: compact AT-SPI window/element descriptions with a fresh snapshot.
  Filter by application or window; default traversal expands active windows. Names,
  text, states, actions, bounds and values are returned with explicit truncation.
- `desktop_act`: execute an explicit short batch and return receipts plus a new
  observation. Accessible actions include activate, set_text, focus, select and
  scroll_into_view. Raw actions include move, click, drag, scroll, key and type_text.
- `desktop_session`: start/status/stop a user-approved GNOME RemoteDesktop session
  for keyboard, pointer and one monitor. Start returns pending while GNOME asks the
  local user to select the monitor and permit control. No permission token is persisted.

Start with `desktop_observe(application="...")`. Use element IDs from that exact
snapshot. Accessible operations use AT-SPI directly and do not require a raw-input
session. For graphical canvases, start the session, wait for active, then request
`desktop_observe(..., screenshot=true)`. It returns the selected monitor as a native
MCP PNG plus its pixel and logical sizes. Raw coordinates are normalized 0..1 within
that image, with the origin at its top left. Do not use global screen coordinates.
Pass the session_id and snapshot_id to `desktop_act`; screenshot=true returns the
resulting image in the same tool call. Monitor selection and mapping remain bound
to that session. There is no automatic click fallback for a failed semantic action.

Snapshot IDs are single-use for actions, expire after 120 seconds, and are invalidated
by another observation. Target identity, state, text and geometry are rechecked before
each accessible action. The window must be active except for an explicit focus action.
Batch only predictable operations: if a later target changes, execution stops and
the completed actions are reported without rollback. A transport timeout is an unknown
outcome, never an invitation to replay input. Observe again before retrying.

`executed` reports that an operation was accepted; `verified` requires readback
(currently set_text and focus). Inspect the returned window/image for the broader
task outcome. A successful click alone does not prove a file was saved. At most 8
actions, 400 visible elements, 4000 characters for set_text and 256 for raw type_text
are allowed per request. `type_text` inserts through an observed focused editable
element when available, replacing its selection and verifying Unicode text without
accessing the clipboard. Otherwise it uses keyboard events for ASCII; unsupported
Unicode is refused instead of silently losing characters. Password text is not returned.
UI content is untrusted data.

The helper uses `/usr/bin/python3`, GI AT-SPI, D-Bus and GStreamer plugins already
installed on this host. Its protocol uses private parent-owned pipes, not a new socket,
port or tunnel. It cannot execute supplied code. The MCP virtualenv remains unchanged.
The RemoteDesktop backend uses the documented D-Bus Notify methods; it does not
claim to implement libei. The backend retains the compositor's permission session
without granting access to `/dev/uinput` or changing device permissions. Frames come
through the authorized PipeWire stream (at most 5 fps), not repeated screenshot dialogs.
Sessions close on revocation, process exit, explicit stop or 15 minutes of inactivity.
Shell commands remain Bubblewrap-sandboxed; network follows `sandbox.network`. Desktop tools control the signed-in desktop;
filesystem sandbox rules are not a containment boundary for graphical applications.

Blender and Unity retain their dedicated MCPs as the source of truth for editing
their projects. Accessibility and visual input complement those tools. AT-SPI coverage
depends on each application and toolkit; an incomplete tree is reported, not invented.

### Desktop validation and recovery

Run protocol tests with system Python (GI), and existing/MCP tests with the virtualenv:

```sh
/usr/bin/python3 -B -m unittest -v test_desktop
BRIDGE_SANDBOX_TESTS=1 BRIDGE_SYSTEMD_TESTS=1 BRIDGE_WORKSPACE=/home/user .venv/bin/python -B -m unittest -v
BRIDGE_DESKTOP_TESTS=1 BRIDGE_WORKSPACE=/home/user .venv/bin/python -B -m unittest -v test_desktop_live
BRIDGE_WORKSPACE=/home/user .venv/bin/python -B check_desktop_portal.py
```

The live tests create a disposable `Bridge Desktop Test` GTK window; the last one
requires GNOME consent and operates only controls in that test window. It stops the
session and closes the fixture even after failure. It does not test the ChatGPT model.

The pre-extension version is preserved in the Git tag
`backup/pre-desktop-20260908T220345Z` (commit `92c4151`) and the local archive and
Git bundle at `/home/user/chatgpt-local-bridge-backups/pre-desktop-20260908T220345Z`.
The manifest records the archive SHA-256. The archive excludes the virtualenv and
caches; `requirements.lock` records dependencies. To disable desktop tools, set
`desktop.enabled` to false and restart only the Bridge service. To roll back code,
restore the backup into a separate directory, inspect any subsequent changes, then
replace the affected Bridge files and restart the same service. Do not reset or
overwrite unrelated work. Unity/Blender services and installers are unchanged.

Start each ChatGPT session with `get_session_context(cwd=<project>)` and inspect
the live tool inventory. Global AGENTS.md is also included in MCP initialization.
Refresh the plugin's tools in ChatGPT after changing the server's tool catalog.

## Boundaries

- `bridge_config.json` lists protected credential paths, read-only control paths,
  application aliases and process signal policy. The remainder of the configured
  workspace stays available for normal project editing.
- File reads/writes validate paths. Recursive search, patches, Git and shell run
  through Bubblewrap; host `/run`, `/tmp`, `/proc` and home mounts are isolated.
- The shell uses no login/profile scripts and its HOME is private `/tmp`. Network is
  controlled by `sandbox.network`; it is enabled here for normal development traffic.
  Host IPC and credentials remain isolated. Do not use Blender/Unity Python/C# to bypass a denied operation.
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

The updated Bridge advertises 26 tools; Blender advertises 30 tools and Unity 114
currently enabled tools. A saved ChatGPT connection may retain older metadata.
Open each of the three existing connections in ChatGPT Plugins, select Refresh,
check the tools, and start a new conversation with the connections enabled.
Current Bridge additions include `get_session_context`, `integration_status`,
`process_info`, `journal_query` and the four `desktop_*` tools. Blender adds
`get_context` and `get_scene_objects`. The five newly enabled Unity state
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

## 0.5.0 validation status

Installed code advertises 24 tools and passed a real MCP text action/readback and
a stale-snapshot error test. All 29 pre-existing host tests, 10 desktop protocol
tests, 4 MCP unit tests and the AT-SPI fixture test passed. The portal fixture
passed monitor capture, keyboard, Unicode insertion, click, drag and closure before
a final capture-startup adjustment. The repeat of that adjustment and scroll test
requires GNOME consent and remains pending; the last request timed out. Refresh
the ChatGPT connection and validate a Sol action before treating the full ChatGPT
workflow as proven. Firefox was running but absent by name from the current AT-SPI
application inventory; no browser settings were changed.

## 0.6.0 staged validation status

The normal Python suite passed 38 tests with 8 expected integration skips. Targeted Bridge/security tests passed 29 tests with 4 expected skips. Host Bubblewrap integration tests could not be rerun from inside the already-sandboxed active Bridge because nested unprivileged user namespaces are unavailable there. The generated Bubblewrap argv is unit-tested to retain `--unshare-all`, capability dropping and private mounts while adding `--share-net` only when configured. Before deployment, rerun host integration outside an existing Bridge command sandbox, restart only the Bridge service and refresh the ChatGPT tool catalog.
