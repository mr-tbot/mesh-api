"""
OpenWeatherMap extension for MESH-API.

Provides weather data from the OpenWeatherMap API:
- /weather [city]    — current conditions for a city or default location.
- /forecast [city]   — 3-day forecast summary.
- /wxalerts          — weather alerts for the default lat/lon (One Call API).
- Auto-broadcast:    optionally posts periodic weather updates and/or
  severe weather alerts onto the mesh.

Requires an OpenWeatherMap API key (free tier works for current weather
and 5-day forecast; One Call API 3.0 needed for alerts).

Units: "imperial" (°F, mph), "metric" (°C, m/s), or "standard" (K, m/s).
"""

import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class OpenWeatherMapExtension(BaseExtension):
    """OpenWeatherMap weather data extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "OpenWeatherMap"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/weather": "Current weather (usage: /weather [city])",
            "/forecast": "3-day forecast (usage: /forecast [city])",
            "/wxalerts": "Weather alerts for default location",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def api_key(self) -> str:
        return self.config.get("api_key", "")

    @property
    def default_lat(self) -> str:
        return str(self.config.get("default_lat", ""))

    @property
    def default_lon(self) -> str:
        return str(self.config.get("default_lon", ""))

    @property
    def default_city(self) -> str:
        return self.config.get("default_city", "")

    @property
    def units(self) -> str:
        return self.config.get("units", "imperial")

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def auto_broadcast(self) -> bool:
        return bool(self.config.get("auto_broadcast", False))

    @property
    def broadcast_interval(self) -> int:
        return int(self.config.get("broadcast_interval_seconds", 3600))

    @property
    def alert_broadcast(self) -> bool:
        return bool(self.config.get("alert_broadcast", True))

    @property
    def alert_poll_interval(self) -> int:
        return int(self.config.get("alert_poll_interval_seconds", 600))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._stop_event = threading.Event()
        self._wx_thread = None
        self._alert_thread = None
        self._seen_alert_ids: set = set()

        if not self.api_key:
            self.log("OpenWeatherMap enabled but no API key set.")
            return

        status = []
        if self.default_city:
            status.append(f"city={self.default_city}")
        if self.default_lat and self.default_lon:
            status.append(f"coords={self.default_lat},{self.default_lon}")
        self.log(f"OpenWeatherMap enabled. {', '.join(status)}")

        if self.auto_broadcast and (self.default_city or (self.default_lat and self.default_lon)):
            self._wx_thread = threading.Thread(
                target=self._broadcast_weather_loop,
                daemon=True,
                name="owm-broadcast",
            )
            self._wx_thread.start()

        if self.alert_broadcast and self.default_lat and self.default_lon:
            self._alert_thread = threading.Thread(
                target=self._alert_monitor_loop,
                daemon=True,
                name="owm-alerts",
            )
            self._alert_thread.start()

    def on_unload(self) -> None:
        self._stop_event.set()
        for t in (self._wx_thread, self._alert_thread):
            if t and t.is_alive():
                t.join(timeout=5)
        self.log("OpenWeatherMap extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/weather":
            city = args.strip() if args.strip() else self.default_city
            if not city and self.default_lat and self.default_lon:
                return self._get_weather_by_coords(self.default_lat, self.default_lon)
            if not city:
                return "Usage: /weather <city name>"
            return self._get_weather_by_city(city)

        if command == "/forecast":
            city = args.strip() if args.strip() else self.default_city
            if not city and self.default_lat and self.default_lon:
                return self._get_forecast_by_coords(self.default_lat, self.default_lon)
            if not city:
                return "Usage: /forecast <city name>"
            return self._get_forecast_by_city(city)

        if command == "/wxalerts":
            if not self.default_lat or not self.default_lon:
                return "No default coordinates configured for alerts."
            return self._get_alerts()

        return None

    # ------------------------------------------------------------------
    # Background loops
    # ------------------------------------------------------------------

    def _broadcast_weather_loop(self) -> None:
        time.sleep(15)
        while not self._stop_event.is_set():
            try:
                if self.default_city:
                    text = self._get_weather_by_city(self.default_city)
                elif self.default_lat and self.default_lon:
                    text = self._get_weather_by_coords(self.default_lat, self.default_lon)
                else:
                    text = None
                if text:
                    self.send_to_mesh(text, channel_index=self.broadcast_channel)
                    self.log("Auto-broadcast weather update.")
            except Exception as exc:
                self.log(f"Weather broadcast error: {exc}")
            for _ in range(self.broadcast_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _alert_monitor_loop(self) -> None:
        time.sleep(20)
        while not self._stop_event.is_set():
            try:
                alerts = self._fetch_alerts_raw()
                for alert in alerts:
                    event = alert.get("event", "")
                    sender = alert.get("sender_name", "")
                    desc = alert.get("description", "")
                    start = alert.get("start")
                    end = alert.get("end")
                    # Create a simple ID from event + start
                    alert_id = f"{event}_{start}"
                    if alert_id in self._seen_alert_ids:
                        continue
                    self._seen_alert_ids.add(alert_id)
                    text = f"⚠️ Weather Alert: {event}"
                    if sender:
                        text += f" ({sender})"
                    if desc:
                        short_desc = desc[:250] + "..." if len(desc) > 250 else desc
                        text += f"\n{short_desc}"
                    self.send_to_mesh(text, channel_index=self.broadcast_channel)
                    self.log(f"Broadcast weather alert: {event}")
                # Trim
                if len(self._seen_alert_ids) > 200:
                    excess = len(self._seen_alert_ids) - 100
                    for _ in range(excess):
                        self._seen_alert_ids.pop()
            except Exception as exc:
                self.log(f"Weather alert monitor error: {exc}")
            for _ in range(self.alert_poll_interval):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    # ------------------------------------------------------------------
    # API helpers — Current Weather
    # ------------------------------------------------------------------

    def _get_weather_by_city(self, city: str) -> str:
        try:
            params = {"q": city, "appid": self.api_key, "units": self.units}
            resp = requests.get("https://api.openweathermap.org/data/2.5/weather",
                                params=params, timeout=10)
            if resp.status_code != 200:
                return f"OWM error {resp.status_code}"
            return self._format_current(resp.json())
        except Exception as exc:
            return f"Weather error: {exc}"

    def _get_weather_by_coords(self, lat: str, lon: str) -> str:
        try:
            params = {"lat": lat, "lon": lon, "appid": self.api_key, "units": self.units}
            resp = requests.get("https://api.openweathermap.org/data/2.5/weather",
                                params=params, timeout=10)
            if resp.status_code != 200:
                return f"OWM error {resp.status_code}"
            return self._format_current(resp.json())
        except Exception as exc:
            return f"Weather error: {exc}"

    def _format_current(self, data: dict) -> str:
        name = data.get("name", "?")
        main = data.get("main", {})
        weather = data.get("weather", [{}])[0]
        wind = data.get("wind", {})
        unit_temp = "°F" if self.units == "imperial" else "°C" if self.units == "metric" else "K"
        unit_speed = "mph" if self.units == "imperial" else "m/s"
        return (
            f"🌤️ {name}: {weather.get('description', '?').title()}\n"
            f"Temp: {main.get('temp', '?')}{unit_temp} "
            f"(Feels {main.get('feels_like', '?')}{unit_temp})\n"
            f"Humidity: {main.get('humidity', '?')}% | "
            f"Wind: {wind.get('speed', '?')} {unit_speed}\n"
            f"Hi: {main.get('temp_max', '?')}{unit_temp} "
            f"Lo: {main.get('temp_min', '?')}{unit_temp}"
        )

    # ------------------------------------------------------------------
    # API helpers — Forecast
    # ------------------------------------------------------------------

    def _get_forecast_by_city(self, city: str) -> str:
        try:
            params = {"q": city, "appid": self.api_key, "units": self.units, "cnt": 24}
            resp = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                                params=params, timeout=10)
            if resp.status_code != 200:
                return f"OWM forecast error {resp.status_code}"
            return self._format_forecast(resp.json())
        except Exception as exc:
            return f"Forecast error: {exc}"

    def _get_forecast_by_coords(self, lat: str, lon: str) -> str:
        try:
            params = {"lat": lat, "lon": lon, "appid": self.api_key,
                       "units": self.units, "cnt": 24}
            resp = requests.get("https://api.openweathermap.org/data/2.5/forecast",
                                params=params, timeout=10)
            if resp.status_code != 200:
                return f"OWM forecast error {resp.status_code}"
            return self._format_forecast(resp.json())
        except Exception as exc:
            return f"Forecast error: {exc}"

    def _format_forecast(self, data: dict) -> str:
        city_name = data.get("city", {}).get("name", "?")
        items = data.get("list", [])
        unit_temp = "°F" if self.units == "imperial" else "°C" if self.units == "metric" else "K"
        lines = [f"📅 Forecast: {city_name}"]
        # Show every 8th entry (one per day for 3 days from 3-hour data)
        for i in range(0, min(len(items), 24), 8):
            entry = items[i]
            dt_txt = entry.get("dt_txt", "?")
            main = entry.get("main", {})
            weather = entry.get("weather", [{}])[0]
            lines.append(
                f"{dt_txt}: {weather.get('description', '?').title()} "
                f"{main.get('temp', '?')}{unit_temp}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # API helpers — Alerts (One Call API 3.0)
    # ------------------------------------------------------------------

    def _fetch_alerts_raw(self) -> list:
        """Fetch weather alerts from One Call API."""
        if not self.default_lat or not self.default_lon:
            return []
        try:
            params = {
                "lat": self.default_lat,
                "lon": self.default_lon,
                "appid": self.api_key,
                "exclude": "minutely,hourly,daily,current",
            }
            resp = requests.get(
                "https://api.openweathermap.org/data/3.0/onecall",
                params=params, timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("alerts", [])
        except Exception as exc:
            self.log(f"OWM alerts fetch error: {exc}")
        return []

    def _get_alerts(self) -> str:
        alerts = self._fetch_alerts_raw()
        if not alerts:
            return "No active weather alerts."
        lines = []
        for a in alerts[:5]:
            event = a.get("event", "Unknown")
            sender = a.get("sender_name", "")
            desc = a.get("description", "")[:200]
            lines.append(f"⚠️ {event}" + (f" ({sender})" if sender else "") +
                         (f"\n{desc}" if desc else ""))
        return "\n---\n".join(lines)
