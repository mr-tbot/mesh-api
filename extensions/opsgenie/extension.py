"""
OpsGenie extension for MESH-API.

Integrates the Meshtastic mesh network with Atlassian OpsGenie alert
management.

Features:
- Create OpsGenie alerts from mesh emergency broadcasts.
- Keyword-triggered alert creation.
- /og alert <message>     — create an OpsGenie alert.
- /og ack <alias|id>      — acknowledge an alert.
- /og close <alias|id>    — close an alert.
- /og status              — list open alerts.
- Poll open alerts and broadcast new ones onto the mesh.

Authentication:
- api_key: OpsGenie API key (GenieKey) with create/read/update permissions.
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class OpsgenieExtension(BaseExtension):
    """OpsGenie alert management extension."""

    @property
    def name(self) -> str:
        return "OpsGenie"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/og": "OpsGenie — /og alert|ack|close|status",
        }

    # -- config --
    @property
    def api_key(self) -> str:
        return self.config.get("api_key", "")

    @property
    def api_base(self) -> str:
        return self.config.get("api_base", "https://api.opsgenie.com").rstrip("/")

    @property
    def default_priority(self) -> str:
        return self.config.get("default_priority", "P3")

    @property
    def responders(self) -> list:
        return self.config.get("responders", [])

    @property
    def tags(self) -> list:
        return self.config.get("tags", ["mesh-api", "meshtastic"])

    @property
    def trigger_on_emergency(self) -> bool:
        return bool(self.config.get("trigger_on_emergency", True))

    @property
    def trigger_keywords(self) -> list:
        return self.config.get("trigger_on_keywords", [])

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def poll_alerts(self) -> bool:
        return bool(self.config.get("poll_alerts", False))

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 120))

    @property
    def auto_close_min(self) -> int:
        return int(self.config.get("auto_close_minutes", 0))

    # -- lifecycle --
    def on_load(self) -> None:
        self._poll_thread = None
        self._stop = threading.Event()
        self._known_ids: set = set()
        self.log(f"OpsGenie enabled. API key {'set' if self.api_key else 'NOT set'}.")

        if self.poll_alerts and self.api_key:
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="og-poll")
            self._poll_thread.start()

    def on_unload(self) -> None:
        self._stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("OpsGenie extension unloaded.")

    # -- auth header --
    def _headers(self) -> dict:
        return {
            "Authorization": f"GenieKey {self.api_key}",
            "Content-Type": "application/json",
        }

    # -- commands --
    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command != "/og":
            return None
        parts = args.strip().split(None, 1) if args.strip() else []
        sub = parts[0].lower() if parts else "status"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "alert":
            if not rest:
                return "Usage: /og alert <message>"
            return self._create_alert(rest)
        if sub == "ack":
            return self._ack_alert(rest.strip())
        if sub == "close":
            return self._close_alert(rest.strip())
        if sub == "status":
            return self._list_alerts()
        return "Usage: /og alert|ack|close|status"

    # -- hooks --
    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if not self.trigger_on_emergency or not self.api_key:
            return
        desc = f"MESH EMERGENCY: {message}"
        if gps_coords:
            desc += f"\nGPS: {gps_coords.get('lat','?')}, {gps_coords.get('lon','?')}"
        self._create_alert(desc, priority="P1")

    def on_message(self, message: str, node_info: dict) -> None:
        if not self.api_key or not self.trigger_keywords:
            return
        upper = message.upper()
        for kw in self.trigger_keywords:
            if kw.upper() in upper:
                sender = node_info.get("shortname", "?")
                self._create_alert(
                    f"Keyword '{kw}' from {sender}: {message[:300]}",
                    priority=self.default_priority,
                )
                break

    # -- API calls --
    def _create_alert(self, message: str, priority: str | None = None) -> str:
        if not self.api_key:
            return "No OpsGenie API key configured."
        try:
            payload: dict = {
                "message": message[:130],
                "description": message,
                "priority": priority or self.default_priority,
                "tags": self.tags,
                "source": "mesh-api",
            }
            if self.responders:
                payload["responders"] = self.responders
            resp = requests.post(f"{self.api_base}/v2/alerts", json=payload,
                                 headers=self._headers(), timeout=10)
            if resp.status_code in (200, 201, 202):
                data = resp.json()
                req_id = data.get("requestId", "?")
                self.log(f"OpsGenie alert created: {req_id}")
                return f"🚨 OpsGenie alert created ({priority or self.default_priority})."
            return f"⚠️ OpsGenie create failed: {resp.status_code} {resp.text[:100]}"
        except Exception as exc:
            return f"⚠️ OpsGenie error: {exc}"

    def _ack_alert(self, identifier: str) -> str:
        if not identifier:
            return "Usage: /og ack <alert_id_or_alias>"
        if not self.api_key:
            return "No API key configured."
        try:
            url = f"{self.api_base}/v2/alerts/{identifier}/acknowledge"
            resp = requests.post(url, json={"source": "mesh-api"},
                                 headers=self._headers(), timeout=10)
            if resp.status_code in (200, 202):
                return f"✅ Alert {identifier} acknowledged."
            return f"⚠️ Ack failed: {resp.status_code}"
        except Exception as exc:
            return f"⚠️ OG ack error: {exc}"

    def _close_alert(self, identifier: str) -> str:
        if not identifier:
            return "Usage: /og close <alert_id_or_alias>"
        if not self.api_key:
            return "No API key configured."
        try:
            url = f"{self.api_base}/v2/alerts/{identifier}/close"
            resp = requests.post(url, json={"source": "mesh-api"},
                                 headers=self._headers(), timeout=10)
            if resp.status_code in (200, 202):
                return f"✅ Alert {identifier} closed."
            return f"⚠️ Close failed: {resp.status_code}"
        except Exception as exc:
            return f"⚠️ OG close error: {exc}"

    def _list_alerts(self) -> str:
        if not self.api_key:
            return "No API key configured."
        try:
            params = {"query": "status=open", "limit": 10, "order": "desc"}
            resp = requests.get(f"{self.api_base}/v2/alerts", params=params,
                                headers=self._headers(), timeout=10)
            if resp.status_code != 200:
                return f"⚠️ OG list error: {resp.status_code}"
            alerts = resp.json().get("data", [])
            if not alerts:
                return "✅ No open OpsGenie alerts."
            lines = [f"🚨 Open Alerts ({len(alerts)}):"]
            for a in alerts[:8]:
                aid = a.get("tinyId", a.get("id", "?"))
                pri = a.get("priority", "?")
                msg = a.get("message", "?")[:50]
                status = a.get("status", "?")
                lines.append(f"  [{aid}] {pri} {status}: {msg}")
            return "\n".join(lines)
        except Exception as exc:
            return f"⚠️ OG list error: {exc}"

    # -- polling --
    def _poll_loop(self) -> None:
        time.sleep(15)
        while not self._stop.is_set():
            try:
                params = {"query": "status=open", "limit": 5, "order": "desc"}
                resp = requests.get(f"{self.api_base}/v2/alerts", params=params,
                                    headers=self._headers(), timeout=10)
                if resp.status_code == 200:
                    for a in resp.json().get("data", []):
                        aid = a.get("id")
                        if aid and aid not in self._known_ids:
                            self._known_ids.add(aid)
                            msg = a.get("message", "?")[:80]
                            pri = a.get("priority", "?")
                            tiny = a.get("tinyId", aid[:8])
                            self.send_to_mesh(
                                f"🚨 OG: [{pri}] {msg} (#{tiny})",
                                channel_index=self.broadcast_channel,
                            )
                if len(self._known_ids) > 200:
                    self._known_ids = set(list(self._known_ids)[-100:])
            except Exception as exc:
                self.log(f"OG poll error: {exc}")
            for _ in range(self.poll_interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
