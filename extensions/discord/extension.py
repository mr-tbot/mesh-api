"""
Discord extension for MESH-API.

Provides bidirectional Discord ↔ Mesh integration:
- Outbound: forwards mesh messages and AI responses to a Discord webhook.
- Inbound:  receives messages from Discord (via webhook endpoint or bot
  polling) and routes them onto the mesh.
- Emergency: posts emergency alerts to the configured webhook.

All configuration lives in this extension's own config.json.  Legacy
keys in the main config.json are auto-migrated on first run.
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class DiscordExtension(BaseExtension):
    """Discord ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Discord"

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
    def response_channel_index(self):
        val = self.config.get("response_channel_index")
        return int(val) if val is not None else None

    @property
    def bot_token(self) -> str:
        return self.config.get("bot_token", "")

    @property
    def channel_id(self) -> str:
        return self.config.get("channel_id", "")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()

        status_parts = []
        if self.webhook_url:
            status_parts.append("webhook=set")
        if self.bot_token:
            status_parts.append("bot_token=set")
        if self.channel_id:
            status_parts.append(f"channel_id={self.channel_id}")
        if self.inbound_channel_index is not None:
            status_parts.append(f"inbound_ch={self.inbound_channel_index}")

        self.log(f"Discord enabled. {', '.join(status_parts) if status_parts else 'No settings configured.'}")

        # Start polling thread if bot credentials are configured
        if self.bot_token and self.channel_id:
            self._poll_thread = threading.Thread(
                target=self._poll_discord_channel,
                daemon=True,
                name="discord-poll",
            )
            self._poll_thread.start()
            self.log("Discord bot polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("Discord extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Discord
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Forward a mesh message to Discord via webhook.

        Controlled by the ``send_all`` and ``send_ai`` config flags and
        the channel matching logic.
        """
        if not self.webhook_url:
            return
        metadata = metadata or {}

        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        # send_all: forward messages from the configured inbound channel
        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._post_webhook(message)
            return

        # send_ai: forward AI responses back to Discord
        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._post_webhook(message)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """Observe hook — forward mesh messages to Discord if send_all is on."""
        if not self.webhook_url or not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")

        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._post_webhook(f"**{sender}**: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency and self.webhook_url:
            try:
                self._post_webhook(message)
                self.log("✅ Emergency alert posted to Discord.")
            except Exception as exc:
                self.log(f"⚠️ Discord emergency webhook error: {exc}")

    # ------------------------------------------------------------------
    # Flask routes (inbound webhook)
    # ------------------------------------------------------------------

    def register_routes(self, app) -> None:
        ext = self  # closure reference

        @app.route("/discord_webhook", methods=["POST"],
                    endpoint="discord_ext_webhook")
        def discord_webhook():
            from flask import request, jsonify

            if not ext.receive_enabled:
                return jsonify({"status": "disabled",
                                "message": "Discord receive is disabled"}), 200

            data = request.json
            if not data:
                return jsonify({"status": "error",
                                "message": "No JSON payload provided"}), 400

            username = data.get("username", "DiscordUser")
            channel_index = ext.inbound_channel_index
            message_text = data.get("message")
            if message_text is None:
                return jsonify({"status": "error",
                                "message": "Missing message"}), 400

            formatted_message = f"**{username}**: {message_text}"

            try:
                log_fn = ext.app_context.get("log_message")
                if log_fn:
                    log_fn("Discord", formatted_message, direct=False,
                           channel_idx=int(channel_index) if channel_index is not None else 0)

                iface = ext.app_context.get("interface")
                if iface is None:
                    ext.log("❌ Cannot route Discord message: interface is None.")
                else:
                    send_fn = ext.app_context.get("send_broadcast_chunks")
                    if send_fn and channel_index is not None:
                        send_fn(iface, formatted_message, int(channel_index))

                ext.log(f"✅ Routed Discord message on channel {channel_index}")
                return jsonify({"status": "sent",
                                "channel_index": channel_index,
                                "message": formatted_message})
            except Exception as e:
                ext.log(f"⚠️ Discord webhook error: {e}")
                return jsonify({"status": "error",
                                "message": str(e)}), 500

    # ------------------------------------------------------------------
    # Discord bot polling (inbound)
    # ------------------------------------------------------------------

    def _poll_discord_channel(self) -> None:
        """Polls the Discord API for new messages and routes them to mesh."""
        time.sleep(5)  # let interface initialise
        last_message_id = None
        headers = {"Authorization": f"Bot {self.bot_token}"}
        url = f"https://discord.com/api/v9/channels/{self.channel_id}/messages"
        server_start = self.app_context.get("server_start_time", datetime.now(timezone.utc))

        while not self._stop_event.is_set():
            try:
                params = {"limit": 10}
                if last_message_id:
                    params["after"] = last_message_id
                response = requests.get(url, headers=headers, params=params)
                if response.status_code == 200:
                    msgs = response.json()
                    msgs = sorted(msgs, key=lambda m: int(m["id"]))
                    for msg in msgs:
                        if msg["author"].get("bot"):
                            continue
                        # Skip messages from before startup
                        if last_message_id is None:
                            msg_ts = msg.get("timestamp")
                            if msg_ts:
                                msg_time = datetime.fromisoformat(
                                    msg_ts.replace("Z", "+00:00"))
                                if msg_time < server_start:
                                    continue
                        username = msg["author"].get("username", "DiscordUser")
                        content = msg.get("content")
                        if content:
                            formatted = f"**{username}**: {content}"
                            log_fn = self.app_context.get("log_message")
                            if log_fn:
                                log_fn("DiscordPoll", formatted,
                                       direct=False,
                                       channel_idx=self.inbound_channel_index)
                            iface = self.app_context.get("interface")
                            if iface is None:
                                self.log("❌ Cannot send polled Discord "
                                         "message: interface is None.")
                            else:
                                send_fn = self.app_context.get(
                                    "send_broadcast_chunks")
                                if send_fn and self.inbound_channel_index is not None:
                                    send_fn(iface, formatted,
                                            self.inbound_channel_index)
                            self.log(f"Polled and routed Discord message: "
                                     f"{formatted}")
                            last_message_id = msg["id"]
                else:
                    self.log(f"Discord poll error: {response.status_code} "
                             f"{response.text}")
            except Exception as exc:
                self.log(f"Error polling Discord: {exc}")
            # Sleep in small increments so we can check _stop_event
            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_webhook(self, content: str) -> None:
        """Post a message to the Discord webhook URL."""
        if not self.webhook_url:
            return
        try:
            requests.post(self.webhook_url, json={"content": content})
        except Exception as exc:
            self.log(f"⚠️ Discord webhook error: {exc}")
