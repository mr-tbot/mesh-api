"""
PagerDuty extension for MESH-API.

Integrates the Meshtastic mesh network with PagerDuty incident management.

Features:
- Trigger PagerDuty incidents from mesh emergency alerts.
- Trigger incidents when keyword-matched messages arrive.
- /pd trigger <summary>  — manually trigger a PagerDuty incident.
- /pd ack <incident_id>  — acknowledge an incident from the mesh.
- /pd resolve <id>       — resolve an incident from the mesh.
- /pd status             — show open incidents.
- Poll open incidents and broadcast status onto the mesh.

Authentication:
- routing_key: Events API v2 integration key (for triggering).
- api_token: REST API token (for ack/resolve/list — requires read/write).
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"
API_BASE = "https://api.pagerduty.com"


class PagerdutyExtension(BaseExtension):
    """PagerDuty incident management extension."""

    @property
    def name(self) -> str:
        return "PagerDuty"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/pd": "PagerDuty — /pd trigger|ack|resolve|status",
        }

    # -- config --
    @property
    def routing_key(self) -> str:
        return self.config.get("routing_key", "")

    @property
    def api_token(self) -> str:
        return self.config.get("api_token", "")

    @property
    def service_id(self) -> str:
        return self.config.get("service_id", "")

    @property
    def default_severity(self) -> str:
        return self.config.get("default_severity", "warning")

    @property
    def escalation_policy_id(self) -> str:
        return self.config.get("escalation_policy_id", "")

    @property
    def trigger_on_emergency(self) -> bool:
        return bool(self.config.get("trigger_on_emergency", True))

    @property
    def trigger_keywords(self) -> list:
        return self.config.get("trigger_on_keywords", [])

    @property
    def auto_resolve_min(self) -> int:
        return int(self.config.get("auto_resolve_minutes", 0))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def poll_incidents(self) -> bool:
        return bool(self.config.get("poll_incidents", False))

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 120))

    @property
    def dedup_prefix(self) -> str:
        return self.config.get("dedup_key_prefix", "mesh-api")

    # -- lifecycle --
    def on_load(self) -> None:
        self._poll_thread = None
        self._stop = threading.Event()
        self._known_incidents: set = set()

        info = []
        if self.routing_key:
            info.append("events_key=set")
        if self.api_token:
            info.append("api_token=set")
        self.log(f"PagerDuty enabled. {', '.join(info) if info else 'No keys set.'}")

        if self.poll_incidents and self.api_token:
            self._poll_thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="pd-poll")
            self._poll_thread.start()

    def on_unload(self) -> None:
        self._stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("PagerDuty extension unloaded.")

    # -- commands --
    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command != "/pd":
            return None
        parts = args.strip().split(None, 1) if args.strip() else []
        sub = parts[0].lower() if parts else "status"
        rest = parts[1] if len(parts) > 1 else ""

        if sub == "trigger":
            if not rest:
                return "Usage: /pd trigger <summary>"
            return self._trigger(rest, "mesh-manual", self.default_severity)
        if sub == "ack":
            return self._ack(rest.strip())
        if sub == "resolve":
            return self._resolve(rest.strip())
        if sub == "status":
            return self._list_incidents()
        return "Usage: /pd trigger|ack|resolve|status"

    # -- hooks --
    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if not self.trigger_on_emergency or not self.routing_key:
            return
        summary = f"MESH EMERGENCY: {message}"
        if gps_coords:
            summary += f" (GPS: {gps_coords.get('lat','?')},{gps_coords.get('lon','?')})"
        self._trigger(summary, "mesh-emergency", "critical")

    def on_message(self, message: str, node_info: dict) -> None:
        if not self.routing_key or not self.trigger_keywords:
            return
        upper = message.upper()
        for kw in self.trigger_keywords:
            if kw.upper() in upper:
                sender = node_info.get("shortname", "?")
                self._trigger(
                    f"Keyword '{kw}' from {sender}: {message[:200]}",
                    f"mesh-kw-{kw.lower()}",
                    self.default_severity,
                )
                break

    # -- Events API v2 --
    def _trigger(self, summary: str, source: str, severity: str) -> str:
        if not self.routing_key:
            return "No routing key configured."
        try:
            dedup = f"{self.dedup_prefix}-{source}-{int(time.time())}"
            payload = {
                "routing_key": self.routing_key,
                "event_action": "trigger",
                "dedup_key": dedup,
                "payload": {
                    "summary": summary[:1024],
                    "source": source,
                    "severity": severity,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "component": "mesh-api",
                    "group": "meshtastic",
                },
            }
            resp = requests.post(EVENTS_URL, json=payload, timeout=10)
            if resp.status_code in (200, 201, 202):
                data = resp.json()
                self.log(f"PD incident triggered: {data.get('dedup_key', dedup)}")
                return f"🚨 PagerDuty incident triggered ({severity})."
            return f"⚠️ PagerDuty trigger failed: {resp.status_code} {resp.text[:100]}"
        except Exception as exc:
            return f"⚠️ PagerDuty error: {exc}"

    # -- REST API --
    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Token token={self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.pagerduty+json;version=2",
        }

    def _ack(self, incident_id: str) -> str:
        if not incident_id:
            return "Usage: /pd ack <incident_id>"
        if not self.api_token:
            return "No API token configured."
        try:
            url = f"{API_BASE}/incidents/{incident_id}"
            payload = {"incident": {"type": "incident_reference", "status": "acknowledged"}}
            resp = requests.put(url, json=payload, headers=self._api_headers(), timeout=10)
            if resp.status_code == 200:
                return f"✅ Incident {incident_id} acknowledged."
            return f"⚠️ Ack failed: {resp.status_code}"
        except Exception as exc:
            return f"⚠️ PD ack error: {exc}"

    def _resolve(self, incident_id: str) -> str:
        if not incident_id:
            return "Usage: /pd resolve <incident_id>"
        if not self.api_token:
            return "No API token configured."
        try:
            url = f"{API_BASE}/incidents/{incident_id}"
            payload = {"incident": {"type": "incident_reference", "status": "resolved"}}
            resp = requests.put(url, json=payload, headers=self._api_headers(), timeout=10)
            if resp.status_code == 200:
                return f"✅ Incident {incident_id} resolved."
            return f"⚠️ Resolve failed: {resp.status_code}"
        except Exception as exc:
            return f"⚠️ PD resolve error: {exc}"

    def _list_incidents(self) -> str:
        if not self.api_token:
            return "No API token configured."
        try:
            params = {"statuses[]": ["triggered", "acknowledged"], "limit": 10}
            if self.service_id:
                params["service_ids[]"] = [self.service_id]
            resp = requests.get(f"{API_BASE}/incidents", params=params,
                                headers=self._api_headers(), timeout=10)
            if resp.status_code != 200:
                return f"⚠️ PD API error: {resp.status_code}"
            data = resp.json()
            incidents = data.get("incidents", [])
            if not incidents:
                return "✅ No open PagerDuty incidents."
            lines = [f"🚨 Open Incidents ({len(incidents)}):"]
            for inc in incidents[:8]:
                iid = inc.get("id", "?")
                status = inc.get("status", "?")
                title = inc.get("title", inc.get("summary", "?"))[:60]
                lines.append(f"  [{iid}] {status}: {title}")
            return "\n".join(lines)
        except Exception as exc:
            return f"⚠️ PD list error: {exc}"

    # -- polling --
    def _poll_loop(self) -> None:
        time.sleep(15)
        while not self._stop.is_set():
            try:
                params = {"statuses[]": ["triggered"], "limit": 5}
                if self.service_id:
                    params["service_ids[]"] = [self.service_id]
                resp = requests.get(f"{API_BASE}/incidents", params=params,
                                    headers=self._api_headers(), timeout=10)
                if resp.status_code == 200:
                    for inc in resp.json().get("incidents", []):
                        iid = inc.get("id")
                        if iid and iid not in self._known_incidents:
                            self._known_incidents.add(iid)
                            title = inc.get("title", "?")[:80]
                            self.send_to_mesh(
                                f"🚨 PD Alert: {title} [{iid}]",
                                channel_index=self.broadcast_channel,
                            )
                if len(self._known_incidents) > 200:
                    self._known_incidents = set(list(self._known_incidents)[-100:])
            except Exception as exc:
                self.log(f"PD poll error: {exc}")
            for _ in range(self.poll_interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
