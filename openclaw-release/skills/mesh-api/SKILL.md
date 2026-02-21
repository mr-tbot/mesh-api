---
name: mesh-api
description: Interact with a Meshtastic LoRa mesh network through MESH-API — list nodes, read messages, send texts, and check connection status.
version: 1.0.0
author: mesh-api community
metadata:
  openclaw:
    required_env:
      - MESH_API_URL
      - MESH_API_KEY
    required_bins:
      - curl
    tags:
      - meshtastic
      - mesh
      - radio
      - iot
      - lora
---

# MESH-API Skill

You can interact with a Meshtastic LoRa mesh network through a running MESH-API instance.
MESH-API exposes a REST API (default port 5000) that lets you list online nodes, read recent messages, send texts to specific nodes or broadcast to channels, and check device connectivity.

## Configuration

- `MESH_API_URL` — Base URL of the MESH-API instance (e.g. `http://192.168.1.50:5000`). **Required.**
- `MESH_API_KEY` — Optional bearer token for future authentication support. If set, include it as `Authorization: Bearer <token>` on every request. If empty or unset, omit the header entirely — MESH-API has no auth by default.

## Available Endpoints

### GET /nodes

List all mesh nodes the MESH-API instance can see.

**Request:**
```
curl -s "$MESH_API_URL/nodes"
```

**Response:** JSON array of node objects.
```json
[
  {"id": "!a1b2c3d4", "shortName": "TBot", "longName": "TBot Base Station"},
  {"id": "!e5f6a7b8", "shortName": "Hike", "longName": "Hiker Node"}
]
```

- `id` is the Meshtastic hex node ID (always starts with `!` followed by 8 hex characters).
- `shortName` is a 4-character display name.
- `longName` is the full node name.

### GET /messages

Retrieve recent messages from the mesh.

**Request:**
```
curl -s "$MESH_API_URL/messages"
```

**Response:** JSON array of message objects. Each message contains sender info, text, timestamp, and channel.

### POST /send

Send a message to a specific node (direct) or broadcast to a channel.

**Direct message to a node:**
```
curl -s -X POST "$MESH_API_URL/send" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from OpenClaw", "node_id": "!a1b2c3d4", "direct": true}'
```

**Broadcast to a channel:**
```
curl -s -X POST "$MESH_API_URL/send" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello mesh!", "channel_index": 0}'
```

**Body parameters:**
- `message` (string, required) — The text to send.
- `node_id` (string, required for direct) — Target node hex ID (e.g. `!a1b2c3d4`).
- `direct` (boolean) — Set `true` for a direct message to `node_id`.
- `channel_index` (integer) — Channel index for broadcast (default `0` = LongFast).

**Response:**
```json
{"status": "sent", "to": "!a1b2c3d4", "direct": true, "message": "Hello from OpenClaw"}
```

### POST /ui_send

Broadcast a message to a channel (form-encoded, primarily used by the web UI).

**Request:**
```
curl -s -X POST "$MESH_API_URL/ui_send" \
  -d "message=Hello+mesh!&channel_index=0"
```

**Parameters (form-encoded):**
- `message` (string, required) — The text to send.
- `channel_index` (integer) — Channel index (default `0`).
- `destination_node` (string, optional) — If provided, sends a direct message instead of broadcast.

For programmatic use, prefer `POST /send` with JSON. Use `/ui_send` only when mimicking the web UI.

### GET /connection_status

Check whether MESH-API is connected to its Meshtastic radio device.

**Request:**
```
curl -s "$MESH_API_URL/connection_status"
```

**Response:**
```json
{"status": "connected", "error": null}
```

- `status` will be `"connected"` or `"disconnected"`.
- `error` contains an error description string if disconnected, otherwise `null`.

### GET /commands_info

List all available slash commands registered on the mesh (including extension commands).

**Request:**
```
curl -s "$MESH_API_URL/commands_info"
```

**Response:** JSON array of command objects.
```json
[
  {"command": "/ping", "description": "Check if the bot is online"},
  {"command": "/ai-9z", "description": "Ask the AI a question"},
  {"command": "/nodes", "description": "List online mesh nodes"}
]
```

## Natural Language Examples

When the user says something like the phrases below, map their intent to the corresponding API call:

| User says | Action |
|-----------|--------|
| "Who is online on the mesh?" | `GET /nodes` — list all visible nodes and summarize who is online. |
| "What nodes are on the mesh network?" | `GET /nodes` |
| "Send 'hello' to TBot" | `GET /nodes` first to resolve the name "TBot" to a node ID, then `POST /send` with `{"message": "hello", "node_id": "<resolved_id>", "direct": true}`. |
| "Send a message to !a1b2c3d4" | `POST /send` with `{"message": "<user's message>", "node_id": "!a1b2c3d4", "direct": true}`. |
| "What's been said on the mesh recently?" | `GET /messages` — retrieve and summarize the recent messages. |
| "Show me mesh messages" | `GET /messages` |
| "Is the mesh connected?" | `GET /connection_status` — report whether the radio link is up. |
| "Check mesh connection" | `GET /connection_status` |
| "Broadcast 'weather alert' to the mesh" | `POST /send` with `{"message": "weather alert", "channel_index": 0}`. |
| "Broadcast on channel 2: meeting at noon" | `POST /send` with `{"message": "meeting at noon", "channel_index": 2}`. |
| "What commands does the mesh bot support?" | `GET /commands_info` — list and describe available slash commands. |

When resolving a node by name (e.g. "send to TBot"), always call `GET /nodes` first to find the matching `id`. Never guess a node ID.

## IMPORTANT CONSTRAINTS

1. **Character limit.** Meshtastic mesh messages have a strict practical limit. Keep any message you send via `POST /send` under **200 characters** unless the user explicitly requests a longer message. MESH-API will chunk longer messages automatically, but each chunk is a separate radio transmission — warn the user it will arrive as multiple packets and may take time.

2. **No unsolicited long messages.** Never send AI-generated text directly to the mesh without user confirmation if the text exceeds one chunk (200 characters). Always ask the user first: _"This response is X characters and will be sent as N packets — proceed?"_

3. **Bot-loop prevention.** Messages prefixed with `m@i- ` are AI-generated mesh messages. If you see this prefix on an inbound mesh message (via `GET /messages`), **do not** relay it back to the mesh. Doing so creates an infinite loop between AI agents on the network.

4. **Node ID format.** Meshtastic node IDs are hex strings matching the pattern `!` followed by exactly 8 hexadecimal characters (e.g. `!a1b2c3d4`). Always validate a node ID matches this format before using it in `POST /send`. If the user provides a name instead, resolve it via `GET /nodes`.

5. **Connection check.** Before sending messages, it is good practice to call `GET /connection_status` to verify the mesh radio is connected. If status is `"disconnected"`, inform the user and do not attempt to send.

6. **No auth by default.** MESH-API does not require authentication in its default configuration. The `MESH_API_KEY` env var is optional future-proofing. Only include the `Authorization` header if `MESH_API_KEY` is set and non-empty.

7. **Rate awareness.** Meshtastic is a low-bandwidth LoRa network. Do not send rapid bursts of messages. If you need to send multiple messages, space them out and inform the user about the delay.
