"""
mcp_server.py — Model Context Protocol (MCP) server for MESH-API v0.7.0.

Exposes MESH-API's core functions **and** its extensions as MCP *tools*, so
external AI agents and services (Claude, Perplexity, Hermes, custom agents,
etc.) can drive the mesh networks as a backend — sending/receiving messages,
querying nodes, running commands, and invoking any installed extension —
enabling advanced agentic workflows over Meshtastic and/or MeshCore.

Design
------
MCP is JSON-RPC 2.0 over a transport. This module implements the **Streamable
HTTP** transport as a single Flask endpoint (mounted by the core at ``/mcp``),
returning ``application/json`` responses. That keeps MESH-API's synchronous
Flask architecture intact (no asyncio/uvicorn dependency — important on small
hardware like a Pi Zero) while remaining compatible with MCP clients (directly,
or via the ``mcp-remote`` stdio bridge for clients that only speak stdio).

Security
--------
Tool calling can send mesh traffic and trigger actions, so the server:
  * is **disabled by default** (``mcp.enabled``),
  * supports **bearer-token auth** (``mcp.auth_token``; auto-generated on first
    enable if blank),
  * validates the ``Origin`` header against an allowlist to mitigate DNS
    rebinding,
  * gates sensitive tools (e.g. emergency broadcast) behind explicit config,
  * validates inputs and sanitizes/clamps outputs.

The core wires this in by constructing :class:`MCPServer` with an ``app_context``
(the same dict extensions get) plus a small ``providers`` map of read helpers,
then routing ``/mcp`` POSTs to :meth:`MCPServer.handle_http`.
"""

from __future__ import annotations

import json
import re
import secrets
import time
import traceback
from typing import Any, Callable, Optional

PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = {"2025-06-18", "2025-03-26", "2024-11-05"}
SERVER_NAME = "mesh-api"
SERVER_VERSION = "0.7.0"

# JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _sanitize_tool_name(name: str) -> str:
    """MCP tool names must match ^[a-zA-Z0-9_-]{1,64}$."""
    n = re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_")
    return n[:64] or "tool"


