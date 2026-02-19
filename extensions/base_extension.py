"""
BaseExtension — Abstract base class for all MESH-API extensions.

Every extension must subclass BaseExtension and live in its own subfolder
under the extensions/ directory.  The loader will auto-discover subclasses
and manage their lifecycle.
"""

from abc import ABC, abstractmethod
import json
import os
import traceback


class BaseExtension(ABC):
    """Base class that every MESH-API extension must inherit from.

    An extension is a self-contained plugin package.  Its code and config
    live together in a subfolder under ``extensions/``.  Dropping a folder
    in enables it; deleting the folder removes it.

    Lifecycle
    ---------
    1. The loader instantiates the class, passing the extension directory
       path and a shared ``app_context`` dict that exposes core helpers.
    2. ``on_load()`` is called once at startup (or on hot-reload).
    3. ``on_unload()`` is called on shutdown or before a hot-reload.

    All hook methods (``send_message``, ``receive_message``,
    ``handle_command``, ``on_emergency``, ``on_message``) have safe
    default implementations so extensions only need to override what
    they actually use.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, extension_dir: str, app_context: dict):
        """
        Parameters
        ----------
        extension_dir : str
            Absolute path to this extension's subfolder.
        app_context : dict
            Shared context dict exposing core helpers such as
            ``send_broadcast_chunks``, ``send_direct_chunks``,
            ``add_script_log``, ``interface``, ``flask_app``, etc.
        """
        self.extension_dir = extension_dir
        self.app_context = app_context
        self._config = self._load_config()

    # ------------------------------------------------------------------
    # Required properties — subclasses MUST define these
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the extension (e.g. ``'Discord'``)."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """SemVer version string (e.g. ``'1.0.0'``)."""
        ...

    # ------------------------------------------------------------------
    # Built-in properties
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether the extension is enabled.  Reads ``"enabled"`` from
        the extension's own ``config.json``.  Defaults to ``False``."""
        return bool(self._config.get("enabled", False))

    @property
    def commands(self) -> dict:
        """Return a dict of slash commands this extension registers.

        Format: ``{"/command": "Short description"}``

        The default implementation returns an empty dict.  Override in
        your subclass to register commands.
        """
        return {}

    @property
    def config(self) -> dict:
        """Read-only access to the extension's loaded config."""
        return self._config

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_load(self) -> None:
        """Called once when the extension is loaded at startup.

        Use this for one-time setup: starting background threads,
        opening connections, registering Flask routes, etc.
        """
        pass

    def on_unload(self) -> None:
        """Called when the extension is being unloaded (shutdown or
        hot-reload).

        Use this to clean up resources: stop threads, close connections,
        flush buffers, etc.
        """
        pass

    # ------------------------------------------------------------------
    # Message hooks (override as needed)
    # ------------------------------------------------------------------

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Outbound hook: mesh → external service.

        Called by the loader when the core wants to push a message out
        to external services (e.g. forwarding a mesh message to Discord).

        Parameters
        ----------
        message : str
            The message text.
        metadata : dict, optional
            Extra context such as ``sender_id``, ``channel_idx``,
            ``is_direct``, ``is_ai_response``, etc.
        """
        pass

    def receive_message(self) -> None:
        """Inbound hook: external service → mesh.

        Called periodically if the extension does polling-based inbound.
        Most extensions will start their own background thread in
        ``on_load()`` instead and leave this as a no-op.
        """
        pass

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        """Handle a registered slash command.

        Parameters
        ----------
        command : str
            The slash command (e.g. ``"/weather"``).
        args : str
            Everything after the command on the same line.
        node_info : dict
            Info about the sender: ``node_id``, ``shortname``, etc.

        Returns
        -------
        str or None
            Response text to send back over mesh, or ``None`` to
            indicate the command was not handled.
        """
        return None

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        """Emergency broadcast hook.

        Called when an emergency alert (``/emergency`` or ``/911``) is
        triggered.  Override to forward the alert to your external
        service.

        Parameters
        ----------
        message : str
            The full emergency message text including node info.
        gps_coords : dict, optional
            ``{"lat": float, "lon": float, "time": str}`` if available.
        """
        pass

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """Observe hook — called for every inbound mesh message.

        This is a read-only hook intended for logging, analytics, or
        triggering side-effects.  It is called *before* the core decides
        whether to generate a response.

        Parameters
        ----------
        message : str
            Raw message text from the mesh.
        metadata : dict, optional
            Context: ``sender_id``, ``channel_idx``, ``is_direct``, etc.
        """
        pass

    # ------------------------------------------------------------------
    # Route registration (optional)
    # ------------------------------------------------------------------

    def register_routes(self, app) -> None:
        """Register Flask HTTP endpoints for this extension.

        Parameters
        ----------
        app : Flask
            The Flask application instance.
        """
        pass

    # ------------------------------------------------------------------
    # Convenience helpers (available to all extensions)
    # ------------------------------------------------------------------

    def send_to_mesh(self, text: str, channel_index: int | None = None,
                     destination_id: str | None = None) -> None:
        """Send a message back to the mesh network.

        Proxies to the core ``send_broadcast_chunks`` or
        ``send_direct_chunks`` functions via ``app_context``.

        Parameters
        ----------
        text : str
            Message text to send.
        channel_index : int, optional
            Channel to broadcast on (mutually exclusive with
            ``destination_id``).
        destination_id : str, optional
            Node ID for a direct message.
        """
        iface = self.app_context.get("interface")
        if iface is None:
            self.log("Cannot send to mesh: interface is None.")
            return
        if destination_id:
            send_fn = self.app_context.get("send_direct_chunks")
            if send_fn:
                send_fn(iface, text, destination_id)
        else:
            send_fn = self.app_context.get("send_broadcast_chunks")
            if send_fn:
                send_fn(iface, text, channel_index or 0)

    def log(self, message: str) -> None:
        """Write a log entry via the core logging system."""
        log_fn = self.app_context.get("add_script_log")
        if log_fn:
            log_fn(f"[ext:{self.name}] {message}")
        else:
            print(f"[ext:{self.name}] {message}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        """Load this extension's ``config.json``."""
        config_path = os.path.join(self.extension_dir, "config.json")
        if not os.path.exists(config_path):
            return {"enabled": False}
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"⚠️ Failed to load config for extension in "
                  f"{self.extension_dir}: {exc}")
            return {"enabled": False}

    def _save_config(self) -> None:
        """Persist the current config back to disk."""
        config_path = os.path.join(self.extension_dir, "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self.log(f"⚠️ Failed to save config: {exc}")

    def __repr__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"<{self.__class__.__name__} name={self.name!r} v{self.version} [{status}]>"
