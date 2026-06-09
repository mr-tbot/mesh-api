# MESH-API — Agent Guide

MESH-API is a Meshtastic mesh router + AI chatbot bridge. The core ([mesh-api.py](mesh-api.py))
runs a Flask web dashboard and a Meshtastic interface (serial/WiFi/BLE/TCP), routes slash
commands and AI responses to the mesh, and loads plugins from [extensions/](extensions/).

For details, link to existing docs rather than duplicating them:
- [README.md](README.md) — project overview, features, config reference.
- [DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md) — step-by-step extension guide + API reference.
- [EXTENSIONS.md](EXTENSIONS.md) — reference for all built-in extensions and their config.

## Build / Run

- Install: `pip install -r requirements.txt`
- Run locally: `python mesh-api.py` → dashboard at `http://localhost:5000/dashboard`
- Docker: `docker compose up -d`
- No automated test suite, linter, or formatter is configured. Verify changes by running the app.

## Architecture

- **Core** [mesh-api.py](mesh-api.py): Flask server + Meshtastic interface, built-in slash
  commands, AI provider integration, message chunking, emergency broadcasts.
- **Multi-radio (v0.7.0+)**: MeshCore is a **first-class, core-owned radio**, not a plugin.
  [meshcore_core.py](meshcore_core.py) (`MeshCoreManager`) owns the MeshCore connection
  (serial/TCP/BLE) on its own asyncio thread and feeds inbound messages into the *same*
  network-agnostic pipeline as Meshtastic (`notify_extensions_inbound` → `route_and_respond`
  → `dispatch_response`). This lets commands, AI, and every plugin work on either network,
  and lets the user run Meshtastic-only, MeshCore-only (standalone via `meshtastic_enabled:false`),
  or both. The old `extensions/meshcore` bridge plugin is deprecated and defers to the core.
- **Extension system** [extensions/](extensions/): auto-discovered plugins. The loader
  ([extensions/loader.py](extensions/loader.py)) scans `extensions/` at startup, skips folders
  starting with `_`, and instantiates every [BaseExtension](extensions/base_extension.py) subclass.
- **MCP server (v0.7.0+)** [mcp_server.py](mcp_server.py) (`MCPServer`): exposes core functions
  and extensions as MCP tools over a Streamable-HTTP / JSON-RPC 2.0 Flask endpoint at `POST /mcp`
  (no async deps — fits the sync Flask core). Core tools (`mesh_send_message`, `mesh_list_nodes`,
  `mesh_run_command`, etc.) are built from `app_context`/providers; **every extension slash
  command is auto-exposed** as an `ext_cmd_*` tool, and extensions may add richer typed tools via
  optional `get_mcp_tools()` + `call_mcp_tool()` methods (duck-typed, no framework edit needed).
  Disabled by default; bearer-token auth + gated emergency tool. Config: `mcp` block.
- **Messaging**: event-driven receive via Meshtastic pubsub callbacks; extensions use background
  threads (`threading`) for polling. No `async`/`await` anywhere. Outbound messages > `chunk_size`
  (default 200 chars) are split at word boundaries with a delay between chunks.

## Adding an Extension

1. Copy [extensions/_example/](extensions/_example/) to `extensions/<name>/` (lowercase, underscores,
   valid Python identifier — no hyphens). Keep the layout: `__init__.py`, `config.json`, `extension.py`.
2. In `extension.py`, subclass `BaseExtension` and define required `name` and `version` properties.
   Override only the hooks you need: `on_load`, `on_unload`, `handle_command`, `send_message`,
   `receive_message`, `on_message`, `on_emergency`, `register_routes`.
3. In `config.json`, set `"enabled": true` plus any custom keys.
4. Restart MESH-API (the loader auto-discovers it). Check [EXTENSIONS.md](EXTENSIONS.md) first to
   avoid duplicating an existing extension.

## Conventions & Pitfalls

- Do **not** modify [base_extension.py](extensions/base_extension.py) or
  [extensions/loader.py](extensions/loader.py) when adding features — extend, don't edit the framework.
- Never override `__init__` in an extension; the loader constructs it with `(extension_dir, app_context)`.
- Use `self.log(...)` (not `print`) for log capture; read config via `self.config.get(key, default)`.
- Persist config changes with `self._save_config()` — mutating `self._config` alone does not save.
- Use mesh helpers instead of hardcoding hardware: `self.send_to_mesh(...)`, or
  `self.app_context["interface"]` / `send_broadcast_chunks` / `send_direct_chunks`.
- `handle_command()` returns a string response, or `None` if it does not handle the command.
- Background threads must stop cleanly in `on_unload()`; exceptions in `on_load()` are caught and
  logged by the loader (the extension just won't activate) — check the log.
- Config files are not reloaded mid-run; changes require a restart (or WebUI restart).
- `commands_config.json` must keep its top-level `{"commands": [...]}` shape.
- The AI command alias (`ai_command` in [config.json](config.json)) is a randomized suffix
  (e.g. `/ai-9z`); it regenerates on startup if it doesn't match the expected pattern.
