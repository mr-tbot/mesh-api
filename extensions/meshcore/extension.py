"""
MeshCore extension — Bidirectional bridge between Meshtastic and MeshCore.

Connects to a MeshCore companion radio node (via USB serial or TCP) using
the ``meshcore`` Python library.  Provides:

  * **Bidirectional chat bridging** — messages flow between configurable
    Meshtastic and MeshCore channels with origin tags ([MC] / [MT]).
  * **Full command support** — MeshCore users can issue the same
    ``/slash`` commands that Meshtastic users can (AI, weather, etc.).
  * **Direct message bridging** (optional).
  * **Auto-reconnect** with configurable retry limits.

The ``meshcore`` library is async (``asyncio``).  This extension runs a
dedicated event loop in a background thread so the synchronous MESH-API
core is never blocked.

Requirements
------------
  pip install meshcore

Hardware
--------
You need a **separate** MeshCore companion-firmware device connected via
USB or reachable over TCP — independent of the Meshtastic node that
MESH-API already manages.
"""

from __future__ import annotations

import asyncio
import threading
import time
import traceback
from typing import Any

from extensions.base_extension import BaseExtension

# ---------------------------------------------------------------------------
# Attempt to import the meshcore library.  If it is not installed we still
# allow the extension to *load* (so it appears in the available list) but
# it will refuse to start and print a helpful message.
# ---------------------------------------------------------------------------
try:
    from meshcore import MeshCore, EventType  # type: ignore[import-untyped]
    MESHCORE_AVAILABLE = True
except ImportError:
    MESHCORE_AVAILABLE = False
    MeshCore = None  # type: ignore[assignment,misc]
    EventType = None  # type: ignore[assignment,misc]


