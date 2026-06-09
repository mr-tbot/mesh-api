# Developing MESH-API Extensions

A step-by-step guide for building custom extensions for the MESH-API plugin system.

---

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Extension Structure](#extension-structure)
- [Base Class API Reference](#base-class-api-reference)
- [Step-by-Step Tutorial](#step-by-step-tutorial)
- [Hook Reference](#hook-reference)
- [Configuration](#configuration)
- [Flask Routes](#flask-routes)
- [Background Threads](#background-threads)
- [Best Practices](#best-practices)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Overview

MESH-API uses a plugin-based extension system where each extension is a self-contained Python package that lives in the `extensions/` directory. Extensions can:

- Register slash commands accessible from the mesh network
- Send and receive messages to/from the mesh
- React to emergency broadcasts
- Observe all inbound mesh messages
- Expose HTTP endpoints via Flask
- Run background threads for polling external services
- Act as AI providers

Extensions are automatically discovered and loaded at startup. No changes to core code are required.

---

## Quick Start

1. **Copy the template:**
   ```bash
   cp -r extensions/_example extensions/my_extension
   ```

2. **Edit the three files:**
   - `__init__.py` — leave empty (marks the folder as a Python package)
   - `config.json` — define your settings (must include `"enabled": true`)
   - `extension.py` — implement your extension class

3. **Restart MESH-API** — your extension is auto-discovered and loaded.

4. **Verify** — send `/extensions` on the mesh to see it listed.

---

## Extension Structure

Every extension lives in its own subfolder under `extensions/`:

```
extensions/
├── base_extension.py        # Abstract base class (DO NOT MODIFY)
├── loader.py                 # Extension loader (DO NOT MODIFY)
├── __init__.py
└── my_extension/             # Your extension folder
    ├── __init__.py           # Empty file (required)
    ├── config.json           # Extension configuration
    └── extension.py          # Extension implementation
```

### Naming Rules

- Folder names must be valid Python identifiers (lowercase, underscores OK)
- Folders starting with `_` are **skipped** by the loader (used for templates)
- The class inside `extension.py` must subclass `BaseExtension`
- Class name convention: `<Name>Extension` (e.g. `MyExtension`)

---

## Base Class API Reference

Every extension inherits from `BaseExtension`. Here's the complete API:

### Constructor (automatic)

```python
def __init__(self, extension_dir: str, app_context: dict):
```

You do **not** override `__init__`. The base class handles:
- `self.extension_dir` — absolute path to your extension's folder
- `self.app_context` — shared dict with core helpers (see below)
- `self._config` — loaded from your `config.json`

### Required Properties (must override)

| Property | Returns | Description |
|----------|---------|-------------|
| `name` | `str` | Human-readable name (e.g. `"My Extension"`) |
| `version` | `str` | Semantic version (e.g. `"1.0.0"`) |

### Built-in Properties (inherited)

| Property | Returns | Description |
|----------|---------|-------------|
| `enabled` | `bool` | `config["enabled"]` — the loader checks this |
| `commands` | `dict` | Slash commands to register (override to add) |
| `config` | `dict` | Read-only access to loaded config |

### Lifecycle Hooks

| Method | When Called |
|--------|------------|
| `on_load()` | Once after instantiation at startup |
| `on_unload()` | On shutdown or before hot-reload |

### Message Hooks

| Method | Signature | Purpose |
|--------|-----------|---------|
| `send_message()` | `(message: str, metadata: dict \| None)` | Outbound: mesh → external service |
| `receive_message()` | `()` | Inbound polling (prefer background threads) |
| `handle_command()` | `(command: str, args: str, node_info: dict) → str \| None` | Handle a registered slash command |
| `on_emergency()` | `(message: str, gps_coords: dict \| None)` | Emergency broadcast hook |
| `on_message()` | `(message: str, metadata: dict \| None)` | Observe all inbound mesh messages |

### Flask Integration

| Method | Signature | Purpose |
|--------|-----------|---------|
| `register_routes()` | `(app: Flask)` | Register HTTP endpoints |

### Helper Methods

| Method | Signature | Purpose |
|--------|-----------|---------|
| `send_to_mesh()` | `(text, channel_index=None, destination_id=None)` | Send a message to the mesh network |
| `log()` | `(message: str)` | Write to the MESH-API script log |
| `_save_config()` | `()` | Persist config changes to disk |

### app_context Dict

The `app_context` dict provides access to core functionality:

| Key | Type | Description |
|-----|------|-------------|
| `interface` | `MeshInterface` | The Meshtastic serial/TCP/BLE interface |
| `send_broadcast_chunks` | `function(iface, text, channel_idx)` | Send broadcast message |
| `send_direct_chunks` | `function(iface, text, destination_id)` | Send direct message |
| `add_script_log` | `function(message)` | Core logging function |
| `flask_app` | `Flask` | The Flask application instance |
| `config` | `dict` | Main `config.json` contents |

---

## Step-by-Step Tutorial

### 1. Create the folder structure

```
extensions/my_sensor/
├── __init__.py          # Empty
├── config.json
└── extension.py
```

### 2. Define config.json

```json
{
  "enabled": true,
  "sensor_url": "http://localhost:9000/api/reading",
  "poll_interval_seconds": 300,
  "broadcast_channel_index": 0,
  "unit": "°F"
}
```

The only required key is `"enabled"`. Everything else is up to you.

### 3. Implement extension.py

```python
"""My Sensor extension — reads temperature from a local sensor API."""

import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class MySensorExtension(BaseExtension):

    # ── Required properties ──────────────────────────────────────
    @property
    def name(self) -> str:
        return "My Sensor"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ── Register commands ────────────────────────────────────────
    @property
    def commands(self) -> dict:
        return {
            "/temp": "Read the current temperature",
        }

    # ── Lifecycle ────────────────────────────────────────────────
    def on_load(self) -> None:
        self._stop = threading.Event()
        self.log(f"My Sensor loaded. URL: {self.config.get('sensor_url')}")

    def on_unload(self) -> None:
        self._stop.set()
        self.log("My Sensor unloaded.")

    # ── Command handler ──────────────────────────────────────────
    def handle_command(self, command: str, args: str,
                       node_info: dict) -> str | None:
        if command == "/temp":
            return self._read_sensor()
        return None

    # ── Business logic ───────────────────────────────────────────
    def _read_sensor(self) -> str:
        url = self.config.get("sensor_url", "")
        unit = self.config.get("unit", "°F")
        if not url:
            return "Sensor URL not configured."
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            temp = data.get("temperature", "?")
            return f"🌡️ Current temperature: {temp}{unit}"
        except Exception as exc:
            return f"⚠️ Sensor error: {exc}"
```

### 4. Test it

1. Restart MESH-API
2. Send `/extensions` on mesh — should show "My Sensor v1.0.0 [enabled]"
3. Send `/temp` — should return the temperature reading

---

## Hook Reference

### handle_command(command, args, node_info) → str | None

The most commonly used hook. Called when a mesh user sends one of your registered commands.

```python
def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
    if command == "/mycmd":
        sender = node_info.get("shortname", "?")
        return f"Hello {sender}! You said: {args}"
    return None  # Not our command
```

**node_info dict:**
```python
{
    "node_id": "!abcd1234",      # Hex node ID
    "shortname": "ABC",          # 4-char node short name
    "longname": "Alpha Bravo",   # Full node name
    "channel_index": 0,          # Channel the message arrived on
    "is_direct": False,          # True if DM, False if broadcast
}
```

**Return value:**
- `str` — text sent back to the mesh (broadcast or DM depending on context)
- `None` — command not handled, loader passes to next extension

### on_message(message, metadata)

Read-only observer hook. Called for **every** inbound mesh message. Use for logging, analytics, keyword scanning, or triggering side-effects.

```python
def on_message(self, message: str, metadata: dict | None = None) -> None:
    if "help" in message.lower():
        self.log(f"Help request detected: {message}")
```

**Do NOT** return a response from `on_message`. Use `handle_command` for responses, or `send_to_mesh()` for async replies.

### on_emergency(message, gps_coords)

Called when `/emergency` or `/911` is triggered on the mesh.

```python
def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
    lat = gps_coords.get("lat", "?") if gps_coords else "?"
    lon = gps_coords.get("lon", "?") if gps_coords else "?"
    self.log(f"EMERGENCY at {lat},{lon}: {message}")
    # Forward to your external service here
```

### send_message(message, metadata)

Outbound hook. Called by the loader when the core wants to push a message to external services (e.g., forwarding all mesh traffic to a chat platform).

```python
def send_message(self, message: str, metadata: dict | None = None) -> None:
    # Forward to external API
    requests.post("https://example.com/api", json={"text": message})
```

### register_routes(app)

Register Flask HTTP endpoints for inbound webhooks or APIs.

```python
def register_routes(self, app) -> None:
    @app.route("/my_extension/webhook", methods=["POST"])
    def my_webhook():
        from flask import request, jsonify
        data = request.get_json()
        message = data.get("message", "")
        self.send_to_mesh(message, channel_index=0)
        return jsonify({"status": "ok"})
```

---

## MCP Tools (v0.7.0+)

If the MCP server is enabled (`mcp.enabled` in `config.json`), **every extension
slash command is automatically exposed** as an MCP tool named `ext_cmd_<command>`,
so external AI agents can call it with no extra work.

To expose **richer, typed tools** (custom names + JSON-Schema inputs), add two
optional methods to your extension (duck-typed — no base class change needed):

```python
def get_mcp_tools(self) -> list[dict]:
    """Return extra MCP tools this extension provides."""
    return [{
        "name": "lookup_city",                 # becomes ext_<slug>_lookup_city
        "description": "Look up weather for a city",
        "inputSchema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    }]

def call_mcp_tool(self, name: str, arguments: dict) -> str:
    """Handle a call to one of get_mcp_tools(). Return a text result."""
    if name == "lookup_city":
        return self._weather_for(arguments.get("city", ""))
    return f"Unknown tool: {name}"
```

---

## Configuration

### Reading Config

Access your extension's config via `self.config`:

```python
api_key = self.config.get("api_key", "")
interval = int(self.config.get("poll_interval", 60))
```

### Updating Config at Runtime

```python
self._config["last_check"] = "2025-01-01T00:00:00Z"
self._save_config()  # Writes to config.json on disk
```

### Config Best Practices

- Always provide defaults with `.get(key, default)`
- Include `"enabled": false` as the first key
- Use descriptive key names: `poll_interval_seconds`, `broadcast_channel_index`
- Document every key in your extension's comments or README

---

## Flask Routes

Extensions can expose HTTP endpoints. The Flask app is passed to `register_routes()`:

```python
def register_routes(self, app) -> None:
    @app.route("/my_ext/data", methods=["GET"])
    def my_data():
        from flask import jsonify
        return jsonify({"status": "ok", "extension": self.name})

    @app.route("/my_ext/inbound", methods=["POST"])
    def my_inbound():
        from flask import request
        data = request.get_json(force=True)
        text = data.get("message", "")
        if text:
            self.send_to_mesh(text)
        return "OK", 200
```

**Rules:**
- Use unique route paths prefixed with your extension name
- Import Flask utilities inside the route functions (avoid circular imports)
- Keep route handlers lightweight

---

## Background Threads

Many extensions need to poll external services. Use daemon threads:

```python
import threading
import time

class MyExtension(BaseExtension):
    def on_load(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,            # Dies with main process
            name="my-ext-poll",     # Descriptive name for debugging
        )
        self._thread.start()

    def on_unload(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)

    def _poll_loop(self) -> None:
        time.sleep(10)  # Initial delay to let system stabilize

        while not self._stop.is_set():
            try:
                # Do your work here
                data = self._fetch_data()
                if data:
                    self.send_to_mesh(f"New data: {data}")
            except Exception as exc:
                self.log(f"Poll error: {exc}")

            # Interruptible sleep (checks stop event every second)
            interval = int(self.config.get("poll_interval_seconds", 60))
            for _ in range(interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
```

### Thread Safety Tips

- Use `threading.Lock()` if shared state is accessed from multiple threads
- Use `threading.Event()` for clean shutdown signaling
- Use interruptible sleep pattern (loop with 1-second sleeps)
- Always set `daemon=True` so threads don't prevent exit
- Give threads descriptive names

---

## Best Practices

### General

1. **Guard imports** — wrap optional dependencies in try/except:
   ```python
   try:
       import requests
   except ImportError:
       requests = None
   ```

2. **Handle errors gracefully** — never let exceptions crash the main process:
   ```python
   try:
       result = self._call_api()
   except Exception as exc:
       return f"⚠️ Error: {exc}"
   ```

3. **Respect mesh bandwidth** — keep messages short (< 230 chars if possible). The mesh has limited capacity.

4. **De-duplicate** — track seen message IDs to avoid broadcasting the same alert twice:
   ```python
   if msg_id in self._seen_ids:
       return
   self._seen_ids.add(msg_id)
   ```

5. **Clean up in on_unload()** — stop threads, close sockets, flush buffers.

### Naming Conventions

- Folder: `snake_case` (e.g. `my_extension`)
- Class: `PascalCaseExtension` (e.g. `MyExtension`)
- Commands: `/<lowercase>` — avoid collisions with built-in commands
- Config keys: `snake_case` with descriptive names

### Message Formatting

Use emoji prefixes for visual scanning on small screens:
- 📡 — radio/connectivity
- 🚨 — alerts/emergencies  
- ✅ — success/confirmation
- ⚠️ — warnings/errors
- 📋 — lists/info
- 📧 — email/messages
- 🌡️ — weather/sensors

---

## Testing

### Manual Testing

1. Set `"enabled": true` in your extension's `config.json`
2. Restart MESH-API
3. Check the logs for `[ext:YourName]` entries
4. Send `/extensions` to verify it's loaded
5. Test each command from a mesh node

### Checking Logs

Your `self.log()` calls appear in the MESH-API script log with the prefix `[ext:YourName]`. Check the WebUI Logs panel or the log file.

### Common Test Commands

```
/extensions              — verify your extension is listed
/your_command            — test command handling
/emergency test          — test emergency hook (CAREFULLY!)
```

---

## Troubleshooting

### Extension not loading

- Check that `extension.py` exists in the folder
- Ensure `__init__.py` exists (even if empty)
- Verify the class inherits from `BaseExtension`
- Check that `name` and `version` properties are defined
- Folder names starting with `_` are ignored intentionally
- Check logs for import errors

### Commands not responding

- Verify `commands` property returns a dict with your command
- Check `handle_command()` matches the exact command string
- Make sure no other extension registers the same command
- Confirm `"enabled": true` in your config.json

### send_to_mesh not working

- Ensure `app_context` contains a valid `interface`
- Check that the mesh interface is connected
- Verify channel index is valid for your mesh configuration

### Config not loading

- Validate JSON syntax in `config.json` (use a JSON linter)
- Check file permissions
- Look for log entries about config load failures

---

## Examples

The `extensions/` directory includes 30 working extensions you can reference:

| Extension | Complexity | Good Example Of |
|-----------|-----------|-----------------|
| `_example` | Minimal | Basic structure, all hooks documented |
| `ntfy` | Simple | HTTP API + push notifications |
| `pushover` | Simple | Outbound-only notifications |
| `nws_alerts` | Medium | Polling + auto-broadcast + filtering |
| `telegram` | Medium | Bidirectional bridge + long-polling |
| `mqtt` | Medium | Event-driven with paho-mqtt |
| `bbs` | Complex | SQLite database + thread safety + subcommands |
| `aprs` | Complex | Raw TCP sockets + protocol parsing |
| `discord` | Complex | Webhook + bot + Flask route |
| `meshcore` | Complex | Serial/TCP bridge + bidirectional channel mapping |
| `openclaw` | Medium | External AI agent bridge + polling + emergency forwarding |

---

## See Also

- [EXTENSIONS.md](EXTENSIONS.md) — Full reference for all built-in extensions
- [README.md](README.md) — Main project documentation
- `extensions/_example/` — Annotated template (copy this to start)
