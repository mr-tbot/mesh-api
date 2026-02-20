"""
OpenClaw extension for MESH-API.

Bridges the Meshtastic mesh network to an OpenClaw AI agent instance:
- Outbound commands: mesh users invoke /claw-XY or /agent-XY to query the
  OpenClaw agent, which can fan-out to Telegram, Discord, SMS, etc.
- Inbound polling: optionally polls OpenClaw for proactively queued messages
  (scheduled alerts, reminders) and injects them into the mesh.
- Emergency: forwards /emergency and /911 alerts to OpenClaw for multi-channel
  distribution.

All configuration lives in this extension's own config.json.
Requires only the ``requests`` library (already in requirements.txt).
"""

import re
import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Meshtastic node IDs are hex strings like !a1b2c3d4
_NODE_ID_RE = re.compile(r"^![0-9a-fA-F]{8}$")


def _is_valid_node_id(node_id: str) -> bool:
    """Return True if *node_id* looks like a valid Meshtastic hex node ID."""
    return bool(_NODE_ID_RE.match(node_id or ""))


class OpenClawExtension(BaseExtension):
    """OpenClaw ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "OpenClaw"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config convenience accessors
    # ------------------------------------------------------------------

    @property
    def openclaw_url(self) -> str:
        return self.config.get("openclaw_url", "http://localhost:18789").rstrip("/")

    @property
    def openclaw_token(self) -> str:
        return self.config.get("openclaw_token", "")

    @property
    def agent_name(self) -> str:
        return self.config.get("agent_name", "mesh-api")

    @property
    def allowed_nodes(self) -> list:
        return self.config.get("allowed_nodes", [])

    @property
    def forward_emergency(self) -> bool:
        return bool(self.config.get("forward_emergency", True))

    @property
    def timeout(self) -> int:
        return int(self.config.get("timeout", 15))

    @property
    def poll_enabled(self) -> bool:
        return bool(self.config.get("poll_enabled", False))

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval", 30))

    # ------------------------------------------------------------------
    # Derived: command suffix from the core ai_command alias
    # ------------------------------------------------------------------

    def _ai_suffix(self) -> str:
        """Extract the per-install suffix from the core ai_command alias.

        The main config stores something like "/ai-9z"; we need "9z" so
        our commands become /claw-9z and /agent-9z, matching the install's
        unique namespace.
        """
        main_config = self.app_context.get("config", {})
        alias = main_config.get("ai_command", "")
        m = re.match(r"^(?:/ai-([a-z0-9]+)|/ai([a-z0-9]+))$", alias, re.IGNORECASE)
        if m:
            return m.group(1) or m.group(2)
        return ""

    # ------------------------------------------------------------------
    # Commands registration
    # ------------------------------------------------------------------

    @property
    def commands(self) -> dict:
        """Register /claw-XY and /agent-XY where XY is the install suffix."""
        suffix = self._ai_suffix()
        if not suffix:
            # Fallback: register generic commands (will be rare — ai_command
            # is always set by the time extensions load)
            return {
                "/claw": "Query the OpenClaw AI agent",
                "/agent": "Query the OpenClaw AI agent (alias)",
            }
        return {
            f"/claw-{suffix}": "Query the OpenClaw AI agent",
            f"/agent-{suffix}": "Query the OpenClaw AI agent (alias)",
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        if requests is None:
            self.log("⚠️ 'requests' library is not installed — OpenClaw extension cannot function.")
            return

        self._stop_event = threading.Event()
        self._poll_thread = None

        suffix = self._ai_suffix()
        self.log(
            f"OpenClaw enabled. URL={self.openclaw_url}, "
            f"agent={self.agent_name}, "
            f"commands=/claw-{suffix} /agent-{suffix}, "
            f"poll={'on' if self.poll_enabled else 'off'}"
        )

        # Start the optional polling thread for proactive messages
        if self.poll_enabled:
            self._poll_thread = threading.Thread(
                target=self._poll_loop,
                daemon=True,
                name="openclaw-poll",
            )
            self._poll_thread.start()
            self.log(f"OpenClaw polling thread started (interval={self.poll_interval}s).")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("OpenClaw extension unloaded.")

    # ------------------------------------------------------------------
    # Command handling: /claw-XY <message> and /agent-XY <message>
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        """Forward the mesh user's query to the OpenClaw agent and return
        the response as a mesh message (chunked, with AI prefix)."""

        # ACL check — if allowed_nodes is non-empty, enforce it
        sender_id = node_info.get("node_id", "")
        if self.allowed_nodes and sender_id not in self.allowed_nodes:
            return "Access denied."

        query = (args or "").strip()
        if not query:
            return "Usage: /claw-{suffix} <your question>"

        # Build the payload for OpenClaw's agent message endpoint
        payload = {
            "agent": self.agent_name,
            "message": query,
            "context": {
                "source": "meshtastic",
                "node_id": sender_id,
                "node_name": node_info.get("longname", node_info.get("shortname", "Unknown")),
                "channel": node_info.get("channel_idx", 0),
            },
        }

        try:
            resp = self._post_openclaw("/api/agent/message", payload)
        except Exception as exc:
            self.log(f"⚠️ OpenClaw request failed: {exc}")
            return "OpenClaw unavailable, try again later."

        if resp is None:
            return "No response from OpenClaw."

        # Extract the reply text from the response
        reply_text = self._extract_reply(resp)
        if not reply_text:
            return "OpenClaw returned an empty response."

        # Sanitize model output if the helper is available
        sanitize = self.app_context.get("sanitize_model_output")
        if sanitize:
            reply_text = sanitize(reply_text)

        # Prepend the "m@i" bot-loop marker so MESH-API (and other nodes
        # running MESH-API) will not process this as a human message
        add_ai_prefix = self.app_context.get("add_ai_prefix")
        if add_ai_prefix:
            reply_text = add_ai_prefix(reply_text)
        else:
            # Fallback: manually prepend the tag from app_context
            prefix_tag = self.app_context.get("AI_PREFIX_TAG", "m@i- ")
            if not reply_text.lstrip().startswith(prefix_tag):
                reply_text = f"{prefix_tag}{reply_text}"

        return reply_text

    # ------------------------------------------------------------------
    # Outbound hook: mesh → OpenClaw (send_message)
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Receive responses FROM OpenClaw (relayed through the loader's
        broadcast_message) and send them TO the mesh.

        This hook is called by the loader for every message the core
        wants to push to extensions.  We only act on messages that carry
        metadata flagging them as OpenClaw-originated, to avoid echoing
        every mesh message back.
        """
        metadata = metadata or {}

        # Only relay messages explicitly tagged for this extension
        if not metadata.get("openclaw_relay"):
            return

        text = (message or "").strip()
        if not text:
            return

        # The core's send_to_mesh helper already handles chunking and
        # delay — delegate to it.
        channel = metadata.get("channel_idx", 0)
        dest = metadata.get("destination_id")
        self.send_to_mesh(text, channel_index=channel, destination_id=dest)

    # ------------------------------------------------------------------
    # Inbound hook: OpenClaw → mesh (polling)
    # ------------------------------------------------------------------

    def receive_message(self) -> None:
        """Polling-based inbound: fetch proactively queued messages from
        OpenClaw (scheduled alerts, reminders, etc.) and inject them
        into the mesh.

        In practice the background thread (_poll_loop) calls this;
        the loader also calls it periodically if no thread is used.
        """
        if not self.poll_enabled:
            return

        try:
            resp = self._get_openclaw(f"/api/agent/{self.agent_name}/queue")
        except Exception as exc:
            self.log(f"⚠️ OpenClaw poll error: {exc}")
            return

        if resp is None:
            return

        messages = resp if isinstance(resp, list) else resp.get("messages", [])
        for item in messages:
            text = item.get("message") or item.get("text", "")
            if not text:
                continue

            # Prepend AI marker for loop prevention
            add_ai_prefix = self.app_context.get("add_ai_prefix")
            if add_ai_prefix:
                text = add_ai_prefix(text)
            else:
                prefix_tag = self.app_context.get("AI_PREFIX_TAG", "m@i- ")
                if not text.lstrip().startswith(prefix_tag):
                    text = f"{prefix_tag}{text}"

            dest = item.get("node_id")
            channel = item.get("channel", 0)
            self.send_to_mesh(text, channel_index=channel, destination_id=dest)
            self.log(f"Injected queued OpenClaw message to mesh (dest={dest or 'broadcast'}).")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        """Forward emergency alerts to OpenClaw for multi-channel fan-out."""
        if not self.forward_emergency:
            return

        payload = {
            "agent": self.agent_name,
            "type": "emergency",
            "message": message,
        }
        if gps_coords:
            payload["gps"] = gps_coords

        try:
            self._post_openclaw("/api/agent/emergency", payload)
            self.log("✅ Emergency alert forwarded to OpenClaw.")
        except Exception as exc:
            self.log(f"⚠️ Failed to forward emergency to OpenClaw: {exc}")

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _auth_headers(self) -> dict:
        """Build HTTP headers, including the bearer token if configured."""
        headers = {"Content-Type": "application/json"}
        if self.openclaw_token:
            headers["Authorization"] = f"Bearer {self.openclaw_token}"
        return headers

    def _post_openclaw(self, path: str, payload: dict) -> dict | None:
        """POST JSON to an OpenClaw endpoint.  Returns parsed JSON or None."""
        url = f"{self.openclaw_url}{path}"
        try:
            r = requests.post(
                url,
                json=payload,
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json() if r.text.strip() else None
        except requests.exceptions.Timeout:
            self.log(f"⚠️ OpenClaw request timed out ({self.timeout}s): POST {path}")
            raise
        except requests.exceptions.ConnectionError:
            self.log(f"⚠️ OpenClaw unreachable: POST {path}")
            raise
        except requests.exceptions.HTTPError as exc:
            self.log(f"⚠️ OpenClaw HTTP error: {exc}")
            raise
        except Exception as exc:
            self.log(f"⚠️ OpenClaw unexpected error: {exc}")
            raise

    def _get_openclaw(self, path: str) -> dict | list | None:
        """GET from an OpenClaw endpoint.  Returns parsed JSON or None."""
        url = f"{self.openclaw_url}{path}"
        try:
            r = requests.get(
                url,
                headers=self._auth_headers(),
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json() if r.text.strip() else None
        except requests.exceptions.Timeout:
            self.log(f"⚠️ OpenClaw request timed out ({self.timeout}s): GET {path}")
            raise
        except requests.exceptions.ConnectionError:
            self.log(f"⚠️ OpenClaw unreachable: GET {path}")
            raise
        except Exception as exc:
            self.log(f"⚠️ OpenClaw request error: {exc}")
            raise

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_reply(resp: dict) -> str:
        """Extract the agent's reply text from an OpenClaw response.

        OpenClaw may return the reply under different keys depending on
        the endpoint version; try the most common shapes.
        """
        if isinstance(resp, str):
            return resp
        # Common response shapes: { "reply": "..." } or { "message": "..." }
        # or { "data": { "reply": "..." } }
        for key in ("reply", "message", "text", "response"):
            if key in resp:
                val = resp[key]
                return val if isinstance(val, str) else str(val)
        # Nested under "data"
        data = resp.get("data", {})
        if isinstance(data, dict):
            for key in ("reply", "message", "text", "response"):
                if key in data:
                    val = data[key]
                    return val if isinstance(val, str) else str(val)
        return ""

    # ------------------------------------------------------------------
    # Background polling loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Background thread: periodically polls OpenClaw for queued messages."""
        while not self._stop_event.is_set():
            try:
                self.receive_message()
            except Exception as exc:
                self.log(f"⚠️ OpenClaw poll loop error: {exc}")
            self._stop_event.wait(self.poll_interval)
