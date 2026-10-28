"""Single source of truth for the MESH-API version.

The startup banner, dashboard footer and About panel, the update checker
(firmware_updater.py), and the MCP serverInfo (mcp_server.py) all read this
constant. Bump it here, and only here, on every release.
"""

MESH_API_VERSION = "0.7.5.4"
