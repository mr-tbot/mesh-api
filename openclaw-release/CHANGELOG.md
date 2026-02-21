# Changelog

All notable changes to `@mesh-api/openclaw-meshtastic` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-21

### Added

- **Channel registration** — Meshtastic registered as an OpenClaw messaging channel (`meshtastic`) with direct and group (broadcast) message support.
- **Agent tool** — `meshtastic_mesh` tool with actions: `list_nodes`, `get_messages`, `send_message`, `get_status`, `get_commands`.
- **Auto-reply commands** — `/mesh-status`, `/mesh-nodes`, `/mesh-send` for quick operations without LLM invocation.
- **Background polling service** — Optional `meshtastic-poll` service that periodically fetches new mesh messages from MESH-API.
- **MESH-API HTTP client** — Full client for MESH-API REST endpoints (`/nodes`, `/messages`, `/send`, `/connection_status`, `/commands_info`).
- **Plugin manifest** — `openclaw.plugin.json` with JSON Schema config validation and Control UI hints.
- **Companion skill** — `skills/mesh-api/SKILL.md` for teaching the OpenClaw agent natural-language mesh interactions.
- **Bot-loop prevention** — Filters messages prefixed with `m@i-` during polling to avoid echo loops.
- **Node ID validation** — Enforces `!XXXXXXXX` hex format before sending direct messages.
- **Chunking awareness** — Warns when messages exceed 200 characters (Meshtastic practical limit).
