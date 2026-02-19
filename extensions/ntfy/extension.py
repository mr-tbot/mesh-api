"""
ntfy extension for MESH-API.

ntfy (https://ntfy.sh) is a simple HTTP-based pub/sub notification service.
It supports push notifications to phones, desktops, and other clients.

This extension sends mesh messages, AI responses, and emergency alerts
to an ntfy topic.  It also supports receiving messages by subscribing
to the topic via Server-Sent Events (SSE) and routing them onto the mesh.

Works with both the public ntfy.sh server and self-hosted instances.
"""

import json
import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class NtfyExtension(BaseExtension):
    """ntfy push notification extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Ntfy"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def server_url(self) -> str:
        url = self.config.get("server_url", "https://ntfy.sh")
        return url.rstrip("/")

    @property
    def topic(self) -> str:
        return self.config.get("topic", "")

    @property
    def access_token(self) -> str:
        return self.config.get("access_token", "")

    @property
    def priority(self) -> int:
        return int(self.config.get("priority", 3))

    @property
    def emergency_priority(self) -> int:
        return int(self.config.get("emergency_priority", 5))

    @property
    def tags(self) -> str:
        return self.config.get("tags", "satellite_antenna")

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

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._subscribe_thread = None
        self._stop_event = threading.Event()

        if not self.topic:
            self.log("Ntfy enabled but no topic configured.")
            return

        self.log(f"Ntfy enabled. server={self.server_url}, topic={self.topic}")

        # Start SSE subscription thread for inbound messages
        if self.inbound_channel_index is not None:
            self._subscribe_thread = threading.Thread(
                target=self._subscribe_sse,
                daemon=True,
                name="ntfy-subscribe",
            )
            self._subscribe_thread.start()
            self.log("Ntfy SSE subscription thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._subscribe_thread and self._subscribe_thread.is_alive():
            self._subscribe_thread.join(timeout=5)
        self.log("Ntfy extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → ntfy
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._publish(message, title="Mesh Message")
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._publish(message, title="AI Response")

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._publish(f"{sender}: {message}", title="Mesh Message")

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
                self._publish(body, title="EMERGENCY ALERT",
                              priority=self.emergency_priority,
                              tags="warning,rotating_light")
                self.log("✅ Emergency alert sent via ntfy.")
            except Exception as exc:
                self.log(f"⚠️ Ntfy emergency error: {exc}")

    # ------------------------------------------------------------------
    # Inbound: ntfy SSE → Mesh
    # ------------------------------------------------------------------

    def _subscribe_sse(self) -> None:
        """Subscribe to the ntfy topic via SSE and route messages to mesh."""
        time.sleep(5)
        url = f"{self.server_url}/{self.topic}/sse"
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"

        while not self._stop_event.is_set():
            try:
                resp = requests.get(url, headers=headers, stream=True,
                                    timeout=90)
                for line in resp.iter_lines(decode_unicode=True):
                    if self._stop_event.is_set():
                        break
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        data = json.loads(line[5:].strip())
                        if data.get("event") != "message":
                            continue
                        text = data.get("message", "")
                        title = data.get("title", "")
                        if not text:
                            continue
                        formatted = f"[Ntfy:{title}] {text}" if title else f"[Ntfy] {text}"
                        log_fn = self.app_context.get("log_message")
                        if log_fn:
                            log_fn("Ntfy", formatted, direct=False,
                                   channel_idx=self.inbound_channel_index)
                        if self.inbound_channel_index is not None:
                            self.send_to_mesh(formatted,
                                              channel_index=self.inbound_channel_index)
                        self.log(f"Ntfy inbound: {formatted}")
                    except (json.JSONDecodeError, ValueError):
                        pass
            except Exception as exc:
                if not self._stop_event.is_set():
                    self.log(f"Ntfy SSE error (reconnecting): {exc}")
                    time.sleep(5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish(self, message: str, title: str = "",
                 priority: int | None = None,
                 tags: str | None = None) -> None:
        """Publish a notification to the ntfy topic."""
        if not self.topic:
            return
        try:
            headers = {
                "Title": title or "MESH-API",
                "Priority": str(priority if priority is not None else self.priority),
                "Tags": tags or self.tags,
            }
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            url = f"{self.server_url}/{self.topic}"
            requests.post(url, data=message.encode("utf-8"),
                          headers=headers, timeout=10)
        except Exception as exc:
            self.log(f"⚠️ Ntfy publish error: {exc}")
