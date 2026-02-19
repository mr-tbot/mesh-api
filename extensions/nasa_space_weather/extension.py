"""
NASA Space Weather extension for MESH-API.

Monitors NASA's DONKI (Database Of Notifications, Knowledge, Information)
API for space weather events: geomagnetic storms, solar flares, coronal
mass ejections, solar energetic particles, and more.

Features:
- Polls NASA DONKI API at a configurable interval.
- Auto-broadcasts significant space weather events to the mesh.
- Filters by event type, Kp index (geomagnetic storms), and flare class.
- De-duplicates: each event ID is broadcast only once.
- Slash commands for on-demand queries.

Data source: https://api.nasa.gov (DONKI)
- Free API key available at https://api.nasa.gov
- DEMO_KEY works for light usage (30 req/hr, 50 req/day).

Event types supported:
- GST — Geomagnetic Storm
- FLR — Solar Flare
- CME — Coronal Mass Ejection
- IPS — Interplanetary Shock
- SEP — Solar Energetic Particle
- RBE — Radiation Belt Enhancement
"""

import threading
import time
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension

# Flare class ordering for comparison
_FLARE_CLASSES = {"A": 0, "B": 1, "C": 2, "M": 3, "X": 4}

# Human-readable event type labels
_EVENT_LABELS = {
    "GST": "Geomagnetic Storm",
    "FLR": "Solar Flare",
    "CME": "Coronal Mass Ejection",
    "IPS": "Interplanetary Shock",
    "SEP": "Solar Energetic Particle",
    "RBE": "Radiation Belt Enhancement",
}


