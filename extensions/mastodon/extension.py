"""
Mastodon extension for MESH-API.

Provides a bridge between the Meshtastic mesh network and the Mastodon
fediverse social network.

Features:
- /toot <message>        — post a toot from the mesh.
- /fedi status            — show account info and recent toots.
- /fedi timeline [n]      — show home timeline (last n posts).
- Auto-post mesh emergency alerts to Mastodon.
- Poll for @mentions and forward them onto the mesh.

Authentication:
- instance_url: Mastodon instance (e.g. https://mastodon.social).
- access_token: Application access token with read+write scope.
  Create at: instance_url/settings/applications
"""

import threading
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class MastodonExtension(BaseExtension):
    """Mastodon / Fediverse bridge extension."""

    @property
    def name(self) -> str:
        return "Mastodon"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/toot": "Post to Mastodon (/toot <message>)",
            "/fedi": "Fediverse — /fedi status|timeline",
        }

    # -- config --
    @property
    def instance_url(self) -> str:
        return self.config.get("instance_url", "https://mastodon.social").rstrip("/")

    @property
    def access_token(self) -> str:
        return self.config.get("access_token", "")

    @property
    def visibility(self) -> str:
        return self.config.get("default_visibility", "public")

    @property
    def post_prefix(self) -> str:
        return self.config.get("post_prefix", "📡 [Mesh]")

    @property
    def max_length(self) -> int:
        return int(self.config.get("max_toot_length", 500))

    @property
    def broadcast_channel(self) -> int:
        return int(self.config.get("broadcast_channel_index", 0))

    @property
    def auto_post_emergency(self) -> bool:
        return bool(self.config.get("auto_post_emergency", True))

    @property
    def poll_mentions(self) -> bool:
        return bool(self.config.get("poll_mentions", False))

    @property
    def poll_interval(self) -> int:
        return int(self.config.get("poll_interval_seconds", 120))

    @property
    def forward_mentions(self) -> bool:
        return bool(self.config.get("forward_mentions_to_mesh", True))

    @property
    def hashtags(self) -> list:
        return self.config.get("hashtags", [])

    @property
    def content_warning(self) -> str:
        return self.config.get("content_warning", "")

    # -- helpers --
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    def _api(self, path: str) -> str:
        return f"{self.instance_url}/api/v1{path}"

    # -- lifecycle --
    def on_load(self) -> None:
        self._poll_thread = None
        self._stop = threading.Event()
        self._last_mention_id: str | None = None
        self.log(f"Mastodon enabled. Instance: {self.instance_url} | "
                 f"Token: {'set' if self.access_token else 'NOT set'}")

        if self.poll_mentions and self.access_token:
            self._poll_thread = threading.Thread(
                target=self._poll_mentions_loop, daemon=True, name="mastodon-poll")
            self._poll_thread.start()

    def on_unload(self) -> None:
        self._stop.set()
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=10)
        self.log("Mastodon extension unloaded.")

    # -- commands --
    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/toot":
            if not args.strip():
                return "Usage: /toot <message>"
            return self._post_toot(args.strip(), node_info)

        if command == "/fedi":
            parts = args.strip().split(None, 1) if args.strip() else []
            sub = parts[0].lower() if parts else "status"
            rest = parts[1] if len(parts) > 1 else ""

            if sub == "status":
                return self._account_status()
            if sub == "timeline":
                count = 5
                if rest:
                    try:
                        count = min(int(rest), 10)
                    except ValueError:
                        count = 5
                return self._timeline(count)
            return "Usage: /fedi status|timeline [n]"

        return None

    # -- hooks --
    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        if not self.auto_post_emergency or not self.access_token:
            return
        text = f"🚨 MESH EMERGENCY: {message}"
        if gps_coords:
            text += f"\nGPS: {gps_coords.get('lat','?')}, {gps_coords.get('lon','?')}"
        self._post(text, visibility="public", spoiler="Emergency Alert")

    # -- posting --
    def _post_toot(self, text: str, node_info: dict) -> str:
        if not self.access_token:
            return "No Mastodon access token configured."
        sender = node_info.get("shortname", "MeshUser")
        full = f"{self.post_prefix} {sender}: {text}"
        # Append hashtags
        if self.hashtags:
            tags = " ".join(f"#{t}" for t in self.hashtags)
            full += f"\n{tags}"
        # Trim to max length
        if len(full) > self.max_length:
            full = full[:self.max_length - 3] + "..."
        return self._post(full)

    def _post(self, status: str, visibility: str | None = None,
              spoiler: str | None = None) -> str:
        try:
            payload: dict = {
                "status": status,
                "visibility": visibility or self.visibility,
            }
            cw = spoiler or self.content_warning
            if cw:
                payload["spoiler_text"] = cw
            resp = requests.post(self._api("/statuses"), json=payload,
                                 headers=self._headers(), timeout=10)
            if resp.status_code in (200, 201):
                data = resp.json()
                toot_url = data.get("url", "")
                self.log(f"Toot posted: {toot_url}")
                return f"📯 Posted to Mastodon!"
            return f"⚠️ Post failed: {resp.status_code} {resp.text[:100]}"
        except Exception as exc:
            return f"⚠️ Mastodon error: {exc}"

    # -- account status --
    def _account_status(self) -> str:
        if not self.access_token:
            return "No access token configured."
        try:
            resp = requests.get(self._api("/accounts/verify_credentials"),
                                headers=self._headers(), timeout=10)
            if resp.status_code != 200:
                return f"⚠️ Account error: {resp.status_code}"
            d = resp.json()
            return (
                f"🐘 Mastodon Account:\n"
                f"@{d.get('acct', '?')}\n"
                f"Followers: {d.get('followers_count', 0)} | "
                f"Following: {d.get('following_count', 0)}\n"
                f"Toots: {d.get('statuses_count', 0)}\n"
                f"Instance: {self.instance_url}"
            )
        except Exception as exc:
            return f"⚠️ Account check error: {exc}"

    # -- timeline --
    def _timeline(self, count: int = 5) -> str:
        if not self.access_token:
            return "No access token configured."
        try:
            resp = requests.get(self._api("/timelines/home"),
                                params={"limit": count},
                                headers=self._headers(), timeout=10)
            if resp.status_code != 200:
                return f"⚠️ Timeline error: {resp.status_code}"
            posts = resp.json()
            if not posts:
                return "Timeline is empty."
            lines = [f"🐘 Timeline ({len(posts)}):"]
            for p in posts:
                acct = p.get("account", {}).get("acct", "?")
                # Strip HTML tags from content (basic)
                content = p.get("content", "")
                content = self._strip_html(content)[:80]
                lines.append(f"  @{acct}: {content}")
            return "\n".join(lines)
        except Exception as exc:
            return f"⚠️ Timeline error: {exc}"

    @staticmethod
    def _strip_html(html: str) -> str:
        """Crude HTML tag removal for toot content."""
        import re
        text = re.sub(r"<br\s*/?>", "\n", html)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&apos;", "'").replace("&quot;", '"')
        return text.strip()

    # -- mention polling --
    def _poll_mentions_loop(self) -> None:
        time.sleep(15)
        # Seed with current notifications so we don't replay old ones
        try:
            resp = requests.get(
                self._api("/notifications"),
                params={"types[]": "mention", "limit": 1},
                headers=self._headers(), timeout=10,
            )
            if resp.status_code == 200:
                notifs = resp.json()
                if notifs:
                    self._last_mention_id = notifs[0].get("id")
        except Exception:
            pass

        while not self._stop.is_set():
            try:
                params: dict = {"types[]": "mention", "limit": 5}
                if self._last_mention_id:
                    params["since_id"] = self._last_mention_id
                resp = requests.get(self._api("/notifications"), params=params,
                                    headers=self._headers(), timeout=10)
                if resp.status_code == 200:
                    notifs = resp.json()
                    for n in reversed(notifs):
                        nid = n.get("id")
                        if nid:
                            self._last_mention_id = nid
                        if self.forward_mentions:
                            acct = n.get("account", {}).get("acct", "?")
                            content = n.get("status", {}).get("content", "")
                            content = self._strip_html(content)[:150]
                            self.send_to_mesh(
                                f"🐘 @{acct}: {content}",
                                channel_index=self.broadcast_channel,
                            )
                            self.log(f"Forwarded Mastodon mention from @{acct}")
            except Exception as exc:
                self.log(f"Mastodon poll error: {exc}")
            for _ in range(self.poll_interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
