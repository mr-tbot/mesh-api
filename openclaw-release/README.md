# @mesh-api/openclaw-meshtastic

OpenClaw channel plugin for **Meshtastic** LoRa mesh networks via [MESH-API](https://github.com/mr-tbot/mesh-api).

Bridges OpenClaw to a Meshtastic mesh — send/receive messages, list nodes, relay emergency alerts, and let the AI agent interact with the mesh network autonomously.

---

## Architecture

```
┌──────────────────┐         HTTP/REST          ┌──────────────────┐
│  OpenClaw GW     │◄──────────────────────────►│   MESH-API       │
│                  │  POST /send                │                  │
│  This Plugin:    │  GET  /nodes               │  Extension:      │
│  @mesh-api/      │  GET  /messages            │  openclaw/       │
│  openclaw-       │  GET  /connection_status   │  extension.py    │
│  meshtastic      │                            │                  │
│  (TypeScript)    │  POST /api/agent/message   │  (Python)        │
│                  │  POST /api/agent/emergency │                  │
└────────┬─────────┘◄──────────────────────────►└────────┬─────────┘
         │                                               │
   Telegram, Discord,                              Meshtastic
   SMS, Voice, etc.                                LoRa Radio
```

**This plugin** (left side) runs inside the OpenClaw Gateway and talks to MESH-API over HTTP.  
**MESH-API's OpenClaw extension** (right side) runs inside MESH-API and talks back to OpenClaw.

Both sides complement each other — you can use one or both depending on your needs.

---

## Install

### Option A: Install from npm (recommended)

```bash
openclaw plugins install @mesh-api/openclaw-meshtastic
```

Restart the Gateway afterwards.

### Option B: Install from local folder (dev)

```bash
openclaw plugins install -l ./openclaw-release
cd ./openclaw-release && npm install
```

Restart the Gateway afterwards.

---

## Config

Set config under `plugins.entries.meshtastic.config`:

```jsonc
{
  "plugins": {
    "entries": {
      "meshtastic": {
        "enabled": true,
        "config": {
          "meshApiUrl": "http://192.168.1.50:5000",
          "meshApiKey": "",
          "agentName": "mesh-api",
          "defaultChannel": 0,
          "pollEnabled": false,
          "pollIntervalSeconds": 30,
          "forwardEmergency": true,
          "maxMessageLength": 200,
          "timeoutMs": 15000
        }
      }
    }
  }
}
```

### Channel config (optional)

If you want multi-account support or need the channel to appear under `channels.meshtastic`:

```jsonc
{
  "channels": {
    "meshtastic": {
      "accounts": {
        "default": {
          "meshApiUrl": "http://192.168.1.50:5000",
          "enabled": true
        }
      }
    }
  }
}
```

### Config reference

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `meshApiUrl` | string | `http://localhost:5000` | Base URL of the MESH-API instance |
| `meshApiKey` | string | `""` | Optional bearer token for MESH-API auth |
| `agentName` | string | `"mesh-api"` | Agent name for mesh-originated messages |
| `defaultChannel` | int | `0` | Default Meshtastic channel (0–7) for broadcasts |
| `pollEnabled` | bool | `false` | Enable background polling for new mesh messages |
| `pollIntervalSeconds` | int | `30` | Polling interval in seconds (5–300) |
| `forwardEmergency` | bool | `true` | Forward mesh emergency alerts to OpenClaw |
| `maxMessageLength` | int | `200` | Max chars per mesh message before chunking |
| `timeoutMs` | int | `15000` | HTTP timeout for MESH-API calls (ms) |

Environment variables `MESH_API_URL` and `MESH_API_KEY` are used as fallbacks when config values are empty.

---

## What this plugin registers

### Messaging channel: `meshtastic`

OpenClaw can send outbound messages to the mesh. Direct messages target a node ID; broadcasts go to the default channel.

### Agent tool: `meshtastic_mesh`

The AI agent can call this tool to interact with the mesh. Actions:

| Action | Parameters | Description |
|--------|-----------|-------------|
| `list_nodes` | — | List all visible nodes on the mesh |
| `get_messages` | — | Retrieve recent mesh messages |
| `send_message` | `message`, `node_id?`, `channel_index?` | Send text to the mesh |
| `get_status` | — | Check radio connection status |
| `get_commands` | — | List registered slash commands |

### Auto-reply commands

| Command | Description |
|---------|-------------|
| `/mesh-status` | Check radio connection (no LLM invocation) |
| `/mesh-nodes` | List visible mesh nodes |
| `/mesh-send <text>` | Broadcast a message to the mesh |

### Background service: `meshtastic-poll`

When `pollEnabled: true`, polls MESH-API for new mesh messages on an interval and logs them. Future versions will inject them directly into OpenClaw conversations.

---

## Companion skill

This plugin ships a MESH-API skill at `skills/mesh-api/SKILL.md`. When installed, it teaches the OpenClaw agent how to use the MESH-API REST endpoints (natural language → API call mapping, constraints, and examples).

To install the skill:
```bash
cp -r skills/mesh-api ~/.openclaw/skills/mesh-api
```

---

## MESH-API side (optional)

If you also want mesh users to query OpenClaw from the mesh radio, enable the **OpenClaw extension** inside MESH-API:

1. Edit `extensions/openclaw/config.json`:
   ```json
   { "enabled": true, "openclaw_url": "http://localhost:18789" }
   ```
2. Restart MESH-API.
3. Mesh users can now use `/claw-XY <question>` to query the OpenClaw agent.

This is independent of this plugin — you can run either or both sides.

---

## Development

```bash
cd openclaw-release
npm install
npm run build          # compile TypeScript → dist/
npm run test           # run Vitest tests
npm run dev            # watch mode
```

### Project structure

```
openclaw-release/
├── src/
│   ├── index.ts              # Plugin entrypoint (register function)
│   ├── types.ts              # OpenClaw Plugin API type definitions
│   ├── mesh-api-client.ts    # HTTP client for MESH-API REST endpoints
│   ├── channel.ts            # Meshtastic channel registration
│   ├── tool.ts               # meshtastic_mesh agent tool
│   ├── commands.ts           # Auto-reply slash commands
│   └── poll-service.ts       # Background polling service
├── skills/
│   └── mesh-api/
│       └── SKILL.md          # Agent skill document
├── tests/
│   └── mesh-api-client.test.ts
├── openclaw.plugin.json      # Plugin manifest
├── package.json
├── tsconfig.json
└── README.md
```

---

## Testing

```bash
npm test
```

Tests use Vitest and mock the MESH-API HTTP endpoints.

---

## Community listing

This plugin is designed to meet the [OpenClaw Community Plugins](https://docs.openclaw.ai/plugins/community) listing requirements:

- ✅ Published on npmjs
- ✅ Public GitHub repository with docs
- ✅ Issue tracker (GitHub Issues)
- ✅ Active maintenance

### Candidate entry

```
Meshtastic (MESH-API) — LoRa mesh network channel via MESH-API
npm: `@mesh-api/openclaw-meshtastic`
repo: `https://github.com/mr-tbot/mesh-api`
install: `openclaw plugins install @mesh-api/openclaw-meshtastic`
```

---

## License

GPL-3.0 — see [LICENSE](LICENSE).