class NasaSpaceWeatherExtension(BaseExtension):
    """NASA DONKI space weather alerts monitor."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "NASA_Space_Weather"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/spaceweather": "Show recent space weather events",
            "/solarflare": "Show recent solar flare activity",
            "/geomagstorm": "Show recent geomagnetic storms",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def api_key(self) -> str:
        return self.config.get("api_key", "DEMO_KEY")

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
    def event_types(self) -> list:
        return self.config.get("event_types", ["GST", "FLR", "CME"])

    @property
    def min_kp_index(self) -> int:
        return int(self.config.get("min_kp_index", 5))

    @property
    def min_flare_class(self) -> str:
        return self.config.get("min_flare_class", "M")

    @property
    def lookback_days(self) -> int:
        return int(self.config.get("lookback_days", 3))

    @property
    def max_alert_length(self) -> int:
        return int(self.config.get("max_alert_length", 300))

    @property
    def max_results(self) -> int:
        return int(self.config.get("max_results", 5))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._seen_ids: set = set()

        if requests is None:
            self.log("WARNING: 'requests' library not installed. "
                     "NASA Space Weather extension will not function.")
            return

        key_info = "DEMO_KEY" if self.api_key == "DEMO_KEY" else "custom key"
        types_str = ", ".join(self.event_types)
        self.log(f"NASA Space Weather enabled ({key_info}). "
                 f"Monitoring: {types_str}")

        if self.auto_broadcast:
            self._poll_thread = threading.Thread(
                target=self._poll_loop,
                daemon=True,
                name="nasa-space-weather-poll",
            )
            self._poll_thread.start()
            self.log("NASA DONKI polling thread started "
                     f"(every {self.poll_interval}s).")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("NASA Space Weather extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/spaceweather":
            return self._cmd_spaceweather(args)
        if command == "/solarflare":
            return self._cmd_solar_flare(args)
        if command == "/geomagstorm":
            return self._cmd_geomag_storm(args)
        return None

    def _cmd_spaceweather(self, args: str) -> str:
        """Fetch recent events across all configured types."""
        all_events = []
        for etype in self.event_types:
            events = self._fetch_events(etype)
            all_events.extend(events)
        if not all_events:
            return "No recent space weather events."
        # Sort by time descending
        all_events.sort(key=lambda e: e.get("_time", ""), reverse=True)
        lines = []
        for ev in all_events[:self.max_results]:
            lines.append(self._format_event(ev, short=True))
        return "\n---\n".join(lines)

    def _cmd_solar_flare(self, args: str) -> str:
        """Fetch recent solar flares."""
        events = self._fetch_events("FLR")
        if not events:
            return "No recent solar flares."
        lines = []
        for ev in events[:self.max_results]:
            lines.append(self._format_event(ev, short=True))
        return "\n---\n".join(lines)

    def _cmd_geomag_storm(self, args: str) -> str:
        """Fetch recent geomagnetic storms."""
        events = self._fetch_events("GST")
        if not events:
            return "No recent geomagnetic storms."
        lines = []
        for ev in events[:self.max_results]:
            lines.append(self._format_event(ev, short=True))
        return "\n---\n".join(lines)

    # ------------------------------------------------------------------
    # Polling loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        time.sleep(15)  # let system settle

        while not self._stop_event.is_set():
            try:
                for etype in self.event_types:
                    events = self._fetch_events(etype)
                    for ev in events:
                        ev_id = ev.get("_id", "")
                        if ev_id and ev_id not in self._seen_ids:
                            self._seen_ids.add(ev_id)
                            if self._passes_filter(ev):
                                text = self._format_event(ev, short=False)
                                self.send_to_mesh(
                                    text,
                                    channel_index=self.broadcast_channel,
                                )
                                self.log(f"Broadcast: {ev.get('_type', '?')} "
                                         f"{ev_id}")

                # Trim seen set to prevent unbounded growth
                if len(self._seen_ids) > 500:
                    excess = len(self._seen_ids) - 250
                    for _ in range(excess):
                        self._seen_ids.pop()

            except Exception as exc:
                self.log(f"NASA DONKI poll error: {exc}")

            for _ in range(self.poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def _passes_filter(self, event: dict) -> bool:
        """Return True if the event meets configured thresholds."""
        etype = event.get("_type", "")

        if etype == "GST":
            kp = event.get("kp_index", 0)
            if kp is not None and kp < self.min_kp_index:
                return False

        if etype == "FLR":
            flare_class = event.get("classType", "")
            if flare_class and not self._flare_meets_minimum(flare_class):
                return False

        return True

    @staticmethod
    def _flare_meets_minimum(flare_class: str, minimum: str = "M") -> bool:
        """Check if a solar flare class meets the minimum threshold.
        Classes in ascending order: A, B, C, M, X."""
        if not flare_class:
            return False
        flare_letter = flare_class[0].upper()
        min_letter = minimum[0].upper()
        return _FLARE_CLASSES.get(flare_letter, -1) >= _FLARE_CLASSES.get(min_letter, 0)

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _date_range(self) -> tuple[str, str]:
        """Return (startDate, endDate) strings for the DONKI API."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=self.lookback_days)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    def _fetch_events(self, event_type: str) -> list:
        """Fetch events of a specific type from NASA DONKI."""
        if requests is None:
            return []

        start_date, end_date = self._date_range()
        endpoints = {
            "GST": "GST",
            "FLR": "FLR",
            "CME": "CME",
            "IPS": "IPS",
            "SEP": "SEP",
            "RBE": "RBE",
        }
        endpoint = endpoints.get(event_type)
        if not endpoint:
            return []

        url = (f"https://api.nasa.gov/DONKI/{endpoint}"
               f"?startDate={start_date}&endDate={end_date}"
               f"&api_key={self.api_key}")

        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if not isinstance(data, list):
                    return []
                return self._normalize_events(data, event_type)
            else:
                self.log(f"NASA API {resp.status_code} for {event_type}")
                return []
        except Exception as exc:
            self.log(f"NASA fetch error ({event_type}): {exc}")
            return []

    def _normalize_events(self, raw_items: list, event_type: str) -> list:
        """Normalize raw DONKI JSON into a consistent internal format."""
        events = []
        for item in raw_items:
            ev = {"_type": event_type, "_raw": item}

            if event_type == "GST":
                ev["_id"] = item.get("gstID", "")
                ev["_time"] = item.get("startTime", "")
                # Extract highest Kp from allKpIndex
                kp_list = item.get("allKpIndex", [])
                kp_max = 0
                for entry in kp_list:
                    kp_val = entry.get("kpIndex", 0)
                    if kp_val and kp_val > kp_max:
                        kp_max = kp_val
                ev["kp_index"] = kp_max

            elif event_type == "FLR":
                ev["_id"] = item.get("flrID", "")
                ev["_time"] = item.get("beginTime", "")
                ev["classType"] = item.get("classType", "")
                ev["sourceLocation"] = item.get("sourceLocation", "")
                ev["peakTime"] = item.get("peakTime", "")

            elif event_type == "CME":
                ev["_id"] = item.get("activityID", "")
                ev["_time"] = item.get("startTime", "")
                ev["note"] = item.get("note", "")
                ev["sourceLocation"] = item.get("sourceLocation", "")
                # Extract speed from CME analysis if available
                analyses = item.get("cmeAnalyses", [])
                if analyses:
                    ev["speed"] = analyses[0].get("speed", "")
                    ev["type"] = analyses[0].get("type", "")

            elif event_type == "IPS":
                ev["_id"] = item.get("activityID", "")
                ev["_time"] = item.get("eventTime", "")
                ev["location"] = item.get("location", "")

            elif event_type == "SEP":
                ev["_id"] = item.get("sepID", "")
                ev["_time"] = item.get("eventTime", "")

            elif event_type == "RBE":
                ev["_id"] = item.get("rbeID", "")
                ev["_time"] = item.get("eventTime", "")

            events.append(ev)

        return events

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def _format_event(self, event: dict, short: bool = False) -> str:
        """Format a normalized event into a mesh-friendly string."""
        etype = event.get("_type", "?")
        label = _EVENT_LABELS.get(etype, etype)
        ev_time = event.get("_time", "Unknown time")

        # Shorten the timestamp for mesh display
        if ev_time and len(ev_time) > 16:
            ev_time = ev_time[:16].replace("T", " ")

        if etype == "GST":
            kp = event.get("kp_index", "?")
            text = f"☀️ {label} | Kp={kp} | {ev_time}"
            if not short:
                text += self._kp_impact_note(kp)

        elif etype == "FLR":
            cls = event.get("classType", "?")
            loc = event.get("sourceLocation", "")
            text = f"🔥 {label} {cls} | {ev_time}"
            if loc:
                text += f" | Region: {loc}"
            if not short:
                peak = event.get("peakTime", "")
                if peak:
                    text += f"\nPeak: {peak[:16].replace('T', ' ')}"

        elif etype == "CME":
            speed = event.get("speed", "")
            cme_type = event.get("type", "")
            text = f"💫 {label} | {ev_time}"
            if speed:
                text += f" | {speed} km/s"
            if cme_type:
                text += f" ({cme_type})"
            if not short:
                note = event.get("note", "")
                if note:
                    note = note.strip()
                    if len(note) > self.max_alert_length:
                        note = note[:self.max_alert_length] + "..."
                    text += f"\n{note}"

        elif etype == "IPS":
            loc = event.get("location", "")
            text = f"⚡ {label} | {ev_time}"
            if loc:
                text += f" | {loc}"

        elif etype == "SEP":
            text = f"☢️ {label} | {ev_time}"

        elif etype == "RBE":
            text = f"🌐 {label} | {ev_time}"

        else:
            text = f"🛰️ {label} | {ev_time}"

        return text[:self.max_alert_length] if short else text

    @staticmethod
    def _kp_impact_note(kp) -> str:
        """Return a brief impact description based on Kp index."""
        try:
            kp = int(kp)
        except (ValueError, TypeError):
            return ""
        if kp >= 9:
            return "\n🔴 EXTREME (G5) — Power grids, satellites, HF radio at risk"
        elif kp >= 8:
            return "\n🔴 SEVERE (G4) — Widespread power & radio disruptions"
        elif kp >= 7:
            return "\n🟠 STRONG (G3) — HF radio intermittent, GPS degraded"
        elif kp >= 6:
            return "\n🟡 MODERATE (G2) — HF radio fading at high latitudes"
        elif kp >= 5:
            return "\n🟢 MINOR (G1) — Weak grid fluctuations, aurora visible"
        return ""
