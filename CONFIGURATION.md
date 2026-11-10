# MESH-API Configuration Reference

Core MESH-API settings live in [config.json](config.json) and control the
connection, AI provider, messaging, and emergency-alert behavior. For the
project overview see [README.md](README.md); for per-extension settings see
[EXTENSIONS.md](EXTENSIONS.md).

> **Integration-specific settings** (Discord, Home Assistant, Slack, Telegram,
> etc.) are configured **per-extension** in `extensions/<name>/config.json`, not
> here. Manage them from the WebUI **🧩 Extensions** manager or by editing the
> files directly. See [INTEGRATIONS.md](INTEGRATIONS.md) for the common ones.

> **Tip:** You usually don't need to hand-edit `config.json`. The dashboard's
> **⚙️ Config** editor provides a friendly form for every core setting, plus a
> Raw JSON tab and the re-runnable **🧙 Setup Wizard**. See the
> [Web UI section of the README](README.md#web-ui--dashboard).

---

## Default `config.json`

```json
{
  "debug": false,                          // Enable verbose debug logging
  "use_mesh_interface": false,             // Set true to use the Meshtastic mesh interface
  "use_wifi": false,                       // Set true to connect to your node via WiFi instead of serial
  "wifi_host": "MESHTASTIC NODE IP HERE",  // IP address of your Meshtastic device (WiFi mode)
  "wifi_port": 4403,                       // TCP port for WiFi connection (default 4403)

  "use_bluetooth": false,                   // Set true to connect to your node via Bluetooth Low Energy (BLE)
  "ble_address": "",                        // BLE MAC address or UUID of your node (leave empty for auto-scan)

  "extensions_path": "./extensions",       // Path to the extensions directory

  "ai_respond_on_longfast": false,         // Do NOT auto-respond on LongFast (channel 0) — enable only with mesh/community consent
  "respond_to_mqtt_messages": false,       // If true, the bot responds to messages that arrived via MQTT (off by default to prevent multi-replies)

  "nodes_online_window_sec": 7200,         // Time window (seconds) for /nodes-XY online count

  "serial_port": "/dev/ttyUSB0",           // Serial port if using USB (e.g., /dev/ttyUSB0 on Linux, COMx on Windows)
  "serial_baud": 460800,                   // Baud rate for serial connections (lower for long USB runs)

  "ai_command": "",                        // Randomized per-install AI command suffix (e.g., "/ai-9z") — generated on first run to prevent collisions
  "ai_provider": "lmstudio, openai, ollama, claude, gemini, grok, openrouter, groq, deepseek, mistral, or openai_compatible",
  "system_prompt": "You are a helpful assistant responding to mesh network chats. Respond in as few words as possible while still answering fully.",

  // --- LM Studio ---
  "lmstudio_url": "http://localhost:1234/v1/chat/completions",
  "lmstudio_chat_model": "MODEL IDENTIFIER HERE",
  "lmstudio_embedding_model": "TEXT EMBEDDING MODEL IDENTIFIER HERE",
  "lmstudio_timeout": 60,

  // --- OpenAI ---
  "openai_api_key": "",
  "openai_model": "gpt-4.1-mini",
  "openai_timeout": 60,

  // --- Ollama ---
  "ollama_url": "http://localhost:11434/api/generate",
  "ollama_model": "llama3",
  "ollama_timeout": 60,
  "ollama_max_parallel": 1,               // Max concurrent Ollama requests (useful on low-power hardware)
  "ollama_options": {},                    // Optional generation overrides (e.g., {"num_ctx": 2048, "temperature": 0.2})
  "ollama_keep_alive": "10m",             // Keep model loaded for this duration; "0" to unload immediately

  // --- Claude ---
  "claude_api_key": "",
  "claude_model": "claude-sonnet-4-20250514",
  "claude_timeout": 60,

  // --- Gemini ---
  "gemini_api_key": "",
  "gemini_model": "gemini-2.0-flash",
  "gemini_timeout": 60,

  // --- Grok ---
  "grok_api_key": "",
  "grok_model": "grok-3",
  "grok_timeout": 60,

  // --- OpenRouter ---
  "openrouter_api_key": "",
  "openrouter_model": "openai/gpt-4.1-mini",
  "openrouter_timeout": 60,

  // --- Groq ---
  "groq_api_key": "",
  "groq_model": "llama-3.3-70b-versatile",
  "groq_timeout": 60,

  // --- DeepSeek ---
  "deepseek_api_key": "",
  "deepseek_model": "deepseek-chat",
  "deepseek_timeout": 60,

  // --- Mistral ---
  "mistral_api_key": "",
  "mistral_model": "mistral-small-latest",
  "mistral_timeout": 60,

  // --- OpenAI-Compatible (any provider with an OpenAI-compatible API) ---
  "openai_compatible_api_key": "",
  "openai_compatible_url": "",
  "openai_compatible_model": "",
  "openai_compatible_timeout": 60,

  // --- Channel names ---
  "channel_names": {
    "0": "LongFast",
    "1": "Channel 1",
    "2": "Channel 2",
    "3": "Channel 3",
    "4": "Channel 4",
    "5": "Channel 5",
    "6": "Channel 6",
    "7": "Channel 7",
    "8": "Channel 8",
    "9": "Channel 9"
  },

  "reply_in_channels": true,              // Allow AI to reply in broadcast channels
  "reply_in_directs": true,               // Allow AI to reply in direct messages

  "chunk_size": 200,                      // Maximum size for message chunks (bytes)
  "max_ai_chunks": 5,                     // Maximum number of chunks per AI response
  "chunk_delay": 10,                      // Delay (seconds) between chunks to reduce congestion

  "local_location_string": "@ YOUR LOCATION HERE",  // Location label for your node
  "ai_node_name": "Mesh-API-Alpha",       // Display name for your AI node

  "force_node_num": null,                 // Override the node number (null = auto-detect)
  "max_message_log": 0,                   // Max messages to log (0 = unlimited)

  // --- Emergency Alerts: Twilio SMS ---
  "enable_twilio": false,
  "enable_smtp": false,
  "alert_phone_number": "+15555555555",
  "twilio_sid": "TWILIO_SID",
  "twilio_auth_token": "TWILIO_AUTH_TOKEN",
  "twilio_from_number": "+14444444444",
  "twilio_inbound_target": "channel",      // "channel" or "node" for inbound SMS routing
  "twilio_inbound_channel_index": 1,
  "twilio_inbound_node": "!FFFFFFFF",

  // --- Emergency Alerts: SMTP Email ---
  "smtp_host": "SMTP HOST HERE",
  "smtp_port": 465,                       // 465 for SSL, 587 for TLS
  "smtp_user": "SMTP USER HERE",
  "smtp_pass": "SMTP PASS HERE",
  "alert_email_to": "ALERT EMAIL HERE"
}
```

> **Note:** Discord, Home Assistant, Slack, Telegram, and all other
> integration-specific settings have been moved to the
> [Extensions System](EXTENSIONS.md). Each extension has its own `config.json`
> under `extensions/<name>/`. You can manage them via the WebUI Extensions
> Manager or by editing the files directly.

### Multi-radio blocks (v0.7.0+)

In addition to the core keys above, the v0.7.x multi-radio architecture adds
these top-level blocks (all configurable from the **⚙️ Config** editor and the
**🧙 Setup Wizard**):

- `meshtastic_enabled` — set `false` to run a **MeshCore-only / standalone** node.
- `default_send_network` — `auto` (whichever radios are connected) / `meshtastic` / `meshcore` / `both`.
- `meshcore` — the MeshCore radio (connection type `serial`/`tcp`/`ble`, port/host/address, adverts, channel bridging).
  - **BLE keys:** `ble_address` (blank = scan for a `MeshCore-*` device) and `ble_pin` (the 6-digit pairing passkey, if your node requires one). On Linux, MESH-API auto-registers a BlueZ pairing agent (via `bt-agent` from the `bluez-tools` package) that supplies `ble_pin` during pairing — install `bluez-tools` (`sudo apt install bluez-tools`) for automatic BLE pairing, and make sure the Bluetooth adapter is powered/unblocked. If the link keeps dropping right after connecting, it's usually **weak signal** — the connection banner shows the node's RSSI. Both keys are editable in the **⚙️ Config** editor and the **Setup Wizard**.
- `webui` — dashboard access control: `host` (bind address), `auth` (optional login and API token), `redact_secrets`. See **WebUI access control** below.
- `mcp` — the [MCP server](README.md#mcp-server-model-context-protocol) (disabled by default, bearer-token auth).
- `firmware` — firmware/software update-checker settings.

See the [CHANGELOG](CHANGELOG.md) entry for **v0.7.0 Beta** for details on each block.

---

## Other Important Settings

- **Logging & Archives:**
  - Script logs are stored in `script.log` and message logs in `messages.log`.
  - An archive is maintained in `messages_archive.json` to keep recent messages.

- **Device Connection:**
  - Configure the connection method for your Meshtastic device by setting either the `"serial_port"` or enabling `"use_wifi"` along with `"wifi_host"` and `"wifi_port"`.
  - For Bluetooth Low Energy (BLE) connections, set `"use_bluetooth": true` and optionally provide `"ble_address"` with the device MAC address or UUID. Leave `"ble_address"` empty for auto-scan. Requires the `bleak` Python package.
  - Alternatively, enable `"use_mesh_interface"` if applicable.
  - Connection priority: WiFi TCP > Bluetooth BLE > MeshInterface > USB Serial.
  - Baud Rate is optionally set if you need — this is for longer USB runs (roof nodes connected via USB) and bad USB connections.

- **Message Routing & Commands:**
  - Custom commands can be added in `commands_config.json` (or built visually in the **⚙️ Config** editor).
  - The WebUI Dashboard (accessible at [http://localhost:5000/dashboard](http://localhost:5000/dashboard)) displays messages and node status.

- **AI Provider Settings:**
  - Adjust `"ai_provider"` and related API settings (timeouts, models, etc.) for any of the 12 supported providers: LM Studio, OpenAI, Ollama, Claude, Gemini, Grok, OpenRouter, Groq, DeepSeek, Mistral, or any OpenAI-compatible endpoint. See [INTEGRATIONS.md](INTEGRATIONS.md#llm-api-integration).

- **Extensions:**
  - Integration-specific settings (Discord, Home Assistant, Slack, Telegram, etc.) are configured per-extension in `extensions/<name>/config.json`. Use the WebUI Extensions Manager to enable, disable, and configure extensions without editing files directly.

- **Security:**
  - If using the Home Assistant extension with PIN protection, follow the specified format (`PIN=XXXX your message`) to ensure messages are accepted.
  - If you expose the WebUI beyond localhost, protect access to the dashboard since configuration files may contain secrets (API keys, tokens). Use the `webui` block (below).

### WebUI access control

The dashboard and its JSON API can read and rewrite `config.json`, send to the mesh,
restart MESH-API and (if allowed) flash firmware. By default it listens on every network
interface with **no login**, and MESH-API prints a warning at startup when that is the case.

```jsonc
"webui": {
  "host": "0.0.0.0",            // 127.0.0.1 = reachable from this machine only
  "auth": {
    "enabled": true,            // HTTP Basic login for every route
    "username": "admin",
    "password": "",             // blank = generate one on first start, save it, print it to the log
    "api_token": "",            // optional: also accept "Authorization: Bearer <token>" or "X-API-Key"
    "exempt_paths": ["/mcp", "/twilio_webhook", "/discord_webhook",
                     "/n8n/webhook", "/webhook/mesh", "/whatsapp/webhook"]
  },
  "redact_secrets": true        // mask API keys/tokens/passwords in config sent to the browser
}
```

- **Login:** your browser asks for the username and password once and remembers them for
  the session. `password` can be plain text or a Werkzeug hash, e.g.
  `python -c "from werkzeug.security import generate_password_hash as g; print(g('your-password'))"`.
- **Scripts and integrations** that call the HTTP API (for example `/send`) can use `api_token`
  instead of the password.
- **Exempt paths** skip the login because outside services call them: `/mcp` has its own bearer
  token, and the webhook paths are called by Twilio, Discord, n8n, WhatsApp and the generic
  webhook extension. If you changed an extension's webhook path, add it here. Each entry also
  covers the paths below it.
- **Secret redaction:** values of keys such as `*_api_key`, `*token`, `*_password`, `*_sid`,
  `*_pin` and `*webhook_url` are sent to the browser as `••••••••`. Saving a form with the mask
  unchanged keeps the stored value; clearing the field clears it. The **Backup** download still
  contains the real values, so keep the login on if the dashboard is reachable by others.
- Changes to the `webui` block take effect after a restart.
- **Docker:** inside a container, leave `host` at `0.0.0.0` and limit exposure with the port
  mapping instead, e.g. `"127.0.0.1:5000:5000"` in `docker-compose.yml`.

- **Testing:**
  - You can test SMS sending with your suffixed `/sms-XY` command or trigger an emergency alert to confirm that Twilio and email integrations are functioning.
