"""
Apprise extension for MESH-API.

Apprise is a universal notification library that supports 100+ services
(Slack, Discord, Telegram, Pushover, email, SMS, and many more) through
a simple URL-based configuration.

This extension uses Apprise to broadcast mesh messages, AI responses,
and emergency alerts to any combination of supported services.

Install with:
    pip install apprise

Configure by adding Apprise-format URLs to the ``urls`` list in this
extension's config.json.  See https://github.com/caronc/apprise/wiki
for the full list of supported URL schemas.

Example URLs:
    "slack://token_a/token_b/token_c/#channel"
    "tgram://bot_token/chat_id"
    "mailto://user:pass@gmail.com"
    "pover://user@token"
"""

try:
    import apprise
except ImportError:
    apprise = None

from extensions.base_extension import BaseExtension


class AppriseExtension(BaseExtension):
    """Apprise universal notification extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Apprise"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def urls(self) -> list:
        return self.config.get("urls", [])

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
    def title_prefix(self) -> str:
        return self.config.get("title_prefix", "[MESH-API]")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._apprise = None
        if apprise is None:
            self.log("⚠️ apprise not installed. Run: pip install apprise")
            return

        if not self.urls:
            self.log("Apprise enabled but no URLs configured.")
            return

        self._apprise = apprise.Apprise()
        for url in self.urls:
            self._apprise.add(url)

        self.log(f"Apprise enabled with {len(self.urls)} notification target(s).")

    def on_unload(self) -> None:
        self._apprise = None
        self.log("Apprise extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Apprise notifications
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._notify(message, title=f"{self.title_prefix} Mesh Message")
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._notify(message, title=f"{self.title_prefix} AI Response")

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._notify(f"{sender}: {message}",
                         title=f"{self.title_prefix} Mesh Message")

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
                self._notify(body,
                             title=f"{self.title_prefix} 🚨 EMERGENCY",
                             notify_type="failure")
                self.log("✅ Emergency alert sent via Apprise.")
            except Exception as exc:
                self.log(f"⚠️ Apprise emergency error: {exc}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _notify(self, body: str, title: str = "",
                notify_type: str = "info") -> None:
        """Send a notification through all configured Apprise targets."""
        if not self._apprise:
            return
        try:
            ntype = getattr(apprise.NotifyType, notify_type.upper(),
                            apprise.NotifyType.INFO) if apprise else notify_type
            self._apprise.notify(
                body=body,
                title=title or self.title_prefix,
                notify_type=ntype,
            )
        except Exception as exc:
            self.log(f"⚠️ Apprise notify error: {exc}")
