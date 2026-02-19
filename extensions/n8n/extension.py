"""
n8n Workflow Automation extension for MESH-API.

Provides bidirectional integration with n8n (https://n8n.io):
- Outbound: forwards mesh messages and emergency alerts to n8n workflows
  via webhook trigger nodes.
- Inbound: exposes a Flask endpoint that n8n workflows can POST to,
  routing messages onto the mesh.
- Commands: check n8n instance status and trigger workflows manually.

Setup
-----
1. In n8n, create a Webhook Trigger node and copy its production URL
   into ``webhook_url`` in this extension's config.
2. (Optional) To enable status / trigger commands, set ``api_base_url``
   and ``api_key`` with an n8n API key (Settings → API → Create Key).
3. (Optional) For inbound messages from n8n, point an HTTP Request node
   at ``http://<mesh-api-host>:<port>/n8n/webhook`` with a JSON body
   containing at least a ``message`` field.
"""

import json
import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class N8nExtension(BaseExtension):
    """n8n ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "n8n"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def webhook_url(self) -> str:
        """n8n Webhook Trigger URL for outbound mesh → n8n messages."""
        return self.config.get("webhook_url", "")

    @property
    def webhook_secret(self) -> str:
        """Shared secret sent as X-Webhook-Secret header on outbound calls."""
        return self.config.get("webhook_secret", "")

    @property
    def api_base_url(self) -> str:
        """n8n instance base URL (e.g. http://localhost:5678)."""
        return self.config.get("api_base_url", "http://localhost:5678").rstrip("/")

    @property
    def api_key(self) -> str:
        """n8n API key for REST API calls (status, trigger, executions)."""
        return self.config.get("api_key", "")

    @property
    def send_emergency(self) -> bool:
        return bool(self.config.get("send_emergency", True))

    @property
    def send_ai(self) -> bool:
        return bool(self.config.get("send_ai", False))

    @property
    def send_all(self) -> bool:
        return bool(self.config.get("send_all", False))

    @property
    def receive_enabled(self) -> bool:
        return bool(self.config.get("receive_enabled", True))

    @property
    def receive_endpoint(self) -> str:
        return self.config.get("receive_endpoint", "/n8n/webhook")

    @property
    def receive_secret(self) -> str:
        """Shared secret for inbound webhook verification."""
        return self.config.get("receive_secret", "")

    @property
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    @property
    def message_field(self) -> str:
        return self.config.get("message_field", "message")

    @property
    def sender_field(self) -> str:
        return self.config.get("sender_field", "sender")

    @property
    def include_metadata(self) -> bool:
        return bool(self.config.get("include_metadata", True))

    @property
    def poll_executions(self) -> bool:
        return bool(self.config.get("poll_executions", False))

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 60))

    @property
    def broadcast_channel_index(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def bot_name(self) -> str:
        return self.config.get("bot_name", "MESH-API")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @property
    def commands(self) -> dict:
        return {
            "/n8n": "Show n8n integration status",
            "/n8n trigger": "Trigger an n8n workflow by ID",
            "/n8n workflows": "List active n8n workflows",
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()

        status_parts = []
        if self.webhook_url:
            status_parts.append(f"outbound→{self.webhook_url[:50]}")
        if self.receive_enabled:
            status_parts.append(f"inbound={self.receive_endpoint}")
        if self.api_key:
            status_parts.append("API connected")
        self.log(f"n8n extension loaded. {', '.join(status_parts) if status_parts else 'No settings configured.'}")

        # Start execution polling thread if enabled
        if self.poll_executions and self.api_key:
            self._stop_event.clear()
            self._poll_thread = threading.Thread(
                target=self._poll_executions_loop, daemon=True
            )
            self._poll_thread.start()
            self.log(f"Execution polling started (every {self.poll_interval}s).")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("n8n extension unloaded.")

    # ------------------------------------------------------------------
    # Flask routes (inbound — n8n → mesh)
    # ------------------------------------------------------------------

    def register_routes(self, app) -> None:
        ext = self

        @app.route(ext.receive_endpoint, methods=["POST"],
                    endpoint="n8n_inbound_webhook")
        def n8n_inbound_webhook():
            from flask import request, jsonify
            import hmac
            import hashlib

            if not ext.receive_enabled:
                return jsonify({"status": "disabled"}), 200

            # Optional shared-secret verification
            if ext.receive_secret:
                sig = request.headers.get("X-Webhook-Secret", "")
                if not hmac.compare_digest(sig, ext.receive_secret):
                    return jsonify({"status": "unauthorized"}), 401

            data = request.json
            if not data:
                return jsonify({"status": "error",
                                "message": "No JSON payload"}), 400

            text = data.get(ext.message_field)
            sender = data.get(ext.sender_field, "n8n")
            if not text:
                return jsonify({
                    "status": "error",
                    "message": f"Missing '{ext.message_field}' field"
                }), 400

            # Determine target channel
            channel = data.get("channel_index", ext.inbound_channel_index)
            destination = data.get("destination_id")

            formatted = f"[n8n:{sender}] {text}"

            # Log the message
            log_fn = ext.app_context.get("log_message")
            if log_fn:
                log_fn("n8n", formatted, direct=bool(destination),
                       channel_idx=channel)

            # Route to mesh
            if destination:
                ext.send_to_mesh(formatted, destination_id=destination)
            elif channel is not None:
                ext.send_to_mesh(formatted, channel_index=channel)
            else:
                ext.send_to_mesh(formatted,
                                 channel_index=ext.broadcast_channel_index)

            ext.log(f"Inbound from n8n: {formatted}")
            return jsonify({"status": "ok"})

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        cmd = command.lower().strip()

        if cmd == "/n8n" and not args.strip():
            return self._cmd_status()

        if cmd == "/n8n":
            sub = args.strip().split(None, 1)
            subcmd = sub[0].lower() if sub else ""
            subargs = sub[1] if len(sub) > 1 else ""

            if subcmd == "trigger":
                return self._cmd_trigger(subargs.strip(), node_info)
            if subcmd in ("workflows", "list"):
                return self._cmd_list_workflows()
            return f"Unknown subcommand: {subcmd}. Try /n8n, /n8n trigger <id>, /n8n workflows"

        return None

    def _cmd_status(self) -> str:
        """Return n8n integration status."""
        parts = [f"n8n Extension v{self.version}"]
        parts.append(f"Outbound webhook: {'configured' if self.webhook_url else 'not set'}")
        parts.append(f"Inbound endpoint: {self.receive_endpoint if self.receive_enabled else 'disabled'}")
        parts.append(f"API: {'connected' if self.api_key else 'not configured'}")

        if self.api_key:
            try:
                resp = requests.get(
                    f"{self.api_base_url}/api/v1/workflows",
                    headers=self._api_headers(),
                    params={"active": "true", "limit": 1},
                    timeout=5,
                )
                if resp.status_code == 200:
                    parts.append("n8n instance: reachable")
                else:
                    parts.append(f"n8n instance: HTTP {resp.status_code}")
            except Exception:
                parts.append("n8n instance: unreachable")

        return " | ".join(parts)

    def _cmd_trigger(self, workflow_id: str, node_info: dict) -> str:
        """Trigger an n8n workflow by ID via the API."""
        if not self.api_key:
            return "n8n API key not configured. Set api_key in extension config."
        if not workflow_id:
            return "Usage: /n8n trigger <workflow_id>"

        try:
            # Use the webhook-based test URL or the API activate endpoint
            resp = requests.post(
                f"{self.api_base_url}/api/v1/workflows/{workflow_id}/activate",
                headers=self._api_headers(),
                timeout=10,
            )
            if resp.status_code in (200, 201):
                return f"Workflow {workflow_id} activated successfully."
            return f"Failed to trigger workflow {workflow_id}: HTTP {resp.status_code}"
        except Exception as exc:
            return f"Error triggering workflow: {exc}"

    def _cmd_list_workflows(self) -> str:
        """List active n8n workflows."""
        if not self.api_key:
            return "n8n API key not configured."
        try:
            resp = requests.get(
                f"{self.api_base_url}/api/v1/workflows",
                headers=self._api_headers(),
                params={"active": "true", "limit": 10},
                timeout=10,
            )
            if resp.status_code != 200:
                return f"Failed to list workflows: HTTP {resp.status_code}"
            data = resp.json().get("data", [])
            if not data:
                return "No active workflows found."
            lines = [f"Active n8n workflows ({len(data)}):"]
            for wf in data:
                lines.append(f"  {wf.get('id')} - {wf.get('name', 'Unnamed')}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Error listing workflows: {exc}"

    # ------------------------------------------------------------------
    # Outbound: mesh → n8n
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Forward mesh messages to n8n via webhook."""
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)

        if self.send_all:
            self._fire_webhook(message, metadata)
        elif self.send_ai and is_ai:
            self._fire_webhook(message, metadata)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """Observe all mesh messages — forward if send_all is enabled."""
        if not self.send_all:
            return
        metadata = metadata or {}
        sender = metadata.get("sender_info", "Unknown")
        self._fire_webhook(f"{sender}: {message}", metadata)

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if not self.send_emergency:
            return
        try:
            meta = {"type": "emergency"}
            if gps_coords:
                meta["gps"] = gps_coords
            self._fire_webhook(f"🚨 EMERGENCY: {message}", meta)
            self.log("Emergency alert forwarded to n8n.")
        except Exception as exc:
            self.log(f"⚠️ n8n emergency error: {exc}")

    # ------------------------------------------------------------------
    # Execution polling (optional background thread)
    # ------------------------------------------------------------------

    def _poll_executions_loop(self) -> None:
        """Poll n8n for recent workflow executions and broadcast results."""
        last_check = time.time()
        while not self._stop_event.is_set():
            self._stop_event.wait(self.poll_interval)
            if self._stop_event.is_set():
                break
            try:
                resp = requests.get(
                    f"{self.api_base_url}/api/v1/executions",
                    headers=self._api_headers(),
                    params={
                        "status": "success",
                        "limit": 5,
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                executions = resp.json().get("data", [])
                for ex in executions:
                    finished = ex.get("stoppedAt", "")
                    # Simple time-based dedup: only announce new ones
                    if finished and finished > time.strftime(
                        "%Y-%m-%dT%H:%M:%S", time.gmtime(last_check)
                    ):
                        wf_name = ex.get("workflowData", {}).get("name", "Unknown")
                        msg = f"[n8n] Workflow completed: {wf_name}"
                        self.send_to_mesh(msg,
                                          channel_index=self.broadcast_channel_index)
                        self.log(msg)
                last_check = time.time()
            except Exception as exc:
                self.log(f"⚠️ Execution poll error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _api_headers(self) -> dict:
        """Return headers for n8n REST API requests."""
        return {
            "Accept": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }

    def _fire_webhook(self, message: str, metadata: dict | None = None) -> None:
        """POST a message to the configured n8n webhook URL."""
        if not self.webhook_url:
            return
        if requests is None:
            self.log("⚠️ 'requests' library not installed.")
            return
        try:
            payload = {
                "message": message,
                "source": self.bot_name,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if self.include_metadata and metadata:
                payload["metadata"] = metadata

            headers = {"Content-Type": "application/json"}
            if self.webhook_secret:
                headers["X-Webhook-Secret"] = self.webhook_secret

            resp = requests.post(
                self.webhook_url, json=payload,
                headers=headers, timeout=10
            )
            if resp.status_code not in (200, 201):
                self.log(f"⚠️ n8n webhook returned HTTP {resp.status_code}")
        except Exception as exc:
            self.log(f"⚠️ n8n webhook error: {exc}")
