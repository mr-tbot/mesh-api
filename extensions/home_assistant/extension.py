"""
Home Assistant extension for MESH-API.

Provides two integration modes:

1. **AI Provider mode** — when ``ai_provider`` in the main config is set
   to ``"home_assistant"``, this extension handles AI queries by sending
   them to Home Assistant's ``/api/conversation/process`` endpoint.

2. **Dedicated channel mode** — when ``enabled`` is ``true`` and a
   ``channel_index`` is set, any non-command message arriving on that
   mesh channel is routed to Home Assistant automatically.

Supports optional PIN protection: messages must include ``PIN=XXXX``
before being forwarded to HA when ``enable_pin`` is ``true``.

All configuration lives in this extension's own config.json.  Legacy
keys in the main config.json are auto-migrated on first run.
"""

import threading

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class HomeAssistantExtension(BaseExtension):
    """Home Assistant ↔ Mesh integration extension."""

    # Expose this so the loader / core can find this extension as an
    # AI provider via ``extension_loader.get_ai_provider("home_assistant")``.
    ai_provider_name = "home_assistant"

    # ------------------------------------------------------------------
    # Required properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "Home Assistant"

    @property
    def version(self) -> str:
        return "1.1.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------

    @property
    def ha_url(self) -> str:
        return self.config.get("url", "")

    @property
    def ha_token(self) -> str:
        return self.config.get("token", "")

    @property
    def ha_timeout(self) -> int:
        return int(self.config.get("timeout", 90))

    @property
    def channel_index(self):
        val = self.config.get("channel_index")
        return int(val) if val is not None else -1

    @property
    def enable_pin(self) -> bool:
        return bool(self.config.get("enable_pin", False))

    @property
    def secure_pin(self) -> str:
        return str(self.config.get("secure_pin", "1234"))

    @property
    def agent_id(self) -> str:
        """Optional HA conversation agent id (e.g. 'conversation.llama_cpp_model').
        When set, requests target this agent instead of HA's default (issue #61)."""
        return self._own_or_core("agent_id", "home_assistant_agent_id")

    @property
    def language(self) -> str:
        return self._own_or_core("language", "home_assistant_language")

    def _own_or_core(self, key: str, core_key: str) -> str:
        """This extension's value, else the core config key of the same meaning.

        The WebUI's AI-provider section writes the core ``home_assistant_*``
        keys, but this extension answers whenever it is enabled, so a value
        entered there was silently ignored (#61 follow-up)."""
        core = (self.app_context or {}).get("config") or {}
        return str(self.config.get(key) or core.get(core_key) or "").strip()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        # HA conversation_id per mesh sender, so one user's follow-up never
        # continues (or reads the history of) another user's conversation.
        self._conversation_ids = {}
        self.log(f"Home Assistant enabled. URL={'set' if self.ha_url else 'not set'}, "
                 f"Channel={self.channel_index}, PIN={'on' if self.enable_pin else 'off'}")

    def on_unload(self) -> None:
        self.log("Home Assistant extension unloaded.")

    # ------------------------------------------------------------------
    # on_message hook — dedicated channel routing
    # ------------------------------------------------------------------

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """If a message arrives on the HA-dedicated channel, intercept and
        route it to Home Assistant."""
        metadata = metadata or {}
        ch_idx = metadata.get("channel_idx")
        if ch_idx is None or ch_idx != self.channel_index:
            return
        # Only intercept non-command, non-direct messages on the HA channel
        if metadata.get("is_direct", False):
            return
        if message.strip().startswith("/"):
            return
        # A core Channel Agent assigned to this channel already routes the
        # message and replies. Answering here as well sent the request to HA
        # twice (so "toggle the light" toggled it back) and replied twice.
        get_channel_agent = self.app_context.get("get_channel_agent")
        if get_channel_agent and get_channel_agent(ch_idx):
            return
        # HA may take up to `timeout` seconds. on_message runs on the radio's
        # receive thread (for MeshCore, its asyncio loop), so answer off-thread.
        threading.Thread(target=self._answer_channel_message,
                         args=(message, metadata),
                         daemon=True, name="ha-query").start()

    def _answer_channel_message(self, message: str, metadata: dict) -> None:
        try:
            if self.enable_pin:
                if not self._pin_is_valid(message):
                    resp = "Security code missing/invalid. Format: 'PIN=XXXX your msg'"
                    self._send_reply(resp, metadata)
                    return
                message = self._strip_pin(message)

            ha_response = self._query_home_assistant(message, metadata.get("sender_id"))
            if ha_response:
                self._send_reply(ha_response, metadata)
        except Exception as exc:
            self.log(f"⚠️ HA channel message error: {exc}")

    # ------------------------------------------------------------------
    # AI Provider interface
    # ------------------------------------------------------------------

    def get_ai_response(self, prompt: str, sender_id: str | None = None) -> str | None:
        """Called by ``get_ai_response()`` in core when
        ``ai_provider == "home_assistant"``. The core passes *sender_id* when it
        knows who is asking, which keeps that sender's HA conversation going."""
        return self._query_home_assistant(prompt, sender_id)

    # ------------------------------------------------------------------
    # Home Assistant API call
    # ------------------------------------------------------------------

    def _query_home_assistant(self, user_message: str,
                              sender_id: str | None = None) -> str | None:
        """Send a conversation request to Home Assistant.

        *sender_id* keys the HA conversation, so follow-ups from the same mesh
        node stay in one conversation. Without it the request is stateless: one
        shared conversation_id leaked each user's history into the next
        user's request."""
        if not self.ha_url:
            return None
        headers = {"Content-Type": "application/json"}
        if self.ha_token:
            headers["Authorization"] = f"Bearer {self.ha_token}"
        payload = {"text": user_message}
        # issue #61: target a specific conversation agent when configured, instead
        # of always hitting HA's default agent. Field names per the HA REST
        # conversation API: agent_id, language, conversation_id.
        if self.agent_id:
            payload["agent_id"] = self.agent_id
        if self.language:
            payload["language"] = self.language
        if sender_id and sender_id in self._conversation_ids:
            payload["conversation_id"] = self._conversation_ids[sender_id]

        sanitize = self.app_context.get("sanitize_model_output")
        max_len = self.app_context.get("MAX_RESPONSE_LENGTH", 1000)

        try:
            r = requests.post(self.ha_url, json=payload, headers=headers,
                              timeout=self.ha_timeout)
            if r.status_code == 200:
                data = r.json()
                # Keep the conversation_id for multi-turn continuity.
                cid = data.get("conversation_id")
                if cid and sender_id:
                    self._conversation_ids[sender_id] = cid
                speech = data.get("response", {}).get("speech", {})
                answer = speech.get("plain", {}).get("speech")
                if answer:
                    if sanitize:
                        answer = sanitize(answer)
                    return answer[:max_len]
                return "🤖 [No response from Home Assistant]"
            else:
                self.log(f"⚠️ HA error: {r.status_code} => {r.text}")
                return None
        except Exception as exc:
            self.log(f"⚠️ HA request failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # PIN helpers
    # ------------------------------------------------------------------

    def _pin_is_valid(self, text: str) -> bool:
        pin = self.secure_pin
        if not pin:
            return False
        lower = text.lower()
        marker = lower.find("pin=")
        if marker == -1:
            return False
        idx = marker + 4  # past "pin="
        # Compare against the actual PIN length, not a hardcoded 4 chars —
        # otherwise any PIN whose length != 4 could never validate.
        candidate = lower[idx:idx + len(pin)]
        return candidate == pin.lower()

    def _strip_pin(self, text: str) -> str:
        lower = text.lower()
        idx = lower.find("pin=")
        if idx == -1:
            return text
        # Remove "pin=" + the PIN itself (length-aware, not a hardcoded 8).
        end = idx + 4 + len(self.secure_pin)
        return (text[:idx].strip() + " " + text[end:].strip()).strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_reply(self, text: str, metadata: dict) -> None:
        """Send a response back to the mesh on the appropriate channel."""
        add_ai_prefix = self.app_context.get("add_ai_prefix")
        if add_ai_prefix:
            text = add_ai_prefix(text)

        log_fn = self.app_context.get("log_message")
        ai_name = self.app_context.get("AI_NODE_NAME", "AI-Bot")
        if log_fn:
            log_fn(ai_name, text)

        ch_idx = metadata.get("channel_idx", 0)
        # Route to every active radio (Meshtastic + MeshCore) via the
        # network-agnostic web_send helper; fall back to Meshtastic-only.
        web_send = self.app_context.get("web_send")
        if web_send:
            web_send(text, "auto", "broadcast", channel_idx=int(ch_idx or 0))
            return
        iface = self.app_context.get("interface")
        if iface is None:
            self.log("Cannot reply: interface is None.")
            return
        send_fn = self.app_context.get("send_broadcast_chunks")
        if send_fn:
            send_fn(iface, text, ch_idx)
