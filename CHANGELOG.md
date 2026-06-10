# MESH-API Changelog

All notable changes to MESH-API, newest first. For the project overview and
setup, see [README.md](README.md). For the built-in extension reference, see
[EXTENSIONS.md](EXTENSIONS.md).

---

## Release Summaries (v0.6.0 → present)

- **v0.7.3.6 Beta** — 💓 **AI endpoint heartbeat (token-free connection status).** Each **named AI endpoint** now shows a live **heartbeat** status dot in the **🔌 Manage AI Endpoints** panel (🟢 online · 🟡 reachable/auth · 🔴 offline), so you can tell at a glance whether an endpoint is still reachable. A lightweight background thread periodically pings each endpoint's OpenAI-compatible `/models` route — a cheap GET that **costs zero AI tokens** — and the UI auto-refreshes while the panel is open, with a **Check now** button per endpoint for an on-demand probe. New endpoint: `GET /api/ai_endpoints/health`. Heartbeat interval is configurable via `ai_endpoint_heartbeat_sec` (default 60s).
- **v0.7.3.2 Beta** — 🗺️ **Map filter + MeshCore nodes now appear + [MT]/[MC] labels.** The Node Map gets a **Show:** filter to display **All / ⭐ Favorites only / 🔵 Meshtastic only / 🟣 MeshCore only** nodes (choice persists), with a live count. Fixes a bug where **MeshCore nodes reporting GPS never showed on the map** — the map only read the page-load snapshot, so positions discovered afterward (common for MeshCore adverts) were ignored; the map now merges live `/nodes` GPS for **both** networks on every refresh. Map tooltips now tag every node with its network (`[MT]` for Meshtastic, `[MC]` for MeshCore).
- **v0.7.3.1 Beta** — 🔌 **Named AI endpoints + live extension toggle fix.** You can now define multiple **named AI endpoints** (each with its own **name**, **type**, and **config** — URL, API key, model, timeout) from a new **🔌 Manage AI Endpoints** panel in the **🤖 Channel Agents** modal, then assign a different endpoint to each channel. This lets you point two channels at two separate OpenAI-compatible agents without renaming a shared provider. New endpoints: `GET`/`POST /api/ai_endpoints`. Also fixes a bug where the extension **Enable/Disable** button did nothing for an already-**loaded** extension — toggling now **live-loads/unloads** the extension (no restart needed).
- **v0.7.3 Beta** — 🌉 **Cross-network channel bridge UI.** When both a Meshtastic and a MeshCore radio are connected, you can now **mirror chat between channels on the two networks** from a new **🌉 Bridge** toolbar button — no more hand-editing `config.json`. The visual editor maps **Meshtastic channel ⇄ MeshCore channel** links (the per-device channel indexes can differ), with a per-link **direction** (both / MT→MC / MC→MT), an overall **bridge on/off** toggle, and customizable **tags** (e.g. `[MT]` / `[MC]`) added to bridged messages. Changes **apply live** (no restart) and persist to the `meshcore` block of `config.json`. The Bridge button appears only when MeshCore is in play, and the editor shows live radio-connection status. New endpoints: `GET`/`POST /api/channel_bridge`. (Slash commands and AI replies are never bridged.)
- **v0.7.2.5 Beta** — 🕸️ **Mouse-reactive mesh background.** The dashboard's plain black background is replaced with a dense, animated **"mesh" grid** — a field of points connected by lines that drift continuously and **warp toward your mouse** in real time, evoking a living mesh network behind the UI. The UI boxes are now translucent so the grid shows through behind the panels (inputs and controls stay fully opaque). Fully controllable from **UI Settings → Appearance**: toggle it **on/off**, adjust the **speed**, **line thickness**, **color**, and the **box opacity** (how transparent the panels are). Renders on a single GPU-friendly canvas behind the panels.
- **v0.7.2.4 Beta** — ☁️ **MQTT node indicators + smaller traffic graph.** Nodes heard over **MQTT** (rather than direct RF) now show a teal **☁ MQTT** badge in the Available Nodes list and a distinct teal map marker (with an "☁ Heard via MQTT" note in the popup and a ☁ on the map label), so you can tell at a glance which nodes are coming in via MQTT. The Traffic Monitor graph is now **half the height** for a more compact dashboard.
- **v0.7.2.3 Beta** — 📊 **Traffic monitor upgrades.** The Traffic Monitor is now **full-width** (double-wide) and sits **above the Node Map / Send row** by default (still draggable, hideable, and reorderable like every other box). It now counts **all received packets** — position, telemetry, nodeinfo, routing, text, etc. — not just chat messages, via a dedicated all-packet radio hook. Added a **user-selectable time window** (1 min / 5 min / 15 min / 30 min / 1 hour / 6 hours), persisted per browser, with the graph re-bucketed so it stays readable at any length. `GET /api/traffic` gained `seconds` (up to 6 h) and `buckets` parameters.
- **v0.7.2.2 Beta** — 📊 **Traffic monitor + 🚨 emergency alerts + Hermes is now an extension.**
  - **Real-time traffic monitor** — a new movable **📊 Traffic Monitor** box at the top of the dashboard draws live mesh radio activity as green→red bars (RX received / TX sent, last 60 s). Like every panel it can be dragged, hidden, or reordered. Backed by a new `GET /api/traffic` endpoint.
  - **Emergency alert box** — when a node triggers `/emergency` (or `/911`), a large **flashing red box** appears in the masthead (between the logo and the toolbar, below the connection status). Click it to open a modal with the alert text and node information (name, ID, GPS/map link, reply). Alerts **must be cleared by the user** and persist until then.
  - **Hermes moved out of core** — the Nous Research **Hermes** AI provider is now a bundled **extension** (`extensions/hermes`) instead of core code, keeping the core lean. It registers itself as the `hermes` AI provider automatically, so `ai_provider: "hermes"` and Channel-Agent `provider: hermes` keep working; configure it from the **🧩 Extensions** manager. Legacy `hermes_*` keys in the main config are imported automatically on first load.
