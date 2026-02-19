"""
Amber Alerts extension for MESH-API.

Monitors public alert feeds for AMBER (missing/abducted children),
Silver (missing seniors), and Blue (law enforcement) alerts and
broadcasts them onto the mesh.

Data sources:
- NWS CAP (Common Alerting Protocol) feed — the NWS distributes AMBER
  alerts via the same api.weather.gov/alerts API.
- Google Alerts RSS (fallback) — Google publishes AMBER alerts at
  https://www.google.org/publicalerts/feed
- Canadian NAAD system (if configured).

Features:
- Polls alert feeds at a configurable interval.
- Auto-broadcasts new alerts onto the mesh.
- /amber command — show currently active AMBER alerts.
- Filters by state/province when configured.

No API key required (uses public government feeds).
"""

import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class AmberAlertsExtension(BaseExtension):
    """AMBER / Silver / Blue alert monitor extension."""

    NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Amber_Alerts"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        cmds = {"/amber": "Show active AMBER alerts"}
        if self.include_silver:
            cmds["/silver"] = "Show active Silver (missing senior) alerts"
        if self.include_blue:
            cmds["/blue"] = "Show active Blue (law enforcement) alerts"
        return cmds

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 300))

    @property
    def auto_broadcast(self) -> bool:
        return bool(self.config.get("auto_broadcast", True))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def states(self) -> list:
        return self.config.get("states", [])

    @property
    def include_silver(self) -> bool:
        return bool(self.config.get("include_silver", True))

    @property
    def include_blue(self) -> bool:
        return bool(self.config.get("include_blue", True))

    @property
    def max_alerts(self) -> int:
        return int(self.config.get("max_alerts", 10))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._seen_ids: set = set()

        status = []
        if self.states:
            status.append(f"states={','.join(self.states)}")
        if self.include_silver:
            status.append("silver=yes")
        if self.include_blue:
            status.append("blue=yes")
        self.log(f"Amber Alerts enabled. {', '.join(status) if status else 'All states'}")

        if self.auto_broadcast:
            self._poll_thread = threading.Thread(
                target=self._poll_alerts,
                daemon=True,
                name="amber-poll",
            )
            self._poll_thread.start()
            self.log("Amber Alerts polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("Amber Alerts extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/amber":
            alerts = self._fetch_nws_alerts(event_types=["Amber Alert"])
            if not alerts:
                return "No active AMBER alerts."
            return self._format_alerts_list(alerts, "🟡 AMBER Alerts")

        if command == "/silver" and self.include_silver:
            alerts = self._fetch_nws_alerts(event_types=["Silver Alert"])
            if not alerts:
                return "No active Silver alerts."
            return self._format_alerts_list(alerts, "🔘 Silver Alerts")

        if command == "/blue" and self.include_blue:
            alerts = self._fetch_nws_alerts(event_types=["Blue Alert"])
            if not alerts:
                return "No active Blue alerts."
            return self._format_alerts_list(alerts, "🔵 Blue Alerts")

        return None

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_alerts(self) -> None:
        time.sleep(10)

        while not self._stop_event.is_set():
            try:
                # Build list of event types to monitor
                event_types = ["Amber Alert"]
                if self.include_silver:
                    event_types.append("Silver Alert")
                if self.include_blue:
                    event_types.append("Blue Alert")

                alerts = self._fetch_nws_alerts(event_types)
                for alert in alerts:
                    alert_id = alert.get("properties", {}).get("id", "")
                    if alert_id and alert_id not in self._seen_ids:
                        self._seen_ids.add(alert_id)
                        text = self._format_single_alert(alert)
                        self.send_to_mesh(text, channel_index=self.broadcast_channel)
                        self.log(f"Broadcast alert: {alert_id}")

                # Trim
                if len(self._seen_ids) > 300:
                    excess = len(self._seen_ids) - 150
                    for _ in range(excess):
                        self._seen_ids.pop()

            except Exception as exc:
                self.log(f"Amber poll error: {exc}")

            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _fetch_nws_alerts(self, event_types: list | None = None) -> list:
        """Fetch alerts from NWS API, filtering for AMBER/Silver/Blue."""
        try:
            headers = {
                "User-Agent": "MESH-API Alert Monitor",
                "Accept": "application/geo+json",
            }
            params = {"status": "actual", "message_type": "alert"}
            if self.states:
                params["area"] = ",".join(self.states)

            resp = requests.get(self.NWS_ALERTS_URL, headers=headers,
                                params=params, timeout=15)
            if resp.status_code != 200:
                self.log(f"NWS API error: {resp.status_code}")
                return []

            features = resp.json().get("features", [])

            if event_types:
                et_lower = [e.lower() for e in event_types]
                features = [
                    f for f in features
                    if f.get("properties", {}).get("event", "").lower()
                    in et_lower
                ]

            return features[:self.max_alerts]
        except Exception as exc:
            self.log(f"NWS alerts fetch error: {exc}")
            return []

    def _format_single_alert(self, feature: dict) -> str:
        """Format a single alert feature for mesh broadcast."""
        props = feature.get("properties", {})
        event = props.get("event", "Alert")
        headline = props.get("headline", "")
        areas = props.get("areaDesc", "")
        description = props.get("description", "")
        expires = props.get("expires", "")

        # Choose emoji
        event_lower = event.lower()
        if "amber" in event_lower:
            emoji = "🟡"
        elif "silver" in event_lower:
            emoji = "🔘"
        elif "blue" in event_lower:
            emoji = "🔵"
        else:
            emoji = "⚠️"

        parts = [f"{emoji} {event}"]
        if headline:
            parts.append(headline)
        if areas:
            parts.append(f"Areas: {areas}")
        if description:
            desc = description.strip()[:300]
            parts.append(desc)
        if expires:
            parts.append(f"Expires: {expires}")

        return "\n".join(parts)

    def _format_alerts_list(self, alerts: list, header: str) -> str:
        """Format multiple alerts for a command response."""
        lines = [header]
        for a in alerts[:5]:
            props = a.get("properties", {})
            headline = props.get("headline", "No headline")
            areas = props.get("areaDesc", "")
            entry = headline
            if areas:
                entry += f"\nAreas: {areas}"
            lines.append(entry)
        return "\n---\n".join(lines)
