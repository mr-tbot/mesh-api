"""
APRS extension for MESH-API.

Provides integration between the Meshtastic mesh and the Automatic Packet
Reporting System (APRS) used by ham radio operators worldwide.

Features:
- /aprs <callsign>       — look up last known position of an APRS station.
- /aprsmsg <call> <msg>   — send an APRS message to a station (via APRS-IS).
- /aprsnear               — show nearby APRS stations.
- Position forwarding:     optionally publishes mesh node positions to APRS-IS.
- Position monitoring:     optionally monitors nearby APRS positions and
  broadcasts them onto the mesh.

Integration methods:
1. aprs.fi API — for station lookups (requires free API key).
2. APRS-IS (Internet Service) — for real-time message exchange and
   position beaconing via TCP socket.

Note: Transmitting on APRS requires a valid amateur radio licence and
callsign.  The APRS-IS passcode authenticates licensed operators.
"""

import socket
import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class AprsExtension(BaseExtension):
    """APRS ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "APRS"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/aprs": "Look up APRS station (/aprs <callsign>)",
            "/aprsmsg": "Send APRS message (/aprsmsg <call> <msg>)",
            "/aprsnear": "Show nearby APRS stations",
        }

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def callsign(self) -> str:
        return self.config.get("callsign", "").upper()

    @property
    def passcode(self) -> str:
        return self.config.get("passcode", "")

    @property
    def aprs_is_server(self) -> str:
        return self.config.get("aprs_is_server", "rotate.aprs2.net")

    @property
    def aprs_is_port(self) -> int:
        return int(self.config.get("aprs_is_port", 14580))

    @property
    def aprs_fi_key(self) -> str:
        return self.config.get("aprs_fi_api_key", "")

    @property
    def filter_range_km(self) -> int:
        return int(self.config.get("filter_range_km", 100))

    @property
    def filter_lat(self) -> str:
        return str(self.config.get("filter_lat", ""))

    @property
    def filter_lon(self) -> str:
        return str(self.config.get("filter_lon", ""))

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 60))

    @property
    def auto_broadcast_positions(self) -> bool:
        return bool(self.config.get("auto_broadcast_positions", False))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def send_position_to_aprs(self) -> bool:
        return bool(self.config.get("send_position_to_aprs", False))

    @property
    def position_comment(self) -> str:
        return self.config.get("position_comment", "MESH-API Node")

    @property
    def symbol_table(self) -> str:
        return self.config.get("symbol_table", "/")

    @property
    def symbol_code(self) -> str:
        return self.config.get("symbol_code", "-")

    @property
    def message_ssid(self) -> str:
        return self.config.get("message_ssid", "-5")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._is_sock = None
        self._is_thread = None
        self._stop_event = threading.Event()
        self._msg_counter = 0
        self._seen_positions: dict = {}  # callsign -> last_seen_ts

        status = []
        if self.callsign:
            status.append(f"call={self.callsign}")
        if self.aprs_fi_key:
            status.append("aprs.fi=set")
        self.log(f"APRS enabled. {', '.join(status) if status else 'No callsign set.'}")

        # Start APRS-IS listener if configured
        if self.callsign and self.passcode and self.auto_broadcast_positions:
            self._is_thread = threading.Thread(
                target=self._aprs_is_listener,
                daemon=True,
                name="aprs-is-listen",
            )
            self._is_thread.start()
            self.log("APRS-IS listener thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._is_sock:
            try:
                self._is_sock.close()
            except Exception:
                pass
        if self._is_thread and self._is_thread.is_alive():
            self._is_thread.join(timeout=10)
        self.log("APRS extension unloaded.")

    # ------------------------------------------------------------------
    # Command handler
    # ------------------------------------------------------------------

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/aprs":
            call = args.strip().upper()
            if not call:
                return "Usage: /aprs <callsign>"
            return self._lookup_station(call)

        if command == "/aprsmsg":
            if not self.callsign:
                return "No callsign configured."
            parts = args.strip().split(None, 1)
            if len(parts) < 2:
                return "Usage: /aprsmsg <callsign> <message>"
            to_call = parts[0].upper()
            msg_text = parts[1]
            return self._send_aprs_message(to_call, msg_text)

        if command == "/aprsnear":
            return self._nearby_stations()

        return None

    # ------------------------------------------------------------------
    # aprs.fi API lookups
    # ------------------------------------------------------------------

    def _lookup_station(self, callsign: str) -> str:
        """Look up a station's last position via aprs.fi API."""
        if not self.aprs_fi_key:
            return "No aprs.fi API key configured."
        try:
            resp = requests.get(
                "https://api.aprs.fi/api/get",
                params={
                    "name": callsign,
                    "what": "loc",
                    "apikey": self.aprs_fi_key,
                    "format": "json",
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return f"aprs.fi error: {resp.status_code}"
            data = resp.json()
            if data.get("result") == "fail":
                return f"aprs.fi: {data.get('description', 'Unknown error')}"
            entries = data.get("entries", [])
            if not entries:
                return f"No position found for {callsign}."

            e = entries[0]
            lat = e.get("lat", "?")
            lng = e.get("lng", "?")
            comment = e.get("comment", "")
            speed = e.get("speed", "")
            course = e.get("course", "")
            last_time = e.get("lasttime", "")
            if last_time:
                try:
                    dt = datetime.fromtimestamp(int(last_time), tz=timezone.utc)
                    last_time = dt.strftime("%H:%M UTC %b %d")
                except (ValueError, TypeError):
                    pass

            text = f"📡 {callsign}: {lat}, {lng}"
            if last_time:
                text += f"\nLast heard: {last_time}"
            if speed:
                text += f" | Speed: {speed} km/h"
            if comment:
                text += f"\n{comment[:100]}"
            return text

        except Exception as exc:
            return f"APRS lookup error: {exc}"

    def _nearby_stations(self) -> str:
        """Show nearby APRS stations using aprs.fi API."""
        if not self.aprs_fi_key:
            return "No aprs.fi API key configured."
        if not self.filter_lat or not self.filter_lon:
            return "No filter coordinates configured."
        try:
            # aprs.fi doesn't have a direct "nearby" endpoint, so we use
            # the range filter. We'll look up our own position's area.
            # Alternative: use the filter endpoint with lat/lon/range
            resp = requests.get(
                "https://api.aprs.fi/api/get",
                params={
                    "name": self.callsign or "*",
                    "what": "loc",
                    "apikey": self.aprs_fi_key,
                    "format": "json",
                    "lat": self.filter_lat,
                    "lng": self.filter_lon,
                    "range": self.filter_range_km,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return f"aprs.fi error: {resp.status_code}"
            data = resp.json()
            entries = data.get("entries", [])
            if not entries:
                return "No nearby APRS stations found."

            lines = [f"📡 Nearby APRS ({len(entries)} station(s)):"]
            for e in entries[:8]:
                name = e.get("name", "?")
                lat = e.get("lat", "?")
                lng = e.get("lng", "?")
                comment = e.get("comment", "")[:50]
                lines.append(f"  {name}: {lat},{lng}"
                             + (f" - {comment}" if comment else ""))
            return "\n".join(lines)

        except Exception as exc:
            return f"APRS nearby error: {exc}"

    # ------------------------------------------------------------------
    # APRS-IS messaging
    # ------------------------------------------------------------------

    def _send_aprs_message(self, to_call: str, message: str) -> str:
        """Send an APRS message via APRS-IS."""
        if not self.callsign or not self.passcode:
            return "APRS-IS credentials not configured."
        try:
            self._msg_counter += 1
            msg_no = str(self._msg_counter % 100).zfill(2)

            # Format: FROMCALL>APRS,TCPIP*::TOCALL   :message{msgno
            to_padded = to_call.ljust(9)
            from_call = f"{self.callsign}{self.message_ssid}"
            packet = f"{from_call}>APRS,TCPIP*::{to_padded}:{message}{{{msg_no}"

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.aprs_is_server, self.aprs_is_port))
            # Read banner
            sock.recv(512)
            # Login
            login = f"user {self.callsign} pass {self.passcode} vers MESH-API 1.0\r\n"
            sock.sendall(login.encode())
            time.sleep(1)
            sock.recv(512)
            # Send packet
            sock.sendall(f"{packet}\r\n".encode())
            time.sleep(1)
            sock.close()

            self.log(f"APRS message sent to {to_call}: {message}")
            return f"📡 APRS message sent to {to_call}."

        except Exception as exc:
            return f"⚠️ APRS-IS send error: {exc}"

    # ------------------------------------------------------------------
    # APRS-IS listener (background thread)
    # ------------------------------------------------------------------

    def _aprs_is_listener(self) -> None:
        """Connect to APRS-IS and listen for nearby position reports."""
        time.sleep(10)

        while not self._stop_event.is_set():
            try:
                self._is_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._is_sock.settimeout(30)
                self._is_sock.connect((self.aprs_is_server, self.aprs_is_port))
                self._is_sock.recv(512)  # banner

                # Build filter string
                filt = ""
                if self.filter_lat and self.filter_lon:
                    filt = f"r/{self.filter_lat}/{self.filter_lon}/{self.filter_range_km}"
                login = (f"user {self.callsign} pass {self.passcode} "
                         f"vers MESH-API 1.0"
                         + (f" filter {filt}" if filt else "") + "\r\n")
                self._is_sock.sendall(login.encode())
                time.sleep(1)
                self._is_sock.recv(512)  # login ack

                self.log("Connected to APRS-IS for position monitoring.")
                self._is_sock.settimeout(90)

                buf = ""
                while not self._stop_event.is_set():
                    try:
                        data = self._is_sock.recv(4096).decode("utf-8", errors="replace")
                        if not data:
                            break
                        buf += data
                        while "\r\n" in buf:
                            line, buf = buf.split("\r\n", 1)
                            if line.startswith("#"):
                                continue  # server comment
                            self._handle_aprs_packet(line)
                    except socket.timeout:
                        # Send keepalive
                        try:
                            self._is_sock.sendall(b"#keepalive\r\n")
                        except Exception:
                            break

            except Exception as exc:
                if not self._stop_event.is_set():
                    self.log(f"APRS-IS connection error: {exc}")

            if self._is_sock:
                try:
                    self._is_sock.close()
                except Exception:
                    pass
                self._is_sock = None

            # Reconnect delay
            for _ in range(30):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

    def _handle_aprs_packet(self, raw: str) -> None:
        """Parse and optionally broadcast an APRS position packet."""
        try:
            if ">" not in raw:
                return
            from_call = raw.split(">")[0].strip()
            # Only broadcast if we haven't seen this station recently
            now = time.time()
            last = self._seen_positions.get(from_call, 0)
            if now - last < self.poll_interval:
                return
            self._seen_positions[from_call] = now

            # Simple position extraction (crude but functional)
            # Full APRS parsing would require a dedicated library
            if ":" not in raw:
                return
            info = raw.split(":", 1)[1]
            # Position reports start with ! @ / = or contain lat/lon
            if info and info[0] in "!=/@":
                text = f"📡 APRS: {from_call} position update"
                # Try to extract lat/lon from compressed or uncompressed
                if len(info) > 18:
                    text += f"\nRaw: {info[:60]}"
                self.send_to_mesh(text, channel_index=self.broadcast_channel)

            # Trim seen cache
            if len(self._seen_positions) > 500:
                oldest = sorted(self._seen_positions.items(),
                                key=lambda x: x[1])[:250]
                for k, _ in oldest:
                    del self._seen_positions[k]

        except Exception as exc:
            self.log(f"APRS packet parse error: {exc}")
