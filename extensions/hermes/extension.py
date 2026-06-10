"""
Hermes (Nous Research) AI provider extension for MESH-API.

Hermes used to be a built-in core AI provider; as of v0.7.2.2 it lives here as a
drop-in extension so the core stays lean and Hermes can be enabled/configured
from the WebUI Extensions manager like any other plugin.

Two integration modes (both optional):

1. **AI Provider mode** — when ``ai_provider`` in the main config is set to
   ``"hermes"`` (or a Channel Agent pins ``provider: hermes``), the core calls
   this extension via ``extension_loader.get_ai_provider("hermes")``.

2. **Channel Agent mode** — assign a channel to ``{"agent": "extension",
   "slug": "hermes"}`` and its plain-text traffic is routed here.

Configuration lives in this extension's own ``config.json``.  For backward
compatibility, if no ``api_key`` is set here but legacy ``hermes_*`` keys exist
in the main ``config.json``, they are imported automatically on load.
"""

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class HermesExtension(BaseExtension):
    """Nous Research Hermes models via their OpenAI-compatible inference API."""

    # Lets the core find this extension as an AI provider via
    # ``extension_loader.get_ai_provider("hermes")``.
    ai_provider_name = "hermes"

    @property
    def name(self) -> str:
        return "Hermes"

    @property
    def version(self) -> str:
        return "1.0.0"

    # ------------------------------------------------------------------
    # Config accessors
    # ------------------------------------------------------------------
    @property
    def api_key(self) -> str:
        return self.config.get("api_key", "")

    @property
    def url(self) -> str:
        return self.config.get(
            "url", "https://inference-api.nousresearch.com/v1/chat/completions")

    @property
    def model(self) -> str:
        return self.config.get("model", "Hermes-4-405B")

    @property
    def timeout(self) -> int:
        return int(self.config.get("timeout", 60))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_load(self) -> None:
        # Backward compatibility: import legacy core hermes_* keys if this
        # extension has not been configured yet.
        if not self.api_key:
            main_cfg = self.app_context.get("config", {}) or {}
            legacy_key = main_cfg.get("hermes_api_key", "")
            if legacy_key:
                self.config["api_key"] = legacy_key
                if main_cfg.get("hermes_url"):
                    self.config["url"] = main_cfg["hermes_url"]
                if main_cfg.get("hermes_model"):
                    self.config["model"] = main_cfg["hermes_model"]
                if main_cfg.get("hermes_timeout"):
                    self.config["timeout"] = main_cfg["hermes_timeout"]
                self._save_config()
                self.log("Imported legacy hermes_* keys from main config.")
        self.log(f"Hermes provider ready (model={self.model}, "
                 f"key={'set' if self.api_key else 'not set'}).")

    def on_unload(self) -> None:
        self.log("Hermes extension unloaded.")

    # ------------------------------------------------------------------
    # AI Provider hook
    # ------------------------------------------------------------------
    def get_ai_response(self, prompt: str) -> str | None:
        """Called by core ``get_ai_response()`` when the active (or pinned)
        provider is ``hermes``."""
        if requests is None:
            self.log("⚠️ 'requests' not available; cannot reach Hermes.")
            return None
        if not self.api_key:
            self.log("⚠️ No Hermes (Nous Research) API key configured.")
            return None

        system_prompt = self.app_context.get("SYSTEM_PROMPT", "")
        max_len = int(self.app_context.get("MAX_RESPONSE_LENGTH", 1000))
        sanitize = self.app_context.get("sanitize_model_output")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_len,
        }
        try:
            r = requests.post(self.url, headers=headers, json=payload,
                              timeout=self.timeout)
            if r.status_code == 200:
                jr = r.json()
                content = (
                    jr.get("choices", [{}])[0]
                      .get("message", {})
                      .get("content", "🤖 [No response]")
                )
                if sanitize:
                    content = sanitize(content)
                return content[:max_len]
            self.log(f"⚠️ Hermes error: {r.status_code} => {r.text}")
            return None
        except Exception as exc:
            self.log(f"⚠️ Hermes request failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Channel Agent hook (so a channel can route to this extension directly)
    # ------------------------------------------------------------------
    def handle_channel_message(self, text: str, node_info: dict) -> str | None:
        return self.get_ai_response(text)
