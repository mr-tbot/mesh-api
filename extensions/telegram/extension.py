"""
Telegram extension for MESH-API.

Provides bidirectional Telegram ↔ Mesh integration:
- Outbound: sends mesh messages and AI responses to a Telegram chat via
  the Bot API (sendMessage).
- Inbound:  polls Telegram for new messages using getUpdates and routes
  them onto the mesh.
- Emergency: posts emergency alerts to the configured chat.

Requires a Telegram Bot Token from @BotFather and the numeric chat_id
of the target group / user.
"""

import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class TelegramExtension(BaseExtension):
    """Telegram ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Telegram"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def bot_token(self) -> str:
        return self.config.get("bot_token", "")

    @property
    def chat_id(self) -> str:
        return str(self.config.get("chat_id", ""))

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
        self._last_update_id = 0

        status = []
        if self.bot_token:
            status.append("bot_token=set")
        if self.chat_id:
            status.append(f"chat_id={self.chat_id}")

        self.log(f"Telegram enabled. {', '.join(status) if status else 'No settings configured.'}")

        if self.bot_token and self.chat_id and self.receive_enabled:
            self._poll_thread = threading.Thread(
                target=self._poll_telegram,
                daemon=True,
                name="telegram-poll",
            )
            self._poll_thread.start()
            self.log("Telegram polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("Telegram extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Telegram
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_telegram(message)
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_telegram(message)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._send_telegram(f"<b>{sender}</b>: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                self._send_telegram(f"🚨 <b>EMERGENCY ALERT</b>\n{message}")
                self.log("✅ Emergency alert posted to Telegram.")
            except Exception as exc:
                self.log(f"⚠️ Telegram emergency error: {exc}")

    # ------------------------------------------------------------------
    # Inbound: Telegram → Mesh (long-poll via getUpdates)
    # ------------------------------------------------------------------

    def _poll_telegram(self) -> None:
        time.sleep(5)
        base = f"https://api.telegram.org/bot{self.bot_token}"

        while not self._stop_event.is_set():
            try:
                params = {
                    "offset": self._last_update_id + 1,
                    "timeout": self.poll_interval,
                    "allowed_updates": '["message"]',
                }
                resp = requests.get(f"{base}/getUpdates", params=params,
                                    timeout=self.poll_interval + 5)
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        self._last_update_id = update["update_id"]
                        msg = update.get("message")
                        if not msg:
                            continue
                        # Only accept messages from the configured chat
                        msg_chat_id = str(msg.get("chat", {}).get("id", ""))
                        if msg_chat_id != self.chat_id:
                            continue
                        text = msg.get("text", "")
                        if not text:
                            continue
                        user = msg.get("from", {})
                        username = user.get("username") or user.get("first_name", "TGUser")
                        formatted = f"[TG:{username}] {text}"
                        log_fn = self.app_context.get("log_message")
                        if log_fn:
                            log_fn("Telegram", formatted, direct=False,
                                   channel_idx=self.inbound_channel_index)
                        if self.inbound_channel_index is not None:
                            self.send_to_mesh(formatted,
                                              channel_index=self.inbound_channel_index)
                        self.log(f"Polled TG message: {formatted}")
                else:
                    self.log(f"Telegram API error: {data}")
            except Exception as exc:
                self.log(f"Error polling Telegram: {exc}")
                time.sleep(5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_telegram(self, text: str) -> None:
        """Send a message via the Telegram Bot API."""
        if not self.bot_token or not self.chat_id:
            return
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            requests.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
            })
        except Exception as exc:
            self.log(f"⚠️ Telegram send error: {exc}")
