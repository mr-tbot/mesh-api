"""
Mattermost extension for MESH-API.

Provides bidirectional Mattermost ↔ Mesh integration:
- Outbound: sends mesh messages to a Mattermost channel via webhook or
  the REST API.
- Inbound:  polls the Mattermost API for new posts in a channel and routes
  them onto the mesh.
- Emergency: posts emergency alerts to the configured channel.

Requires either an Incoming Webhook URL (outbound only) or a Personal
Access Token + Channel ID for full bidirectional support.
"""

import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class MattermostExtension(BaseExtension):
    """Mattermost ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Mattermost"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def server_url(self) -> str:
        url = self.config.get("server_url", "")
        return url.rstrip("/") if url else ""

    @property
    def access_token(self) -> str:
        return self.config.get("access_token", "")

    @property
    def channel_id(self) -> str:
        return self.config.get("channel_id", "")

    @property
    def webhook_url(self) -> str:
        return self.config.get("webhook_url", "")

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
        return int(self.config.get("poll_interval_seconds", 5))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._last_post_time = 0

        status = []
        if self.server_url:
            status.append(f"server={self.server_url}")
        if self.webhook_url:
            status.append("webhook=set")
        if self.channel_id:
            status.append(f"channel={self.channel_id}")

        self.log(f"Mattermost enabled. {', '.join(status) if status else 'No settings configured.'}")

        if self.server_url and self.access_token and self.channel_id and self.receive_enabled:
            self._last_post_time = int(time.time() * 1000)  # ms epoch
            self._poll_thread = threading.Thread(
                target=self._poll_mattermost,
                daemon=True,
                name="mattermost-poll",
            )
            self._poll_thread.start()
            self.log("Mattermost polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("Mattermost extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Mattermost
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
            self._post(f"**{sender}**: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                self._post(f"🚨 **EMERGENCY ALERT**\n{message}")
                self.log("✅ Emergency alert posted to Mattermost.")
            except Exception as exc:
                self.log(f"⚠️ Mattermost emergency error: {exc}")

    # ------------------------------------------------------------------
    # Inbound: Mattermost → Mesh (polling API)
    # ------------------------------------------------------------------

    def _poll_mattermost(self) -> None:
        time.sleep(5)
        headers = {"Authorization": f"Bearer {self.access_token}"}

        while not self._stop_event.is_set():
            try:
                url = f"{self.server_url}/api/v4/channels/{self.channel_id}/posts"
                params = {"since": self._last_post_time}
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    order = data.get("order", [])
                    posts = data.get("posts", {})
                    # Process in chronological order (oldest first)
                    for post_id in reversed(order):
                        post = posts.get(post_id, {})
                        # Skip system messages and bot posts
                        if post.get("type") or post.get("props", {}).get("from_webhook"):
                            continue
                        text = post.get("message", "")
                        create_at = post.get("create_at", 0)
                        if not text or create_at <= self._last_post_time:
                            continue
                        username = post.get("props", {}).get("username", "MMUser")
                        # Get username from user_id if not in props
                        user_id = post.get("user_id", "")
                        if username == "MMUser" and user_id:
                            try:
                                u_resp = requests.get(
                                    f"{self.server_url}/api/v4/users/{user_id}",
                                    headers=headers, timeout=5)
                                if u_resp.status_code == 200:
                                    username = u_resp.json().get("username", "MMUser")
                            except Exception:
                                pass

                        formatted = f"[MM:{username}] {text}"
                        log_fn = self.app_context.get("log_message")
                        if log_fn:
                            log_fn("Mattermost", formatted, direct=False,
                                   channel_idx=self.inbound_channel_index)
                        if self.inbound_channel_index is not None:
                            self.send_to_mesh(formatted,
                                              channel_index=self.inbound_channel_index)
                        self.log(f"Polled MM post: {formatted}")
                        self._last_post_time = max(self._last_post_time, create_at)
                else:
                    self.log(f"Mattermost API error: {resp.status_code}")
            except Exception as exc:
                self.log(f"Error polling Mattermost: {exc}")
            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post(self, text: str) -> None:
        """Post a message to Mattermost via webhook or API."""
        try:
            if self.webhook_url:
                requests.post(self.webhook_url, json={"text": text}, timeout=10)
            elif self.server_url and self.access_token and self.channel_id:
                headers = {"Authorization": f"Bearer {self.access_token}"}
                requests.post(
                    f"{self.server_url}/api/v4/posts",
                    headers=headers,
                    json={"channel_id": self.channel_id, "message": text},
                    timeout=10,
                )
        except Exception as exc:
            self.log(f"⚠️ Mattermost post error: {exc}")