class MeshCoreExtension(BaseExtension):
    """Bridge between Meshtastic and MeshCore mesh networks."""

    # ── Required properties ───────────────────────────────────────────

    @property
    def name(self) -> str:
        return "MeshCore"

    @property
    def version(self) -> str:
        return "0.1.0"

    # ── Commands ──────────────────────────────────────────────────────

    @property
    def commands(self) -> dict:
        return {
            "/meshcore": "Show MeshCore bridge status",
        }

    # ── Lifecycle ─────────────────────────────────────────────────────

    def on_load(self) -> None:
        if not MESHCORE_AVAILABLE:
            self.log(
                "⚠️  'meshcore' Python package is not installed. "
                "Install it with:  pip install meshcore"
            )
            return

        # Internal state
        self._mc = None   # MeshCore instance (or None)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._connected = False
        self._stats = {
            "mc_to_mt": 0,      # messages bridged MeshCore → Meshtastic
            "mt_to_mc": 0,      # messages bridged Meshtastic → MeshCore
            "commands": 0,      # commands processed from MeshCore users
            "errors": 0,
        }
        # Track recently bridged messages to prevent echo loops
        self._recent_bridged: list[str] = []
        self._recent_max = 50

        # Start the asyncio background thread
        self._thread = threading.Thread(
            target=self._run_event_loop,
            name="meshcore-bridge",
            daemon=True,
        )
        self._thread.start()
        self.log("MeshCore bridge thread started.")

    def on_unload(self) -> None:
        self._stopping.set()
        if self._loop and self._mc:
            # Schedule a clean disconnect on the event loop
            asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        if self._thread:
            self._thread.join(timeout=10)
        self.log("MeshCore bridge stopped.")

    # ── Meshtastic → MeshCore (on_message hook) ──────────────────────

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """Called for every inbound Meshtastic message.  Bridge to MeshCore
        if the channel mapping is configured."""
        if not self._connected or not self._mc or not self._loop:
            return

        meta = metadata or {}
        cfg = self.config

        if not cfg.get("bridge_enabled", False):
            return

        # Avoid echoing messages that we ourselves just bridged from MeshCore
        if self._is_echo(message):
            return

        is_direct = meta.get("is_direct", False)

        if is_direct:
            if not cfg.get("bridge_direct_messages", False):
                return
            # Direct message bridging — forward to MeshCore public channel 0
            tag = cfg.get("meshtastic_to_meshcore_tag", "[MT]")
            sender = meta.get("sender_info", meta.get("sender_id", "Unknown"))
            bridged = f"{tag} {sender}: {message}"
            self._send_meshcore_channel(0, bridged)
            self._stats["mt_to_mc"] += 1
            return

        ch_idx = meta.get("channel_idx")
        if ch_idx is None:
            return

        # Look up mapping: Meshtastic channel → MeshCore channel
        mt_to_mc_map = cfg.get("bridge_meshtastic_channels_to_meshcore_channel", {})
        mc_channel = mt_to_mc_map.get(str(ch_idx))
        if mc_channel is None:
            return

        mc_channel = int(mc_channel)
        tag = cfg.get("meshtastic_to_meshcore_tag", "[MT]")
        sender = meta.get("sender_info", meta.get("sender_id", "Unknown"))
        bridged = f"{tag} {sender}: {message}"

        max_len = cfg.get("max_message_length", 200)
        if len(bridged) > max_len:
            bridged = bridged[:max_len - 3] + "..."

        self._mark_as_bridged(bridged)
        self._send_meshcore_channel(mc_channel, bridged)
        self._stats["mt_to_mc"] += 1

    # ── AI / outbound response hook ──────────────────────────────────

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Called when the core generates an AI response.  If it was
        triggered from a bridged MeshCore channel we can optionally
        forward the response back."""
        # We don't need to act here because we handle command responses
        # directly inside the MeshCore listener.  This hook is reserved
        # for future use (e.g. forwarding all AI responses to MeshCore).
        pass

    # ── Emergency hook ────────────────────────────────────────────────

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        """Forward emergency alerts to all configured MeshCore channels."""
        if not self._connected or not self._mc or not self._loop:
            return
        self._send_meshcore_channel(0, f"🚨 EMERGENCY: {message}")

    # ── Command handling ──────────────────────────────────────────────

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        if command == "/meshcore":
            return self._status_text()
        return None

    # ── Flask routes ──────────────────────────────────────────────────

    def register_routes(self, app) -> None:
        @app.route("/api/meshcore/status")
        def meshcore_status():
            from flask import jsonify
            return jsonify({
                "connected": self._connected,
                "stats": self._stats,
                "config": {
                    "connection_type": self.config.get("connection_type"),
                    "bridge_enabled": self.config.get("bridge_enabled"),
                },
            })

    # ==================================================================
    #  PRIVATE — asyncio event loop & MeshCore interaction
    # ==================================================================

    def _run_event_loop(self) -> None:
        """Entry point for the background thread.  Creates an asyncio
        event loop, connects to MeshCore, and runs until ``_stopping``
        is set."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._main_loop())
        except Exception as exc:
            self.log(f"⚠️  MeshCore event loop crashed: {exc}")
            self.log(traceback.format_exc())
        finally:
            self._loop.close()
            self._loop = None

    async def _main_loop(self) -> None:
        """Connect (with retries) and listen for MeshCore events."""
        cfg = self.config
        reconnect_interval = cfg.get("reconnect_interval_sec", 30)

        while not self._stopping.is_set():
            try:
                self._mc = await self._connect()
                if self._mc is None:
                    self.log("MeshCore connection failed. Retrying…")
                    await asyncio.sleep(reconnect_interval)
                    continue

                self._connected = True
                self.log("✅ Connected to MeshCore companion node.")

                # Subscribe to incoming messages
                await self._subscribe_events()

                # Start auto-fetching so the library polls for messages
                await self._mc.start_auto_message_fetching()

                # Keep alive until disconnected or stop requested
                while not self._stopping.is_set() and self._mc.is_connected:
                    await asyncio.sleep(1)

                self.log("MeshCore connection lost.")
            except Exception as exc:
                self.log(f"⚠️  MeshCore error: {exc}")
                self._stats["errors"] += 1
            finally:
                self._connected = False
                if self._mc:
                    try:
                        await self._mc.stop_auto_message_fetching()
                    except Exception:
                        pass
                    try:
                        await self._mc.disconnect()
                    except Exception:
                        pass
                    self._mc = None

            if not self._stopping.is_set():
                self.log(
                    f"Reconnecting to MeshCore in {reconnect_interval}s…"
                )
                await asyncio.sleep(reconnect_interval)

    async def _connect(self):
        """Create a MeshCore connection based on config."""
        cfg = self.config
        conn_type = cfg.get("connection_type", "serial").lower()
        auto_reconnect = cfg.get("auto_reconnect", True)
        max_attempts = cfg.get("max_reconnect_attempts", 0)

        try:
            if conn_type == "tcp":
                host = cfg.get("tcp_host", "192.168.1.100")
                port = int(cfg.get("tcp_port", 5000))
                self.log(f"Connecting to MeshCore via TCP {host}:{port}…")
                mc = await MeshCore.create_tcp(
                    host, port,
                    auto_reconnect=auto_reconnect,
                    max_reconnect_attempts=max_attempts if max_attempts > 0 else None,
                )
            else:
                serial_port = cfg.get("serial_port", "/dev/ttyUSB1")
                baud = int(cfg.get("serial_baud", 115200))
                self.log(
                    f"Connecting to MeshCore via serial {serial_port} "
                    f"@ {baud} baud…"
                )
                mc = await MeshCore.create_serial(serial_port, baud)
            return mc
        except Exception as exc:
            self.log(f"⚠️  MeshCore connection error: {exc}")
            return None

    async def _subscribe_events(self) -> None:
        """Register callbacks for incoming MeshCore messages."""
        if not self._mc:
            return

        # Direct (contact) messages
        self._mc.subscribe(
            EventType.CONTACT_MSG_RECV,
            self._on_meshcore_contact_message,
        )
        # Channel messages
        self._mc.subscribe(
            EventType.CHANNEL_MSG_RECV,
            self._on_meshcore_channel_message,
        )
        # Connection events for logging
        self._mc.subscribe(EventType.CONNECTED, self._on_mc_connected)
        self._mc.subscribe(EventType.DISCONNECTED, self._on_mc_disconnected)

    # ── MeshCore event handlers (async callbacks) ─────────────────────

    async def _on_meshcore_contact_message(self, event: Any) -> None:
        """Handle a direct message received from a MeshCore contact."""
        try:
            data = event.payload
            text = data.get("text", "")
            sender_prefix = data.get("pubkey_prefix", "unknown")[:8]
            sender_name = self._resolve_sender_name(sender_prefix)

            self.log(f"[MC DM] {sender_name}: {text}")

            # Process commands from MeshCore users
            if self._should_process_command(text):
                response = self._process_command(text, sender_name, sender_prefix)
                if response:
                    await self._reply_to_contact(sender_prefix, response)
                return

            # If AI commands enabled and this is a direct message, try AI
            if self.config.get("ai_commands_enabled", True):
                get_ai = self.app_context.get("get_ai_response")
                if get_ai:
                    ai_resp = get_ai(text)
                    if ai_resp:
                        ai_prefix_fn = self.app_context.get("add_ai_prefix")
                        if ai_prefix_fn:
                            ai_resp = ai_prefix_fn(ai_resp)
                        await self._reply_to_contact(sender_prefix, ai_resp)
                        return

            # Bridge direct messages to Meshtastic if configured
            if self.config.get("bridge_enabled") and self.config.get(
                "bridge_direct_messages", False
            ):
                tag = self.config.get("meshcore_to_meshtastic_tag", "[MC]")
                bridged = f"{tag} {sender_name}: {text}"
                self._mark_as_bridged(bridged)
                self._bridge_to_meshtastic(bridged, channel_index=None, is_direct=False)
                self._stats["mc_to_mt"] += 1

        except Exception as exc:
            self.log(f"⚠️  Error handling MeshCore DM: {exc}")
            self._stats["errors"] += 1

    async def _on_meshcore_channel_message(self, event: Any) -> None:
        """Handle a channel message received from MeshCore."""
        try:
            data = event.payload
            text = data.get("text", "")
            mc_channel = data.get("channel_idx", 0)
            sender_prefix = data.get("pubkey_prefix", "unknown")[:8]
            sender_name = self._resolve_sender_name(sender_prefix)

            self.log(f"[MC ch{mc_channel}] {sender_name}: {text}")

            # Avoid echoing our own bridged messages
            if self._is_echo(text):
                return

            # Process commands from MeshCore users on channels
            if self._should_process_command(text):
                response = self._process_command(text, sender_name, sender_prefix)
                if response:
                    await self._send_meshcore_channel_async(mc_channel, response)
                self._stats["commands"] += 1
                return

            # Bridge to Meshtastic
            if not self.config.get("bridge_enabled", False):
                return

            mc_to_mt_map = self.config.get(
                "bridge_meshcore_channel_to_meshtastic_channel", {}
            )
            mt_channel = mc_to_mt_map.get(str(mc_channel))
            if mt_channel is None:
                return

            mt_channel = int(mt_channel)
            tag = self.config.get("meshcore_to_meshtastic_tag", "[MC]")
            bridged = f"{tag} {sender_name}: {text}"

            max_len = self.config.get("max_message_length", 200)
            if len(bridged) > max_len:
                bridged = bridged[:max_len - 3] + "..."

            self._mark_as_bridged(bridged)
            self._bridge_to_meshtastic(bridged, channel_index=mt_channel)
            self._stats["mc_to_mt"] += 1

        except Exception as exc:
            self.log(f"⚠️  Error handling MeshCore channel msg: {exc}")
            self._stats["errors"] += 1

    async def _on_mc_connected(self, event: Any) -> None:
        self._connected = True
        payload = event.payload if hasattr(event, "payload") else {}
        reconnected = payload.get("reconnected", False) if isinstance(payload, dict) else False
        if reconnected:
            self.log("✅ MeshCore reconnected.")

    async def _on_mc_disconnected(self, event: Any) -> None:
        self._connected = False
        self.log("⚠️  MeshCore disconnected.")

    # ── Command processing ────────────────────────────────────────────

    def _should_process_command(self, text: str) -> bool:
        """Check if a message is a slash command."""
        if not self.config.get("commands_enabled", True):
            return False
        prefix = self.config.get("command_prefix", "/")
        return text.strip().startswith(prefix)

    def _process_command(
        self, text: str, sender_name: str, sender_prefix: str
    ) -> str | None:
        """Route a MeshCore command through the MESH-API command system."""
        text = text.strip()
        cmd = text.split()[0].lower()

        # Use the core handle_command exposed via app_context
        handle_cmd_fn = self.app_context.get("handle_command")
        if handle_cmd_fn:
            try:
                # Build a pseudo sender_id for MeshCore users
                mc_sender_id = f"!mc-{sender_prefix}"
                response = handle_cmd_fn(cmd, text, mc_sender_id)
                if response:
                    self._stats["commands"] += 1
                    return response
            except Exception as exc:
                self.log(f"⚠️  Error processing command '{cmd}': {exc}")
                self._stats["errors"] += 1

        return None

    # ── Sending helpers ───────────────────────────────────────────────

    def _send_meshcore_channel(self, channel: int, text: str) -> None:
        """Send a message to a MeshCore channel (thread-safe, sync)."""
        if not self._mc or not self._loop or not self._connected:
            return
        asyncio.run_coroutine_threadsafe(
            self._send_meshcore_channel_async(channel, text),
            self._loop,
        )

    async def _send_meshcore_channel_async(self, channel: int, text: str) -> None:
        """Send a message to a MeshCore channel."""
        if not self._mc:
            return
        try:
            max_len = self.config.get("max_message_length", 200)
            if len(text) > max_len:
                text = text[:max_len - 3] + "..."
            result = await self._mc.commands.send_chan_msg(channel, text)
            if EventType and hasattr(result, "type") and result.type == EventType.ERROR:
                self.log(f"⚠️  MeshCore send_chan_msg error: {result.payload}")
        except Exception as exc:
            self.log(f"⚠️  Error sending to MeshCore ch{channel}: {exc}")
            self._stats["errors"] += 1

    async def _reply_to_contact(self, pubkey_prefix: str, text: str) -> None:
        """Reply to a MeshCore contact by their public key prefix."""
        if not self._mc:
            return
        try:
            contact = self._mc.get_contact_by_key_prefix(pubkey_prefix)
            if contact:
                max_len = self.config.get("max_message_length", 200)
                if len(text) > max_len:
                    text = text[:max_len - 3] + "..."
                result = await self._mc.commands.send_msg(contact, text)
                if EventType and hasattr(result, "type") and result.type == EventType.ERROR:
                    self.log(f"⚠️  MeshCore send_msg error: {result.payload}")
            else:
                self.log(
                    f"⚠️  Cannot find MeshCore contact for prefix {pubkey_prefix}"
                )
        except Exception as exc:
            self.log(f"⚠️  Error replying to MeshCore contact: {exc}")
            self._stats["errors"] += 1

    def _bridge_to_meshtastic(
        self,
        text: str,
        channel_index: int | None = None,
        is_direct: bool = False,
        destination_id: str | None = None,
    ) -> None:
        """Forward a message to the Meshtastic network via app_context."""
        iface = self.app_context.get("interface")
        if iface is None:
            self.log("Cannot bridge to Meshtastic: interface is None.")
            return

        if destination_id:
            send_fn = self.app_context.get("send_direct_chunks")
            if send_fn:
                send_fn(iface, text, destination_id)
        else:
            send_fn = self.app_context.get("send_broadcast_chunks")
            if send_fn and channel_index is not None:
                send_fn(iface, text, channel_index)

    # ── Echo / loop prevention ────────────────────────────────────────

    def _mark_as_bridged(self, text: str) -> None:
        """Remember a message we bridged to prevent echoing it back."""
        self._recent_bridged.append(text)
        if len(self._recent_bridged) > self._recent_max:
            self._recent_bridged.pop(0)

    def _is_echo(self, text: str) -> bool:
        """Check if a message is one we recently bridged."""
        mc_tag = self.config.get("meshcore_to_meshtastic_tag", "[MC]")
        mt_tag = self.config.get("meshtastic_to_meshcore_tag", "[MT]")

        # Messages that carry our bridge tags were originated by us
        if text.startswith(mc_tag) or text.startswith(mt_tag):
            return True

        # Check the recent bridged list for exact matches
        if text in self._recent_bridged:
            return True

        # Also check AI prefix tag
        ai_tag = self.app_context.get("AI_PREFIX_TAG", "")
        if ai_tag and text.startswith(ai_tag):
            # AI responses generated by our own command processing
            # are handled directly; don't re-bridge them
            return True

        return False

    # ── Contact name resolution ───────────────────────────────────────

    def _resolve_sender_name(self, pubkey_prefix: str) -> str:
        """Try to resolve a MeshCore pubkey prefix to a human name."""
        if self._mc:
            try:
                contact = self._mc.get_contact_by_key_prefix(pubkey_prefix)
                if contact and contact.get("adv_name"):
                    return contact["adv_name"]
            except Exception:
                pass
        return pubkey_prefix

    # ── Status ────────────────────────────────────────────────────────

    def _status_text(self) -> str:
        """Human-readable status for the /meshcore command."""
        lines = [f"MeshCore Bridge v{self.version}"]
        lines.append(f"Connected: {'Yes' if self._connected else 'No'}")
        cfg = self.config
        lines.append(f"Connection: {cfg.get('connection_type', 'serial')}")
        lines.append(f"Bridge: {'ON' if cfg.get('bridge_enabled') else 'OFF'}")
        lines.append(
            f"Stats: MC→MT={self._stats['mc_to_mt']} "
            f"MT→MC={self._stats['mt_to_mc']} "
            f"Cmds={self._stats['commands']} "
            f"Errs={self._stats['errors']}"
        )
        return "\n".join(lines)

    # ── Clean shutdown ────────────────────────────────────────────────

    async def _shutdown(self) -> None:
        """Gracefully disconnect from MeshCore."""
        if self._mc:
            try:
                await self._mc.stop_auto_message_fetching()
            except Exception:
                pass
            try:
                await self._mc.disconnect()
            except Exception:
                pass
            self._mc = None
        self._connected = False
