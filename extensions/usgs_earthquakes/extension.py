"""
USGS Earthquakes extension for MESH-API.

Monitors the USGS Earthquake Hazards Program real-time GeoJSON feeds
(https://earthquake.usgs.gov/earthquakes/feed/) for significant seismic
events and broadcasts alerts onto the mesh.

Features:
- Polls USGS GeoJSON feed at a configurable interval.
- Filters by minimum magnitude and optional geographic radius.
- Auto-broadcasts new earthquakes meeting the threshold.
- /quake command — show recent significant earthquakes.
- /quakeconfig — show current filter settings.

The USGS API is free and requires no API key.
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


class UsgsEarthquakesExtension(BaseExtension):
    """USGS earthquake monitoring extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "USGS_Earthquakes"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/quake": "Show recent earthquakes (usage: /quake [min_mag])",
            "/quakeconfig": "Show earthquake monitor configuration",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def min_magnitude(self) -> float:
        return float(self.config.get("min_magnitude", 4.0))

    @property
    def max_radius_km(self) -> float:
        return float(self.config.get("max_radius_km", 500))

    @property
    def center_lat(self) -> str:
        return str(self.config.get("center_lat", ""))

    @property
    def center_lon(self) -> str:
        return str(self.config.get("center_lon", ""))

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
    def lookback_minutes(self) -> int:
        return int(self.config.get("lookback_minutes", 60))

    @property
    def include_tsunami(self) -> bool:
        return bool(self.config.get("include_tsunami_warning", True))

    @property
    def max_results(self) -> int:
        return int(self.config.get("max_results", 10))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._seen_ids: set = set()

        status = [f"min_mag={self.min_magnitude}"]
        if self.center_lat and self.center_lon:
            status.append(f"center={self.center_lat},{self.center_lon}")
            status.append(f"radius={self.max_radius_km}km")
        self.log(f"USGS Earthquakes enabled. {', '.join(status)}")

        if self.auto_broadcast:
            self._poll_thread = threading.Thread(
                target=self._poll_usgs,
                daemon=True,
                name="usgs-quake-poll",
            )
            self._poll_thread.start()
            self.log("USGS earthquake polling thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("USGS Earthquakes extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/quakeconfig":
            parts = [
                f"Min Magnitude: {self.min_magnitude}",
                f"Lookback: {self.lookback_minutes} min",
            ]
            if self.center_lat and self.center_lon:
                parts.append(f"Center: {self.center_lat}, {self.center_lon}")
                parts.append(f"Radius: {self.max_radius_km} km")
            parts.append(f"Auto-broadcast: {'On' if self.auto_broadcast else 'Off'}")
            return "\n".join(parts)

        if command == "/quake":
            min_mag = self.min_magnitude
            if args.strip():
                try:
                    min_mag = float(args.strip())
                except ValueError:
                    return "Usage: /quake [min_magnitude]"

            quakes = self._fetch_earthquakes(min_mag=min_mag)
            if not quakes:
                return f"No earthquakes M{min_mag}+ in the last hour."

            lines = [f"🌍 Earthquakes M{min_mag}+:"]
            for q in quakes[:5]:
                lines.append(self._format_quake(q))
            return "\n---\n".join(lines)

        return None

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_usgs(self) -> None:
        time.sleep(10)

        while not self._stop_event.is_set():
            try:
                quakes = self._fetch_earthquakes()
                for q in quakes:
                    qid = q.get("id", "")
                    if qid and qid not in self._seen_ids:
                        self._seen_ids.add(qid)
                        text = self._format_quake(q)
                        self.send_to_mesh(text, channel_index=self.broadcast_channel)
                        self.log(f"Broadcast earthquake: {qid}")

                        # Check tsunami warning
                        props = q.get("properties", {})
                        tsunami = props.get("tsunami", 0)
                        if self.include_tsunami and tsunami:
                            self.send_to_mesh(
                                f"🌊 TSUNAMI WARNING associated with earthquake: "
                                f"{props.get('title', 'Unknown')}",
                                channel_index=self.broadcast_channel,
                            )

                # Trim seen set
                if len(self._seen_ids) > 500:
                    excess = len(self._seen_ids) - 250
                    for _ in range(excess):
                        self._seen_ids.pop()

            except Exception as exc:
                self.log(f"USGS poll error: {exc}")

            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _fetch_earthquakes(self, min_mag: float | None = None) -> list:
        """Fetch earthquakes from USGS GeoJSON feed."""
        mag = min_mag if min_mag is not None else self.min_magnitude
        # Use the query API for filtering
        params = {
            "format": "geojson",
            "minmagnitude": mag,
            "orderby": "time",
            "limit": self.max_results,
        }
        # Time window
        now = datetime.now(timezone.utc)
        start = now - timedelta(minutes=self.lookback_minutes)
        params["starttime"] = start.strftime("%Y-%m-%dT%H:%M:%S")

        # Geographic filter
        if self.center_lat and self.center_lon:
            params["latitude"] = self.center_lat
            params["longitude"] = self.center_lon
            params["maxradiuskm"] = self.max_radius_km

        try:
            resp = requests.get(
                "https://earthquake.usgs.gov/fdsnws/event/1/query",
                params=params,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("features", [])
            else:
                self.log(f"USGS API error: {resp.status_code}")
        except Exception as exc:
            self.log(f"USGS fetch error: {exc}")
        return []

    def _format_quake(self, feature: dict) -> str:
        """Format an earthquake feature into a mesh-friendly string."""
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        coords = geom.get("coordinates", [0, 0, 0])

        mag = props.get("mag", "?")
        place = props.get("place", "Unknown location")
        time_ms = props.get("time", 0)
        tsunami = props.get("tsunami", 0)

        # Convert epoch ms to readable time
        if time_ms:
            dt = datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
            time_str = dt.strftime("%H:%M UTC %b %d")
        else:
            time_str = "?"

        depth = coords[2] if len(coords) > 2 else "?"
        lat = coords[1] if len(coords) > 1 else "?"
        lon = coords[0] if len(coords) > 0 else "?"

        text = f"🌍 M{mag} — {place}\n{time_str} | Depth: {depth}km"
        text += f"\n📍 {lat}, {lon}"
        if tsunami:
            text += "\n🌊 Tsunami warning!"
        return text
