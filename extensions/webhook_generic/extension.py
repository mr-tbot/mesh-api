"""
Generic Webhook extension for MESH-API.

Provides a flexible, configurable webhook bridge:
- Outbound: sends mesh messages to any HTTP endpoint with a customisable
  JSON template, method, and headers.
- Inbound:  exposes a Flask endpoint that accepts POST payloads and routes
  the extracted message onto the mesh.
- Emergency: fires emergency alerts to the outbound URL.

This extension is designed to integrate with services that don't have a
dedicated extension — any system that can send/receive JSON webhooks.
"""

import json
import hmac
import hashlib

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class WebhookGenericExtension(BaseExtension):
    """Generic Webhook ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Webhook_Generic"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def outbound_url(self) -> str:
        return self.config.get("outbound_url", "")

    @property
    def outbound_method(self) -> str:
        return self.config.get("outbound_method", "POST").upper()

    @property
    def outbound_headers(self) -> dict:
        return self.config.get("outbound_headers", {})

    @property
    def outbound_template(self) -> str:
        return self.config.get("outbound_template",
                               '{"text": "{{message}}", "source": "mesh-api"}')

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
    def receive_endpoint(self) -> str:
        return self.config.get("receive_endpoint", "/webhook/mesh")

    @property
    def receive_secret(self) -> str:
        return self.config.get("receive_secret", "")

    @property
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    @property
    def message_field(self) -> str:
        return self.config.get("message_field", "message")

    @property
    def sender_field(self) -> str:
        return self.config.get("sender_field", "sender")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        status = []
        if self.outbound_url:
            status.append(f"out={self.outbound_url}")
        if self.receive_enabled:
            status.append(f"in={self.receive_endpoint}")
        self.log(f"Webhook_Generic enabled. {', '.join(status) if status else 'No settings configured.'}")

    def on_unload(self) -> None:
        self.log("Webhook_Generic extension unloaded.")

    # ------------------------------------------------------------------
    # Flask routes (inbound webhook)
    # ------------------------------------------------------------------

    def register_routes(self, app) -> None:
        ext = self

        @app.route(ext.receive_endpoint, methods=["POST"],
                    endpoint="webhook_generic_inbound")
        def webhook_generic_inbound():
            from flask import request, jsonify

            if not ext.receive_enabled:
                return jsonify({"status": "disabled"}), 200

            # Optional HMAC signature verification
            if ext.receive_secret:
                sig_header = request.headers.get("X-Signature-256", "")
                body = request.get_data()
                expected = "sha256=" + hmac.new(
                    ext.receive_secret.encode(),
                    body,
                    hashlib.sha256,
                ).hexdigest()
                if not hmac.compare_digest(sig_header, expected):
                    return jsonify({"status": "unauthorized"}), 401

            data = request.json
            if not data:
                return jsonify({"status": "error",
                                "message": "No JSON payload"}), 400

            text = data.get(ext.message_field)
            sender = data.get(ext.sender_field, "Webhook")
            if not text:
                return jsonify({"status": "error",
                                "message": f"Missing '{ext.message_field}' field"}), 400

            formatted = f"[WH:{sender}] {text}"
            log_fn = ext.app_context.get("log_message")
            if log_fn:
                log_fn("Webhook", formatted, direct=False,
                       channel_idx=ext.inbound_channel_index)
            if ext.inbound_channel_index is not None:
                ext.send_to_mesh(formatted,
                                 channel_index=ext.inbound_channel_index)
            ext.log(f"Inbound webhook: {formatted}")
            return jsonify({"status": "ok"})

    # ------------------------------------------------------------------
    # Outbound: mesh → Webhook
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._fire_webhook(message, metadata)
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._fire_webhook(message, metadata)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._fire_webhook(f"{sender}: {message}", metadata)

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                meta = {"type": "emergency"}
                if gps_coords:
                    meta["gps"] = gps_coords
                self._fire_webhook(f"🚨 EMERGENCY: {message}", meta)
                self.log("✅ Emergency alert fired via webhook.")
            except Exception as exc:
                self.log(f"⚠️ Webhook emergency error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fire_webhook(self, message: str, metadata: dict | None = None) -> None:
        """Send a message to the outbound webhook URL."""
        if not self.outbound_url:
            return
        try:
            # Render template
            body_str = self.outbound_template.replace("{{message}}", message)
            # Try to add metadata fields
            if metadata:
                for key, val in metadata.items():
                    body_str = body_str.replace(f"{{{{{key}}}}}", str(val))

            headers = {"Content-Type": "application/json"}
            headers.update(self.outbound_headers)

            try:
                body = json.loads(body_str)
            except (json.JSONDecodeError, ValueError):
                body = {"text": message}

            if self.outbound_method == "POST":
                requests.post(self.outbound_url, json=body,
                              headers=headers, timeout=10)
            elif self.outbound_method == "PUT":
                requests.put(self.outbound_url, json=body,
                             headers=headers, timeout=10)
            else:
                requests.request(self.outbound_method, self.outbound_url,
                                 json=body, headers=headers, timeout=10)
        except Exception as exc:
            self.log(f"⚠️ Webhook fire error: {exc}")
