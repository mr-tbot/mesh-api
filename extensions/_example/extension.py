"""
_example extension — Developer template for MESH-API extensions.

This file is heavily commented to serve as a walkthrough for anyone
building a new extension.  Copy this entire ``_example/`` folder,
rename it, and start customising.

IMPORTANT: Folders prefixed with ``_`` are ignored by the extension
loader, so this template will never be loaded into a running system.
Remove the underscore prefix from your copy to make it discoverable.
"""

# ── Step 1: Import the base class ────────────────────────────────────
#
# Every extension MUST subclass BaseExtension.  It provides lifecycle
# hooks, config loading, mesh helpers, and logging out of the box.

from extensions.base_extension import BaseExtension


# ── Step 2: Define your extension class ──────────────────────────────
#
# The class name can be anything, but by convention use
# ``<Name>Extension``.  The loader will find it automatically as long
# as it inherits from BaseExtension.

class ExampleExtension(BaseExtension):
    """A minimal example extension that demonstrates all available hooks."""

    # ── Step 3: Required properties ──────────────────────────────────
    #
    # ``name`` and ``version`` are abstract — you MUST provide them.

    @property
    def name(self) -> str:
        # Human-readable name shown in /extensions and logs.
        return "Example"

    @property
    def version(self) -> str:
        # Semantic version string.
        return "1.0.0"

    # ── Step 4: Register slash commands (optional) ───────────────────
    #
    # Return a dict mapping command strings to short descriptions.
    # The loader registers these before built-in commands, so pick
    # unique names to avoid collisions.

    @property
    def commands(self) -> dict:
        return {
            "/example": "Run the example extension command",
        }

    # ── Step 5: Lifecycle hooks ──────────────────────────────────────

    def on_load(self) -> None:
        """Called once when the extension is loaded.

        Use this for one-time setup like opening connections or
        starting background threads.
        """
        self.log("Example extension loaded!")
        self.log(f"Config greeting: {self.config.get('greeting', 'N/A')}")

    def on_unload(self) -> None:
        """Called when the extension is being unloaded.

        Clean up resources here: stop threads, close connections, etc.
        """
        self.log("Example extension unloaded.")

    # ── Step 6: Handle your registered commands ──────────────────────

    def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
        """Dispatch incoming commands.

        Parameters
        ----------
        command : str
            The command string (e.g. ``"/example"``).
        args : str
            Everything after the command on the message line.
        node_info : dict
            ``{"node_id": "!abcd1234", "shortname": "ABC", ...}``

        Returns
        -------
        str or None
            Text to send back on the mesh, or ``None`` if not handled.
        """
        if command == "/example":
            greeting = self.config.get("greeting", "Hello!")
            sender = node_info.get("shortname", "Unknown")
            return f"{greeting} Nice to meet you, {sender}!"
        return None

    # ── Step 7: Outbound hook — mesh → external (optional) ───────────

    def send_message(self, message: str, metadata: dict | None = None) -> None:
        """Called when the core wants to push a message to external services.

        For example, this is how the Discord extension forwards mesh
        messages to a Discord webhook.  In this example, we just log it.
        """
        self.log(f"[outbound] {message}")

    # ── Step 8: Observe hook — see all inbound messages (optional) ───

    def on_message(self, message: str, metadata: dict | None = None) -> None:
        """Called for every inbound mesh message (read-only).

        Use for analytics, logging, or triggering side-effects.  Do NOT
        return a response from here — use ``handle_command`` instead.
        """
        pass  # no-op in the example

    # ── Step 9: Emergency hook (optional) ────────────────────────────

    def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
        """Called when an emergency is triggered on the mesh.

        Override to forward alerts to your service (e.g. Slack, email).
        """
        self.log(f"[EMERGENCY] {message}")

    # ── Step 10: Flask routes (optional) ─────────────────────────────

    def register_routes(self, app) -> None:
        """Register HTTP endpoints on the Flask app.

        Use this for inbound webhooks from external services.  Example:

            @app.route("/example_webhook", methods=["POST"])
            def example_webhook():
                ...

        Be careful to use unique route paths to avoid conflicts.
        """
        pass
