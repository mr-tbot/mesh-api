"""
ExtensionLoader — Auto-discovers, loads, and manages MESH-API extensions.

Scans the ``extensions/`` directory on startup and dynamically imports any
valid ``BaseExtension`` subclass.  Each extension lives in its own subfolder
with its own ``config.json``.  Folders prefixed with ``_`` are skipped.

The loader never crashes the main process — if an extension fails to load
for *any* reason, the error is logged and execution continues.
"""

import importlib
import importlib.util
import inspect
import json
import os
import traceback

from extensions.base_extension import BaseExtension


class ExtensionLoader:
    """Discovers, loads, and manages the lifecycle of MESH-API extensions."""

    def __init__(self, extensions_path: str, app_context: dict):
        """
        Parameters
        ----------
        extensions_path : str
            Path to the ``extensions/`` directory.
        app_context : dict
            Shared context dict passed to every extension.
        """
        self.extensions_path = os.path.abspath(extensions_path)
        self.app_context = app_context
        self.loaded: dict[str, BaseExtension] = {}       # slug -> instance
        self.available: dict[str, dict] = {}             # slug -> info dict
        self.command_registry: dict[str, BaseExtension] = {}  # "/cmd" -> instance
        self._legacy_migrated = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        """Scan the extensions directory and load every valid extension."""
        if not os.path.isdir(self.extensions_path):
            self._log(f"Extensions directory not found: {self.extensions_path}")
            return

        self._migrate_legacy_config()

        for entry in sorted(os.listdir(self.extensions_path)):
            # Skip private/template folders, files, __pycache__
            if entry.startswith("_") or entry.startswith("."):
                continue
            if entry == "__pycache__":
                continue
            ext_dir = os.path.join(self.extensions_path, entry)
            if not os.path.isdir(ext_dir):
                continue

            self._load_extension(entry, ext_dir)

        # Summary
        loaded_names = [f"{e.name} v{e.version}" for e in self.loaded.values()]
        disabled_names = [info["name"] for slug, info in self.available.items()
                          if slug not in self.loaded]
        if loaded_names:
            self._log(f"Extensions loaded: {', '.join(loaded_names)}")
        if disabled_names:
            self._log(f"Extensions available but disabled: {', '.join(disabled_names)}")
        if not loaded_names and not disabled_names:
            self._log("No extensions found.")

    def unload_all(self) -> None:
        """Unload all loaded extensions, calling ``on_unload()`` on each."""
        for slug, ext in list(self.loaded.items()):
            try:
                ext.on_unload()
                self._log(f"Extension unloaded: {ext.name}")
            except Exception as exc:
                self._log(f"⚠️ Error unloading extension '{slug}': {exc}")
        self.loaded.clear()
        self.command_registry.clear()

    def reload(self) -> None:
        """Hot-reload: unloads all extensions then loads them again."""
        self._log("Reloading all extensions...")
        self.unload_all()
        self.available.clear()
        self.load_all()

    def list_extensions(self) -> str:
        """Return a human-readable summary of extension status."""
        lines = []
        if self.loaded:
            lines.append("Loaded:")
            for slug, ext in self.loaded.items():
                cmd_list = ", ".join(ext.commands.keys()) if ext.commands else "none"
                lines.append(f"  {ext.name} v{ext.version} (cmds: {cmd_list})")
        disabled = [info for slug, info in self.available.items()
                    if slug not in self.loaded]
        if disabled:
            lines.append("Disabled:")
            for info in disabled:
                lines.append(f"  {info['name']} (set enabled:true to activate)")
        if not lines:
            lines.append("No extensions installed.")
        return "\n".join(lines)

    def list_extension_commands(self) -> list[tuple[str, str]]:
        """Return ``[(command, description), ...]`` for all extension commands."""
        result = []
        for cmd, ext in self.command_registry.items():
            desc = ext.commands.get(cmd, "Extension command")
            result.append((cmd, f"[{ext.name}] {desc}"))
        return sorted(result, key=lambda x: x[0].lower())

    # ------------------------------------------------------------------
    # Command routing
    # ------------------------------------------------------------------

    def route_command(self, command: str, args: str, node_info: dict) -> str | None:
        """Route a slash command to the owning extension.

        Returns the response string, or ``None`` if no extension owns
        the command (allowing the core to fall through to built-ins).
        """
        ext = self.command_registry.get(command.lower())
        if ext is None:
            return None
        try:
            return ext.handle_command(command.lower(), args, node_info)
        except Exception as exc:
            self._log(f"⚠️ Extension '{ext.name}' error handling "
                      f"command '{command}': {exc}")
            return None

    # ------------------------------------------------------------------
    # Broadcast hooks
    # ------------------------------------------------------------------

    def broadcast_message(self, message: str, metadata: dict | None = None) -> None:
        """Call ``send_message()`` on all loaded extensions."""
        for ext in self.loaded.values():
            try:
                ext.send_message(message, metadata)
            except Exception as exc:
                self._log(f"⚠️ Extension '{ext.name}' send_message error: {exc}")

    def broadcast_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        """Call ``on_emergency()`` on all loaded extensions."""
        for ext in self.loaded.values():
            try:
                ext.on_emergency(message, gps_coords)
            except Exception as exc:
                self._log(f"⚠️ Extension '{ext.name}' on_emergency error: {exc}")

    def broadcast_on_message(self, message: str, metadata: dict | None = None) -> None:
        """Call ``on_message()`` on all loaded extensions."""
        for ext in self.loaded.values():
            try:
                ext.on_message(message, metadata)
            except Exception as exc:
                self._log(f"⚠️ Extension '{ext.name}' on_message error: {exc}")

    # ------------------------------------------------------------------
    # AI provider delegation (for Home Assistant extension)
    # ------------------------------------------------------------------

    def get_ai_provider(self, provider_name: str):
        """Return the extension instance that acts as the named AI provider,
        or ``None`` if not found.  Used by ``get_ai_response()`` in core."""
        for ext in self.loaded.values():
            if hasattr(ext, "ai_provider_name") and ext.ai_provider_name == provider_name:
                return ext
        return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_extension(self, slug: str, ext_dir: str) -> None:
        """Attempt to load a single extension from *ext_dir*."""
        ext_module_path = os.path.join(ext_dir, "extension.py")
        if not os.path.isfile(ext_module_path):
            self._log(f"⚠️ Extension '{slug}': no extension.py found, skipping.")
            return

        try:
            # Dynamically import the module
            module_name = f"extensions.{slug}.extension"
            spec = importlib.util.spec_from_file_location(module_name, ext_module_path)
            if spec is None or spec.loader is None:
                self._log(f"⚠️ Extension '{slug}': could not create module spec.")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the BaseExtension subclass
            ext_class = None
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (inspect.isclass(obj)
                        and issubclass(obj, BaseExtension)
                        and obj is not BaseExtension):
                    ext_class = obj
                    break

            if ext_class is None:
                self._log(f"⚠️ Extension '{slug}': no BaseExtension subclass found.")
                return

            # Instantiate
            instance = ext_class(ext_dir, self.app_context)

            # Record in available list regardless of enabled state
            self.available[slug] = {
                "name": instance.name,
                "version": instance.version,
                "enabled": instance.enabled,
                "commands": list(instance.commands.keys()),
            }

            if not instance.enabled:
                self._log(f"Extension '{instance.name}' is available but disabled.")
                return

            # Register commands (first-come wins on conflicts)
            for cmd, desc in instance.commands.items():
                cmd_lower = cmd.lower()
                if cmd_lower in self.command_registry:
                    existing = self.command_registry[cmd_lower]
                    self._log(f"⚠️ Command conflict: '{cmd}' already registered by "
                              f"'{existing.name}', ignoring from '{instance.name}'.")
                else:
                    self.command_registry[cmd_lower] = instance

            # Register Flask routes if extension provides them
            flask_app = self.app_context.get("flask_app")
            if flask_app:
                try:
                    instance.register_routes(flask_app)
                except Exception as exc:
                    self._log(f"⚠️ Extension '{instance.name}' route "
                              f"registration error: {exc}")

            # Call on_load
            instance.on_load()
            self.loaded[slug] = instance
            self._log(f"✅ Extension loaded: {instance.name} v{instance.version}")

        except Exception as exc:
            self._log(f"⚠️ Failed to load extension '{slug}': {exc}")
            self._log(traceback.format_exc())

    # ------------------------------------------------------------------
    # Legacy config migration
    # ------------------------------------------------------------------

    def _migrate_legacy_config(self) -> None:
        """Migrate legacy Discord / Home Assistant keys from the main
        ``config.json`` into the respective extension ``config.json``
        files.  Runs only once per startup.  Never modifies the main
        config — it just seeds the extension configs with the legacy
        values so existing setups keep working."""
        if self._legacy_migrated:
            return
        self._legacy_migrated = True

        main_config = self.app_context.get("config", {})
        if not main_config:
            return

        # --- Discord migration ---
        discord_keys = {
            "enable_discord": "enabled",
            "discord_webhook_url": "webhook_url",
            "discord_send_emergency": "send_emergency",
            "discord_send_ai": "send_ai",
            "discord_send_all": "send_all",
            "discord_receive_enabled": "receive_enabled",
            "discord_inbound_channel_index": "inbound_channel_index",
            "discord_response_channel_index": "response_channel_index",
            "discord_bot_token": "bot_token",
            "discord_channel_id": "channel_id",
        }
        self._migrate_keys(main_config, "discord", discord_keys)

        # --- Home Assistant migration ---
        ha_keys = {
            "home_assistant_enabled": "enabled",
            "home_assistant_url": "url",
            "home_assistant_token": "token",
            "home_assistant_timeout": "timeout",
            "home_assistant_channel_index": "channel_index",
            "home_assistant_enable_pin": "enable_pin",
            "home_assistant_secure_pin": "secure_pin",
        }
        self._migrate_keys(main_config, "home_assistant", ha_keys)

    def _migrate_keys(self, main_config: dict, slug: str,
                      key_map: dict[str, str]) -> None:
        """Copy legacy keys from *main_config* into the extension's
        ``config.json`` if they are present and the extension config
        still has default/empty values."""
        # Check whether any legacy keys exist in main config
        has_legacy = any(k in main_config for k in key_map)
        if not has_legacy:
            return

        ext_config_path = os.path.join(self.extensions_path, slug, "config.json")
        if not os.path.isfile(ext_config_path):
            return

        try:
            with open(ext_config_path, "r", encoding="utf-8") as f:
                ext_config = json.load(f)
        except Exception:
            return

        changed = False
        for legacy_key, ext_key in key_map.items():
            if legacy_key not in main_config:
                continue
            legacy_val = main_config[legacy_key]
            current_ext_val = ext_config.get(ext_key)
            # Only migrate if the extension's value is still the default
            # (empty string, False, None, or missing)
            if current_ext_val in (None, "", False, 0) or ext_key not in ext_config:
                ext_config[ext_key] = legacy_val
                changed = True

        if changed:
            try:
                with open(ext_config_path, "w", encoding="utf-8") as f:
                    json.dump(ext_config, f, ensure_ascii=False, indent=2)
                self._log(f"⚠️ Legacy config detected: {slug} settings migrated "
                          f"from config.json to extensions/{slug}/config.json. "
                          f"Please update your config — legacy keys will be "
                          f"removed in a future version.")
            except Exception as exc:
                self._log(f"⚠️ Could not write migrated config for {slug}: {exc}")

    def _log(self, message: str) -> None:
        """Log via core logging system or fall back to print."""
        log_fn = self.app_context.get("add_script_log")
        if log_fn:
            log_fn(f"[ExtensionLoader] {message}")
        else:
            print(f"[ExtensionLoader] {message}")
