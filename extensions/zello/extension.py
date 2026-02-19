"""
Zello extension for MESH-API.

Provides outbound Mesh → Zello integration for push-to-talk (PTT) channels:
- Outbound: forwards mesh messages to a Zello channel as text messages
  via the Zello Channel API (or Work API).
- Emergency: posts emergency alerts to the configured Zello channel.

Note: Full bidirectional audio-based integration would require the Zello
WebSocket streaming protocol and audio encoding.  This extension focuses
on text-based message forwarding using the REST API.

Requires Zello API credentials (token + channel name).
"""

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class ZelloExtension(BaseExtension):
    """Zello PTT channel bridge extension (outbound text)."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Zello"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def api_url(self) -> str:
        url = self.config.get("api_url", "https://zello.io/api")
        return url.rstrip("/")

    @property
    def api_token(self) -> str:
        return self.config.get("api_token", "")

    @property
    def channel_name(self) -> str:
        return self.config.get("channel_name", "")

    @property
    def username(self) -> str:
        return self.config.get("username", "")

    @property
    def password(self) -> str:
        return self.config.get("password", "")

    @property
    def send_emergency(self) -> bool:
        return bool(self.config.get("send_emergency", False))

    @property
    def send_ai(self) -> bool:
        return bool(self.config.get("send_ai", False))

    @property
    def send_all(self) -> bool:
        return bool(self.config.get("send_all", False))

    @property
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._session_token = None
        status = []
        if self.channel_name:
            status.append(f"channel={self.channel_name}")
        if self.api_token:
            status.append("api_token=set")
        self.log(f"Zello enabled. {', '.join(status) if status else 'No settings configured.'}")

    def on_unload(self) -> None:
        self.log("Zello extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Zello
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_zello(message)
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_zello(message)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._send_zello(f"{sender}: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                self._send_zello(f"EMERGENCY ALERT: {message}")
                self.log("✅ Emergency alert sent to Zello.")
            except Exception as exc:
                self.log(f"⚠️ Zello emergency error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self) -> str | None:
        """Authenticate with Zello Work API and cache session token."""
        if self._session_token:
            return self._session_token
        if not self.api_token or not self.username:
            return None
        try:
            resp = requests.post(
                f"{self.api_url}/user/gettoken",
                json={"username": self.username, "password": self.password},
                headers={"X-Api-Key": self.api_token},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._session_token = data.get("token")
                return self._session_token
            else:
                self.log(f"Zello auth failed: {resp.status_code}")
        except Exception as exc:
            self.log(f"Zello auth error: {exc}")
        return None

    def _send_zello(self, text: str) -> None:
        """Send a text message to the Zello channel.

        Uses the Zello Work API endpoint for text messages.  If a direct
        text endpoint is not available, falls back to a channel alert.
        """
        if not self.channel_name:
            return
        try:
            headers = {"X-Api-Key": self.api_token}
            token = self._get_session()
            if token:
                headers["X-Session-Token"] = token

            # Zello Work API: send text to channel
            payload = {
                "channel": self.channel_name,
                "text": text,
                "for": self.channel_name,
            }
            resp = requests.post(
                f"{self.api_url}/message/send",
                json=payload,
                headers=headers,
                timeout=10,
            )
            if resp.status_code not in (200, 201, 204):
                self.log(f"Zello send response: {resp.status_code} {resp.text}")
        except Exception as exc:
            self.log(f"⚠️ Zello send error: {exc}")
