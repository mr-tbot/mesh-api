"""
GDACS extension for MESH-API.

Monitors the Global Disaster Alert and Coordination System (GDACS)
RSS/GeoJSON feeds for worldwide natural disaster alerts.

GDACS covers:
- EQ = Earthquakes
- TC = Tropical Cyclones
- FL = Floods
- VO = Volcanoes
- DR = Droughts
- WF = Wildfires

Features:
- Polls the GDACS GeoJSON API at a configurable interval.
- Filters by alert level (Green, Orange, Red) and event type.
- Auto-broadcasts new disaster alerts onto the mesh.
- /gdacs command — show current active alerts.
- Optional geographic proximity filter.

The GDACS API is free and requires no API key.
https://www.gdacs.org/
"""

import threading
import time
import math
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class GdacsExtension(BaseExtension):
    """GDACS global disaster monitoring extension."""

    EVENT_LABELS = {
        "EQ": "Earthquake",
        "TC": "Tropical Cyclone",
        "FL": "Flood",
        "VO": "Volcano",
        "DR": "Drought",
        "WF": "Wildfire",
    }

    ALERT_EMOJI = {
        "Red": "🔴",
        "Orange": "🟠",
        "Green": "🟢",
    }

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "GDACS"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/gdacs": "Show active GDACS disaster alerts",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 600))

    @property
    def auto_broadcast(self) -> bool:
        return bool(self.config.get("auto_broadcast", True))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def alert_levels(self) -> list:
        return self.config.get("alert_levels", ["Red", "Orange"])

    @property
    def event_types(self) -> list:
        return self.config.get("event_types",
                               ["EQ", "TC", "FL", "VO", "DR", "WF"])

    @property
    def max_alerts(self) -> int:
        return int(self.config.get("max_alerts", 10))

    @property
    def center_lat(self) -> str:
        return str(self.config.get("center_lat", ""))

    @property
    def center_lon(self) -> str:
        return str(self.config.get("center_lon", ""))

    @property
    def max_distance_km(self) -> float:
        return float(self.config.get("max_distance_km", 0))

    @property
    def max_alert_age_hours(self) -> int:
        return int(self.config.get("max_alert_age_hours", 72))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._seen_ids: set = set()

        status = [f"levels={','.join(self.alert_levels)}",
                  f"types={','.join(self.event_types)}"]
        if self.center_lat and self.center_lon and self.max_distance_km:
            status.append(f"near={self.center_lat},{self.center_lon} "
                          f"r={self.max_distance_km}km")
        self.log(f"GDACS enabled. {', '.join(status)}")

        if self.auto_broadcast:
            self._poll_thread = threading.Thread(
                target=self._poll_gdacs,
                daemon=True,
                name="gdacs-poll",
            )
            self._poll_thread.start()
            self.log("GDACS polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("GDACS extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/gdacs":
            events = self._fetch_events()
            if not events:
                return "No active GDACS alerts matching filters."
            lines = []
            for e in events[:5]:
                lines.append(self._format_event(e))
            return "\n---\n".join(lines)
        return None

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_gdacs(self) -> None:
        time.sleep(15)

        while not self._stop_event.is_set():
            try:
                events = self._fetch_events()
                for event in events:
                    eid = event.get("properties", {}).get("eventid", "")
                    etype = event.get("properties", {}).get("eventtype", "")
                    event_key = f"{etype}_{eid}"
                    if event_key and event_key not in self._seen_ids:
                        self._seen_ids.add(event_key)
                        text = self._format_event(event)
                        self.send_to_mesh(text, channel_index=self.broadcast_channel)
                        self.log(f"Broadcast GDACS event: {event_key}")

                if len(self._seen_ids) > 300:
                    excess = len(self._seen_ids) - 150
                    for _ in range(excess):
                        self._seen_ids.pop()

            except Exception as exc:
                self.log(f"GDACS poll error: {exc}")

            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _fetch_events(self) -> list:
        """Fetch events from the GDACS GeoJSON API."""
        try:
            url = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
            params = {
                "alertlevel": ";".join(self.alert_levels),
                "eventlist": ";".join(self.event_types),
                "fromDate": (datetime.now(timezone.utc) -
                             timedelta(hours=self.max_alert_age_hours)
                             ).strftime("%Y-%m-%dT%H:%M:%S"),
                "toDate": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "maxresults": self.max_alerts,
            }
            if self.center_lat and self.center_lon and self.max_distance_km:
                params["lat"] = self.center_lat
                params["lon"] = self.center_lon
                params["maxdist"] = self.max_distance_km

            headers = {"Accept": "application/json"}
            resp = requests.get(url, params=params, headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("features", [])
            else:
                self.log(f"GDACS API error: {resp.status_code}")
        except Exception as exc:
            self.log(f"GDACS fetch error: {exc}")
        return []

    def _format_event(self, feature: dict) -> str:
        """Format a GDACS event feature into a mesh-friendly string."""
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})

        etype = props.get("eventtype", "?")
        ename = props.get("name", props.get("eventname", ""))
        alert_level = props.get("alertlevel", "?")
        country = props.get("country", "")
        severity = props.get("severity", {})
        fromdate = props.get("fromdate", "")
        todate = props.get("todate", "")

        emoji = self.ALERT_EMOJI.get(alert_level, "⚠️")
        type_label = self.EVENT_LABELS.get(etype, etype)
        severity_text = ""
        if isinstance(severity, dict):
            val = severity.get("severity_value", "")
            unit = severity.get("severity_unit", "")
            if val:
                severity_text = f" ({val} {unit})"
        elif severity:
            severity_text = f" ({severity})"

        coords = geom.get("coordinates", [])
        coord_str = ""
        if coords and len(coords) >= 2:
            coord_str = f"\n📍 {coords[1]}, {coords[0]}"

        parts = [f"{emoji} GDACS {alert_level}: {type_label}{severity_text}"]
        if ename:
            parts[0] += f" — {ename}"
        if country:
            parts.append(f"Location: {country}")
        if coord_str:
            parts.append(coord_str.strip())
        if fromdate:
            parts.append(f"Since: {fromdate}")

        return "\n".join(parts)
