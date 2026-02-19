"""
NWS Alerts extension for MESH-API.

Monitors the National Weather Service (weather.gov) Alerts API for active
weather warnings, watches, and advisories in configured zones.

Features:
- Polls api.weather.gov/alerts at a configurable interval.
- Auto-broadcasts new alerts onto the mesh when detected.
- Filters by severity, urgency, and certainty.
- De-duplicates: each alert ID is broadcast only once.
- Slash command /nws — fetch and display current active alerts on demand.
- Slash command /nwszones — show configured zone IDs.

Configuration:
- zone_ids: list of NWS zone codes (e.g. ["TXZ211", "TXC453"])
- point: lat,lon pair for point-based alerts (e.g. "30.27,-97.74")
- state: two-letter state code for state-wide monitoring (e.g. "TX")
- severity_filter: only broadcast alerts matching these severities
  (Extreme, Severe, Moderate, Minor, Unknown)

The NWS API is free, requires no key, and requests a User-Agent header.
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class NwsAlertsExtension(BaseExtension):
    """National Weather Service alerts monitor."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "NWS_Alerts"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/nws": "Show active NWS alerts for configured zones",
            "/nwszones": "Show configured NWS zone IDs",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def zone_ids(self) -> list:
        return self.config.get("zone_ids", [])

    @property
    def point(self) -> str:
        return self.config.get("point", "")

    @property
    def state(self) -> str:
        return self.config.get("state", "")

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
    def severity_filter(self) -> list:
        return self.config.get("severity_filter", ["Extreme", "Severe"])

    @property
    def urgency_filter(self) -> list:
        return self.config.get("urgency_filter", [])

    @property
    def certainty_filter(self) -> list:
        return self.config.get("certainty_filter", [])

    @property
    def max_alert_length(self) -> int:
        return int(self.config.get("max_alert_length", 300))

    @property
    def include_instruction(self) -> bool:
        return bool(self.config.get("include_instruction", True))

    @property
    def user_agent(self) -> str:
        return self.config.get("user_agent",
                               "MESH-API Emergency Alert System")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._seen_ids: set = set()

        sources = []
        if self.zone_ids:
            sources.append(f"zones={','.join(self.zone_ids)}")
        if self.point:
            sources.append(f"point={self.point}")
        if self.state:
            sources.append(f"state={self.state}")

        self.log(f"NWS Alerts enabled. {', '.join(sources) if sources else 'No zones configured.'}")

        if (self.zone_ids or self.point or self.state) and self.auto_broadcast:
            self._poll_thread = threading.Thread(
                target=self._poll_nws,
                daemon=True,
                name="nws-alerts-poll",
            )
            self._poll_thread.start()
            self.log("NWS polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("NWS Alerts extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/nwszones":
            if not self.zone_ids:
                return "No NWS zones configured."
            return "NWS Zones: " + ", ".join(self.zone_ids)

        if command == "/nws":
            alerts = self._fetch_alerts()
            if not alerts:
                return "No active NWS alerts for configured area."
            lines = []
            for a in alerts[:5]:  # limit to 5 for mesh
                lines.append(self._format_alert(a, short=True))
            return "\n---\n".join(lines)

        return None

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_nws(self) -> None:
        time.sleep(10)  # let system settle

        while not self._stop_event.is_set():
            try:
                alerts = self._fetch_alerts()
                for alert in alerts:
                    alert_id = alert.get("properties", {}).get("id", "")
                    if alert_id and alert_id not in self._seen_ids:
                        self._seen_ids.add(alert_id)
                        props = alert.get("properties", {})
                        # Apply severity filter
                        severity = props.get("severity", "")
                        if self.severity_filter and severity not in self.severity_filter:
                            continue
                        # Apply urgency filter
                        urgency = props.get("urgency", "")
                        if self.urgency_filter and urgency not in self.urgency_filter:
                            continue
                        # Apply certainty filter
                        certainty = props.get("certainty", "")
                        if self.certainty_filter and certainty not in self.certainty_filter:
                            continue

                        text = self._format_alert(alert, short=False)
                        self.send_to_mesh(text, channel_index=self.broadcast_channel)
                        self.log(f"Broadcast NWS alert: {props.get('event', '?')}")

                # Trim seen set to avoid unbounded growth
                if len(self._seen_ids) > 500:
                    # Keep the most recent 250
                    excess = len(self._seen_ids) - 250
                    for _ in range(excess):
                        self._seen_ids.pop()

            except Exception as exc:
                self.log(f"NWS poll error: {exc}")

            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _fetch_alerts(self) -> list:
        """Fetch active alerts from the NWS API."""
        headers = {"User-Agent": self.user_agent, "Accept": "application/geo+json"}
        alerts = []
        try:
            urls = self._build_api_urls()
            for url in urls:
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    alerts.extend(features)
                else:
                    self.log(f"NWS API {resp.status_code} for {url}")
        except Exception as exc:
            self.log(f"NWS fetch error: {exc}")
        return alerts

    def _build_api_urls(self) -> list:
        """Build API URLs from configured zones/point/state."""
        urls = []
        base = "https://api.weather.gov/alerts/active"
        if self.zone_ids:
            zones = ",".join(self.zone_ids)
            urls.append(f"{base}?zone={zones}")
        if self.point:
            urls.append(f"{base}?point={self.point}")
        if self.state:
            urls.append(f"{base}?area={self.state}")
        if not urls:
            urls.append(base)
        return urls

    def _format_alert(self, alert: dict, short: bool = False) -> str:
        """Format an NWS alert feature into a mesh-friendly string."""
        props = alert.get("properties", {})
        event = props.get("event", "Unknown Alert")
        severity = props.get("severity", "?")
        headline = props.get("headline", "")
        areas = props.get("areaDesc", "")
        description = props.get("description", "")
        instruction = props.get("instruction", "")
        expires = props.get("expires", "")

        if short:
            text = f"⚠️ {event} [{severity}]"
            if headline:
                text += f"\n{headline}"
            if areas:
                text += f"\nAreas: {areas}"
            return text[:self.max_alert_length]

        parts = [f"⚠️ NWS: {event} [{severity}]"]
        if headline:
            parts.append(headline)
        if areas:
            parts.append(f"Areas: {areas}")
        if description:
            desc = description.strip()
            if len(desc) > self.max_alert_length:
                desc = desc[:self.max_alert_length] + "..."
            parts.append(desc)
        if self.include_instruction and instruction:
            inst = instruction.strip()
            if len(inst) > 150:
                inst = inst[:150] + "..."
            parts.append(f"Action: {inst}")
        if expires:
            parts.append(f"Expires: {expires}")

        return "\n".join(parts)
