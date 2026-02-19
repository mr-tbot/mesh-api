"""
Matrix extension for MESH-API.

Provides bidirectional Matrix ↔ Mesh integration using the Matrix
Client-Server API (/_matrix/client/r0):
- Outbound: sends mesh messages to a Matrix room via PUT /send.
- Inbound:  polls the room via /sync and routes new messages to mesh.
- Emergency: posts emergency alerts to the configured room.

Requires a homeserver URL, an access token (from an application service
or a logged-in user), and a room ID (!xxx:server).
"""

import threading
import time
import uuid

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class MatrixExtension(BaseExtension):
    """Matrix ↔ Mesh bridge extension."""

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Matrix"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def homeserver_url(self) -> str:
        url = self.config.get("homeserver_url", "")
        return url.rstrip("/") if url else ""

    @property
    def access_token(self) -> str:
        return self.config.get("access_token", "")

    @property
    def room_id(self) -> str:
        return self.config.get("room_id", "")

    @property
    def send_emergency(self) -> bool:
        return bool(self.config.get("send_emergency", False))

    @property
    def send_ai(self) -> bool:
        return bool(self.config.get("send_ai", False))

    @property
    def send_all(self) -> bool:
        return bool(self.config.get("send_all", False))

    @property
    def receive_enabled(self) -> bool:
        return bool(self.config.get("receive_enabled", True))

    @property
    def inbound_channel_index(self):
        val = self.config.get("inbound_channel_index")
        return int(val) if val is not None else None

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 5))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        self._poll_thread = None
        self._stop_event = threading.Event()
        self._sync_token = None

        status = []
        if self.homeserver_url:
            status.append(f"hs={self.homeserver_url}")
        if self.room_id:
            status.append(f"room={self.room_id}")

        self.log(f"Matrix enabled. {', '.join(status) if status else 'No settings configured.'}")

        if self.homeserver_url and self.access_token and self.room_id and self.receive_enabled:
            self._poll_thread = threading.Thread(
                target=self._poll_matrix,
                daemon=True,
                name="matrix-sync",
            )
            self._poll_thread.start()
            self.log("Matrix sync thread started.")

    def on_unload(self) -> None:
        self._stop_event.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=5)
        self.log("Matrix extension unloaded.")

    # ------------------------------------------------------------------
    # Outbound: mesh → Matrix
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        metadata = metadata or {}
        is_ai = metadata.get("is_ai_response", False)
        ch_idx = metadata.get("channel_idx")

        if self.send_all and not is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_matrix(message)
            return

        if self.send_ai and is_ai:
            if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
                self._send_matrix(message)

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        if not self.send_all:
            return
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if self.inbound_channel_index is not None and ch_idx == self.inbound_channel_index:
            sender = metadata.get("sender_info", "Unknown")
            self._send_matrix(f"**{sender}**: {message}")

    # ------------------------------------------------------------------
    # Emergency hook
    # ------------------------------------------------------------------

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if self.send_emergency:
            try:
                self._send_matrix(f"🚨 **EMERGENCY ALERT**\n{message}")
                self.log("✅ Emergency alert posted to Matrix.")
            except Exception as exc:
                self.log(f"⚠️ Matrix emergency error: {exc}")

    # ------------------------------------------------------------------
    # Inbound: Matrix → Mesh (via /sync long-poll)
    # ------------------------------------------------------------------

    def _poll_matrix(self) -> None:
        time.sleep(5)
        headers = {"Authorization": f"Bearer {self.access_token}"}

        # Do an initial sync to get the since token (skip backlog)
        try:
            resp = requests.get(
                f"{self.homeserver_url}/_matrix/client/r0/sync",
                headers=headers,
                params={"timeout": 0, "filter": '{"room":{"timeline":{"limit":0}}}'},
                timeout=30,
            )
            if resp.status_code == 200:
                self._sync_token = resp.json().get("next_batch")
        except Exception as exc:
            self.log(f"Matrix initial sync error: {exc}")

        while not self._stop_event.is_set():
            try:
                params = {"timeout": str(self.poll_interval * 1000)}
                if self._sync_token:
                    params["since"] = self._sync_token
                resp = requests.get(
                    f"{self.homeserver_url}/_matrix/client/r0/sync",
                    headers=headers,
                    params=params,
                    timeout=self.poll_interval + 10,
                )
                if resp.status_code != 200:
                    self.log(f"Matrix sync error: {resp.status_code}")
                    time.sleep(5)
                    continue
                data = resp.json()
                self._sync_token = data.get("next_batch")

                rooms = data.get("rooms", {}).get("join", {})
                room_data = rooms.get(self.room_id)
                if room_data:
                    events = room_data.get("timeline", {}).get("events", [])
                    for event in events:
                        if event.get("type") != "m.room.message":
                            continue
                        content = event.get("content", {})
                        body = content.get("body", "")
                        sender = event.get("sender", "MatrixUser")
                        if not body:
                            continue

                        formatted = f"[Matrix:{sender}] {body}"
                        log_fn = self.app_context.get("log_message")
                        if log_fn:
                            log_fn("Matrix", formatted, direct=False,
                                   channel_idx=self.inbound_channel_index)
                        if self.inbound_channel_index is not None:
                            self.send_to_mesh(formatted,
                                              channel_index=self.inbound_channel_index)
                        self.log(f"Polled Matrix message: {formatted}")
            except Exception as exc:
                self.log(f"Error syncing Matrix: {exc}")
                time.sleep(5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_matrix(self, text: str) -> None:
        """Send a message to the Matrix room via PUT /send."""
        if not self.homeserver_url or not self.access_token or not self.room_id:
            return
        txn_id = uuid.uuid4().hex
        url = (f"{self.homeserver_url}/_matrix/client/r0/rooms/"
               f"{self.room_id}/send/m.room.message/{txn_id}")
        headers = {"Authorization": f"Bearer {self.access_token}"}
        body = {"msgtype": "m.text", "body": text}
        try:
            requests.put(url, headers=headers, json=body)
        except Exception as exc:
            self.log(f"⚠️ Matrix send error: {exc}")
