"""
meshcore_core.py — Core-owned MeshCore radio manager for MESH-API v0.7.0.

Starting with v0.7.0 Beta, MeshCore is a **first-class radio** inside MESH-API,
on equal footing with Meshtastic — not a bridge plugin.  A user can run:

  * a Meshtastic radio only (classic behaviour, unchanged), or
  * a MeshCore radio only (standalone — no Meshtastic device required), or
  * one of each, with MESH-API acting as the man-in-the-middle so traffic,
    commands, the AI assistant, and every plugin work across both networks.

This module owns the MeshCore connection.  It wraps the asynchronous
``meshcore`` Python library (https://github.com/meshcore-dev/meshcore_py) in a
dedicated asyncio event loop running on a background thread, and exposes a
small **synchronous, thread-safe** surface that the synchronous MESH-API core
can call without ever blocking:

    mgr = MeshCoreManager(config, on_inbound=..., log=...)
    mgr.start()
    mgr.send_channel(0, "hello")
    mgr.send_dm("a1b2c3d4", "hi there")
    nodes = mgr.get_nodes()       # for the harmonized map
    status = mgr.get_status()     # for the web UI
    mgr.stop()

Inbound MeshCore messages are handed to the ``on_inbound`` callback using a
network-agnostic signature so the core can route them through the *same*
pipeline as Meshtastic messages (AI, slash commands, and all extension
hooks).  This is what lets a message that originates on MeshCore reach
Telegram, Discord, the AI provider, etc. (GitHub issue #59).

The library is optional: if it is not installed, the manager degrades
gracefully (``available`` is False) so MESH-API still runs.
"""

from __future__ import annotations

import asyncio
import re
import threading
import time
import traceback
from typing import Any, Callable, Optional

try:
    from meshcore import MeshCore, EventType  # type: ignore[import-untyped]
    MESHCORE_AVAILABLE = True
except Exception:  # pragma: no cover - import guard
    MESHCORE_AVAILABLE = False
    MeshCore = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment,misc]


# Inbound callback signature (kept network-agnostic on purpose):
#   on_inbound(network, sender_id, sender_name, text, is_direct, channel_idx, reply_target)
# where reply_target carries enough info to reply over MeshCore:
#   {"kind": "dm", "key": "<pubkey_prefix>"}  or  {"kind": "channel", "channel": <int>}
InboundCallback = Callable[[str, str, str, str, bool, Optional[int], dict], None]
LogCallback = Callable[[str], None]


