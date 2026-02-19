"""
MQTT extension for MESH-API.

Provides bidirectional MQTT ↔ Mesh integration:
- Outbound: publishes mesh messages and AI responses to an MQTT topic.
- Inbound:  subscribes to an MQTT topic and routes incoming messages
  onto the mesh.
- Emergency: publishes emergency alerts to a dedicated topic.

Uses the paho-mqtt client library.  Install with:
    pip install paho-mqtt

Configuration lives in this extension's own config.json.
"""

import json
import threading
import time

try:
    import paho.mqtt.client as mqtt_client
except ImportError:
    mqtt_client = None

from extensions.base_extension import BaseExtension


class MqttExtension(BaseExtension):
    """MQTT ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "MQTT"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def broker_host(self) -> str:
        return self.config.get("broker_host", "localhost")

    @property
    def broker_port(self) -> int:
        return int(self.config.get("broker_port", 1883))

    @property
    def mqtt_username(self) -> str:
        return self.config.get("username", "")

    @property
    def mqtt_password(self) -> str:
        return self.config.get("password", "")

    @property
    def use_tls(self) -> bool:
        return bool(self.config.get("use_tls", False))

    @property
    def client_id(self) -> str:
        return self.config.get("client_id", "mesh-api")

    @property
    def publish_topic(self) -> str:
        return self.config.get("publish_topic", "mesh/outbound")

    @property
    def subscribe_topic(self) -> str:
        return self.config.get("subscribe_topic", "mesh/inbound")

    @property
    def emergency_topic(self) -> str:
        return self.config.get("emergency_topic", "mesh/emergency")

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
    def qos(self) -> int:
        return int(self.config.get("qos", 1))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._client = None
        self._connected = False

        if mqtt_client is None:
            self.log("⚠️ paho-mqtt not installed. Run: pip install paho-mqtt")
            return

        self.log(f"MQTT connecting to {self.broker_host}:{self.broker_port}")

        try:
            self._client = mqtt_client.Client(
                client_id=self.client_id,
                protocol=mqtt_client.MQTTv311,
            )
            if self.mqtt_username:
                self._client.username_pw_set(self.mqtt_username, self.mqtt_password)
            if self.use_tls:
                self._client.tls_set()

            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect

            self._client.connect_async(self.broker_host, self.broker_port, keepalive=60)
            self._client.loop_start()
        except Exception as exc:
            self.log(f"⚠️ MQTT connection error: {exc}")

    def on_unload(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self.log("MQTT extension unloaded.")

    # ------------------------------------------------------------------
    # MQTT callbacks
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            self.log(f"✅ Connected to MQTT broker {self.broker_host}")
            if self.receive_enabled and self.subscribe_topic:
                client.subscribe(self.subscribe_topic, qos=self.qos)
                self.log(f"Subscribed to {self.subscribe_topic}")
        else:
            self.log(f"⚠️ MQTT connect failed with rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            self.log(f"MQTT disconnected unexpectedly (rc={rc}), will auto-reconnect.")

    def _on_message(self, client, userdata, msg):
        """Handle inbound MQTT messages → Mesh."""
        try:
            payload = msg.payload.decode("utf-8", errors="replace")
            # Try to parse JSON payload with sender/message fields
            try:
                data = json.loads(payload)
                sender = data.get("sender", "MQTT")
                text = data.get("message", payload)
            except (json.JSONDecodeError, ValueError):
                sender = "MQTT"
                text = payload

            if not text:
                return

            formatted = f"[MQTT:{sender}] {text}"
            log_fn = self.app_context.get("log_message")
            if log_fn:
                log_fn("MQTT", formatted, direct=False,
                       channel_idx=self.inbound_channel_index)
            if self.inbound_channel_index is not None:
                self.send_to_mesh(formatted,
                                  channel_index=self.inbound_channel_index)
            self.log(f"MQTT inbound: {formatted}")
        except Exception as exc:
            self.log(f"Error handling MQTT message: {exc}")

    # ------------------------------------------------------------------
    # Outbound: mesh → MQTT
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._publish(self.publish_topic, message, metadata)
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._publish(self.publish_topic, message, metadata)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            self._publish(self.publish_topic, message, metadata)

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                payload = {"message": message, "type": "emergency"}
                if gps_coords:
                    payload["gps"] = gps_coords
                self._publish(self.emergency_topic, json.dumps(payload))
                self.log("✅ Emergency alert published to MQTT.")
            except Exception as exc:
                self.log(f"⚠️ MQTT emergency publish error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _publish(self, topic: str, message, metadata: dict | None = None) -> None:
        """Publish a message to an MQTT topic."""
        if not self._client or not self._connected:
            return
        try:
            if isinstance(message, str):
                payload_data = {
                    "message": message,
                    "source": "mesh-api",
                }
                if metadata:
                    payload_data["metadata"] = {
                        k: v for k, v in metadata.items()
                        if isinstance(v, (str, int, float, bool, type(None)))
                    }
                payload = json.dumps(payload_data)
            else:
                payload = str(message)
            self._client.publish(topic, payload, qos=self.qos)
        except Exception as exc:
            self.log(f"⚠️ MQTT publish error: {exc}")
