"""
Slack extension for MESH-API.

Provides bidirectional Slack ↔ Mesh integration:
- Outbound: forwards mesh messages and AI responses to a Slack webhook or
  channel via the Bot API.
- Inbound:  polls Slack for new messages using the Bot API and routes them
  onto the mesh.
- Emergency: posts emergency alerts to the configured webhook / channel.

Configuration lives in this extension's own config.json.
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class SlackExtension(BaseExtension):
    """Slack ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Slack"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def webhook_url(self) -> str:
        return self.config.get("webhook_url", "")

    @property
    def bot_token(self) -> str:
        return self.config.get("bot_token", "")

    @property
    def channel_id(self) -> str:
        return self.config.get("channel_id", "")

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
    def receive_enabled(self) -> bool:
        return bool(self.config.get("receive_enabled", True))

    @property
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 10))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._last_ts = None

        status = []
        if self.webhook_url:
            status.append("webhook=set")
        if self.bot_token:
            status.append("bot_token=set")
        if self.channel_id:
            status.append(f"channel={self.channel_id}")

        self.log(f"Slack enabled. {', '.join(status) if status else 'No settings configured.'}")

        if self.bot_token and self.channel_id and self.receive_enabled:
            self._poll_thread = threading.Thread(
                target=self._poll_slack,
                daemon=True,
                name="slack-poll",
            )
            self._poll_thread.start()
            self.log("Slack polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("Slack extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Slack
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._post(message)
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._post(message)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._post(f"*{sender}*: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                self._post(f"🚨 *EMERGENCY ALERT*\n{message}")
                self.log("✅ Emergency alert posted to Slack.")
            except Exception as exc:
                self.log(f"⚠️ Slack emergency error: {exc}")

    # ------------------------------------------------------------------
    # Inbound: Slack → Mesh (polling via conversations.history)
    # ------------------------------------------------------------------

    def _poll_slack(self) -> None:
        time.sleep(5)
        headers = {"Authorization": f"Bearer {self.bot_token}"}
        url = "https://slack.com/api/conversations.history"
        start_ts = str(datetime.now(timezone.utc).timestamp())
        self._last_ts = start_ts

        while not self._stop_event.is_set():
            try:
                params = {"channel": self.channel_id, "limit": 20}
                if self._last_ts:
                    params["oldest"] = self._last_ts
                resp = requests.get(url, headers=headers, params=params)
                data = resp.json()
                if data.get("ok"):
                    msgs = data.get("messages", [])
                    msgs.sort(key=lambda m: float(m.get("ts", 0)))
                    for msg in msgs:
                        if msg.get("subtype"):
                            continue  # skip bot messages, joins, etc.
                        user = msg.get("user", "SlackUser")
                        text = msg.get("text", "")
                        ts = msg.get("ts", "")
                        if not text:
                            continue
                        formatted = f"[Slack:{user}] {text}"
                        log_fn = self.app_context.get("log_message")
                        if log_fn:
                            log_fn("Slack", formatted, direct=False,
                                   channel_idx=self.inbound_channel_index)
                        if self.inbound_channel_index is not None:
                            self.send_to_mesh(formatted,
                                              channel_index=self.inbound_channel_index)
                        self.log(f"Polled Slack message: {formatted}")
                        self._last_ts = ts
                else:
                    self.log(f"Slack API error: {data.get('error', 'unknown')}")
            except Exception as exc:
                self.log(f"Error polling Slack: {exc}")
            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, text: str) -> None:
        """Post a message to Slack via webhook or Bot API."""
        try:
            if self.webhook_url:
                requests.post(self.webhook_url, json={"text": text})
            elif self.bot_token and self.channel_id:
                headers = {
                    "Authorization": f"Bearer {self.bot_token}",
                    "Content-Type": "application/json; charset=utf-8",
                }
                requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers=headers,
                    json={"channel": self.channel_id, "text": text},
                )
        except Exception as exc:
            self.log(f"⚠️ Slack post error: {exc}")
