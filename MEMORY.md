# Project memory

The installed Bridge can retain project notes, checkpoints and command metadata in
SQLite (Python stdlib, FTS5 required). This is explicit MCP-accessible context,
not automatic access to ChatGPT conversations. Stored text never overrides current
instructions, filesystem policy, permissions or live application checks.

## Configuration

Add this section to the existing local `bridge_config.json`:

```json
"memory": {
  "enabled": true,
  "path": "/home/user/.local/state/mcp-integration/bridge-memory/memory.sqlite3",
  "retention_days": 30,
  "max_commands": 5000,
  "max_entries_per_project": 2000
}
```

The database must live inside a configured `filesystem.denied_paths` subtree.
The existing `mcp-integration` state directory provides that protection on this
host. Its dedicated database directory is mode 0700; the database is mode 0600.
Use a local filesystem. The service rejects an unsupported schema version and
creates schema version 1 transactionally. Missing FTS5/storage faults are reported
as memory unavailable, without pretending the underlying shell operation failed.

Configuration is loaded at process startup. `enabled: false` disables persistence
and retrieval without deleting existing data. `BRIDGE_MEMORY_DISABLED=1` forces
memory off, chiefly for tests. Restart only the Bridge service after changing
configuration, when no Bridge-owned command is running. Refresh the ChatGPT
connection's tool catalogue after deployment to expose the four new tools.

## Workflow and tool contracts

1. Call `get_session_context(cwd=PROJECT_ROOT)` at session start. Existing live rules
   and policy are returned with the newest checkpoint (up to 3000 body characters)
   and up to five prioritized notes (400 body characters each).
2. Use `memory_search(cwd, query, kind, limit)` before repeating project discovery.
   Search accepts plain words, requires all supplied words, ignores accents, and
   returns at most 50 previews. Empty query lists recent entries, priority first
   for notes. Use `memory_get(cwd, entry_id)` for complete content and version.
3. Save durable findings explicitly with `memory_save(cwd, title, body, source,
   request_id, kind="note"|"checkpoint", priority=0..2)`. Identify user-provided
   statements versus agent observations in `source`, with the evidence reference.
   A checkpoint should state the goal, completed work, validation and next step.
4. Correct an entry using `entry_id`, its `expected_version` and a new request ID.
   A stale version is rejected. Retry a possibly completed save with the exact
   same request ID and payload; it returns the current entry, without overwriting
   newer edits. Reusing a key for different content is rejected.
5. Delete obsolete entries with `memory_delete(cwd, entry_id, expected_version)`.
   This also removes the searchable entry and its retry keys. Repeated deletion
   of a missing entry is harmless. Keys can be reused after deleting their entry.

Every lookup, update and deletion validates the current project path policy.
Project identity is the canonical **exact directory**, with no implicit global
search, Git-root discovery or grouping of similarly named repositories. Use the
same explicit root on subsequent calls. Moving a project does not migrate its
memory. The project directory must still exist to access its entries through MCP.

Bodies are limited to 8000 characters, titles to 200, source to 500 and request IDs
to 128. Explicit notes/checkpoints are retained until deleted; the per-project cap
rejects additional entries rather than silently dropping them. Retry keys are
limited to 1000 revisions per entry. After that, create a replacement and delete
the old entry. No vector service, embeddings, scheduler or new server is required.

## Command history and recovery

Both synchronous and background `run_command` calls record exact cwd, ID, start
and update times, lifecycle state, return code and timeout status. Responses carry
`history.status` and, when recorded, `history.id`. Query with
`memory_search(cwd=COMMAND_CWD, kind="command")`. Commands run in subdirectories
belong to those exact directories. Other tools' internal shell helpers are not
recorded as user commands.

No command string or stdout/stderr is automatically persisted. Common credential
formats in explicitly saved notes are redacted on write; this is best-effort, not
a guarantee that arbitrary secrets can be detected. Do not save secrets. Search
previews are marked as untrusted context and include provenance and timestamps.

Running records carry a local owner PID plus Linux process start identity. On
opening/searching/starting history, records whose owners have exited become
`unknown`; another live server's records are preserved. No commands are restarted
or replayed. A synchronous exception also records an unknown outcome; timeout is
separately indicated. Memory recording failure is separate from execution success.

Completed/unknown history is pruned on history writes and searches: 30 days and
5000 records by default, across projects. Running records are not evicted. There
is no scheduled cleanup while idle. SQLite lock waits and local lock acquisition
are bounded; a busy memory request can fail without blocking indefinitely.
WAL setup has a bounded retry for concurrent first opens; mutations are not
silently replayed. Logical deletion is not a forensic erasure guarantee and does
not remove copies in independent backups.

## Backup and rollback

Use the online SQLite backup API (do not copy only the main file while WAL is active):

```bash
/home/user/chatgpt-local-bridge/.venv/bin/python -B \
  /home/user/chatgpt-local-bridge/memory_store.py \
  --backup /home/user/.local/state/mcp-integration/bridge-memory/backup-YYYYMMDD.sqlite3
```

The destination must not exist; it is created mode 0600. Backups contain private
project memory and are not committed to Git. To restore, stop the Bridge with no
owned jobs active, retain the current database and its WAL/SHM together as a
rollback copy, restore the backup as `memory.sqlite3` without stale sidecars, and
start the Bridge. Keep version-compatible code. To roll back the feature without
restoring data, set `memory.enabled` to false and restart the Bridge.

## Verification

```bash
BRIDGE_SANDBOX_TESTS=1 BRIDGE_SYSTEMD_TESTS=1 ./check.sh
.venv/bin/python -B check_memory_mcp.py
```

The normal suite forces production memory off; memory tests create isolated
stores. Wire acceptance uses a temporary workspace/config/database and two real
stdio MCP server lifetimes. It checks persisted context, duplicate suppression,
real synchronous/background command receipts, cross-project denial, database
protection through file tools and Bubblewrap, and indexed deletion.

A hosted ChatGPT conversation choosing to use these tools is a separate acceptance
step. These checks do not quantify token savings or guarantee agent recall.