class MeshCoreManager:
    """Manages a single MeshCore companion-radio connection for the core."""

    NETWORK = "meshcore"

    def __init__(
        self,
        config: dict,
        on_inbound: Optional[InboundCallback] = None,
        log: Optional[LogCallback] = None,
    ) -> None:
        self._config = config or {}
        self._on_inbound = on_inbound
        self._log_fn = log or (lambda m: print(m))

        self._mc = None  # MeshCore instance or None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._stopping = threading.Event()
        self._connected = False
        self._started = False

        # Cached device + contact state (refreshed in the bg loop, read by web UI)
        self._self_info: dict = {}
        self._device_info: dict = {}
        self._contacts: dict = {}
        self._contacts_lock = threading.Lock()
        self._channels: dict = {}  # idx -> {"name": str, "index": int}
        self._channels_lock = threading.Lock()
        self._last_rx_ts: float = 0.0
        self._last_advert: float = 0.0

        self._stats = {
            "rx": 0,            # messages received from MeshCore
            "tx": 0,            # messages sent to MeshCore
            "commands": 0,      # commands processed from MeshCore users
            "errors": 0,
            "reconnects": 0,
        }

    # ── Public properties ────────────────────────────────────────────

    @property
    def available(self) -> bool:
        """True if the ``meshcore`` library is importable."""
        return MESHCORE_AVAILABLE

    @property
    def enabled(self) -> bool:
        return bool(self._config.get("enabled", False))

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background asyncio thread (idempotent)."""
        if self._started:
            return
        if not self.enabled:
            self._log("MeshCore radio is disabled in config; not starting.")
            return
        if not MESHCORE_AVAILABLE:
            self._log(
                "⚠️  MeshCore radio is enabled but the 'meshcore' package is not "
                "installed. Install it with:  pip install meshcore"
            )
            return
        self._started = True
        self._stopping.clear()
        self._thread = threading.Thread(
            target=self._run_event_loop,
            name="meshcore-core",
            daemon=True,
        )
        self._thread.start()
        self._log("MeshCore radio manager started.")

    def stop(self) -> None:
        self._stopping.set()
        if self._loop and self._mc:
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=10)
        self._started = False
        self._connected = False
        self._log("MeshCore radio manager stopped.")

    # ── Public send surface (thread-safe, synchronous) ───────────────

    def send_channel(self, channel: int, text: str) -> bool:
        """Send a message to a MeshCore channel. Returns True if scheduled."""
        if not self._can_send():
            return False
        asyncio.run_coroutine_threadsafe(
            self._send_channel_async(int(channel), text), self._loop  # type: ignore[arg-type]
        )
        return True

    def send_dm(self, key_prefix: str, text: str) -> bool:
        """Send a direct message to a MeshCore contact by public-key prefix."""
        if not self._can_send():
            return False
        asyncio.run_coroutine_threadsafe(
            self._send_dm_async(key_prefix, text), self._loop  # type: ignore[arg-type]
        )
        return True

    def broadcast(self, text: str) -> bool:
        """Broadcast to the public channel (0)."""
        return self.send_channel(0, text)

    # ── Public read surface (for web UI / harmonized map) ────────────

    def get_nodes(self) -> list:
        """Return MeshCore contacts in a UI-friendly, network-tagged shape."""
        nodes = []
        with self._contacts_lock:
            contacts = dict(self._contacts)
        for key, c in contacts.items():
            if not isinstance(c, dict):
                continue
            pub = c.get("public_key", key) or key
            name = c.get("adv_name") or c.get("name") or f"MC_{str(pub)[:6]}"
            lat = c.get("adv_lat")
            lon = c.get("adv_lon")
            entry = {
                "id": f"!mc-{str(pub)[:8]}",
                "pubkey": pub,
                "shortName": name,
                "longName": name,
                "network": self.NETWORK,
            }
            try:
                if lat not in (None, 0) or lon not in (None, 0):
                    entry["lat"] = float(lat)
                    entry["lon"] = float(lon)
            except (TypeError, ValueError):
                pass
            nodes.append(entry)
        return nodes

    def get_status(self) -> dict:
        return {
            "available": MESHCORE_AVAILABLE,
            "enabled": self.enabled,
            "connected": self._connected,
            "connection_type": self._config.get("connection_type", "serial"),
            "self": {
                "name": self._self_info.get("name"),
                "public_key": self._self_info.get("public_key"),
                "lat": self._self_info.get("adv_lat"),
                "lon": self._self_info.get("adv_lon"),
            },
            "contacts": len(self._contacts),
            "channels": self.get_channels(),
            "last_rx_age_sec": (time.time() - self._last_rx_ts) if self._last_rx_ts else None,
            "stats": dict(self._stats),
        }

    def get_channels(self) -> list:
        """Return MeshCore channels (group chats / private channels) for the UI."""
        with self._channels_lock:
            chans = dict(self._channels)
        out = []
        for idx in sorted(chans.keys()):
            c = chans[idx]
            name = (c.get("name") or "").strip() or (f"Public" if idx == 0 else f"Channel {idx}")
            out.append({"index": idx, "name": name})
        if not out:
            # Always offer the public channel even before a channel scan completes.
            out = [{"index": 0, "name": "Public"}]
        return out

    def get_device_info(self) -> dict:
        """Return MeshCore device model + firmware version (for update checks)."""
        di = self._device_info or {}
        si = self._self_info or {}
        return {
            "model": di.get("model") or si.get("model"),
            "firmware_version": (di.get("ver") or di.get("firmware_version")
                                  or di.get("fw_version") or si.get("firmware_version")),
            "manufacturer": di.get("manufacturer"),
        }

    def get_contacts(self) -> list:
        """Return MeshCore contacts (for DM targets) with full pubkeys."""
        with self._contacts_lock:
            contacts = dict(self._contacts)
        out = []
        for key, c in contacts.items():
            if not isinstance(c, dict):
                continue
            pub = str(c.get("public_key", key) or key)
            name = c.get("adv_name") or c.get("name") or f"MC_{pub[:6]}"
            out.append({
                "id": f"!mc-{pub[:8]}",
                "pubkey": pub,
                "name": name,
                "is_repeater": bool(c.get("type") == 2 or c.get("is_repeater")),
            })
        return out

    # ==================================================================
    #  Internal — asyncio event loop & connection management
    # ==================================================================

    def _log(self, msg: str) -> None:
        try:
            self._log_fn(f"[MeshCore] {msg}")
        except Exception:
            print(f"[MeshCore] {msg}")

    def _can_send(self) -> bool:
        return bool(self._mc and self._loop and self._connected)

    def _max_len(self) -> int:
        return int(self._config.get("max_message_length", 200))

    def _run_event_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as exc:  # pragma: no cover - defensive
            self._log(f"⚠️  event loop crashed: {exc}")
            self._log(traceback.format_exc())
        finally:
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None

    async def _main_loop(self) -> None:
        """Connect (with bounded attempts + exponential backoff) and listen."""
        base_interval = int(self._config.get("reconnect_interval_sec", 15))
        backoff = base_interval
        max_backoff = max(base_interval, int(self._config.get("max_reconnect_interval_sec", 120)))

        while not self._stopping.is_set():
            try:
                self._mc = await self._connect()
                if self._mc is None:
                    self._log(f"connection failed; retrying in {backoff}s…")
                    await self._interruptible_sleep(backoff)
                    backoff = min(max_backoff, backoff * 2)
                    continue

                self._connected = True
                backoff = base_interval  # reset backoff on a good connect
                self._log("✅ connected to MeshCore companion node.")

                await self._after_connect()
                await self._subscribe_events()
                try:
                    await self._mc.start_auto_message_fetching()
                except Exception as exc:
                    self._log(f"⚠️  could not start auto message fetching: {exc}")

                # Announce ourselves so other MeshCore nodes can discover us as a
                # contact (required before they can DM us — e.g. for ping/pong).
                await self._send_advert()
                self._last_advert = time.time()

                # Health-checked keep-alive loop.  Fixes silent dead links by
                # actively watching the library's connection flag.  Also re-adverts
                # on a configurable interval so we stay discoverable for DMs.
                advert_interval = int(self._config.get("advert_interval_sec", 1800))
                while not self._stopping.is_set() and self._is_link_alive():
                    await asyncio.sleep(1)
                    if advert_interval > 0 and (time.time() - self._last_advert) >= advert_interval:
                        await self._send_advert()
                        self._last_advert = time.time()

                self._log("connection lost.")
            except Exception as exc:
                self._log(f"⚠️  error: {exc}")
                self._stats["errors"] += 1
            finally:
                self._connected = False
                await self._teardown_connection()

            if not self._stopping.is_set():
                self._stats["reconnects"] += 1
                self._log(f"reconnecting in {backoff}s…")
                await self._interruptible_sleep(backoff)
                backoff = min(max_backoff, backoff * 2)

    def _is_link_alive(self) -> bool:
        if not self._mc:
            return False
        try:
            return bool(self._mc.is_connected)
        except Exception:
            return False

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep that wakes early if a stop is requested."""
        end = time.time() + seconds
        while time.time() < end and not self._stopping.is_set():
            await asyncio.sleep(0.5)

    async def _connect(self):
        cfg = self._config
        conn_type = str(cfg.get("connection_type", "serial")).lower()
        auto_reconnect = bool(cfg.get("auto_reconnect", True))
        max_attempts = int(cfg.get("max_reconnect_attempts", 0))
        connect_timeout = float(cfg.get("connect_timeout_sec", 20))

        try:
            if conn_type == "tcp":
                host = cfg.get("tcp_host", "192.168.1.100")
                port = int(cfg.get("tcp_port", 5000))
                self._log(f"connecting via TCP {host}:{port}…")
                coro = MeshCore.create_tcp(
                    host, port,
                    auto_reconnect=auto_reconnect,
                    max_reconnect_attempts=(max_attempts if max_attempts > 0 else None),
                )
            elif conn_type == "ble":
                addr = cfg.get("ble_address", "") or None
                pin = cfg.get("ble_pin", "") or None
                self._log(f"connecting via BLE {addr or '(scan)'}…")
                if pin:
                    coro = MeshCore.create_ble(addr, pin=str(pin))
                else:
                    coro = MeshCore.create_ble(addr)
            else:
                serial_port = cfg.get("serial_port", "/dev/ttyUSB1")
                baud = int(cfg.get("serial_baud", 115200))
                self._log(f"connecting via serial {serial_port} @ {baud} baud…")
                coro = MeshCore.create_serial(serial_port, baud)

            # Bound the connect so a wedged transport can never hang us forever.
            return await asyncio.wait_for(coro, timeout=connect_timeout)
        except asyncio.TimeoutError:
            self._log(f"⚠️  connect timed out after {connect_timeout}s.")
            return None
        except Exception as exc:
            self._log(f"⚠️  connection error: {exc}")
            return None

    async def _send_advert(self) -> None:
        """Flood an advertisement so peers add us as a contact (enables DMs)."""
        if not self._mc:
            return
        if not self._config.get("send_adverts", True):
            return
        try:
            await self._mc.commands.send_advert(flood=True)
            self._log("sent advert (discoverable for DMs).")
        except Exception as exc:
            self._log(f"could not send advert: {exc}")

    async def _after_connect(self) -> None:
        """Pull self-info and the contact list once connected."""
        if not self._mc:
            return
        try:
            res = await self._mc.commands.send_appstart()
            if res is not None and not self._is_error(res):
                payload = getattr(res, "payload", None)
                if isinstance(payload, dict):
                    self._self_info = payload
        except Exception as exc:
            self._log(f"could not fetch self info: {exc}")
        # Device query gives firmware version + model (for the update checker).
        try:
            dq = await self._mc.commands.send_device_query()
            if dq is not None and not self._is_error(dq):
                p = getattr(dq, "payload", None)
                if isinstance(p, dict):
                    self._device_info = p
        except Exception as exc:
            self._log(f"could not fetch device info: {exc}")
        await self._refresh_contacts()
        await self._refresh_channels()

    async def _refresh_channels(self) -> None:
        """Read MeshCore channel configs (group chats / private channels)."""
        if not self._mc:
            return
        max_ch = int(self._config.get("max_channels", 8))
        found = {}
        for idx in range(max_ch):
            try:
                res = await self._mc.commands.get_channel(idx)
            except Exception:
                continue
            if res is None or self._is_error(res):
                continue
            payload = getattr(res, "payload", None)
            if isinstance(payload, dict):
                name = (payload.get("channel_name") or payload.get("name") or "").strip()
                # A channel with a secret/name configured is active; channel 0 is
                # always the public channel.
                has_secret = bool(payload.get("channel_secret") or payload.get("secret"))
                if idx == 0 or name or has_secret:
                    found[idx] = {"name": name, "index": idx}
        if found:
            with self._channels_lock:
                self._channels = found

    async def _refresh_contacts(self) -> None:
        if not self._mc:
            return
        try:
            res = await self._mc.commands.get_contacts()
            if res is not None and not self._is_error(res):
                payload = getattr(res, "payload", None)
                if isinstance(payload, dict):
                    with self._contacts_lock:
                        self._contacts = payload
        except Exception as exc:
            self._log(f"could not refresh contacts: {exc}")

    async def _subscribe_events(self) -> None:
        if not self._mc or EventType is None:
            return
        self._mc.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_message)
        self._mc.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_message)
        self._mc.subscribe(EventType.CONNECTED, self._on_connected)
        self._mc.subscribe(EventType.DISCONNECTED, self._on_disconnected)
        # Keep the contact cache fresh as the mesh advertises new nodes.
        for evt_name in ("NEW_CONTACT", "ADVERTISEMENT"):
            evt = getattr(EventType, evt_name, None)
            if evt is not None:
                self._mc.subscribe(evt, self._on_contact_change)

    async def _teardown_connection(self) -> None:
        if not self._mc:
            return
        try:
            await self._mc.stop_auto_message_fetching()
        except Exception:
            pass
        try:
            await self._mc.disconnect()
        except Exception:
            pass
        self._mc = None

    async def _shutdown(self) -> None:
        await self._teardown_connection()

    # ── Inbound event handlers ───────────────────────────────────────

    async def _on_contact_message(self, event: Any) -> None:
        try:
            data = event.payload or {}
            text = data.get("text", "")
            prefix = (data.get("pubkey_prefix") or "").strip()[:12]
            name = self._resolve_name(prefix)
            sender_id = self._sender_id(prefix, name)
            self._stats["rx"] += 1
            self._last_rx_ts = time.time()
            self._log(f"[DM] {name}: {text}")
            self._dispatch_inbound(
                sender_id=sender_id,
                sender_name=name,
                text=text,
                is_direct=True,
                channel_idx=None,
                reply_target={"kind": "dm", "key": prefix},
            )
        except Exception as exc:
            self._log(f"⚠️  error handling DM: {exc}")
            self._stats["errors"] += 1

    async def _on_channel_message(self, event: Any) -> None:
        try:
            data = event.payload or {}
            raw_text = data.get("text", "")
            channel = int(data.get("channel_idx", 0))
            prefix = (data.get("pubkey_prefix") or "").strip()[:12]
            # MeshCore channel broadcasts are shared-key with no per-sender
            # crypto identity, so the firmware embeds the sender name *inside*
            # the text as "SenderName: actual message". Parse it out so the
            # real message (e.g. a "/ai" command) is seen by the command/AI
            # router, and so the sender shows correctly instead of "unknown".
            name, text = self._split_channel_sender(raw_text, prefix)
            # Channel messages usually carry NO pubkey_prefix, so derive a
            # stable sender id from the parsed name (otherwise every channel
            # sender collides on "!mc-unknown").
            sender_id = self._sender_id(prefix, name)
            self._stats["rx"] += 1
            self._last_rx_ts = time.time()
            self._log(f"[ch{channel}] {name}: {text}")
            self._dispatch_inbound(
                sender_id=sender_id,
                sender_name=name,
                text=text,
                is_direct=False,
                channel_idx=channel,
                reply_target={"kind": "channel", "channel": channel},
            )
        except Exception as exc:
            self._log(f"⚠️  error handling channel msg: {exc}")
            self._stats["errors"] += 1

    def _split_channel_sender(self, raw_text: str, prefix: str):
        """Split a MeshCore channel message of the form "Name: message".

        Returns (sender_name, message). Falls back to a contact-resolved name
        (or MC_<prefix>) and the raw text when no embedded name is present.
        """
        fallback = self._resolve_name(prefix)
        if not raw_text:
            return fallback, raw_text
        # Only treat a leading "Name: " as a sender tag when the name part is
        # short, has no leading slash (so we never eat a real "/cmd"), and the
        # separator is an early ": ".
        sep = raw_text.find(": ")
        if 0 < sep <= 32:
            candidate = raw_text[:sep].strip()
            if candidate and not candidate.startswith("/") and "\n" not in candidate:
                return candidate, raw_text[sep + 2:].lstrip()
        return fallback, raw_text

    async def _on_connected(self, event: Any) -> None:
        self._connected = True

    async def _on_disconnected(self, event: Any) -> None:
        self._connected = False
        self._log("⚠️  disconnected event received.")

    async def _on_contact_change(self, event: Any) -> None:
        await self._refresh_contacts()

    def _dispatch_inbound(self, **kwargs) -> None:
        if not self._on_inbound:
            return
        try:
            self._on_inbound(
                self.NETWORK,
                kwargs["sender_id"],
                kwargs["sender_name"],
                kwargs["text"],
                kwargs["is_direct"],
                kwargs["channel_idx"],
                kwargs["reply_target"],
            )
        except Exception as exc:
            self._log(f"⚠️  inbound handler error: {exc}")
            self._stats["errors"] += 1

    # ── Outbound async helpers ───────────────────────────────────────

    def _chunks(self, text: str) -> list:
        max_len = self._max_len()
        if not text:
            return []
        if len(text) <= max_len:
            return [text]
        out, remaining = [], text
        while remaining and len(out) < int(self._config.get("max_chunks", 5)):
            if len(remaining) <= max_len:
                out.append(remaining)
                break
            cut = remaining.rfind(" ", 0, max_len)
            if cut <= max_len // 2:
                cut = max_len
            out.append(remaining[:cut].rstrip())
            remaining = remaining[cut:].lstrip()
        return out

    async def _send_channel_async(self, channel: int, text: str) -> None:
        if not self._mc:
            return
        delay = float(self._config.get("chunk_delay_sec", 2))
        for chunk in self._chunks(text):
            try:
                res = await self._mc.commands.send_chan_msg(channel, chunk)
                self._stats["tx"] += 1
                if self._is_error(res):
                    self._log(f"⚠️  send_chan_msg error: {getattr(res, 'payload', '')}")
            except Exception as exc:
                self._log(f"⚠️  error sending to ch{channel}: {exc}")
                self._stats["errors"] += 1
                break
            await asyncio.sleep(delay)

    async def _send_dm_async(self, key_prefix: str, text: str) -> None:
        if not self._mc:
            return
        contact = await self._resolve_contact(key_prefix)
        if not contact:
            self._log(f"⚠️  no contact for prefix {key_prefix}; cannot DM "
                      "(the node may not have advertised to us yet).")
            return
        delay = float(self._config.get("chunk_delay_sec", 2))
        for chunk in self._chunks(text):
            try:
                res = await self._mc.commands.send_msg(contact, chunk)
                self._stats["tx"] += 1
                if self._is_error(res):
                    self._log(f"⚠️  send_msg error: {getattr(res, 'payload', '')}")
            except Exception as exc:
                self._log(f"⚠️  error sending DM: {exc}")
                self._stats["errors"] += 1
                break
            await asyncio.sleep(delay)

    async def _resolve_contact(self, key_prefix: str):
        """Find a contact by pubkey prefix, refreshing the device contact list
        once if the first lookup misses (the node may have just advertised)."""
        try:
            contact = self._mc.get_contact_by_key_prefix(key_prefix)
        except Exception:
            contact = None
        if contact:
            return contact
        # Miss: refresh contacts from the device and try again.
        await self._refresh_contacts()
        try:
            return self._mc.get_contact_by_key_prefix(key_prefix)
        except Exception:
            return None

    # ── Small utilities ──────────────────────────────────────────────

    @staticmethod
    def _is_error(result: Any) -> bool:
        if result is None or EventType is None:
            return False
        return getattr(result, "type", None) == EventType.ERROR

    def _resolve_name(self, prefix: str) -> str:
        try:
            if prefix:
                with self._contacts_lock:
                    for key, c in self._contacts.items():
                        if not isinstance(c, dict):
                            continue
                        pub = str(c.get("public_key", key) or key)
                        if pub.startswith(prefix) or str(key).startswith(prefix):
                            return c.get("adv_name") or c.get("name") or f"MC_{prefix[:6]}"
        except Exception:
            pass
        return f"MC_{prefix[:6]}" if prefix else "MC_unknown"

    def _sender_id(self, prefix: str, name: str) -> str:
        """Build a stable node id for a MeshCore sender.

        DMs carry a real ``pubkey_prefix`` (use it). Channel broadcasts are
        shared-key with no per-sender crypto id, so we derive a stable id from
        the parsed display name instead of collapsing everyone onto
        ``!mc-unknown``. Two distinct named senders get distinct ids.
        """
        if prefix and prefix.lower() != "unknown":
            return f"!mc-{prefix[:8]}"
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", (name or "").strip()).strip("-").lower()
        if slug and not slug.startswith("mc-"):
            return f"!mc-{slug[:16]}"
        return f"!mc-{slug[:16]}" if slug else "!mc-unknown"