- **v0.7.2.1 Beta** — 🧩 **All v0.7.x settings are now in the WebUI config form**, plus a channel-panel fix. The friendly **⚙️ Config** editor gained sections for **Multi-Radio** (`meshtastic_enabled`, `default_send_network`), the **MeshCore** radio, the **MCP Server**, **Firmware & Updates**, and the **Hermes** and **Home Assistant** AI providers — previously these v0.7.x blocks were only reachable via the Raw JSON tab. 🐛 Also hardened the **Channel Messages** panel so a single malformed message can no longer blank the entire panel (each channel/message now renders in isolation; channels sort numerically).
- **v0.7.2 Beta** — 🤖 **Channel Agents are now manageable from the WebUI.** A new **🤖 Agents** toolbar button opens a Channel Agents manager where you can assign any channel to a specific **AI provider** (OpenAI, Hermes, Ollama, Claude, …) or a loaded **extension** (e.g. OpenClaw), with an optional per-channel **PIN** gate. Assignments **apply live** (no restart) and persist to [config.json](config.json). Channels with an assigned agent now show a badge (🤖 provider / 🧩 extension) in the Channel Messages panel, and the legacy `home_assistant_channel_index` mapping is surfaced automatically. The `/api/channel_agents` endpoint gained a `POST` to save assignments.
- **v0.7.1 Beta** — 🐛 **Bug fix:** the WebUI Extensions Manager **Enable / Disable** buttons now update immediately. The toggle wrote the new state to the extension's `config.json` but the in-memory status returned by `/extensions/status` stayed stale, so the button label and status dot never changed (the change only appeared after a restart). The loader's in-memory state is now kept in sync, so toggling reflects instantly; use **Reload** (or restart) to apply it to the running extensions.
- **v0.7.0 Beta** — 🚀 **Multi-radio overhaul + MCP tool server + firmware updates.**
  - **MeshCore is a first-class radio.** Run Meshtastic-only, MeshCore-only (fully standalone — no Meshtastic device required), or both with MESH-API as the man-in-the-middle. MeshCore connects over serial / TCP / BLE.
  - **Cross-network routing & UI parity** — per-network connection banner, a node **network filter** with collapsible Meshtastic/MeshCore sections, network badges on nodes and messages, distinct map markers, MeshCore channels (group chats / private channels) in the send form, and DMs to MeshCore contacts — mirroring the Meshtastic experience.
  - **MCP (Model Context Protocol) server** — external AI agents (Claude, Perplexity, Hermes, custom) can call MESH-API core functions **and** extensions as tools, driving the mesh networks as an agentic backend. `POST /mcp` (Streamable HTTP / JSON-RPC 2.0), disabled by default, bearer-token auth. See **[MCP Server](README.md#mcp-server-model-context-protocol)**.
  - **Firmware & software updates** — detects the connected Meshtastic/MeshCore device, checks GitHub for newer Meshtastic firmware, MeshCore firmware, and MESH-API itself, and shows a 🔄 **Updates** notification with **stable / beta / alpha release-channel** selection per firmware. Optional one-click ESP32 flashing (off by default). See **[Firmware Updates](README.md#firmware--software-updates)**.
  - **Bug fixes:** **#59** (MeshCore-origin messages now reach plugins like Telegram and the AI) and **#58** (bounded Meshtastic (re)connect + an actually-running connection watchdog).
  - New config blocks in [config.json](config.json): `meshtastic_enabled`, `default_send_network`, `meshcore`, `mcp`, and `firmware`.
  - MeshCore requires the `meshcore` Python package (already in [requirements.txt](requirements.txt)): `pip install meshcore`. ESP32 firmware flashing additionally needs `esptool`.
- **v0.6.0** — Full release! Plugin-based extensions system with 30 built-in extensions, 12 AI providers, drop-in plugin architecture, interactive node map, collapsible channel views, draggable dashboard layout, and a fully revamped WebUI. **Docker images now available** for x86_64 and ARM64 (Raspberry Pi 4/5)!

> **Community note:** A massive amount of work has landed — the plugin-based extensions system, 30+ extensions, OpenClaw AI agent integration, MeshCore bridging, and the full WebUI overhaul all shipped in a compressed timeline. **I depend on the community to help test, identify, and crush bugs.** If something breaks, doesn't work as documented, or behaves unexpectedly — please open a [GitHub Issue](https://github.com/mr-tbot/mesh-api/issues) with as much detail as possible.

---

## Detailed History

### v0.7.3.6 Beta — AI Endpoint Heartbeat

- **Token-free heartbeat for named AI endpoints.** A background thread (started in `main()`) periodically checks each named AI endpoint by issuing a plain `GET` to its OpenAI-compatible `/models` route — derived automatically from the endpoint's chat/completions URL. Any HTTP response means the server is reachable; the check never sends a chat completion, so it **spends no AI tokens**.
- **Live status in the WebUI.** The **🔌 Manage AI Endpoints** panel (inside **🤖 Channel Agents**) now shows a per-endpoint status dot: 🟢 **online** (HTTP 200), 🟡 **reachable**/**auth?** (server up, or 401/403 key issue), 🔴 **offline** (connection refused / timeout / DNS error), with round-trip latency. The panel auto-refreshes status every 30s while open, and each row has a **Check now** button for an immediate probe.
- **New endpoint:** `GET /api/ai_endpoints/health` returns cached per-endpoint status; pass `?check=1` to force an immediate live re-check.
- **New config key:** `ai_endpoint_heartbeat_sec` (default `60`) controls the background heartbeat interval.

### v0.7.0 Beta — Initial Full MeshCore Support

> Run MESH-API with a Meshtastic node, a MeshCore node, or **both** with
> cross-network routing. Widely untested — community feedback wanted.

#### Multi-radio (MeshCore as a first-class radio)
- **MeshCore promoted to a core-owned radio** (`meshcore_core.py`) on equal footing with Meshtastic, feeding the *same* network-agnostic message pipeline. Connects over serial / TCP / BLE.
- **Three topologies:** Meshtastic-only (unchanged), MeshCore-only standalone (`meshtastic_enabled: false`, no Meshtastic device needed), or both with MESH-API as the man-in-the-middle bridge.
- **Cross-network everything** — slash commands, AI, and every extension now work on both networks; outbound send to one network or both at once.
- **WebUI parity for MeshCore** — per-network connection banner; node **network filter** with **collapsible Meshtastic/MeshCore sections**; network badges (📡/🟣) on nodes & messages; distinct purple map markers with DM/interact; MeshCore channels (group chats / private channels) in the send form; DMs to MeshCore contacts.
- **Staged startup + exponential backoff** so two USB radios on a power-limited host (e.g. Pi Zero) don't fight over the bus during connect.

#### MCP server (Model Context Protocol)
- New built-in **MCP server** (`mcp_server.py`) at `POST /mcp` (Streamable HTTP / JSON-RPC 2.0, no async deps). Lets external AI agents (Claude, Perplexity, Hermes, custom) call MESH-API core functions and extensions as **tools**, using the mesh as an agentic backend.
- Core tools for sending, listing nodes/messages/channels, AI queries, running commands, and MeshCore contacts; **every extension slash command is auto-exposed** as `ext_cmd_*`, and extensions can add richer typed tools via `get_mcp_tools()` + `call_mcp_tool()`.
- Disabled by default; bearer-token auth, Origin allowlist, rate limiting, gated emergency tool.

#### Firmware & software updates
- New **update manager** (`firmware_updater.py`) detects the connected Meshtastic/MeshCore device and notifies (🔄 Updates button + badge) when newer Meshtastic firmware, MeshCore firmware, or MESH-API is available.
- **Stable / beta / alpha release channels** selectable per firmware. Optional ESP32 over-USB flashing via `esptool` (off by default); nRF52/UF2 + MeshCore use the web flasher.

#### Bug fixes
- **#59 — MeshCore-origin messages now reach plugins/AI.** Both radios funnel through one inbound pipeline, so a MeshCore message reaches Telegram, Discord, the AI provider, etc.
- **#58 — Reconnect hangs.** Bounded Meshtastic (re)connect (no more infinite hang on a wedged Wi-Fi/TCP link) and the connection watchdog is now actually started; exponential reconnect backoff.
- **OpenAI reasoning models** — `gpt-5`/`o1`/`o3`/`o4` now use `max_completion_tokens` with proper headroom, fixing empty AI replies.
- **Logging cascade** — hardened `script.log` truncation against non-UTF-8 bytes that could spin into a `RecursionError`.

#### New config blocks
- `meshtastic_enabled`, `default_send_network`, and the `meshcore`, `mcp`, and `firmware` blocks in [config.json](config.json). Old configs keep working; the new keys are additive.

### v0.6.0 (Full Release)

#### Bug Fixes
- **#53 — Home Assistant interface stale after reconnect** — The `app_context["interface"]` reference is now refreshed after every successful reconnect, preventing `None` errors in HA and other extensions. Thanks to [@InstigatorX](https://github.com/InstigatorX) for reporting. *(GitHub Issue #53)*
- **#51 — AI channel reply routing** — Added detailed dispatch logging to trace AI reply routing across channels and DMs. Verified the routing logic correctly respects `respond_to_broadcast_messages`, `respond_to_dms`, and `ai_respond_on_longfast` flags. Thanks to [@droidblastnz](https://github.com/droidblastnz) for reporting. *(GitHub Issue #51)*
- **#44 — Stability improvements** — Smart word‑boundary message chunking (never splits mid‑word), `requests.Session()` connection pooling for Ollama calls, `num_predict` parameter to cap AI token generation, cross‑platform `OSError` handling with specific error code checks (errno 19, 32, 107, 108, 110). Thanks to [@omgitsgela](https://github.com/omgitsgela) for reporting. *(GitHub Issue #44)*

#### New Features
- **Interactive Node Map** — Leaflet.js map view with colored markers for all GPS‑enabled nodes. Dark mode (CARTO dark tiles) and light mode (OpenStreetMap) selectable in settings. Offline detection with a banner notice when tiles are unavailable. Connected node shown as a green circle. Popups display node name, hex ID, last heard, hop count, DM button, and Google Maps link.
- **Collapsible Channel Groups** — Channel messages are now grouped by channel name. Each group has a clickable 📻 header that expands/collapses the messages. Unread message counts shown as orange pill badges.
- **Draggable Dashboard Layout** — All major dashboard sections (Send Form, Node Map, Message Panels, Discord) can be reordered via ☰ drag handles. The three message columns (DMs, Channels, Nodes) are independently sortable. Sections can be hidden/shown from the UI Settings panel. Layout order persists in localStorage.
- **Five Built‑in Notification Sounds** — Two‑Tone Beep, Triple Chirp, Alert Chime, Sonar Ping, Radio Blip generated via Web Audio API. Separate sound assignments for DMs, channels, and per‑node. Per‑node sounds use a dropdown populated from available nodes. Custom sound file upload also supported. Test button and volume slider in the settings panel.
- **Compact Settings Panel** — UI Settings redesigned as a two‑column grid with emoji‑labeled sections (⚙️ UI Settings). Includes button theme color, section colors, dark/light map style, hue rotation, section visibility toggles, and an About section with links to Meshtastic, MeshCore, and project resources.
- **Node Enhancements** — DM, PING, and PONG buttons shown for every node. Show on Map (fly‑to) and Google Maps buttons on the same line. Last‑heard time displayed with 📡 icon. Node items rendered as rounded cards with hover effects.
- **Emoji Section Headers** — All dashboard panels now have emoji prefixes: ✉️ Send a Message, 🗺️ Node Map, 💬 Message Panels, 📨 Direct Messages, 📡 Channel Messages, 📋 Available Nodes, 🎮 Discord Messages.
- **Differentiated Send Buttons** — Send, Reply to Last DM, and Reply to Last Channel buttons now have distinct colors (green, blue, purple) for quick visual identification.
- **Welcome Setup Guide** — Initial popup changed from beta disclaimer to a friendly setup guide with configuration steps and links to documentation.
- **Report a Bug** — Footer button links directly to GitHub Issues for easy bug reporting.

#### Visual Overhaul
- CSS custom properties (`--bg-primary`, `--bg-panel`, `--bg-input`, `--text-primary`, `--text-muted`, `--border-radius`) for consistent theming.
- Segoe UI font stack, smooth transitions, hover effects on panels/messages/nodes.
- Mobile‑responsive breakpoints: collapsible map, stacked masthead, footer, and send form at ≤600px.
- "❤️ Support this Developer" PayPal donation button added to the footer alongside the version badge.

#### Updated Dependencies
- protobuf 6.33.5 → 7.34.0
- meshtastic 2.7.7 → 2.7.8
- Flask 3.1.2 → 3.1.3
- twilio 9.10.1 → 9.10.2
- bleak ≥0.22.0 → ≥2.1.1
- meshcore ≥2.2.0 → ≥2.2.30

### v0.6.0 RC1 (Release Candidate 1)
- **WebUI Extensions Manager**
  - New "Extensions" button in the dashboard toolbar opens a full Extensions Manager modal.
  - View all available extensions with color-coded status indicators (green=active, yellow=enabled but not loaded, grey=disabled).
  - Enable/disable extensions directly from the WebUI — toggles are saved to each extension's `config.json`.
  - Inline JSON config editor for each extension — edit and save any extension's configuration without touching the filesystem.
  - Hot-Reload button to live-reload all extensions without restarting the server.
  - New REST API endpoints: `GET /extensions/status`, `GET/PUT /extensions/config/<slug>`, `POST /extensions/toggle/<slug>`, `POST /extensions/reload`.
- **Incoming Message Sound — Fixed & Improved**
  - The notification sound system has been completely rewritten. Previously, the `<audio>` element was configured but `.play()` was never called — sounds were non-functional.
  - New built-in two-tone notification beep using the Web Audio API (no external files required).
  - Sound plays automatically when new inbound messages arrive (not for outgoing/WebUI/system messages).
  - New UI Settings controls: enable/disable toggle, volume slider, sound type selector (built-in beep vs. custom file), and a "Test Sound" button.
  - First page load silently seeds the seen-message set so existing messages don't trigger sounds.
- **Config Modal Alignment**
  - Updated config editor help text to reflect the new extension system — removed legacy Discord/Home Assistant references from config.json help.
  - Added note directing users to the Extensions button for extension configuration.
- **Docker Preparation**
  - Updated Dockerfile to include the `extensions/` directory and all built-in extensions.
  - Updated `docker-compose.yml` with optional extensions volume mount.
  - Docker images coming with the full v0.6.0 release!
- **Version Bump**
  - Updated all version references (banner, footer, README, scripts) to v0.6.0 RC1.
- **Plugin-Based Extensions System**
  - Brand new drop-in plugin architecture with 26+ built-in extensions across 5 categories: Communication, Notifications, Emergency/Weather, Ham Radio/Off-Grid, and Smart Home.
  - Extensions can register slash commands, react to emergencies, observe all mesh messages, expose HTTP endpoints via Flask, and run background polling threads.
  - Each extension is fully self-contained with its own `config.json` — no core code changes required to add, remove, or configure extensions.
  - New `/extensions` mesh command to list all loaded extensions and their status.
  - **⚠️ The extensions system and all corresponding extensions are new and largely untested. Please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues) so they may be investigated and addressed.**
- **12 AI Providers**
  - Added support for **Claude**, **Gemini**, **Grok**, **OpenRouter**, **Groq**, **DeepSeek**, **Mistral**, and a generic **OpenAI-compatible** endpoint option — in addition to existing LM Studio, OpenAI, Ollama, and Home Assistant providers.
  - All OpenAI-compatible providers share a unified helper for consistent behavior and error handling.
- **Extension Categories**
  - **Communication (12):** Discord, Slack, Telegram, Matrix, Signal, Mattermost, Zello, MQTT, Webhook Generic, IMAP, Mastodon, n8n
  - **Notifications (5):** Apprise, Ntfy, Pushover, PagerDuty, OpsGenie
  - **Emergency/Weather (6):** NWS Alerts, OpenWeatherMap, USGS Earthquakes, GDACS, Amber Alerts, NASA Space Weather
  - **Ham Radio/Off-Grid (3):** Winlink, APRS, BBS (SQLite store-and-forward)
  - **Smart Home (1):** Home Assistant (AI provider extension)
- **Backward Compatibility**
  - Legacy Discord and Home Assistant configuration keys in the main `config.json` are automatically migrated to their respective extension configs on first load.
  - Old configs should work out of the box with the new extension system.
- **Developer Documentation**
  - Full extension development guide with base class API reference, step-by-step tutorial, hook reference, configuration patterns, Flask route examples, background thread patterns, best practices, and troubleshooting.

### v0.6.0 Pre-Release 3 (PR3)
- **New `/nodes-XY` command**
  - Reports online nodes (heard within the last window) and total known nodes.
- **Online window config**
  - New `nodes_online_window_sec` setting controls the online window (default 2 hours).
- **Ollama stability limit**
  - New `ollama_max_parallel` setting caps concurrent Ollama requests (default 1).
- **AI command matching improvements**
  - `/ai-XY` works reliably in channels; legacy `/aiXY` is also accepted for compatibility.

### v0.6.0 Pre-Release 2 → Pre-Release 3
- **Mesh safety defaults**
  - LongFast (channel 0) responses are OFF by default; enable `ai_respond_on_longfast` only if your mesh agrees.
  - MQTT response gating: new `respond_to_mqtt_messages` flag (default `false`) to prevent multiple servers from replying at once over MQTT.
  - Community note: Using AI bots on public LongFast channels is generally frowned upon because it increases congestion for everyone. The toggle remains available for isolated/private deployments or special cases, but it is off by default.
- **Bot‑loop prevention**
  - All AI replies now start with a tiny fixed marker `m@i` (≤ 3 chars). Other MESH‑AI instances ignore messages that begin with this marker.
  - Each instance also remembers node IDs that send AI‑tagged messages and ignores further requests from those nodes to mitigate bot‑to‑bot chatter.
- **User‑initiated only**
  - No features are planned that allow the AI to auto‑respond to “join/arrive” events or otherwise talk without an explicit message from a legitimate user.
- **Per‑install command alias**
  - On first run, a randomized alias (e.g. `/ai-9z`) is generated and saved as `ai_command` in `config.json`. Use it to avoid collisions; you can change it anytime.
  - Strongly encouraged: customize your commands in `commands_config.json` to minimize collisions on shared meshes/MQTT.
- **No chain‑of‑thought on mesh**
  - A global sanitizer removes any “thinking”/reasoning content before sending. This includes XML‑style tags (e.g. `<thinking>…</thinking>`), fenced blocks, YAML/JSON meta fields, and heading lines.
  - Applied consistently across all providers (LM Studio, OpenAI, Ollama) and Home Assistant so only final answers are transmitted.
- **Ollama reliability**
  - Added keep‑alive and request options, simple retries on transient failures, and response normalization plus sanitization for cleaner output.
- **WebUI**
  - Fixed ticker behavior: it now correctly honors read/unread state for both DMs and channel messages, and dismissals persist across refreshes.
  - Refined layout: Direct Messages, Channel Messages, and Available Nodes order; mobile stacking with 3‑wide desktop; controls moved to the “Send a Message” header (top‑right).
  - New Commands modal overlay: quickly view available commands and descriptions (via the Commands button). Backed by a lightweight JSON endpoint (`/commands_info`).
  - Scrollable panels with sensible max heights; on mobile, each panel can be collapsed/expanded for easier navigation.
  - Footer badge: "MESH-API v0.6.0" and "by: MR-TBOT".
  - Emoji reactions: every message now includes a React button that toggles a hidden emoji picker; picking an emoji auto‑sends a reaction (works for both DMs and channel messages).
  - Quick Emoji bar: the “Send a Message” form includes common emojis; clicking inserts into your draft at the cursor without auto‑sending.
  - Reaction feedback: React buttons show Sending/Sent/Failed states and temporarily disable during send to prevent accidental double‑presses.
- **Docs & help**
  - Updated README and in‑app `/help` to highlight safety defaults, MQTT gating, and your unique alias.
  - New config keys summarized above; defaults favor safety and reduce congestion.

### v0.4.2 → v0.5.1 - NOW IN BETA!
- **REBRANDED TO MESH-API**
- **WebUI Enhancements**
  - **Node Search** added for easier node management.
  - **Channel Message Organization** with support for custom channels in `config.json`.
  - **Revamped DM threaded messaging** system.
  - **Location Links** for nodes with available location data via Google Maps.
  - **Timezone Selection** for accurate incoming message timestamps.
  - **Custom Local Sounds** for message notifications (no longer relying on hosted files).
  - **Logs Page Auto-Refresh** for live updates.
- **Baudrate Adjustment**
  - Configurable **baud rate** in `config.json` for longer USB connections (e.g., roof nodes).
- **LM Studio Model Selection**
  - Support for selecting models when multiple are loaded in LM Studio, enabling multi-model instances.
- **Protobuf Noise Debugging**
  - Moved any protobuf-related errors behind debug logs as they do not affect functionality.
  - Can be enabled by setting `"debug": true` in `config.json` to track.
- **Updated Docker Support**
  - Updated Docker configuration to always pull/build the latest Meshtastic-Python libraries, ensuring compatibility with Protobuf versions.
- *POSSIBLE BUGS IN BETA v0.5.1* — Web UI ticker isn't honoring read messages in some cases.
- *INCOMING MESSAGE SOUNDS ARE UNTESTED ON ALL PLATFORMS AND FILESYSTEMS.*

### v0.4.1 → v0.4.2
- **Initial Ubuntu & Ollama Unidecode Support:**
  - User @milo_o - Thank you so much!  I have merged your idea into the main branch - hoping this works as expected for users - please report any problems!  -  https://github.com/mr-tbot/mesh-api/discussions/19
- **Emergency Email Google Maps Link:**
  - Emergency email now includes a Google Maps link to the sender's location, rather than just coordinates. - Great call, @Nlantz79!  (Remember - this is only as accurate as the sender node's location precision allows!)

### v0.4.0 → v0.4.1
- **Error Handling (ongoing):**
  - Trying a new method to handle WinError exceptions - which though much improved in v0.4.0 - still occur under the right connection circumstances - especially over Wi-Fi.
     (**UPDATE: My WinError issues were being caused by a combination of low solar power, and MQTT being enabled on my node.  MQTT - especially using LongFast is very intense on a node, and can cause abrupt connection restarts as noted here:  https://github.com/meshtastic/meshtastic/pull/901 - but - now the script is super robust regardless for handling errors!)**
- **Emergency Email Subject:**
  - Email Subject now includes the long name, short name & Node ID of the sending node, rather than just the Node ID.
- **INITIAL Docker Support**

### v0.3.0 → v0.4.0
- **Logging & Timestamps:**
  - Shift to UTC‑based timestamps and enhanced log management.
- **Discord Integration:**
  - Added configuration for inbound/outbound Discord message routing.
  - Introduced a new `/discord_webhook` endpoint for processing messages from Discord.
- **Emergency Notifications:**
  - Expanded emergency alert logic to include detailed context (GPS data, UTC time) and Discord notifications.
- **Sending and receiving SMS:**
  - Send SMS using `/sms <+15555555555> <message>`
  - Config options to either route incoming Twilio SMS messages to a specific node, or a channel index.
- **Command Handling:**
  - Made all slash commands case‑insensitive to improve usability.
  - Enhanced custom command support via `commands_config.json` with dynamic AI prompt insertion.
- **Improved Error Handling & Reconnection:**
  - More granular detection of connection errors (e.g., specific OSError codes) and use of a global reset event for reconnects.
- **Code Refactoring:**
  - Overall code improvements for maintainability and clarity, with additional debug prints for troubleshooting.

### v0.2.2 → v0.3.0 (from the original Main Branch README)
- **WebUI Overhaul:**
  - Redesigned three‑column dashboard showing channel messages, direct messages, and node list.
  - New send‑message form with toggleable modes (broadcast vs. direct), dynamic character counting, and message chunk preview.
- **Improved Error Handling & Stability:**
  - Redirected stdout/stderr to a persistent `script.log` file with auto‑truncation.
  - Added a connection monitor thread to detect disconnections and trigger automatic reconnects.
  - Implemented a thread exception hook for better error logging.
- **Enhanced Message Routing & AI Response Options:**
  - Added configuration flags (`reply_in_channels` and `reply_in_directs`) to control AI responses.
  - Increased maximum message chunks (default up to 5) for longer responses.
  - Updated slash command processing (e.g., added `/about`) and support for custom commands.
- **Expanded API Endpoints:**
  - New endpoints: `/nodes`, updated `/connection_status`, and `/ui_send`.
- **Additional Improvements:**
  - Robust Home Assistant integration and basic emergency alert enhancements.

### v0.1 → v0.2.2
- **Expanded Configuration & JSON Files**
   - **New `config.json` fields**
     - Added `debug` toggle for verbose debugging.
     - Added options for multiple AI providers (`lmstudio`, `openai`, `ollama`), including timeouts and endpoints.
     - Introduced **Home Assistant** integration toggles (`home_assistant_enabled`, `home_assistant_channel_index`, secure pin, etc.).
     - Implemented **Twilio** and **SMTP** settings for emergency alerts (including phone number, email, and credentials).
     - Added **Discord** webhook configuration toggles (e.g., `enable_discord`, `discord_send_emergency`, etc.).
     - Several new user-configurable parameters to control message chunking (`chunk_size`, `max_ai_chunks`, and `chunk_delay`) to reduce radio congestion.
- **Support for Multiple AI Providers**
   - **Local Language Models** (LM Studio, Ollama) and **OpenAI** (GPT-3.5, etc.) can be selected via `ai_provider`.
   - Behavior is routed depending on which provider you specify in `config.json`.
- **Home Assistant Integration**
   - Option to route messages on a dedicated channel directly to Home Assistant’s conversation API.
   - **Security PIN** requirement can be enabled, preventing unauthorized control of Home Assistant.
- **Improved Command Handling**
   - Replaced single-purpose code with a new, flexible **commands system** loaded from `commands_config.json`.
   - Users can define custom commands that either have direct string responses or prompt an AI.
   - Built-in commands now include `/ping`, `/test`, `/emergency`, `/whereami`, `/help`, `/motd`, and more.
- **Emergency Alert System**
   - `/emergency` (or `/911`) triggers optional Twilio SMS, SMTP email, and/or Discord alerts.
   - Retrieves node GPS coordinates (if available) to include location in alerts.
- **Improved Message Chunking & Throttling**
   - Long AI responses are split into multiple smaller segments (configurable via `chunk_size` & `max_ai_chunks`).
   - Delays (`chunk_delay`) between chunks to avoid flooding the mesh network.
- **REST API Endpoints** (via built-in Flask server)
   - `GET /messages`: Returns the last 100 messages in JSON.
   - `GET /dashboard`: Displays a simple HTML dashboard showing the recently received messages.
   - `POST /send`: Manually send messages to nodes (direct or broadcast) from external scripts or tools.
- **Improved Logging and File Structure**
   - **`messages.log`** for persistent logging of all incoming messages, commands, and emergencies.
   - Distinct JSON config files: `config.json`, `commands_config.json`, and `motd.json`.
- **Refined Startup & Script Structure**
  - A new `Run MESH-API - Windows.bat` script for straightforward Windows startup.
   - Added disclaimers for alpha usage throughout the code.
   - Streamlined reconnection and exception handling logic with more robust error-handling.
- **General Stability & Code Quality Enhancements**
   - Thorough refactoring of the code to be more modular and maintainable.
   - Better debugging hooks, improved concurrency handling, and safer resource cleanup.
