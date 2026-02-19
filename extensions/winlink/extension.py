"""
Winlink extension for MESH-API.

Provides integration between the Meshtastic mesh network and the Winlink
Global Radio Email system (winlink.org) used by ham radio operators.

Features:
- Inbound:  polls a Winlink mailbox (via gateway or API) for new messages
  and forwards them onto the mesh.
- Outbound: sends messages from the mesh to Winlink email addresses via
  the /winlink command.
- /winlink <address> <message> — send a message to a Winlink address.
- /wlcheck — check for new Winlink messages.
- /wlstatus — show Winlink connection status.

Integration methods (in priority order):
1. Winlink REST API (api.winlink.org) — requires API key.
2. Direct RMS gateway connection (Telnet/TCP) — requires gateway host.
3. Pat (pat.winlink.org) local REST API — if Pat is running locally.

Note: This extension focuses on text-based Winlink messaging.  Full
VARA/Ardop modem integration would require additional hardware setup.
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class WinlinkExtension(BaseExtension):
    """Winlink radio email ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Winlink"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/winlink": "Send Winlink message (/winlink <addr> <msg>)",
            "/wlcheck": "Check for new Winlink messages",
            "/wlstatus": "Show Winlink connection status",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def callsign(self) -> str:
        return self.config.get("callsign", "").upper()

    @property
    def gateway_host(self) -> str:
        return self.config.get("gateway_host", "")

    @property
    def gateway_port(self) -> int:
        return int(self.config.get("gateway_port", 8772))

    @property
    def password(self) -> str:
        return self.config.get("password", "")

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 300))

    @property
    def auto_forward(self) -> bool:
        return bool(self.config.get("auto_forward_to_mesh", True))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def max_body_length(self) -> int:
        return int(self.config.get("max_body_length", 250))

    @property
    def outbound_enabled(self) -> bool:
        return bool(self.config.get("outbound_enabled", True))

    @property
    def api_url(self) -> str:
        url = self.config.get("winlink_api_url", "https://api.winlink.org")
        return url.rstrip("/")

    @property
    def api_key(self) -> str:
        return self.config.get("winlink_api_key", "")

    @property
    def rms_relay_path(self) -> str:
        return self.config.get("rms_relay_path", "")

    @property
    def default_to(self) -> str:
        return self.config.get("default_to_address", "")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._seen_ids: set = set()
        self._connected = False

        status = []
        if self.callsign:
            status.append(f"callsign={self.callsign}")
        if self.gateway_host:
            status.append(f"gw={self.gateway_host}:{self.gateway_port}")
        if self.api_key:
            status.append("api_key=set")

        self.log(f"Winlink enabled. {', '.join(status) if status else 'No settings configured.'}")

        if self.callsign and self.auto_forward and (self.api_key or self.gateway_host):
            self._poll_thread = threading.Thread(
                target=self._poll_winlink,
                daemon=True,
                name="winlink-poll",
            )
            self._poll_thread.start()
            self.log("Winlink polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("Winlink extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/wlstatus":
            return self._get_status()

        if command == "/wlcheck":
            count = self._check_messages()
            if count == 0:
                return f"📬 No new Winlink messages for {self.callsign}."
            return f"📬 {count} new Winlink message(s) for {self.callsign}."

        if command == "/winlink":
            if not self.outbound_enabled:
                return "Winlink outbound is disabled."
            if not args.strip():
                return "Usage: /winlink <address> <message>"
            parts = args.strip().split(None, 1)
            if len(parts) < 2:
                return "Usage: /winlink <address> <message>"
            to_addr = parts[0]
            body = parts[1]
            return self._send_winlink_message(to_addr, body, node_info)

        return None

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_winlink(self) -> None:
        time.sleep(15)

        while not self._stop_event.is_set():
            try:
                messages = self._fetch_messages()
                for msg in messages:
                    msg_id = msg.get("id", msg.get("mid", ""))
                    if msg_id and msg_id not in self._seen_ids:
                        self._seen_ids.add(msg_id)
                        text = self._format_message(msg)
                        self.send_to_mesh(text, channel_index=self.broadcast_channel)
                        self.log(f"Forwarded Winlink message: {msg_id}")

                if len(self._seen_ids) > 200:
                    excess = len(self._seen_ids) - 100
                    for _ in range(excess):
                        self._seen_ids.pop()

            except Exception as exc:
                self.log(f"Winlink poll error: {exc}")

            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        """Forward emergency alerts via Winlink if a default address is set."""
        if self.default_to and self.outbound_enabled:
            try:
                subject = "MESH-API EMERGENCY ALERT"
                body = message
                if gps_coords:
                    lat = gps_coords.get("lat", "?")
                    lon = gps_coords.get("lon", "?")
                    body += f"\nGPS: {lat}, {lon}"
                self._send_message_api(self.default_to, subject, body)
                self.log("✅ Emergency alert forwarded via Winlink.")
            except Exception as exc:
                self.log(f"⚠️ Winlink emergency send error: {exc}")

    # ------------------------------------------------------------------
    # API-based methods (Winlink REST API)
    # ------------------------------------------------------------------

    def _fetch_messages(self) -> list:
        """Fetch new messages from Winlink API or Pat."""
        # Try Winlink API first
        if self.api_key:
            return self._fetch_via_api()
        # Try Pat local REST API
        return self._fetch_via_pat()

    def _fetch_via_api(self) -> list:
        """Fetch messages via the Winlink REST API."""
        try:
            url = f"{self.api_url}/message/list"
            params = {
                "callsign": self.callsign,
                "key": self.api_key,
            }
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                messages = data if isinstance(data, list) else data.get("messages", [])
                return messages
            else:
                self.log(f"Winlink API error: {resp.status_code}")
        except Exception as exc:
            self.log(f"Winlink API fetch error: {exc}")
        return []

    def _fetch_via_pat(self) -> list:
        """Fetch messages from a local Pat instance (http://localhost:8080)."""
        try:
            resp = requests.get("http://localhost:8080/api/mailbox/INBOX",
                                timeout=5)
            if resp.status_code == 200:
                return resp.json() if isinstance(resp.json(), list) else []
        except Exception:
            pass  # Pat not running, silently skip
        return []

    def _check_messages(self) -> int:
        """Return count of new messages."""
        messages = self._fetch_messages()
        new_count = 0
        for msg in messages:
            msg_id = msg.get("id", msg.get("mid", ""))
            if msg_id and msg_id not in self._seen_ids:
                new_count += 1
        return new_count

    def _send_winlink_message(self, to_addr: str, body: str,
                               node_info: dict) -> str:
        """Send a message via Winlink."""
        sender = node_info.get("shortname", "MeshUser")
        subject = f"Mesh message from {sender}"

        # Try API first
        if self.api_key:
            return self._send_message_api(to_addr, subject, body)
        # Try Pat
        return self._send_message_pat(to_addr, subject, body)

    def _send_message_api(self, to_addr: str, subject: str,
                           body: str) -> str:
        """Send via Winlink REST API."""
        try:
            url = f"{self.api_url}/message/send"
            payload = {
                "callsign": self.callsign,
                "key": self.api_key,
                "to": to_addr,
                "subject": subject,
                "body": body,
            }
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code in (200, 201, 204):
                self.log(f"Winlink message sent to {to_addr}")
                return f"📧 Winlink message sent to {to_addr}."
            else:
                return f"⚠️ Winlink send failed: {resp.status_code}"
        except Exception as exc:
            return f"⚠️ Winlink send error: {exc}"

    def _send_message_pat(self, to_addr: str, subject: str,
                           body: str) -> str:
        """Send via local Pat REST API."""
        try:
            payload = {
                "to": to_addr,
                "subject": subject,
                "body": body,
                "from": self.callsign,
            }
            resp = requests.post("http://localhost:8080/api/mailbox/out",
                                 json=payload, timeout=10)
            if resp.status_code in (200, 201, 204):
                self.log(f"Winlink message queued via Pat to {to_addr}")
                return f"📧 Winlink message queued to {to_addr} (via Pat)."
            else:
                return f"⚠️ Pat send failed: {resp.status_code}"
        except Exception as exc:
            return f"⚠️ Pat not available: {exc}"

    def _format_message(self, msg: dict) -> str:
        """Format a Winlink message for mesh display."""
        sender = msg.get("from", msg.get("sender", "?"))
        subject = msg.get("subject", "(no subject)")
        body = msg.get("body", msg.get("message", ""))
        date = msg.get("date", msg.get("timestamp", ""))

        if body and len(body) > self.max_body_length:
            body = body[:self.max_body_length] + "..."

        parts = [f"📧 Winlink from {sender}"]
        if date:
            parts.append(f"Date: {date}")
        parts.append(f"Subj: {subject}")
        if body:
            parts.append(body)
        return "\n".join(parts)

    def _get_status(self) -> str:
        """Return current Winlink status."""
        parts = [f"📡 Winlink Status:"]
        parts.append(f"Callsign: {self.callsign or 'Not set'}")
        if self.api_key:
            parts.append("Method: Winlink API")
        elif self.gateway_host:
            parts.append(f"Method: Gateway {self.gateway_host}:{self.gateway_port}")
        else:
            parts.append("Method: Pat (local)")
        parts.append(f"Outbound: {'Enabled' if self.outbound_enabled else 'Disabled'}")
        parts.append(f"Auto-forward: {'On' if self.auto_forward else 'Off'}")
        parts.append(f"Poll interval: {self.poll_interval}s")
        return "\n".join(parts)
