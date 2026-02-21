"""
WhatsApp extension for MESH-API.

Provides bidirectional WhatsApp ↔ Mesh integration via the Meta WhatsApp
Business Cloud API (https://developers.facebook.com/docs/whatsapp/cloud-api):
- Outbound: sends mesh messages and AI responses to a WhatsApp recipient
  via the Cloud API (POST /{phone_number_id}/messages).
- Inbound:  receives WhatsApp messages via a registered webhook endpoint
  and routes them onto the mesh.
- Emergency: sends emergency alerts to the configured recipient.

Requires a Meta Business account with WhatsApp Business API access,
a System User permanent token, and a registered phone number ID.  See
https://developers.facebook.com/docs/whatsapp/cloud-api/get-started
for setup instructions.

No additional dependencies beyond ``requests`` (already in requirements.txt).
"""

import hashlib
import hmac
import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class WhatsAppExtension(BaseExtension):
    """WhatsApp ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "WhatsApp"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def api_url(self) -> str:
        """Base URL for the WhatsApp Cloud API (no trailing slash)."""
        url = self.config.get("api_url", "https://graph.facebook.com/v21.0")
        return url.rstrip("/") if url else "https://graph.facebook.com/v21.0"

    @property
    def phone_number_id(self) -> str:
        """The WhatsApp Business phone number ID (not the phone number itself)."""
        return self.config.get("phone_number_id", "")

    @property
    def access_token(self) -> str:
        """System User permanent token or temporary access token."""
        return self.config.get("access_token", "")

    @property
    def verify_token(self) -> str:
        """Webhook verification token (you choose this; Meta echoes it back)."""
        return self.config.get("verify_token", "")

    @property
    def recipient_number(self) -> str:
        """Default recipient phone number in E.164 format (e.g. +15551234567)."""
        return self.config.get("recipient_number", "")

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
    def webhook_path(self) -> str:
        return self.config.get("webhook_path", "/whatsapp/webhook")

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
            "/whatsapp": "Show WhatsApp integration status",
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        if requests is None:
            self.log("⚠️ 'requests' library is not installed — WhatsApp extension cannot function.")
            return

        status = []
        if self.phone_number_id:
            status.append(f"phone_id={self.phone_number_id}")
        if self.recipient_number:
            status.append(f"recipient={self.recipient_number}")
        if self.receive_enabled:
            status.append(f"webhook={self.webhook_path}")

        self.log(
            f"WhatsApp enabled. "
            f"{', '.join(status) if status else 'No settings configured.'}"
        )

    def on_unload(self) -> None:
        self.log("WhatsApp extension unloaded.")

    # ------------------------------------------------------------------
    # Flask routes — inbound webhook from Meta
    # ------------------------------------------------------------------

    def register_routes(self, app) -> None:
        """Register the WhatsApp webhook endpoint.

        Meta's Cloud API uses two requests:
        1. GET  — Webhook verification (hub.mode, hub.verify_token,
           hub.challenge).
        2. POST — Inbound message notifications (JSON payload).
        """
        ext = self  # closure reference

        @app.route(ext.webhook_path, methods=["GET"],
                    endpoint="whatsapp_webhook_verify")
        def whatsapp_verify():
            """Handle the Meta webhook verification challenge."""
            from flask import request, Response

            mode = request.args.get("hub.mode", "")
            token = request.args.get("hub.verify_token", "")
            challenge = request.args.get("hub.challenge", "")

            if mode == "subscribe" and token == ext.verify_token:
                ext.log("✅ WhatsApp webhook verified.")
                return Response(challenge, status=200, mimetype="text/plain")

            ext.log("⚠️ WhatsApp webhook verification failed.")
            return Response("Forbidden", status=403)

        @app.route(ext.webhook_path, methods=["POST"],
                    endpoint="whatsapp_webhook_inbound")
        def whatsapp_inbound():
            """Process inbound WhatsApp messages from the Cloud API webhook."""
            from flask import request, jsonify

            if not ext.receive_enabled:
                return jsonify({"status": "disabled"}), 200

            data = request.get_json(silent=True)
            if not data:
                return jsonify({"status": "ok"}), 200

            # Meta sends a nested structure:
            # entry[].changes[].value.messages[]
            try:
                for entry in data.get("entry", []):
                    for change in entry.get("changes", []):
                        value = change.get("value", {})
                        contacts = {
                            c.get("wa_id", ""): c.get("profile", {}).get("name", "WhatsApp User")
                            for c in value.get("contacts", [])
                        }
                        for msg in value.get("messages", []):
                            msg_type = msg.get("type", "")
                            # Only process text messages
                            if msg_type != "text":
                                continue
                            text = msg.get("text", {}).get("body", "")
                            if not text:
                                continue
                            sender_id = msg.get("from", "")
                            sender_name = contacts.get(sender_id, sender_id)

                            formatted = f"[WA:{sender_name}] {text}"

                            log_fn = ext.app_context.get("log_message")
                            if log_fn:
                                log_fn(
                                    "WhatsApp", formatted,
                                    direct=False,
                                    channel_idx=ext.broadcast_channel_index,
                                )

                            ext.send_to_mesh(
                                formatted,
                                channel_index=ext.broadcast_channel_index,
                            )
                            ext.log(f"Inbound WA message: {formatted}")
            except Exception as exc:
                ext.log(f"⚠️ Error processing WhatsApp webhook: {exc}")

            # Always return 200 so Meta doesn't retry
            return jsonify({"status": "ok"}), 200

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/whatsapp":
            parts = [f"WhatsApp: {'✅ connected' if self.phone_number_id and self.access_token else '❌ not configured'}"]
            if self.phone_number_id:
                parts.append(f"Phone ID: {self.phone_number_id}")
            if self.recipient_number:
                parts.append(f"Recipient: {self.recipient_number}")
            parts.append(f"Send all: {'on' if self.send_all else 'off'}")
            parts.append(f"Receive: {'on' if self.receive_enabled else 'off'}")
            return " | ".join(parts)
        return None

    # ------------------------------------------------------------------
    # Outbound: mesh → WhatsApp
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Forward mesh messages to WhatsApp based on config flags."""
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        # send_all: forward non-AI messages from the watched channel
        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_whatsapp(message)
            return

        # send_ai: forward AI responses from the watched channel
        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_whatsapp(message)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """Observer hook — forward mesh messages to WhatsApp when send_all is on."""
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._send_whatsapp(f"*{sender}*: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                self._send_whatsapp(f"🚨 *EMERGENCY ALERT*\n{message}")
                self.log("✅ Emergency alert sent via WhatsApp.")
            except Exception as exc:
                self.log(f"⚠️ WhatsApp emergency error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_whatsapp(self, text: str) -> None:
        """Send a text message via the WhatsApp Cloud API.

        POST /{phone_number_id}/messages
        The recipient must have an active conversation window (user-initiated
        message within 24 hours) or the business must use an approved
        message template.
        """
        if not self.phone_number_id or not self.access_token or not self.recipient_number:
            return

        url = f"{self.api_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": self.recipient_number,
            "type": "text",
            "text": {"body": text},
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code not in (200, 201):
                self.log(f"⚠️ WhatsApp API error {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            self.log(f"⚠️ WhatsApp send error: {exc}")
