"""
Pushover extension for MESH-API.

Pushover (https://pushover.net) provides real-time push notifications to
Android, iOS, and desktop devices.

This extension sends mesh messages, AI responses, and emergency alerts
to Pushover.  Supports priority levels including emergency (priority=2)
with retry/expire acknowledgement.

Requires a Pushover Application API Token and a User Key.
"""

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class PushoverExtension(BaseExtension):
    """Pushover push notification extension."""

    PUSHOVER_API = "https://api.pushover.net/1/messages.json"

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Pushover"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def api_token(self) -> str:
        return self.config.get("api_token", "")

    @property
    def user_key(self) -> str:
        return self.config.get("user_key", "")

    @property
    def device(self) -> str:
        return self.config.get("device", "")

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
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    @property
    def priority(self) -> int:
        return int(self.config.get("priority", 0))

    @property
    def emergency_priority(self) -> int:
        return int(self.config.get("emergency_priority", 2))

    @property
    def emergency_retry(self) -> int:
        return int(self.config.get("emergency_retry", 60))

    @property
    def emergency_expire(self) -> int:
        return int(self.config.get("emergency_expire", 3600))

    @property
    def sound(self) -> str:
        return self.config.get("sound", "pushover")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        status = []
        if self.api_token:
            status.append("token=set")
        if self.user_key:
            status.append("user=set")
        if self.device:
            status.append(f"device={self.device}")
        self.log(f"Pushover enabled. {', '.join(status) if status else 'No settings configured.'}")

    def on_unload(self) -> None:
        self.log("Pushover extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Pushover
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._push(message, title="Mesh Message")
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._push(message, title="AI Response")

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._push(f"{sender}: {message}", title="Mesh Message")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                body = message
                if gps_coords:
                    lat = gps_coords.get("lat", "?")
                    lon = gps_coords.get("lon", "?")
                    body += f"\nGPS: {lat}, {lon}"
                self._push(body, title="EMERGENCY ALERT",
                           priority=self.emergency_priority,
                           sound="siren")
                self.log("✅ Emergency alert sent via Pushover.")
            except Exception as exc:
                self.log(f"⚠️ Pushover emergency error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _push(self, message: str, title: str = "MESH-API",
              priority: int | None = None,
              sound: str | None = None) -> None:
        """Send a push notification via Pushover API."""
        if not self.api_token or not self.user_key:
            return
        try:
            prio = priority if priority is not None else self.priority
            payload = {
                "token": self.api_token,
                "user": self.user_key,
                "message": message,
                "title": title,
                "priority": prio,
                "sound": sound or self.sound,
            }
            if self.device:
                payload["device"] = self.device
            # Emergency priority requires retry and expire
            if prio == 2:
                payload["retry"] = self.emergency_retry
                payload["expire"] = self.emergency_expire

            resp = requests.post(self.PUSHOVER_API, data=payload, timeout=10)
            if resp.status_code != 200:
                self.log(f"Pushover API error: {resp.status_code} {resp.text}")
        except Exception as exc:
            self.log(f"⚠️ Pushover send error: {exc}")