class MCPServer:
    """A minimal, dependency-free MCP server exposing MESH-API as tools."""

    def __init__(
        self,
        config: dict,
        app_context: dict,
        providers: dict,
        log: Optional[Callable[[str], None]] = None,
        save_config: Optional[Callable[[], None]] = None,
    ) -> None:
        self._cfg = config or {}
        self._ctx = app_context or {}
        self._providers = providers or {}
        self._log = log or (lambda m: print(m))
        self._save_config = save_config
        self._tools: dict[str, dict] = {}
        self._sessions: dict[str, float] = {}
        self._call_count = 0
        self._last_call_ts = 0.0
        self._ensure_auth_token()
        self._build_core_tools()

    # ── config helpers ───────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return bool(self._cfg.get("enabled", False))

    def _mcp(self, key: str, default: Any = None) -> Any:
        return self._cfg.get(key, default)

    def _ensure_auth_token(self) -> None:
        if not self.enabled:
            return
        if self._mcp("require_auth", True) and not self._mcp("auth_token"):
            token = "mesh-mcp-" + secrets.token_urlsafe(24)
            self._cfg["auth_token"] = token
            self._log(
                f"[MCP] Generated auth token (save this for your MCP client): {token}"
            )
            if self._save_config:
                try:
                    self._save_config()
                except Exception:
                    pass

    # ── auth / origin ────────────────────────────────────────────────

    def check_request(self, request) -> Optional[tuple]:
        """Return None if allowed, else (status_code, error_text)."""
        # Origin allowlist (DNS-rebinding mitigation). "*" disables the check.
        allowed = self._mcp("allowed_origins", ["*"])
        origin = request.headers.get("Origin")
        if origin and allowed and "*" not in allowed and origin not in allowed:
            return (403, "Origin not allowed")
        # Bearer token
        if self._mcp("require_auth", True):
            expected = self._mcp("auth_token", "")
            if expected:
                auth = request.headers.get("Authorization", "")
                token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
                if not token:
                    token = request.headers.get("X-API-Key", "")
                if not secrets.compare_digest(token, expected):
                    return (401, "Unauthorized: missing/invalid bearer token")
        return None

    # ── tool registry ────────────────────────────────────────────────

    def register_tool(self, name: str, description: str, input_schema: dict,
                      handler: Callable[[dict], Any]) -> None:
        safe = _sanitize_tool_name(name)
        self._tools[safe] = {
            "name": safe,
            "description": description,
            "inputSchema": input_schema or {"type": "object", "properties": {}},
            "handler": handler,
        }

    def _build_core_tools(self) -> None:
        ctx = self._ctx
        prov = self._providers

        # 1) Send a message to one/both networks (broadcast or DM)
        self.register_tool(
            "mesh_send_message",
            "Send a text message over the mesh. Choose network "
            "(meshtastic, meshcore, both, or auto), and either broadcast on a "
            "channel index or direct-message a node by id.",
            {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message text to send."},
                    "network": {"type": "string", "enum": ["auto", "meshtastic", "meshcore", "both"],
                                 "description": "Target network. Default auto (active radios)."},
                    "direct": {"type": "boolean", "description": "True for a direct message (requires dest_node)."},
                    "dest_node": {"type": "string", "description": "Destination node id for a direct message (e.g. !abcd1234 or !mc-xxxx)."},
                    "channel_index": {"type": "integer", "description": "Channel index for a broadcast (default 0)."},
                },
                "required": ["message"],
            },
            self._tool_send_message,
        )

        # 2) List nodes across both networks
        self.register_tool(
            "mesh_list_nodes",
            "List known nodes across both mesh networks, optionally filtered by "
            "network. Returns id, names, and network for each node.",
            {
                "type": "object",
                "properties": {
                    "network": {"type": "string", "enum": ["all", "meshtastic", "meshcore"],
                                 "description": "Filter by network. Default all."},
                },
            },
            self._tool_list_nodes,
        )

        # 3) Recent messages
        self.register_tool(
            "mesh_get_messages",
            "Get the most recent mesh messages (chat log) across both networks, "
            "newest last. Useful to read what is happening on the mesh.",
            {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "How many recent messages (default 20, max 100)."},
                },
            },
            self._tool_get_messages,
        )

        # 4) Network status
        self.register_tool(
            "mesh_network_status",
            "Get the connection status of both radios (Meshtastic and MeshCore), "
            "including which are enabled/connected and basic stats.",
            {"type": "object", "properties": {}},
            self._tool_network_status,
        )

        # 5) List channels
        self.register_tool(
            "mesh_list_channels",
            "List available channels for each network (Meshtastic channel names "
            "and MeshCore channels / group chats).",
            {"type": "object", "properties": {}},
            self._tool_list_channels,
        )

        # 6) AI query through the configured provider
        if ctx.get("get_ai_response"):
            self.register_tool(
                "mesh_ai_query",
                "Ask the MESH-API-configured AI provider a question and get its "
                "response text (the same AI used by the mesh chatbot).",
                {
                    "type": "object",
                    "properties": {"prompt": {"type": "string", "description": "The prompt/question."}},
                    "required": ["prompt"],
                },
                self._tool_ai_query,
            )

        # 7) List commands
        self.register_tool(
            "mesh_list_commands",
            "List all slash commands available on this MESH-API node (built-in, "
            "custom, and extension-provided).",
            {"type": "object", "properties": {}},
            self._tool_list_commands,
        )

        # 8) Run a slash command
        if ctx.get("handle_command"):
            self.register_tool(
                "mesh_run_command",
                "Run a MESH-API slash command exactly as if a mesh user sent it "
                "(e.g. '/ping', '/weather 90210'). Returns the command response.",
                {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Full command text including leading slash and args."},
                    },
                    "required": ["command"],
                },
                self._tool_run_command,
            )

        # 9) MeshCore contacts (DM targets)
        if prov.get("get_meshcore_contacts"):
            self.register_tool(
                "meshcore_list_contacts",
                "List MeshCore contacts (potential direct-message targets) with "
                "their ids and public keys.",
                {"type": "object", "properties": {}},
                self._tool_meshcore_contacts,
            )

        # 10) Emergency broadcast (gated)
        if self._mcp("allow_emergency", False) and self._providers.get("send_emergency"):
            self.register_tool(
                "mesh_send_emergency",
                "Trigger an EMERGENCY alert/broadcast (Twilio/email/Discord if "
                "configured). Use only for genuine emergencies.",
                {
                    "type": "object",
                    "properties": {"message": {"type": "string", "description": "Emergency message."}},
                    "required": ["message"],
                },
                self._tool_send_emergency,
            )

    def _build_extension_tools(self) -> None:
        """(Re)build extension-provided tools. Called per tools/list so newly
        loaded/reloaded extensions are reflected without a restart."""
        # Drop previously generated extension tools
        for k in [k for k, v in self._tools.items() if v.get("_ext")]:
            del self._tools[k]

        loader = None
        getter = self._providers.get("get_extension_loader")
        if getter:
            try:
                loader = getter()
            except Exception:
                loader = None
        if not loader:
            return

        # (a) Rich, typed tools from extensions that opt in via get_mcp_tools()
        for slug, ext in getattr(loader, "loaded", {}).items():
            if hasattr(ext, "get_mcp_tools") and callable(getattr(ext, "get_mcp_tools")):
                try:
                    for t in (ext.get_mcp_tools() or []):
                        name = _sanitize_tool_name(f"ext_{slug}_{t.get('name', 'tool')}")
                        self._tools[name] = {
                            "name": name,
                            "description": f"[{getattr(ext, 'name', slug)}] " + t.get("description", ""),
                            "inputSchema": t.get("inputSchema") or {"type": "object", "properties": {}},
                            "handler": self._make_ext_tool_handler(ext, t.get("name")),
                            "_ext": True,
                        }
                except Exception as exc:
                    self._log(f"[MCP] extension {slug} get_mcp_tools error: {exc}")

        # (b) Auto-expose every extension slash command as a tool
        try:
            cmds = loader.list_extension_commands()  # [(cmd, "[Name] desc"), ...]
        except Exception:
            cmds = []
        for cmd, desc in cmds:
            name = _sanitize_tool_name("ext_cmd_" + cmd.lstrip("/"))
            if name in self._tools:
                continue
            self._tools[name] = {
                "name": name,
                "description": f"Run mesh command '{cmd}'. {desc}",
                "inputSchema": {
                    "type": "object",
                    "properties": {"args": {"type": "string", "description": f"Arguments for {cmd} (optional)."}},
                },
                "handler": self._make_command_tool_handler(cmd),
                "_ext": True,
            }

    def _make_ext_tool_handler(self, ext, tool_name):
        def handler(args: dict):
            if hasattr(ext, "call_mcp_tool") and callable(getattr(ext, "call_mcp_tool")):
                return ext.call_mcp_tool(tool_name, args or {})
            return f"Extension does not implement call_mcp_tool for '{tool_name}'."
        return handler

    def _make_command_tool_handler(self, cmd: str):
        def handler(args: dict):
            handle = self._ctx.get("handle_command")
            if not handle:
                return "Command handling is unavailable."
            extra = (args or {}).get("args", "")
            full = (cmd + " " + extra).strip() if extra else cmd
            resp = handle(cmd, full, "MCP")
            return resp if resp is not None else f"(no response from {cmd})"
        return handler

    # ── core tool handlers ───────────────────────────────────────────

    def _tool_send_message(self, args: dict) -> str:
        msg = (args or {}).get("message", "").strip()
        if not msg:
            raise ValueError("'message' is required")
        network = (args.get("network") or "auto").lower()
        direct = bool(args.get("direct")) or bool(args.get("dest_node"))
        web_send = self._ctx.get("web_send")
        log_message = self._ctx.get("log_message")
        if not web_send:
            return "Sending is unavailable (no web_send in context)."
        if direct:
            dest = args.get("dest_node")
            if not dest:
                raise ValueError("'dest_node' is required for a direct message")
            web_send(msg, network, "direct", dest_node=dest)
            if log_message:
                try:
                    log_message("MCP", f"{msg} [to: {dest}]", direct=True)
                except Exception:
                    pass
            return f"Direct message sent to {dest}."
        ch = int(args.get("channel_index", 0) or 0)
        web_send(msg, network, "broadcast", channel_idx=ch)
        resolve = self._ctx.get("resolve_send_networks")
        nets = resolve(network) if resolve else [network]
        if log_message:
            try:
                log_message("MCP", f"{msg} [to: ch{ch} via {'+'.join(nets)}]", direct=False, channel_idx=ch)
            except Exception:
                pass
        return f"Broadcast sent on channel {ch} via {', '.join(nets)}."

    def _tool_list_nodes(self, args: dict) -> str:
        net = (args or {}).get("network", "all").lower()
        getter = self._providers.get("get_nodes")
        nodes = getter() if getter else []
        if net != "all":
            nodes = [n for n in nodes if (n.get("network") or "meshtastic") == net]
        return json.dumps(nodes, ensure_ascii=False)

    def _tool_get_messages(self, args: dict) -> str:
        limit = int((args or {}).get("limit", 20) or 20)
        limit = max(1, min(100, limit))
        getter = self._providers.get("get_messages")
        msgs = getter() if getter else []
        return json.dumps(msgs[-limit:], ensure_ascii=False)

    def _tool_network_status(self, args: dict) -> str:
        getter = self._providers.get("get_networks")
        return json.dumps(getter() if getter else {}, ensure_ascii=False)

    def _tool_list_channels(self, args: dict) -> str:
        out = {"meshtastic": {}, "meshcore": []}
        mt = self._providers.get("get_meshtastic_channels")
        if mt:
            try:
                out["meshtastic"] = mt()
            except Exception:
                pass
        mc = self._providers.get("get_meshcore_channels")
        if mc:
            try:
                out["meshcore"] = mc()
            except Exception:
                pass
        return json.dumps(out, ensure_ascii=False)

    def _tool_ai_query(self, args: dict) -> str:
        prompt = (args or {}).get("prompt", "").strip()
        if not prompt:
            raise ValueError("'prompt' is required")
        fn = self._ctx.get("get_ai_response")
        resp = fn(prompt) if fn else None
        return resp or "(no AI response)"

    def _tool_list_commands(self, args: dict) -> str:
        getter = self._providers.get("get_commands")
        cmds = getter() if getter else []
        return json.dumps(cmds, ensure_ascii=False)

    def _tool_run_command(self, args: dict) -> str:
        full = (args or {}).get("command", "").strip()
        if not full:
            raise ValueError("'command' is required")
        cmd = full.split()[0]
        handle = self._ctx.get("handle_command")
        resp = handle(cmd, full, "MCP") if handle else None
        return resp if resp is not None else f"(no response from {cmd})"

    def _tool_meshcore_contacts(self, args: dict) -> str:
        getter = self._providers.get("get_meshcore_contacts")
        return json.dumps(getter() if getter else [], ensure_ascii=False)

    def _tool_send_emergency(self, args: dict) -> str:
        msg = (args or {}).get("message", "").strip()
        if not msg:
            raise ValueError("'message' is required")
        fn = self._providers.get("send_emergency")
        if not fn:
            return "Emergency sending is unavailable."
        fn(msg)
        return "Emergency alert triggered."

    # ── JSON-RPC dispatch ────────────────────────────────────────────

    def _list_tools_payload(self) -> dict:
        self._build_extension_tools()
        tools = []
        for t in self._tools.values():
            tools.append({
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            })
        tools.sort(key=lambda x: x["name"])
        return {"tools": tools}

    def _call_tool(self, params: dict) -> dict:
        name = (params or {}).get("name")
        args = (params or {}).get("arguments") or {}
        if name not in self._tools:
            # Rebuild extension tools in case it's a freshly added one
            self._build_extension_tools()
        tool = self._tools.get(name)
        if not tool:
            raise _RpcError(METHOD_NOT_FOUND, f"Unknown tool: {name}")
        # Basic rate limiting
        max_per_min = int(self._mcp("rate_limit_per_min", 120))
        now = time.time()
        if now - self._last_call_ts > 60:
            self._call_count = 0
            self._last_call_ts = now
        self._call_count += 1
        if self._call_count > max_per_min:
            return {"content": [{"type": "text", "text": "Rate limit exceeded; slow down."}], "isError": True}
        try:
            result = tool["handler"](args)
            text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
            # clamp very large outputs
            if len(text) > 20000:
                text = text[:20000] + "\n…(truncated)"
            self._log(f"[MCP] tool '{name}' called OK")
            return {"content": [{"type": "text", "text": text}], "isError": False}
        except _RpcError:
            raise
        except Exception as exc:
            self._log(f"[MCP] tool '{name}' error: {exc}")
            return {"content": [{"type": "text", "text": f"Tool error: {exc}"}], "isError": True}

    def _negotiate_version(self, params: dict) -> str:
        requested = (params or {}).get("protocolVersion")
        if requested in SUPPORTED_PROTOCOL_VERSIONS:
            return requested
        return PROTOCOL_VERSION

    def dispatch(self, msg: dict) -> Optional[dict]:
        """Handle a single JSON-RPC message. Returns a response dict, or None
        for notifications (which get no response)."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
            return _error(None, INVALID_REQUEST, "Invalid JSON-RPC request")
        method = msg.get("method")
        msg_id = msg.get("id")
        is_notification = "id" not in msg
        params = msg.get("params") or {}

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": self._negotiate_version(params),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "instructions": (
                        "MESH-API exposes Meshtastic/MeshCore mesh networks as tools. "
                        "Use mesh_list_nodes, mesh_network_status and mesh_get_messages to "
                        "observe; mesh_send_message and mesh_run_command to act; and any "
                        "ext_* tools to drive installed extensions."
                    ),
                }
                return _result(msg_id, result)

            if method in ("notifications/initialized", "initialized"):
                return None  # notification, no response

            if method == "ping":
                return _result(msg_id, {})

            if method == "tools/list":
                return _result(msg_id, self._list_tools_payload())

            if method == "tools/call":
                return _result(msg_id, self._call_tool(params))

            if is_notification:
                return None
            return _error(msg_id, METHOD_NOT_FOUND, f"Method not found: {method}")
        except _RpcError as re:
            return _error(msg_id, re.code, re.message)
        except Exception as exc:
            self._log(f"[MCP] dispatch error: {exc}\n{traceback.format_exc()}")
            return _error(msg_id, INTERNAL_ERROR, f"Internal error: {exc}")

    def handle_http(self, request):
        """Handle a Flask request to the MCP endpoint. Returns (body, status,
        headers)."""
        denied = self.check_request(request)
        if denied:
            code, text = denied
            return (json.dumps(_error(None, INVALID_REQUEST, text)), code,
                    {"Content-Type": "application/json"})
        try:
            raw = request.get_data(as_text=True) or ""
            payload = json.loads(raw) if raw.strip() else {}
        except Exception:
            return (json.dumps(_error(None, PARSE_ERROR, "Parse error")), 400,
                    {"Content-Type": "application/json"})

        # Batch support
        if isinstance(payload, list):
            responses = [r for r in (self.dispatch(m) for m in payload) if r is not None]
            if not responses:
                return ("", 202, {})
            return (json.dumps(responses), 200, {"Content-Type": "application/json"})

        resp = self.dispatch(payload)
        if resp is None:
            return ("", 202, {})  # notification accepted
        headers = {"Content-Type": "application/json"}
        # Offer a session id on initialize (clients may echo it back)
        if isinstance(payload, dict) and payload.get("method") == "initialize":
            sid = secrets.token_hex(16)
            self._sessions[sid] = time.time()
            headers["Mcp-Session-Id"] = sid
        return (json.dumps(resp), 200, headers)

    # ── introspection for the web UI ─────────────────────────────────

    def info(self) -> dict:
        self._build_extension_tools()
        return {
            "enabled": self.enabled,
            "endpoint": "/mcp",
            "require_auth": bool(self._mcp("require_auth", True)),
            "tool_count": len(self._tools),
            "tools": sorted(self._tools.keys()),
            "protocol_version": PROTOCOL_VERSION,
        }


class _RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _result(msg_id, result) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code, message) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
