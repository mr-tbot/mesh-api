# MESH-API v0.6.0 - Full Release!

- **v0.6.0** — Full release! Plugin-based extensions system with 30 built-in extensions, 12 AI providers, drop-in plugin architecture, interactive node map, collapsible channel views, draggable dashboard layout, and a fully revamped WebUI. **Docker images now available** for x86_64 and ARM64 (Raspberry Pi 4/5)!

> ### Community-Driven Improvements
>
> A massive amount of work has landed — the new plugin-based extensions system, 30+ extensions, OpenClaw AI agent integration, MeshCore bridging, and the full WebUI overhaul all shipped in a compressed timeline. **v0.6.0 includes critical bug fixes reported by the community** — thank you to everyone who filed issues and tested!
>
> **I am depending on the community to help test, identify, and crush bugs.** If something breaks, doesn't work as documented, or behaves unexpectedly — please open a [GitHub Issue](https://github.com/mr-tbot/mesh-api/issues) with as much detail as possible. Every report helps make this project better for everyone.
>
> If MESH-API is useful to you, please consider MAKING A DONATION — this project is built and maintained by one developer with the help of AI tools, and your support directly fuels continued development.

- PLEASE NOTE - There are new requirements and new config options - v0.6.0 updates many required library versions and brings us into alignment with the 2.7 branch of the Meshtastic Python library!  Old configs should work out of the box - but there are new config flags and a new "description" feature for custom commands in commands_config.json.  Read the changelogs.

## ❤️ Support MESH-API Development — Keep the Lights On

MESH-API is built and maintained by **one developer** with the help of AI tools. There is no corporate sponsor, no VC funding — just late nights, community feedback, and a passion for off-grid communication.

If MESH-API has been useful to you — whether you're running it on a Raspberry Pi in your go-bag, bridging your local mesh to Discord, or experimenting with AI on LoRa — **please consider making a donation.** Every contribution, no matter the size, directly fuels continued development, bug fixes, new extensions, and keeping this project free and open-source for everyone.

### Donate via PayPal (Preferred)

[![Donate via PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg?logo=paypal&style=for-the-badge)](https://www.paypal.com/donate/?business=7DQWLBARMM3FE&no_recurring=0&item_name=Support+the+development+and+growth+of+innovative+MR_TBOT+projects.&currency_code=USD)

[**Click here to donate via PayPal**](https://www.paypal.com/donate/?business=7DQWLBARMM3FE&no_recurring=0&item_name=Support+the+development+and+growth+of+innovative+MR_TBOT+projects.&currency_code=USD)

### Crypto Donations

| Currency | Address |
|----------|---------|
| **BTC** | `bc1qalnp0xze5t9nner2754k2pj7yjhkrt3uzvzdvt` |
| **ETH** | `0xAd640c506f5d2368cAF420a117380820C0C5F61C` |
| **XRP** | `rpciwKrQSaRZ1UjPunH8vLJhoM2s4NaYoL` |
| **DOGE** | `DM79aRx58J6RYuWakHjiELWbNJkTTDj1cv` |

**Thank you to everyone who has donated, filed issues, tested pre-releases, and spread the word.** You are what makes this project possible. 🙏



![MESH-API](https://github.com/user-attachments/assets/438dc643-6727-439d-a719-0fb905bec920)



**MESH-API** is an experimental project that bridges [Meshtastic](https://meshtastic.org/) (& now [MeshCore](https://meshcore.co.uk/) ) LoRa mesh networks with powerful AI chatbots and 3rd party APIs.

## What Sets MESH-API Apart?

Most projects in this space stop at being "AI chatbot integrations" — but **MESH-API is much more than that.**

- **Full Router / Mesh Operator**  
  MESH-API isn’t just talking to an LLM. It’s a **protocol bridge** and **mesh backbone**, designed to let LoRa networks, online (or offline) services, and APIs talk to each other in real time.

- **Not a One-Trick Pony**  
  Where other tools simply connect to AI, MESH-API is built to **route, translate, and post messages** between different systems and services — making it a true hub for both on-grid and off-grid communication.

- **Expandable by Design**  
  Any software with a working API can be integrated. That means you can merge in external services, dashboards, or automation platforms, extending the mesh far beyond its original scope.

- **AI-Powered Off-Grid Networks**  
  MESH-API provides the foundation for **self-sufficient LoRa mesh networks enhanced with AI**, ensuring communication, automation, and decision-making remain possible — even without the internet.

In short, MESH-API bridges the gap between **mesh services** and **online/locally hosted services**, making it a powerful backbone for resilient, intelligent LoRa networks.

> **Disclaimer:**  
> This project is **NOT ASSOCIATED** with the official Meshtastic Project. It is provided solely as an extension to add AI and advanced features to your Mesh network.  

> **v0.6.0 — Full Release:**  
> This is the full v0.6.0 release, incorporating community‑reported bug fixes, a visual dashboard overhaul, and updated dependencies. While significantly more stable than earlier pre‑releases, please avoid relying on it for mission‑critical tasks or emergencies. Always have backup communication methods available and use responsibly.  

>  
> *I am one robot using other robots to write this code. Some features are still untested in the field. Check the GitHub issues for fixes or feedback!*

---

[![image](https://github.com/user-attachments/assets/bdf08934-3a80-4dc6-8a91-78e33c34db59)](https://meshtastic.org)
The Meshtastic logo trademark is the trademark of Meshtastic LLC.



## Features

- **Plugin-Based Extensions System** *(New in v0.6.0)*  
  - 30 built-in extensions across 7 categories: Communication, Notifications, Emergency/Weather, Ham Radio/Off-Grid, Smart Home, Mesh Bridging, and AI Agents.
  - Drop-in plugin architecture — add or remove extensions by copying a folder. No core code changes required.
  - Extensions can register slash commands, react to emergencies, observe messages, expose HTTP endpoints, and run background services.
  - **WebUI Extensions Manager** — view, enable/disable, and configure extensions from the dashboard.
  - See the [Extensions Reference](#extensions-reference) section below for full details on all built-in extensions, or [Developing Custom Extensions](#developing-custom-extensions) to build your own.
- **Multiple AI Providers**  
  - Support for **Local** models (LM Studio, Ollama), **OpenAI**, **Claude**, **Gemini**, **Grok**, **OpenRouter**, **Groq**, **DeepSeek**, **Mistral**, generic OpenAI-compatible endpoints, and **Home Assistant** integration.
- **Home Assistant Integration**  
  - Seamlessly forward messages from a designated channel to Home Assistant’s conversation API. Optionally secure the integration using a PIN.
- **NASA Space Weather Monitoring**  
  - Track geomagnetic storms, solar flares, coronal mass ejections, and more via NASA's DONKI API. Auto-broadcast significant events to the mesh with configurable Kp index and flare class thresholds. Slash commands: `/spaceweather`, `/solarflare`, `/geomagstorm`.
- **n8n Workflow Automation**  
  - Bidirectional bridge with [n8n](https://n8n.io) — forward mesh messages and emergencies to n8n webhook triggers, receive workflow outputs on the mesh, list active workflows, and trigger them via slash commands. Enables powerful no-code automation pipelines for your mesh network.
- **Advanced Slash Commands**  
  - Built‑in commands: suffixed `/about-XY`, `/help-XY`, `/motd-XY`, `/whereami-XY`, `/nodes-XY`, AI commands with your unique suffix (e.g., `/ai-XY`, `/bot-XY`, `/query-XY`, `/data-XY`), unsuffixed `/test`, and unsuffixed `/emergency` (or `/911`), plus custom commands via `commands_config.json`.
  - Commands are now case‑insensitive for improved mobile usability.
  - New: a per-install randomized alias (e.g. `/ai-9z`) is generated on first run to reduce collisions when multiple bots exist on the same mesh or MQTT network. You can change it in `config.json` (field `ai_command`). All AI commands require this suffix, and other built‑ins (except emergency/911) also require your suffix.
  - Strongly encouraged: customize your commands in `commands_config.json` to avoid collisions with other users.
- **Emergency Alerts**  
  - Trigger alerts that are sent via **Twilio SMS**, **SMTP Email**, and, if enabled, **Discord**.
  - Emergency notifications include GPS coordinates, UTC timestamps, and user messages.
- **Enhanced REST API & WebUI Dashboard**  
  - A modern three‑column layout showing direct messages, channel messages, and available nodes. Stacks on mobile; 3‑wide on desktop. Controls (⌘ Commands, 🧩 Extensions, ⚙️ Config, 📜 Logs) live in the “Send a Message” header (top‑right).
  - **Interactive Node Map** — Leaflet.js‑powered map view with markers for all GPS‑enabled nodes. **25 tile providers** including OpenStreetMap, Carto (Light, Dark, Voyager, No‑Label variants), OpenTopoMap, Esri (Street, Satellite, Topo, NatGeo, Light/Dark Gray Canvas, Ocean), Stadia (Stamen Terrain/Toner/Toner Lite/Watercolor, Alidade Smooth/Dark, Outdoors, OSM Bright), Humanitarian OSM, CyclOSM, and OPNVKarte. Defaults to Carto Positron (Light). **Offline map image support** — upload a local map image with lat/lon bounds via settings; Leaflet overlays it as a fully functional map layer with markers, pan, and zoom. Offline detection with fallback notice. Popups include node name, custom name, favorite star, ID, last heard, hop count, DM/PING/PONG buttons, and Google Maps link — all on a single row. Mini DM box over the map includes Send, PING, and PONG on the same row.
  - **Collapsible Channel Groups** — Each channel is a toggle‑able group with an unread‑count badge. Click the 📻 header to expand/collapse.
  - **Draggable Dashboard** — All major sections (Send Form, Node Map, Message Panels, Discord) can be reordered via ☰ drag handles. The three message columns (DMs, Channels, Nodes) are also independently sortable. Layout order is saved to localStorage. Sections can be hidden/shown from the UI Settings panel.
  - **Notification Sounds** — Five built‑in Web Audio API sounds (Two‑Tone Beep, Triple Chirp, Alert Chime, Sonar Ping, Radio Blip) plus a **custom sounds library** supporting multiple uploaded audio files (stored as base64 in localStorage). Separate sound selection for Default, DMs, Channels, and individual nodes — each with its own dropdown populated from built‑in plus all custom sounds. Test button, volume slider, and per‑node sound management in settings.
  - **Node Enhancements** — Every node shows DM, PING, and PONG buttons, last‑heard time (📡), beacon time, hop count, distance, Show on Map (fly‑to), and Google Maps link on a single line. **Favorite nodes** — toggle a ⭐ star to pin nodes to the top of the Available Nodes list (persisted in localStorage). **Custom node names** — click ✏️ to assign a logical name displayed in cyan alongside the original shortName. Favorites and custom names also appear in map popup titles and tooltip labels.
  - Emoji enhancements: each message has a React button that reveals a compact, hidden emoji picker; choosing an emoji auto‑sends a reaction (DM or channel). The send form includes a Quick Emoji bar that inserts emojis into your draft (does not auto‑send).
  - Additional endpoints include `/messages`, `/nodes`, `/connection_status`, `/logs`, `/logs_stream`, `/send`, `/ui_send`, `/commands_info` (JSON commands list), and a new `/discord_webhook` for inbound Discord messages.
  - UI customization through settings panel including button theme color, section colors, 25 map tile styles (default: Carto Light), offline map image upload with lat/lon bounds, hue rotation, notification sounds (built‑in or custom library with multiple files), per‑node sound assignments, section visibility toggles, and volume control. An About section with links to Meshtastic, MeshCore, and the project's GitHub and website.
  - Config Editor (WebUI): Click the “Config” button in the header to view/edit `config.json`, `commands_config.json`, and `motd.json` in a tabbed editor. JSON is validated before saving; writes are atomic. Some changes may require a restart to take effect.
  - Extensions Manager (WebUI): Click the “Extensions” button to view extension status, enable/disable extensions, edit extension configs, and hot‑reload all extensions — all from the browser.
- **Improved Message Chunking & Routing**  
  - Automatically splits long AI responses into configurable chunks with delays to reduce radio congestion.
  - Configurable flags control whether the bot replies to broadcast channels and/or direct messages.
  - New: LongFast (channel 0) response toggle — by default the bot will NOT respond on LongFast to avoid congestion. Enable `ai_respond_on_longfast` only if your local mesh agrees.
  - Etiquette: Using AI bots on public LongFast is discouraged; keep it off unless you’re on an isolated/private mesh with community consent.
- **Robust Error Handling & Logging**  
  - Uses UTC‑based timestamps with an auto‑truncating script log file (keeping the last 100 lines if the file grows beyond 100 MB).
  - Enhanced error detection (including specific OSError codes) and graceful reconnection using threaded exception hooks.
- **Discord Integration Enhancements**  
  - Route messages to and from Discord.
  - New configuration options and a dedicated `/discord_webhook` endpoint allow for inbound Discord message processing.
  - MQTT-aware response gating: set `respond_to_mqtt_messages` to true in `config.json` if you want the bot to respond to messages that arrive via MQTT. Off by default to prevent multiple server responses.
  - User‑initiated only: The AI does not auto‑message or greet new nodes; it responds only to explicit user input.
- **Commands modal & startup helper**
  - WebUI includes a Commands modal (button in the “Send a Message” header) that lists available commands with descriptions.
  - The current alias suffix and a one‑line commands list are printed at startup for easy reference.
- **Windows & Linux Focused**
  - Official support for Windows environments with installation guides; instructions for Linux available now - MacOS coming soon!

---

![image](https://github.com/user-attachments/assets/8ea74ff1-bb34-4e3e-9514-01a98a469cb2)

> An example of an awesome Raspberry Pi 5 powered mini terminal - running MESH-API & Ollama with HomeAssistant integration!
> - Top case model here by oinkers1: https://www.thingiverse.com/thing:6571150
> - Bottom Keyboard tray model here by mr_tbot: https://www.thingiverse.com/thing:7084222
> - Keyboard on Amazon here:  https://a.co/d/2dAC9ph

---

## Quick Start (Windows)

1. **Prerequisites**
   - **Python 3.11+** — Download from [python.org](https://www.python.org/downloads/). During install, check **“Add Python to PATH”**.
   - **Git** (optional) — [git-scm.com](https://git-scm.com/downloads/win) for cloning, or download the ZIP from GitHub.

2. **Download/Clone**
   - Clone the repository (or download and extract the ZIP):
     ```bash
     git clone https://github.com/mr-tbot/mesh-api.git
     cd mesh-api
     ```

3. **Create & Activate a Virtual Environment:**
     ```bash
     python -m venv venv
     .\venv\Scripts\activate
     ```

4. **Install Dependencies:**
     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```

5. **Configure Files:**
   - Edit `config.json`, `commands_config.json`, and `motd.json` as needed. Refer to the **Configuration** section below.
   - Or use the **Setup Wizard** on first launch in the WebUI.

6. **Start the Bot:**
   - Double-click `Run MESH-API - Windows.bat` or run:
     ```bash
     python mesh-api.py
     ```

7. **Access the WebUI Dashboard:**
   - Open your browser and navigate to [http://localhost:5000/dashboard](http://localhost:5000/dashboard).

---

## Quick Start (Ubuntu / Linux)

1. **Prerequisites**
   - Python 3.11+ and pip:
     ```bash
     sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
     ```
   - Grant serial port access (required for USB-connected Meshtastic devices):
     ```bash
     sudo usermod -aG dialout $USER
     ```
     Log out and back in for the group change to take effect.

2. **Download/Clone**
     ```bash
     git clone https://github.com/mr-tbot/mesh-api.git
     cd mesh-api
     ```

3. **Create & Activate a Virtual Environment:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

4. **Install Dependencies:**
     ```bash
     pip install --upgrade pip
     pip install -r requirements.txt
     ```

5. **Configure Files:**
   - Edit `config.json`, `commands_config.json`, and `motd.json` as needed. Refer to the **Configuration** section below.
   - Or use the **Setup Wizard** on first launch in the WebUI.

6. **Start the Bot:**
     ```bash
     python mesh-api.py
     ```

7. **Access the WebUI Dashboard:**
   - Open your browser and navigate to [http://localhost:5000/dashboard](http://localhost:5000/dashboard).


## Quick Start (Docker)

Multi-arch Docker images are published for **linux/amd64** (x86_64) and **linux/arm64** (Raspberry Pi 4/5, Apple Silicon).

1. **Prerequisites**
   - [Docker Engine](https://docs.docker.com/engine/install/) (or Docker Desktop) installed on your host.
   - A Meshtastic device connected via USB serial, Wi-Fi, or Bluetooth.

2. **Prepare the Volume Structure**
   - The `docker-required-volumes/` folder in the repository contains a ready-to-use `mesh-api/` directory with default configs, all 30 built-in extensions, and empty log files. Copy it to your working directory:
     ```bash
     git clone https://github.com/mr-tbot/mesh-api.git
     cd mesh-api
     cp -r docker-required-volumes/mesh-api ./mesh-api
     ```
   - Edit the config files inside `mesh-api/config/` before starting:

   ```
   mesh-api/
   ├── config/
   │   ├── config.json           # Core configuration (AI provider, connection, etc.)
   │   ├── commands_config.json   # Custom slash commands
   │   └── motd.json              # Message of the Day
   ├── extensions/                # All 30 built-in extensions (add your own here too)
   │   ├── __init__.py
   │   ├── base_extension.py
   │   ├── loader.py
   │   ├── discord/
   │   ├── telegram/
   │   ├── mqtt/
   │   └── ...  (30 built-in extensions)
   └── logs/
       ├── script.log
       ├── messages.log
       └── messages_archive.json
   ```

3. **Pull & Run with Docker Compose**
   - Copy the included `docker-compose.yml` to the same directory as your `mesh-api/` folder, then:
     ```bash
     docker compose pull
     docker compose up -d
     ```
   - **USB Serial devices:** Uncomment the `devices` and `/dev` volume lines in `docker-compose.yml` and set your serial device path (e.g. `/dev/ttyUSB0` or `/dev/ttyACM0`).
   - **Wi-Fi connection:** Set `use_wifi: true` and `wifi_host` in `mesh-api/config/config.json` — no device passthrough needed.

4. **Verify the Container:**
     ```bash
     docker compose logs -f mesh-api
     ```

5. **Access the WebUI Dashboard:**
   - Open your browser and navigate to [http://localhost:5000/dashboard](http://localhost:5000/dashboard).
   - On first launch the **Setup Wizard** will guide you through initial configuration.

> **Tip:** To add custom extensions, drop the extension folder into `mesh-api/extensions/` on the host — it's volume-mounted into the container so no rebuild is needed. Restart the container with `docker compose restart` to pick up new extensions.

---


## Supported Mesh Networks

MESH-API supports **two mesh radio platforms** that can operate independently or be **bridged together** for cross-network communication.

### Meshtastic (Primary)

[Meshtastic](https://meshtastic.org/) is MESH-API's primary mesh network. Connection is handled automatically by the core — just plug in your Meshtastic device and configure the connection method in `config.json`.

| Setting | Description |
|---------|-------------|
| `use_wifi` | Set `true` to connect via TCP/WiFi instead of USB serial |
| `wifi_host` | IP address of your Meshtastic node (when using WiFi) |
| `wifi_port` | TCP port (default `4403`) |
| `serial_port` | USB serial port (e.g. `/dev/ttyUSB0` or `COM3`) — leave empty for auto-detect |
| `serial_baud` | Baud rate (default `460800`) |
| `use_mesh_interface` | Set `true` for direct MeshInterface mode (no serial/WiFi) |

**All MESH-API features** — AI commands, slash commands, emergency alerts, extensions, WebUI dashboard — work natively over the Meshtastic connection.

### MeshCore (Extension-Based Bridge)

[MeshCore](https://meshcore.co.uk/) is a lightweight, multi-hop LoRa mesh firmware focused on embedded packet routing. MESH-API supports MeshCore through the **MeshCore extension** (`extensions/meshcore/`), which connects to a **separate** MeshCore companion-firmware device.

> **Hardware requirement:** You need **two separate LoRa devices** — one running Meshtastic (connected to MESH-API core) and one running MeshCore companion firmware (connected to the MeshCore extension via USB serial or TCP/WiFi). Each device has its own independent radio settings.

#### How It Works

```
┌──────────────┐           ┌──────────────┐           ┌──────────────┐
│  Meshtastic  │◀── USB ──▶│   MESH-API   │◀── USB ──▶│   MeshCore   │
│    Device    │  or WiFi  │   (Server)   │  or TCP   │   Companion  │
│              │           │              │           │    Device    │
└──────┬───────┘           └──────┬───────┘           └──────┬───────┘
       │                          │                          │
  Meshtastic                 Bridges chat              MeshCore
  Mesh Network              + commands                 Mesh Network
```

- **Bidirectional chat bridging** — Messages flow between configurable Meshtastic and MeshCore channels, tagged with their origin (`[MC]` for MeshCore, `[MT]` for Meshtastic) to show where each message came from.
- **Full command support** — MeshCore users can issue the same `/slash` commands that Meshtastic users can (AI queries, `/help`, `/emergency`, custom commands, etc.).
- **Direct message support** — Optionally bridge DMs between the two networks.
- **Emergency relay** — Emergency alerts triggered on either network are forwarded to the other.
- **Independent command processing** — MeshCore users get AI responses sent directly back to their MeshCore device without needing to go through Meshtastic.

#### MeshCore Quick Setup

1. **Install the MeshCore Python library:**
   ```bash
   pip install meshcore
   ```
   *(This is already included in `requirements.txt`)*

2. **Flash a companion device** with MeshCore companion firmware:
   - Visit [https://flasher.meshcore.co.uk](https://flasher.meshcore.co.uk)
   - Flash the **Companion** firmware type (Serial or WiFi variant depending on your setup)

3. **Enable the extension** — edit `extensions/meshcore/config.json`:
   ```json
   {
     "enabled": true,
     "connection_type": "serial",
     "serial_port": "COM5",
     "serial_baud": 115200,
     "bridge_enabled": true,
     "bridge_meshcore_channel_to_meshtastic_channel": { "0": 1 },
     "bridge_meshtastic_channels_to_meshcore_channel": { "1": 0 }
   }
   ```

4. **Restart MESH-API** — the extension will connect to the MeshCore device and begin bridging.

5. **Verify** — use the `/meshcore` command from either network, or visit `http://localhost:5000/api/meshcore/status`.

#### Channel Mapping

Channel mapping is defined by two config keys:

- **`bridge_meshcore_channel_to_meshtastic_channel`** — Maps MeshCore channel numbers to Meshtastic channel numbers. Example: `{"0": 1}` means MeshCore public channel 0 bridges to Meshtastic channel 1.
- **`bridge_meshtastic_channels_to_meshcore_channel`** — The reverse direction. Example: `{"1": 0}` means Meshtastic channel 1 bridges to MeshCore channel 0.

You can map multiple channels in each direction:
```json
{
  "bridge_meshcore_channel_to_meshtastic_channel": { "0": 1, "1": 2 },
  "bridge_meshtastic_channels_to_meshcore_channel": { "1": 0, "2": 1 }
}
```

#### Echo Prevention

The extension includes multiple layers of loop prevention:
- **Origin tags** (`[MC]` / `[MT]`) — messages carrying these tags are recognized as bridged and not re-bridged.
- **AI prefix detection** — AI-generated responses are not echoed back.
- **Rolling buffer** — a buffer of the last 50 bridged messages prevents exact duplicates.

#### Connection Types

| Type | Config | Description |
|------|--------|-------------|
| USB Serial | `"connection_type": "serial"` | Direct USB connection to a MeshCore companion device |
| TCP/WiFi | `"connection_type": "tcp"` | Network connection to a WiFi-enabled MeshCore companion |

See the full config reference in the [MeshCore Extension](#meshcore) section below.

---

<img width="2545" height="1272" alt="MESH-API-v0 6 0-FINAL" src="https://github.com/user-attachments/assets/49a26e2c-c5fc-4e84-aee9-531d9d38e2bc" />

The latest v0.6.0 Web-UI revamp!  NEW MAPS FEATURES AND TONS OF NEW GOODIES!

---

## Extensions Reference

> **Note:** The extensions system and all corresponding extensions are **new and largely untested**. Please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues) so they may be investigated and addressed.

Complete reference for all built-in extensions included with MESH-API.  
Each extension is a self-contained plugin in the `extensions/` directory with its own `config.json`, `extension.py`, and `__init__.py`.

**Quick start:** Enable any extension by setting `"enabled": true` in its `config.json` file and restarting MESH-API.

---

### Extensions Table of Contents

- **[Communication Extensions](#communication-extensions):** [Discord](#discord) · [Slack](#slack) · [Telegram](#telegram) · [Matrix](#matrix) · [Signal](#signal) · [WhatsApp](#whatsapp) · [Mattermost](#mattermost) · [Zello](#zello) · [MQTT (Extension)](#mqtt-extension) · [Webhook Generic](#webhook-generic) · [IMAP](#imap) · [Mastodon](#mastodon) · [n8n](#n8n)
- **[Notification Extensions](#notification-extensions):** [Apprise](#apprise) · [Ntfy](#ntfy) · [Pushover](#pushover) · [PagerDuty](#pagerduty) · [OpsGenie](#opsgenie)
- **[Emergency & Weather Extensions](#emergency--weather-extensions):** [NWS Alerts](#nws-alerts) · [OpenWeatherMap](#openweathermap) · [USGS Earthquakes](#usgs-earthquakes) · [GDACS](#gdacs) · [Amber Alerts](#amber-alerts) · [NASA Space Weather](#nasa-space-weather)
- **[Ham Radio & Off-Grid Extensions](#ham-radio--off-grid-extensions):** [Winlink](#winlink) · [APRS](#aprs) · [BBS](#bbs)
- **[Smart Home Extensions](#smart-home-extensions):** [Home Assistant (Extension)](#home-assistant-extension)
- **[Mesh Bridging Extensions](#mesh-bridging-extensions):** [MeshCore](#meshcore)
- **[AI Agent Extensions](#ai-agent-extensions):** [OpenClaw](#openclaw)

---

### Communication Extensions

#### Discord

Bidirectional bridge between Meshtastic mesh and a Discord channel.

**Commands:**
| Command | Description |
|---------|-------------|
| `/discord` | Show Discord integration status |

**Config (`extensions/discord/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `webhook_url` | string | `""` | Discord webhook URL for outbound messages |
| `bot_token` | string | `""` | Bot token for reading Discord messages |
| `channel_id` | string | `""` | Discord channel ID to bridge |
| `poll_interval_seconds` | int | `5` | How often to poll for new Discord messages |
| `forward_to_mesh` | bool | `true` | Forward Discord messages to mesh |
| `mesh_channel_index` | int | `0` | Mesh channel to bridge |
| `bot_name` | string | `"MESH-API"` | Display name for webhook posts |

**Hooks:** `on_message` (forwards mesh→Discord), `on_emergency` (posts alerts), Flask route `/discord_webhook`.

---

#### Slack

Bidirectional Slack integration using Bot API and incoming webhooks.

**Commands:**
| Command | Description |
|---------|-------------|
| `/slack` | Show Slack integration status |

**Config (`extensions/slack/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `bot_token` | string | `""` | Slack Bot User OAuth Token (`xoxb-...`) |
| `webhook_url` | string | `""` | Incoming webhook URL for outbound messages |
| `channel_id` | string | `""` | Slack channel ID to bridge |
| `poll_interval_seconds` | int | `10` | Polling interval for new messages |
| `forward_to_mesh` | bool | `true` | Forward Slack messages to mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `bot_name` | string | `"MESH-API"` | Bot display name |

**Hooks:** `on_message`, `on_emergency`.

---

#### Telegram

Bidirectional Telegram bot bridge using the Bot API with `getUpdates` long-polling.

**Commands:**
| Command | Description |
|---------|-------------|
| `/telegram` | Show Telegram bot status |

**Config (`extensions/telegram/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `bot_token` | string | `""` | Telegram Bot API token from @BotFather |
| `chat_id` | string | `""` | Target chat/group/channel ID |
| `poll_interval_seconds` | int | `5` | Polling interval |
| `forward_to_mesh` | bool | `true` | Forward Telegram→mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `parse_mode` | string | `"HTML"` | Telegram parse mode |

**Hooks:** `on_message`, `on_emergency`.

---

#### Matrix

Bidirectional Matrix (Element) bridge using the Client-Server API.

**Commands:**
| Command | Description |
|---------|-------------|
| `/matrix` | Show Matrix connection status |

**Config (`extensions/matrix/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `homeserver_url` | string | `""` | Matrix homeserver (e.g. `https://matrix.org`) |
| `access_token` | string | `""` | Matrix access token |
| `room_id` | string | `""` | Room ID to bridge (`!abc:matrix.org`) |
| `user_id` | string | `""` | Bot user ID (`@bot:matrix.org`) |
| `poll_interval_seconds` | int | `5` | Sync polling interval |
| `forward_to_mesh` | bool | `true` | Forward Matrix→mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |

**Hooks:** `on_message`, `on_emergency`.

---

#### Signal

Bidirectional Signal bridge using the signal-cli-rest-api.

**Commands:**
| Command | Description |
|---------|-------------|
| `/signal` | Show Signal integration status |

**Config (`extensions/signal/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `signal_api_url` | string | `"http://localhost:8080"` | signal-cli REST API URL |
| `phone_number` | string | `""` | Registered Signal phone number |
| `recipient` | string | `""` | Recipient number or group ID |
| `poll_interval_seconds` | int | `5` | Polling interval |
| `forward_to_mesh` | bool | `true` | Forward Signal→mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |

**Hooks:** `on_message`, `on_emergency`.

---

#### WhatsApp

Bidirectional WhatsApp bridge using the Meta WhatsApp Business Cloud API. Outbound messages are sent via the Cloud API; inbound messages are received via a webhook endpoint registered with Meta.

**Commands:**
| Command | Description |
|---------|-------------|
| `/whatsapp` | Show WhatsApp integration status |

**Config (`extensions/whatsapp/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `api_url` | string | `"https://graph.facebook.com/v21.0"` | WhatsApp Cloud API base URL |
| `phone_number_id` | string | `""` | WhatsApp Business phone number ID |
| `access_token` | string | `""` | System User permanent token |
| `verify_token` | string | `""` | Webhook verification token (you choose this) |
| `recipient_number` | string | `""` | Default recipient in E.164 format (e.g. `+15551234567`) |
| `send_emergency` | bool | `false` | Forward emergency alerts to WhatsApp |
| `send_ai` | bool | `false` | Forward AI responses to WhatsApp |
| `send_all` | bool | `false` | Forward all mesh messages to WhatsApp |
| `receive_enabled` | bool | `true` | Accept inbound WhatsApp messages |
| `inbound_channel_index` | int\|null | `null` | Mesh channel filter for outbound |
| `webhook_path` | string | `"/whatsapp/webhook"` | Flask endpoint for Meta webhook |
| `broadcast_channel_index` | int | `0` | Mesh channel for inbound messages |
| `bot_name` | string | `"MESH-API"` | Bot display name |

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/whatsapp/webhook` | GET | Meta webhook verification (hub challenge) |
| `/whatsapp/webhook` | POST | Receive inbound WhatsApp messages |

**Hooks:** `on_message`, `on_emergency`, Flask routes for inbound webhook.

---

#### Mattermost

Bidirectional Mattermost bridge using REST API + incoming webhook.

**Commands:**
| Command | Description |
|---------|-------------|
| `/mattermost` | Show Mattermost integration status |

**Config (`extensions/mattermost/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `server_url` | string | `""` | Mattermost server URL |
| `access_token` | string | `""` | Personal access token or bot token |
| `channel_id` | string | `""` | Channel ID to bridge |
| `webhook_url` | string | `""` | Incoming webhook URL |
| `poll_interval_seconds` | int | `10` | Polling interval |
| `forward_to_mesh` | bool | `true` | Forward Mattermost→mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `bot_name` | string | `"MESH-API"` | Bot display name |

**Hooks:** `on_message`, `on_emergency`.

---

#### Zello

Outbound message forwarding to Zello Work PTT channels.

**Commands:**
| Command | Description |
|---------|-------------|
| `/zello` | Show Zello status |

**Config (`extensions/zello/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `api_url` | string | `""` | Zello Work API URL |
| `api_token` | string | `""` | Zello API token |
| `channel_name` | string | `""` | Target Zello channel |
| `forward_mesh_messages` | bool | `true` | Forward mesh→Zello |

**Hooks:** `on_message`, `on_emergency`.

---

#### MQTT (Extension)

Bidirectional MQTT messaging with JSON payloads and optional TLS.

**Commands:**
| Command | Description |
|---------|-------------|
| `/mqtt` | Show MQTT broker status |

**Config (`extensions/mqtt/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `broker_host` | string | `"localhost"` | MQTT broker hostname |
| `broker_port` | int | `1883` | MQTT broker port |
| `username` | string | `""` | MQTT username |
| `password` | string | `""` | MQTT password |
| `topic_publish` | string | `"mesh-api/outbound"` | Publish topic |
| `topic_subscribe` | string | `"mesh-api/inbound"` | Subscribe topic |
| `topic_emergency` | string | `"mesh-api/emergency"` | Emergency topic |
| `use_tls` | bool | `false` | Enable TLS |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `qos` | int | `1` | MQTT QoS level |
| `client_id` | string | `"mesh-api"` | MQTT client ID |

**Hooks:** `on_message`, `on_emergency`.

---

#### Webhook Generic

Fully configurable bidirectional HTTP webhook with HMAC verification.

**Commands:**
| Command | Description |
|---------|-------------|
| `/webhook` | Show webhook status |

**Config (`extensions/webhook_generic/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `outbound_url` | string | `""` | URL to POST outbound messages to |
| `outbound_method` | string | `"POST"` | HTTP method |
| `outbound_headers` | object | `{}` | Custom headers |
| `outbound_template` | string | `""` | JSON body template (`{message}`, `{sender}` placeholders) |
| `hmac_secret` | string | `""` | HMAC-SHA256 secret for inbound verification |
| `inbound_message_field` | string | `"message"` | JSON field containing the message |
| `broadcast_channel_index` | int | `0` | Mesh channel index |

**Hooks:** `on_message`, `on_emergency`. Flask route for inbound webhooks.

---

#### IMAP

Inbound email monitoring with subject/sender filtering.

**Commands:**
| Command | Description |
|---------|-------------|
| `/imap` | Show IMAP monitoring status |

**Config (`extensions/imap/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `imap_server` | string | `""` | IMAP server hostname |
| `imap_port` | int | `993` | IMAP port |
| `username` | string | `""` | Email username |
| `password` | string | `""` | Email password |
| `use_ssl` | bool | `true` | Use SSL/TLS |
| `folder` | string | `"INBOX"` | Mailbox folder |
| `poll_interval_seconds` | int | `60` | Polling interval |
| `subject_filter` | string | `""` | Only forward emails matching this subject |
| `sender_filter` | string | `""` | Only forward emails from this sender |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `max_body_length` | int | `250` | Max message body length |
| `mark_as_read` | bool | `true` | Mark processed emails as read |

**Hooks:** `on_emergency` (none — inbound only).

---

#### Mastodon

Fediverse / Mastodon bridge for posting toots and reading timeline from the mesh.

**Commands:**
| Command | Description |
|---------|-------------|
| `/toot <message>` | Post a toot from the mesh |
| `/fedi status` | Show Mastodon account info |
| `/fedi timeline [n]` | Show home timeline (last n posts) |

**Config (`extensions/mastodon/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `instance_url` | string | `"https://mastodon.social"` | Mastodon instance URL |
| `access_token` | string | `""` | Application access token (read+write) |
| `default_visibility` | string | `"public"` | Post visibility (`public`, `unlisted`, `private`, `direct`) |
| `post_prefix` | string | `"📡 [Mesh]"` | Prefix for toots |
| `max_toot_length` | int | `500` | Maximum toot length |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `auto_post_emergency` | bool | `true` | Post emergencies to Mastodon |
| `poll_mentions` | bool | `false` | Poll for @mentions |
| `poll_interval_seconds` | int | `120` | Mention polling interval |
| `forward_mentions_to_mesh` | bool | `true` | Forward mentions to mesh |
| `hashtags` | array | `["meshtastic", "meshnetwork"]` | Hashtags appended to toots |
| `content_warning` | string | `""` | Default content warning / spoiler text |

**Hooks:** `on_emergency` (auto-post).

---

#### n8n

Bidirectional workflow automation bridge with [n8n](https://n8n.io). Forward mesh messages and emergencies to n8n webhook triggers, receive messages from n8n workflows, query instance status, and list or trigger workflows from the mesh.

**Commands:**
| Command | Description |
|---------|-------------|
| `/n8n` | Show n8n integration status |
| `/n8n trigger <id>` | Trigger (activate) an n8n workflow by ID |
| `/n8n workflows` | List active n8n workflows |

**Config (`extensions/n8n/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `webhook_url` | string | `""` | n8n Webhook Trigger URL for outbound messages |
| `webhook_secret` | string | `""` | Shared secret sent as `X-Webhook-Secret` header |
| `api_base_url` | string | `"http://localhost:5678"` | n8n instance base URL |
| `api_key` | string | `""` | n8n API key (Settings → API → Create Key) |
| `send_emergency` | bool | `true` | Forward emergency alerts to n8n |
| `send_ai` | bool | `false` | Forward AI responses to n8n |
| `send_all` | bool | `false` | Forward all mesh messages to n8n |
| `receive_enabled` | bool | `true` | Accept inbound messages from n8n |
| `receive_endpoint` | string | `"/n8n/webhook"` | Flask endpoint for inbound n8n→mesh messages |
| `receive_secret` | string | `""` | Shared secret for inbound verification |
| `inbound_channel_index` | int/null | `null` | Default mesh channel for inbound messages |
| `message_field` | string | `"message"` | JSON field containing the message text |
| `sender_field` | string | `"sender"` | JSON field containing the sender name |
| `include_metadata` | bool | `true` | Include metadata in outbound payloads |
| `poll_executions` | bool | `false` | Poll n8n for completed workflow executions |
| `poll_interval_seconds` | int | `60` | Execution polling interval |
| `broadcast_channel_index` | int | `0` | Mesh channel index for broadcasts |
| `bot_name` | string | `"MESH-API"` | Source name in outbound payloads |

**Hooks:** `on_message`, `on_emergency`. Flask route for inbound webhooks.

---

### Notification Extensions

#### Apprise

Universal notification gateway supporting 100+ services through URL-based configuration.

**Commands:**
| Command | Description |
|---------|-------------|
| `/notify <message>` | Send notification via all configured Apprise URLs |

**Config (`extensions/apprise/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `apprise_urls` | array | `[]` | List of Apprise notification URLs |
| `notify_on_emergency` | bool | `true` | Auto-notify on emergency |
| `default_title` | string | `"MESH-API"` | Notification title |
| `default_type` | string | `"info"` | Notification type (`info`, `warning`, `failure`, `success`) |

Apprise URL examples: `slack://token`, `telegram://bot_token/chat_id`, `discord://webhook_id/webhook_token`, etc. See [Apprise docs](https://github.com/caronc/apprise/wiki) for 100+ supported services.

**Hooks:** `on_emergency`.

---

#### Ntfy

Push notifications via [ntfy.sh](https://ntfy.sh) with SSE-based inbound subscription.

**Commands:**
| Command | Description |
|---------|-------------|
| `/ntfy <message>` | Send ntfy push notification |

**Config (`extensions/ntfy/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `server_url` | string | `"https://ntfy.sh"` | ntfy server URL |
| `topic` | string | `""` | ntfy topic name |
| `token` | string | `""` | Access token (optional) |
| `priority` | int | `3` | Default priority (1-5) |
| `tags` | string | `"mesh,meshtastic"` | Comma-separated tags |
| `notify_on_emergency` | bool | `true` | Auto-notify on emergency |
| `subscribe_inbound` | bool | `false` | Subscribe for inbound messages |
| `broadcast_channel_index` | int | `0` | Mesh channel index |

**Hooks:** `on_emergency`.

---

#### Pushover

Push notifications via the Pushover API with priority levels.

**Commands:**
| Command | Description |
|---------|-------------|
| `/pushover <message>` | Send Pushover notification |

**Config (`extensions/pushover/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `api_token` | string | `""` | Pushover application API token |
| `user_key` | string | `""` | Pushover user/group key |
| `default_priority` | int | `0` | Default priority (-2 to 2) |
| `emergency_priority` | int | `2` | Priority for emergency alerts |
| `default_sound` | string | `"pushover"` | Notification sound |
| `device` | string | `""` | Target device (blank = all) |
| `retry` | int | `60` | Retry interval for emergency priority (seconds) |
| `expire` | int | `3600` | Expiry for emergency priority (seconds) |
| `notify_on_emergency` | bool | `true` | Auto-notify on emergency |

**Hooks:** `on_emergency`.

---

#### PagerDuty

PagerDuty incident management — trigger, acknowledge, and resolve incidents from the mesh.

**Commands:**
| Command | Description |
|---------|-------------|
| `/pd trigger <summary>` | Create a PagerDuty incident |
| `/pd ack <incident_id>` | Acknowledge an incident |
| `/pd resolve <incident_id>` | Resolve an incident |
| `/pd status` | List open incidents |

**Config (`extensions/pagerduty/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `routing_key` | string | `""` | Events API v2 integration/routing key |
| `api_token` | string | `""` | REST API token (for ack/resolve/list) |
| `service_id` | string | `""` | Service ID to filter incidents |
| `default_severity` | string | `"warning"` | Default severity (`critical`, `error`, `warning`, `info`) |
| `escalation_policy_id` | string | `""` | Escalation policy ID |
| `trigger_on_emergency` | bool | `true` | Auto-trigger on emergency broadcasts |
| `trigger_on_keywords` | array | `["SOS", "MAYDAY", "EMERGENCY"]` | Keywords that trigger incidents |
| `auto_resolve_minutes` | int | `0` | Auto-resolve after N minutes (0 = off) |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `poll_incidents` | bool | `false` | Poll and broadcast new incidents |
| `poll_interval_seconds` | int | `120` | Polling interval |
| `dedup_key_prefix` | string | `"mesh-api"` | Deduplication key prefix |

**Hooks:** `on_emergency`, `on_message` (keyword matching).

---

#### OpsGenie

Atlassian OpsGenie alert management from the mesh.

**Commands:**
| Command | Description |
|---------|-------------|
| `/og alert <message>` | Create an OpsGenie alert |
| `/og ack <id>` | Acknowledge an alert |
| `/og close <id>` | Close an alert |
| `/og status` | List open alerts |

**Config (`extensions/opsgenie/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `api_key` | string | `""` | OpsGenie API key (GenieKey) |
| `api_base` | string | `"https://api.opsgenie.com"` | API base URL |
| `default_priority` | string | `"P3"` | Default priority (P1-P5) |
| `responders` | array | `[]` | Responder list (OpsGenie format) |
| `tags` | array | `["mesh-api", "meshtastic"]` | Alert tags |
| `trigger_on_emergency` | bool | `true` | Auto-trigger on emergency |
| `trigger_on_keywords` | array | `["SOS", "MAYDAY", "EMERGENCY"]` | Keywords that trigger alerts |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `poll_alerts` | bool | `false` | Poll and broadcast new alerts |
| `poll_interval_seconds` | int | `120` | Polling interval |
| `auto_close_minutes` | int | `0` | Auto-close after N minutes (0 = off) |

**Hooks:** `on_emergency`, `on_message` (keyword matching).

---

### Emergency & Weather Extensions

#### NWS Alerts

National Weather Service severe weather alerts with zone-based filtering.

**Commands:**
| Command | Description |
|---------|-------------|
| `/nws` | Show active NWS alerts for configured zones |
| `/nwszones` | Show configured alert zones |

**Config (`extensions/nws_alerts/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `zones` | array | `[]` | NWS zone codes (e.g. `["TXC453", "TXZ211"]`) |
| `poll_interval_seconds` | int | `300` | Polling interval |
| `min_severity` | string | `"Moderate"` | Minimum severity (`Minor`, `Moderate`, `Severe`, `Extreme`) |
| `min_urgency` | string | `"Expected"` | Minimum urgency |
| `min_certainty` | string | `"Likely"` | Minimum certainty |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `auto_broadcast` | bool | `true` | Auto-broadcast new alerts |
| `max_alert_length` | int | `300` | Max alert text length |

**Hooks:** `on_emergency` (none — outbound broadcast only).

---

#### OpenWeatherMap

Weather data including current conditions, forecasts, and severe weather alerts.

**Commands:**
| Command | Description |
|---------|-------------|
| `/weather [city]` | Current weather for a city or default location |
| `/forecast [city]` | 5-day forecast |
| `/wxalerts` | Active weather alerts for configured coordinates |

**Config (`extensions/openweathermap/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `api_key` | string | `""` | OpenWeatherMap API key |
| `default_city` | string | `""` | Default city for queries |
| `default_lat` | string | `""` | Latitude for alerts (One Call 3.0) |
| `default_lon` | string | `""` | Longitude for alerts |
| `units` | string | `"imperial"` | Units (`imperial`, `metric`, `standard`) |
| `poll_interval_seconds` | int | `600` | Alert polling interval |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `auto_broadcast_alerts` | bool | `true` | Auto-broadcast severe weather |
| `max_alert_length` | int | `250` | Max alert text length |

**Hooks:** `on_emergency` (none — outbound only).

---

#### USGS Earthquakes

USGS earthquake monitoring with magnitude and radius filtering.

**Commands:**
| Command | Description |
|---------|-------------|
| `/quake` | Show recent earthquakes matching filters |
| `/quakeconfig` | Show current earthquake monitor config |

**Config (`extensions/usgs_earthquakes/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `min_magnitude` | float | `4.0` | Minimum magnitude to report |
| `filter_lat` | string | `""` | Center latitude for radius filter |
| `filter_lon` | string | `""` | Center longitude |
| `filter_radius_km` | int | `500` | Radius in km (0 = worldwide) |
| `poll_interval_seconds` | int | `300` | Polling interval |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `auto_broadcast` | bool | `true` | Auto-broadcast new quakes |
| `include_tsunami_warning` | bool | `true` | Include tsunami flag |
| `max_results` | int | `5` | Max results per query |

**Hooks:** `on_emergency` (none — outbound only).

---

#### GDACS

Global Disaster Alerting Coordination System — monitors 6 disaster types worldwide.

**Commands:**
| Command | Description |
|---------|-------------|
| `/gdacs [type]` | Show GDACS alerts (optional type filter: EQ, TC, FL, VO, DR, WF) |

**Config (`extensions/gdacs/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `alert_levels` | array | `["Orange", "Red"]` | Alert levels to include (`Green`, `Orange`, `Red`) |
| `disaster_types` | array | `["EQ", "TC", "FL", "VO", "DR", "WF"]` | Disaster types |
| `filter_lat` | string | `""` | Center latitude for proximity filter |
| `filter_lon` | string | `""` | Center longitude |
| `filter_radius_km` | int | `0` | Radius (0 = all global) |
| `poll_interval_seconds` | int | `600` | Polling interval |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `auto_broadcast` | bool | `true` | Auto-broadcast new alerts |
| `max_alert_length` | int | `300` | Max alert text length |

Disaster type codes: **EQ** = Earthquake, **TC** = Tropical Cyclone, **FL** = Flood, **VO** = Volcano, **DR** = Drought, **WF** = Wildfire.

**Hooks:** `on_emergency` (none — outbound only).

---

#### Amber Alerts

Missing person alerts (AMBER, Silver, Blue) from the NWS CAP feed with state filtering.

**Commands:**
| Command | Description |
|---------|-------------|
| `/amber` | Show active AMBER alerts |
| `/silver` | Show active Silver alerts |
| `/blue` | Show active Blue alerts |

**Config (`extensions/amber_alerts/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `states` | array | `[]` | State codes to filter (e.g. `["TX", "CA"]`, empty = all) |
| `poll_interval_seconds` | int | `300` | Polling interval |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `auto_broadcast` | bool | `true` | Auto-broadcast new alerts |
| `max_alert_length` | int | `300` | Max alert text length |
| `include_silver` | bool | `true` | Include Silver (elderly) alerts |
| `include_blue` | bool | `true` | Include Blue (law enforcement) alerts |

**Hooks:** `on_emergency` (none — outbound only).

---

#### NASA Space Weather

NASA DONKI (Database Of Notifications, Knowledge, Information) space weather monitor — tracks geomagnetic storms, solar flares, coronal mass ejections, and more.

**Commands:**
| Command | Description |
|---------|-------------|
| `/spaceweather` | Show recent space weather events |
| `/solarflare` | Show recent solar flare activity |
| `/geomagstorm` | Show recent geomagnetic storms |

**Config (`extensions/nasa_space_weather/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `api_key` | string | `"DEMO_KEY"` | NASA API key (free at [api.nasa.gov](https://api.nasa.gov)) |
| `poll_interval_seconds` | int | `600` | Polling interval |
| `auto_broadcast` | bool | `true` | Auto-broadcast new events |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `event_types` | array | `["GST","FLR","CME","IPS","SEP","RBE"]` | Event types to monitor |
| `min_kp_index` | int | `5` | Min Kp index for geomagnetic storm alerts (1-9) |
| `min_flare_class` | string | `"M"` | Min solar flare class to broadcast (`A`,`B`,`C`,`M`,`X`) |
| `lookback_days` | int | `3` | Days of history to query |
| `max_alert_length` | int | `300` | Max alert text length |
| `max_results` | int | `5` | Max results per command query |

**Event Types:**
| Code | Description |
|------|-------------|
| `GST` | Geomagnetic Storm — Kp index & G-scale impact |
| `FLR` | Solar Flare — class (A/B/C/M/X) & source region |
| `CME` | Coronal Mass Ejection — speed & direction |
| `IPS` | Interplanetary Shock |
| `SEP` | Solar Energetic Particle |
| `RBE` | Radiation Belt Enhancement |

**Hooks:** `on_emergency` (none — outbound only).

---

### Ham Radio & Off-Grid Extensions

#### Winlink

Winlink Global Radio Email gateway for ham radio operators.

**Commands:**
| Command | Description |
|---------|-------------|
| `/winlink <address> <message>` | Send a Winlink email |
| `/wlcheck` | Check for new Winlink messages |
| `/wlstatus` | Show Winlink connection status |

**Config (`extensions/winlink/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `callsign` | string | `""` | Ham radio callsign |
| `gateway_host` | string | `""` | RMS gateway hostname |
| `gateway_port` | int | `8772` | RMS gateway port |
| `password` | string | `""` | Winlink password |
| `poll_interval_seconds` | int | `300` | Mailbox polling interval |
| `auto_forward_to_mesh` | bool | `true` | Auto-forward new mail to mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `max_body_length` | int | `250` | Max message body length |
| `outbound_enabled` | bool | `true` | Allow sending outbound messages |
| `winlink_api_url` | string | `"https://api.winlink.org"` | Winlink REST API URL |
| `winlink_api_key` | string | `""` | Winlink API key |
| `rms_relay_path` | string | `""` | RMS relay path |
| `default_to_address` | string | `""` | Default recipient for emergency forwarding |

Integration methods (priority order): Winlink REST API → Pat local client → RMS gateway.

**Hooks:** `on_emergency` (forwards emergency to default address).

---

#### APRS

Automatic Packet Reporting System integration for position and message bridging.

**Commands:**
| Command | Description |
|---------|-------------|
| `/aprs <callsign>` | Look up station position via aprs.fi |
| `/aprsmsg <call> <message>` | Send APRS message via APRS-IS |
| `/aprsnear` | Show nearby APRS stations |

**Config (`extensions/aprs/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `callsign` | string | `""` | Ham radio callsign |
| `passcode` | string | `""` | APRS-IS passcode |
| `aprs_is_server` | string | `"rotate.aprs2.net"` | APRS-IS server |
| `aprs_is_port` | int | `14580` | APRS-IS port |
| `aprs_fi_api_key` | string | `""` | aprs.fi API key (free) |
| `filter_range_km` | int | `100` | Position filter radius |
| `filter_lat` | string | `""` | Filter center latitude |
| `filter_lon` | string | `""` | Filter center longitude |
| `poll_interval_seconds` | int | `60` | De-dupe interval for positions |
| `auto_broadcast_positions` | bool | `false` | Broadcast nearby APRS positions to mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `send_position_to_aprs` | bool | `false` | Publish mesh positions to APRS-IS |
| `position_comment` | string | `"MESH-API Node"` | APRS position comment |
| `symbol_table` | string | `"/"` | APRS symbol table |
| `symbol_code` | string | `"-"` | APRS symbol code |
| `message_ssid` | string | `"-5"` | SSID for outbound messages |

**Note:** Transmitting on APRS requires a valid amateur radio licence.

**Hooks:** None (command-driven + background listener).

---

#### BBS

Full-featured Bulletin Board System with SQLite store-and-forward messaging.

**Commands:**
| Command | Description |
|---------|-------------|
| `/bbs help` | Show all BBS commands |
| `/bbs boards` | List available boards |
| `/bbs read <board> [n]` | Read last n messages (default 5, max 20) |
| `/bbs post <board> <msg>` | Post a message |
| `/bbs search <text>` | Search across all boards |
| `/bbs msg <node_id> <msg>` | Send a private message |
| `/bbs inbox` | Check private messages |
| `/bbs new <name>` | Create a new board |
| `/bbs del <board> <id>` | Delete your own message |
| `/bbs info` | Show BBS statistics |

**Config (`extensions/bbs/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `db_filename` | string | `"bbs.db"` | SQLite database filename |
| `board_name` | string | `"MESH-BBS"` | BBS display name |
| `motd` | string | `"Welcome to the Mesh BBS!"` | Message of the day |
| `max_messages_per_board` | int | `500` | Max messages per board (oldest auto-deleted) |
| `max_message_length` | int | `500` | Max message character length |
| `max_boards` | int | `20` | Maximum number of boards |
| `default_boards` | array | `["general", "emergency", "trading", "tech"]` | Default boards created on init |
| `allow_private_messages` | bool | `true` | Enable private messaging |
| `message_retention_days` | int | `90` | Auto-delete messages older than N days |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `announce_new_posts` | bool | `true` | Broadcast new post announcements |
| `require_shortname` | bool | `true` | Require node shortname |

**Database:** SQLite (`bbs.db`) stored in the extension directory. Three tables: `boards`, `messages`, `private_messages`. Automatic cleanup runs every 6 hours.

**Hooks:** None (fully command-driven).

---

### Smart Home Extensions

#### Home Assistant (Extension)

Routes mesh messages to the Home Assistant Conversation API as an AI provider.

This extension functions as an **AI provider** — when `ai_provider` is set to `"home_assistant"` in the main `config.json`, AI queries are routed through HA's conversation API.

**Config (`extensions/home_assistant/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `ha_url` | string | `""` | Home Assistant URL (e.g. `http://homeassistant.local:8123`) |
| `ha_token` | string | `""` | Long-lived access token |
| `ha_channel_index` | int | `-1` | Mesh channel for HA (-1 = DM only) |
| `ha_pin` | string | `""` | Optional PIN to protect access |
| `ha_language` | string | `"en"` | Conversation language |

**Hooks:** AI provider via `get_ai_response()`.

---

### Mesh Bridging Extensions

#### MeshCore

Bidirectional bridge between the Meshtastic mesh network and a [MeshCore](https://meshcore.co.uk/) mesh network. Requires a separate MeshCore companion-firmware device connected via USB serial or TCP/WiFi. See also [Supported Mesh Networks — MeshCore](#meshcore-extension-based-bridge) above for setup instructions.

**Commands:**
| Command | Description |
|---------|-------------|
| `/meshcore` | Show MeshCore bridge status (connected device, bridge state, channel map) |

**Config (`extensions/meshcore/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `connection_type` | string | `"serial"` | `"serial"` or `"tcp"` |
| `serial_port` | string | `""` | Serial port for the MeshCore companion device (e.g. `COM5`, `/dev/ttyACM0`) |
| `serial_baud` | int | `115200` | Serial baud rate |
| `tcp_host` | string | `""` | TCP/WiFi host (when `connection_type` is `"tcp"`) |
| `tcp_port` | int | `5000` | TCP port for MeshCore WiFi companion |
| `bridge_enabled` | bool | `true` | Enable bidirectional channel bridging |
| `bridge_meshcore_channel_to_meshtastic_channel` | object | `{"0": 1}` | Map MeshCore channel → Meshtastic channel |
| `bridge_meshtastic_channels_to_meshcore_channel` | object | `{"1": 0}` | Map Meshtastic channel → MeshCore channel |
| `bridge_dm` | bool | `false` | Bridge direct messages between networks |
| `commands_enabled` | bool | `true` | Allow MeshCore users to issue `/commands` |
| `ai_commands_enabled` | bool | `true` | Allow MeshCore users to send AI queries |
| `meshcore_origin_tag` | string | `"[MC]"` | Tag prepended to messages originating from MeshCore |
| `meshtastic_origin_tag` | string | `"[MT]"` | Tag prepended to messages originating from Meshtastic |
| `emergency_relay` | bool | `true` | Relay emergency alerts between networks |
| `max_message_length` | int | `200` | Max characters per bridged message |
| `reconnect_interval` | int | `30` | Seconds between reconnect attempts on disconnect |

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/meshcore/status` | GET | Returns JSON with connection status, bridge state, and channel mappings |

**Hooks:** `on_message()` (outbound Meshtastic→MeshCore bridging), `on_load()` / `on_unload()` (lifecycle).

---

### AI Agent Extensions

#### OpenClaw

Bridges the Meshtastic mesh network to an [OpenClaw](https://openclaw.dev) AI agent instance. Mesh users can query the OpenClaw agent via slash commands; the agent can fan-out responses through its own channels (Telegram, Discord, SMS, etc.). Emergency alerts are optionally forwarded to OpenClaw for multi-channel distribution. An optional polling mode injects proactive messages (scheduled alerts, reminders) from OpenClaw into the mesh.

**Commands:**
| Command | Description |
|---------|-------------|
| `/claw-XY` | Query the OpenClaw AI agent (XY = your install suffix) |
| `/agent-XY` | Alias for `/claw-XY` |

**Config (`extensions/openclaw/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `openclaw_url` | string | `"http://localhost:18789"` | OpenClaw gateway API URL |
| `openclaw_token` | string | `""` | Bearer token for OpenClaw authentication (optional) |
| `agent_name` | string | `"mesh-api"` | Agent name to address in OpenClaw |
| `allowed_nodes` | array | `[]` | Node IDs allowed to use OpenClaw (empty = all nodes) |
| `forward_emergency` | bool | `true` | Forward `/emergency` alerts to OpenClaw |
| `timeout` | int | `15` | HTTP request timeout in seconds |
| `poll_enabled` | bool | `false` | Poll OpenClaw for proactively queued messages |
| `poll_interval` | int | `30` | Polling interval in seconds |

**Hooks:** `handle_command()` (query agent), `on_emergency()` (forward alerts), `send_message()` (relay tagged messages), `receive_message()` (poll queue).

**Companion Skill:** A MESH-API skill file for OpenClaw is included at `openclaw-release/skills/mesh-api/SKILL.md` — copy it to `~/.openclaw/skills/mesh-api/SKILL.md` to teach an OpenClaw agent how to interact with MESH-API's REST API. If you install the `@mesh-api/openclaw-meshtastic` plugin via npm, the skill ships automatically.

**OpenClaw Community Plugin:** A full OpenClaw-native TypeScript plugin is being prepared for release as `@mesh-api/openclaw-meshtastic` — see the [OpenClaw Integration & Community Plugin](#openclaw-integration--community-plugin) section below for the full plan.

---

### Extension Management

**Listing Extensions:** Use the `/extensions` command on the mesh to see all loaded extensions and their status.

**Enabling/Disabling:** Edit the extension's `config.json` and set `"enabled": true` or `"enabled": false`, then restart MESH-API.

**Extension Loading:** Extensions are automatically discovered from the `extensions_path` directory (default: `./extensions`). Each subfolder containing an `extension.py` file is loaded. Folders starting with `_` (like `_example`) are skipped.

---

## Developing Custom Extensions

> A step-by-step guide for building custom extensions for the MESH-API plugin system.

### Overview

MESH-API uses a plugin-based extension system where each extension is a self-contained Python package that lives in the `extensions/` directory. Extensions can:

- Register slash commands accessible from the mesh network
- Send and receive messages to/from the mesh
- React to emergency broadcasts
- Observe all inbound mesh messages
- Expose HTTP endpoints via Flask
- Run background threads for polling external services
- Act as AI providers

Extensions are automatically discovered and loaded at startup. No changes to core code are required.

### Quick Start (Extensions)

1. **Copy the template:**
   ```bash
   cp -r extensions/_example extensions/my_extension
   ```

2. **Edit the three files:**
   - `__init__.py` — leave empty (marks the folder as a Python package)
   - `config.json` — define your settings (must include `"enabled": true`)
   - `extension.py` — implement your extension class

3. **Restart MESH-API** — your extension is auto-discovered and loaded.

4. **Verify** — send `/extensions` on the mesh to see it listed.

### Extension Structure

Every extension lives in its own subfolder under `extensions/`:

```
extensions/
├── base_extension.py        # Abstract base class (DO NOT MODIFY)
├── loader.py                 # Extension loader (DO NOT MODIFY)
├── __init__.py
└── my_extension/             # Your extension folder
    ├── __init__.py           # Empty file (required)
    ├── config.json           # Extension configuration
    └── extension.py          # Extension implementation
```

**Naming Rules:**
- Folder names must be valid Python identifiers (lowercase, underscores OK)
- Folders starting with `_` are **skipped** by the loader (used for templates)
- The class inside `extension.py` must subclass `BaseExtension`
- Class name convention: `<Name>Extension` (e.g. `MyExtension`)

### Base Class API Reference

Every extension inherits from `BaseExtension`. Here's the complete API:

**Constructor (automatic):**

```python
def __init__(self, extension_dir: str, app_context: dict):
```

You do **not** override `__init__`. The base class handles:
- `self.extension_dir` — absolute path to your extension's folder
- `self.app_context` — shared dict with core helpers (see below)
- `self._config` — loaded from your `config.json`

**Required Properties (must override):**

| Property | Returns | Description |
|----------|---------|-------------|
| `name` | `str` | Human-readable name (e.g. `"My Extension"`) |
| `version` | `str` | Semantic version (e.g. `"1.0.0"`) |

**Built-in Properties (inherited):**

| Property | Returns | Description |
|----------|---------|-------------|
| `enabled` | `bool` | `config["enabled"]` — the loader checks this |
| `commands` | `dict` | Slash commands to register (override to add) |
| `config` | `dict` | Read-only access to loaded config |

**Lifecycle Hooks:**

| Method | When Called |
|--------|------------|
| `on_load()` | Once after instantiation at startup |
| `on_unload()` | On shutdown or before hot-reload |

**Message Hooks:**

| Method | Signature | Purpose |
|--------|-----------|---------|
| `send_message()` | `(message: str, metadata: dict \| None)` | Outbound: mesh → external service |
| `receive_message()` | `()` | Inbound polling (prefer background threads) |
| `handle_command()` | `(command: str, args: str, node_info: dict) → str \| None` | Handle a registered slash command |
| `on_emergency()` | `(message: str, gps_coords: dict \| None)` | Emergency broadcast hook |
| `on_message()` | `(message: str, metadata: dict \| None)` | Observe all inbound mesh messages |

**Flask Integration:**

| Method | Signature | Purpose |
|--------|-----------|---------|
| `register_routes()` | `(app: Flask)` | Register HTTP endpoints |

**Helper Methods:**

| Method | Signature | Purpose |
|--------|-----------|---------|
| `send_to_mesh()` | `(text, channel_index=None, destination_id=None)` | Send a message to the mesh network |
| `log()` | `(message: str)` | Write to the MESH-API script log |
| `_save_config()` | `()` | Persist config changes to disk |

**app_context Dict:**

The `app_context` dict provides access to core functionality:

| Key | Type | Description |
|-----|------|-------------|
| `interface` | `MeshInterface` | The Meshtastic serial/TCP/BLE interface |
| `send_broadcast_chunks` | `function(iface, text, channel_idx)` | Send broadcast message |
| `send_direct_chunks` | `function(iface, text, destination_id)` | Send direct message |
| `add_script_log` | `function(message)` | Core logging function |
| `flask_app` | `Flask` | The Flask application instance |
| `config` | `dict` | Main `config.json` contents |

### Step-by-Step Tutorial

**1. Create the folder structure:**

```
extensions/my_sensor/
├── __init__.py          # Empty
├── config.json
└── extension.py
```

**2. Define config.json:**

```json
{
  "enabled": true,
  "sensor_url": "http://localhost:9000/api/reading",
  "poll_interval_seconds": 300,
  "broadcast_channel_index": 0,
  "unit": "°F"
}
```

The only required key is `"enabled"`. Everything else is up to you.

**3. Implement extension.py:**

```python
"""My Sensor extension — reads temperature from a local sensor API."""

import threading
import time

try:
    import requests
except ImportError:
    requests = None

from extensions.base_extension import BaseExtension


class MySensorExtension(BaseExtension):

    @property
    def name(self) -> str:
        return "My Sensor"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def commands(self) -> dict:
        return {
            "/temp": "Read the current temperature",
        }

    def on_load(self) -> None:
        self._stop = threading.Event()
        self.log(f"My Sensor loaded. URL: {self.config.get('sensor_url')}")

    def on_unload(self) -> None:
        self._stop.set()
        self.log("My Sensor unloaded.")

    def handle_command(self, command: str, args: str,
                       node_info: dict) -> str | None:
        if command == "/temp":
            return self._read_sensor()
        return None

    def _read_sensor(self) -> str:
        url = self.config.get("sensor_url", "")
        unit = self.config.get("unit", "°F")
        if not url:
            return "Sensor URL not configured."
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            temp = data.get("temperature", "?")
            return f"🌡️ Current temperature: {temp}{unit}"
        except Exception as exc:
            return f"⚠️ Sensor error: {exc}"
```

**4. Test it:**

1. Restart MESH-API
2. Send `/extensions` on mesh — should show "My Sensor v1.0.0 [enabled]"
3. Send `/temp` — should return the temperature reading

### Hook Reference

**handle_command(command, args, node_info) → str | None**

The most commonly used hook. Called when a mesh user sends one of your registered commands.

```python
def handle_command(self, command: str, args: str, node_info: dict) -> str | None:
    if command == "/mycmd":
        sender = node_info.get("shortname", "?")
        return f"Hello {sender}! You said: {args}"
    return None  # Not our command
```

**node_info dict:**
```python
{
    "node_id": "!abcd1234",      # Hex node ID
    "shortname": "ABC",          # 4-char node short name
    "longname": "Alpha Bravo",   # Full node name
    "channel_index": 0,          # Channel the message arrived on
    "is_direct": False,          # True if DM, False if broadcast
}
```

**Return value:**
- `str` — text sent back to the mesh (broadcast or DM depending on context)
- `None` — command not handled, loader passes to next extension

**on_message(message, metadata)**

Read-only observer hook. Called for **every** inbound mesh message. Use for logging, analytics, keyword scanning, or triggering side-effects.

```python
def on_message(self, message: str, metadata: dict | None = None) -> None:
    if "help" in message.lower():
        self.log(f"Help request detected: {message}")
```

**Do NOT** return a response from `on_message`. Use `handle_command` for responses, or `send_to_mesh()` for async replies.

**on_emergency(message, gps_coords)**

Called when `/emergency` or `/911` is triggered on the mesh.

```python
def on_emergency(self, message: str, gps_coords: dict | None = None) -> None:
    lat = gps_coords.get("lat", "?") if gps_coords else "?"
    lon = gps_coords.get("lon", "?") if gps_coords else "?"
    self.log(f"EMERGENCY at {lat},{lon}: {message}")
    # Forward to your external service here
```

**send_message(message, metadata)**

Outbound hook. Called by the loader when the core wants to push a message to external services.

```python
def send_message(self, message: str, metadata: dict | None = None) -> None:
    requests.post("https://example.com/api", json={"text": message})
```

**register_routes(app)**

Register Flask HTTP endpoints for inbound webhooks or APIs.

```python
def register_routes(self, app) -> None:
    @app.route("/my_extension/webhook", methods=["POST"])
    def my_webhook():
        from flask import request, jsonify
        data = request.get_json()
        message = data.get("message", "")
        self.send_to_mesh(message, channel_index=0)
        return jsonify({"status": "ok"})
```

### Extension Configuration

**Reading Config:**

```python
api_key = self.config.get("api_key", "")
interval = int(self.config.get("poll_interval", 60))
```

**Updating Config at Runtime:**

```python
self._config["last_check"] = "2025-01-01T00:00:00Z"
self._save_config()  # Writes to config.json on disk
```

**Config Best Practices:**
- Always provide defaults with `.get(key, default)`
- Include `"enabled": false` as the first key
- Use descriptive key names: `poll_interval_seconds`, `broadcast_channel_index`
- Document every key in your extension's comments or README

### Flask Routes (Extensions)

Extensions can expose HTTP endpoints. The Flask app is passed to `register_routes()`:

```python
def register_routes(self, app) -> None:
    @app.route("/my_ext/data", methods=["GET"])
    def my_data():
        from flask import jsonify
        return jsonify({"status": "ok", "extension": self.name})

    @app.route("/my_ext/inbound", methods=["POST"])
    def my_inbound():
        from flask import request
        data = request.get_json(force=True)
        text = data.get("message", "")
        if text:
            self.send_to_mesh(text)
        return "OK", 200
```

**Rules:**
- Use unique route paths prefixed with your extension name
- Import Flask utilities inside the route functions (avoid circular imports)
- Keep route handlers lightweight

### Background Threads

Many extensions need to poll external services. Use daemon threads:

```python
import threading
import time

class MyExtension(BaseExtension):
    def on_load(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="my-ext-poll",
        )
        self._thread.start()

    def on_unload(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)

    def _poll_loop(self) -> None:
        time.sleep(10)  # Initial delay to let system stabilize

        while not self._stop.is_set():
            try:
                data = self._fetch_data()
                if data:
                    self.send_to_mesh(f"New data: {data}")
            except Exception as exc:
                self.log(f"Poll error: {exc}")

            # Interruptible sleep (checks stop event every second)
            interval = int(self.config.get("poll_interval_seconds", 60))
            for _ in range(interval):
                if self._stop.is_set():
                    break
                time.sleep(1)
```

**Thread Safety Tips:**
- Use `threading.Lock()` if shared state is accessed from multiple threads
- Use `threading.Event()` for clean shutdown signaling
- Use interruptible sleep pattern (loop with 1-second sleeps)
- Always set `daemon=True` so threads don't prevent exit
- Give threads descriptive names

### Extension Best Practices

1. **Guard imports** — wrap optional dependencies in try/except:
   ```python
   try:
       import requests
   except ImportError:
       requests = None
   ```

2. **Handle errors gracefully** — never let exceptions crash the main process:
   ```python
   try:
       result = self._call_api()
   except Exception as exc:
       return f"⚠️ Error: {exc}"
   ```

3. **Respect mesh bandwidth** — keep messages short (< 230 chars if possible). The mesh has limited capacity.

4. **De-duplicate** — track seen message IDs to avoid broadcasting the same alert twice:
   ```python
   if msg_id in self._seen_ids:
       return
   self._seen_ids.add(msg_id)
   ```

5. **Clean up in on_unload()** — stop threads, close sockets, flush buffers.

**Naming Conventions:**
- Folder: `snake_case` (e.g. `my_extension`)
- Class: `PascalCaseExtension` (e.g. `MyExtension`)
- Commands: `/<lowercase>` — avoid collisions with built-in commands
- Config keys: `snake_case` with descriptive names

**Message Formatting — Use emoji prefixes for visual scanning on small screens:**
- 📡 — radio/connectivity
- 🚨 — alerts/emergencies  
- ✅ — success/confirmation
- ⚠️ — warnings/errors
- 📋 — lists/info
- 📧 — email/messages
- 🌡️ — weather/sensors

### Testing Extensions

1. Set `"enabled": true` in your extension's `config.json`
2. Restart MESH-API
3. Check the logs for `[ext:YourName]` entries
4. Send `/extensions` to verify it's loaded
5. Test each command from a mesh node

Your `self.log()` calls appear in the MESH-API script log with the prefix `[ext:YourName]`. Check the WebUI Logs panel or the log file.

### Extension Troubleshooting

**Extension not loading:**
- Check that `extension.py` exists in the folder
- Ensure `__init__.py` exists (even if empty)
- Verify the class inherits from `BaseExtension`
- Check that `name` and `version` properties are defined
- Folder names starting with `_` are ignored intentionally
- Check logs for import errors

**Commands not responding:**
- Verify `commands` property returns a dict with your command
- Check `handle_command()` matches the exact command string
- Make sure no other extension registers the same command
- Confirm `"enabled": true` in your config.json

**send_to_mesh not working:**
- Ensure `app_context` contains a valid `interface`
- Check that the mesh interface is connected
- Verify channel index is valid for your mesh configuration

**Config not loading:**
- Validate JSON syntax in `config.json` (use a JSON linter)
- Check file permissions
- Look for log entries about config load failures

### Extension Examples Reference

The `extensions/` directory includes 25+ working extensions you can reference:

| Extension | Complexity | Good Example Of |
|-----------|-----------|-----------------|
| `_example` | Minimal | Basic structure, all hooks documented |
| `ntfy` | Simple | HTTP API + push notifications |
| `pushover` | Simple | Outbound-only notifications |
| `nws_alerts` | Medium | Polling + auto-broadcast + filtering |
| `telegram` | Medium | Bidirectional bridge + long-polling |
| `mqtt` | Medium | Event-driven with paho-mqtt |
| `bbs` | Complex | SQLite database + thread safety + subcommands |
| `aprs` | Complex | Raw TCP sockets + protocol parsing |
| `discord` | Complex | Webhook + bot + Flask route |

---

## Roadmap

- **API Integration Workflow (Planned)**
  - A guided workflow for adding new API integrations, including configuration templates, validation checks, and safe test routes before production use.
  - Goal: make it easier to connect external services without editing core code.

- **MeshCore Routing Support (Initial Implementation — v0.6.0)**
  - MeshCore extension added with bidirectional bridge, command support, and AI integration.
  - Supports USB serial and TCP/WiFi connections to MeshCore companion devices.
  - See [Supported Mesh Networks — MeshCore](#meshcore-extension-based-bridge) and the [MeshCore extension reference](#meshcore) for details.

---

## Changelog

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
### POSSIBLE BUGS IN BETA v0.5.1 - Web UI ticker isn't honoring read messages in some cases.
### INCOMING MESSAGE SOUNDS ARE UNTESTED ON ALL PLATFORMS AND FILESYSTEMS.

### v0.4.1 → v0.4.2
- **Initial Ubuntu & Ollama Unidecode Support: -**  
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

### Changelog: v0.2.2 → v0.3.0 (from the original Main Branch README)
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

## 1. Changelog: v0.1 → v0.2.2

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

---

## Basic Usage

- **Interacting with the AI:**  
  - Use your randomized alias shown at startup (e.g., `/ai-9z`) — AI commands require the suffix: `/ai-9z`, `/bot-9z`, `/query-9z`, `/data-9z` followed by your message.
  - To avoid collisions (multiple bots responding), prefer your unique alias and/or customize commands in `commands_config.json`.
  - For direct messages, simply DM the AI node if configured to reply.
- **Location Query:**  
  - Send `/whereami-XY` (replace `XY` with your suffix) to retrieve the node’s GPS coordinates (if available).
- **Emergency Alerts:**  
  - Trigger an emergency using `/emergency <message>` or `/911 <message>`.  
    - These commands send alerts via Twilio, SMTP, and Discord (if enabled), including GPS data and timestamps.
- **Sending and receiving SMS:**  
  - Send SMS using your suffixed command, e.g., `/sms-9z <+15555555555> <message>`
  - Config options to either route incoming Twilio SMS messages to a specific node, or a channel index.
- **Home Assistant Integration:**  
  - When enabled, messages sent on the designated Home Assistant channel (as defined by `"home_assistant_channel_index"`) are forwarded to Home Assistant’s conversation API.
  - In secure mode, include the PIN in your message (format: `PIN=XXXX your message`).
- **WebUI Messaging:**  
  - Use the dashboard’s send‑message form to send broadcast or direct messages. The mode toggle and node selection simplify quick replies.

### WebUI Config Editor (new)

- Open the dashboard and click the “Config” button in the header (next to Commands/Logs).
- A tabbed editor appears with four views:
  - **⚙️ config.json** — a form-based editor for all core app settings (providers, timeouts, routing, integrations, etc.)
  - **📝 Raw JSON** — direct JSON editing for advanced users
  - **commands_config.json** — a form-based command builder. Add, edit, or remove slash commands. Each command has a trigger (`/mycommand`), a type (Static Response or AI Prompt), a response/prompt value, and a description. No manual JSON editing needed.
  - **motd.json** — a simple text field for the Message of the Day string
- Make edits and click Save. The editor validates data before saving and writes changes atomically.
- **🧙 Run Setup Wizard** — re-run the first-start wizard at any time from the Config Editor header. The wizard pre-populates fields from the existing configuration so you can review and update settings without starting from scratch.
- Changes to some settings may require restarting the app/container to take effect (e.g., provider, connectivity, or Discord/Twilio credentials).
- Security note: If you expose the WebUI beyond localhost, protect access to the dashboard since configuration files may contain secrets (API keys, tokens).

### Manual GPS Location

- If your node does not have a GPS module, you can set your latitude and longitude manually in the **UI Settings** panel under "📍 My Location (Manual GPS)".
- When set, distance calculations to other nodes and the “You” marker on the map will use your manual coordinates instead of the connected node’s GPS.
- Leave the fields blank to revert to the connected node’s GPS.

### Channel Names from Node

- Channel names are now automatically pulled from the connected Meshtastic node via the `/api/channels` endpoint.
- You can rename channels in the **UI Settings** panel under "📡 Channel Names". Overrides are stored locally and take priority over node-reported names.

#### WebUI Config Options (Quick Guide)

The Config Editor includes a grouped help panel. These are the main groups and what they cover:

- **Core**: AI provider selection, system prompt, alias suffix, AI node name, local location string.
- **Diagnostics**: debug logging and message log limits.
- **Providers**: LM Studio, OpenAI, Ollama, and Home Assistant settings.
- **Connectivity**: WiFi, serial, or mesh interface options and advanced node overrides.
- **Policy**: Reply behavior and MQTT response gating.
- **Performance**: Chunk sizing and delays for radio-friendly responses.
- **Channels**: Friendly channel names and `/nodes-XY` online window.
- **Integrations**: Home Assistant, Discord, Twilio, and SMTP credentials and routing.  (future home of API integration settings)

### How AI messages are identified and ignored by other bots

- AI responses include a very short prefix marker `m@i` at the start of the message body. This is not configurable on purpose and is capped at 3 characters to conserve airtime.
- Other MESH-API instances will ignore messages that start with this marker, preventing bots from talking to each other.
- Each instance also tracks node IDs that have sent AI-tagged messages and ignores further messages from those nodes.

#### What is bot‑looping and why is it a problem?
- Bot‑looping happens when two or more automated agents see each other’s messages as prompts and keep replying back and forth without a human in the loop.
- On a constrained LoRa mesh, this can quickly saturate airtime (especially on LongFast), drain batteries, and crowd out legitimate traffic.
- Loops can be surprisingly hard to break because:
  - Messages may be re‑broadcast via MQTT and multiple gateways, multiplying replies.
  - Nodes can buffer/retry after brief outages, re‑triggering the loop even if you silence one side.
  - Different bots might parse/quote each other in ways that keep producing “valid” prompts.
- MESH‑API mitigations:
  - A fixed 3‑char marker (`m@i`) at the start of AI replies so other instances will ignore them.
  - A memory of node IDs that have emitted AI‑tagged messages to avoid engaging those nodes.
  - Conservative defaults: no LongFast replies by default and MQTT response gating disabled by default.
  - Policy: the AI never initiates conversations or responds to arrival/presence events—only explicit human messages.

---

## Using the API

The MESH-API server (running on Flask) exposes the following endpoints:

- **GET `/messages`**  
  Retrieve the last 100 messages in JSON format.
- **GET `/nodes`**  
  Retrieve a live list of connected nodes as JSON.
- **GET `/connection_status`**  
  Get current connection status and error details.
- **GET `/logs`**  
  View a styled log page showing uptime, restarts, and recent log entries.
- **GET `/logs_stream`**  
  Stream recent logs in JSON for lightweight polling.
- **GET `/dashboard`**  
  Access the full WebUI dashboard.
- **GET `/commands_info`**  
  Retrieve a JSON list of available commands and descriptions (used by the in‑app Commands modal).
 - **GET `/config_editor/load`**  
  Load the current contents of `config.json`, `commands_config.json`, and `motd.json` for the WebUI Config Editor.
 - **POST `/config_editor/save`**  
  Save updates to the above files. Payload is validated (JSON where applicable) and written atomically. Some settings require an app restart to apply.
- **POST `/send`** and **POST `/ui_send`**  
  Send messages programmatically.
- **POST `/discord_webhook`**  
  Receive messages from Discord (if configured).

---

## Configuration

Your `config.json` file controls core MESH-API settings — connection, AI, messaging, and emergency alerts. **Integration-specific settings** (Discord, Home Assistant, Slack, Telegram, etc.) are now configured per-extension in `extensions/<name>/config.json`. See the [Extensions System](#extensions-system) section and the WebUI Extensions Manager for details.

Below is the **default** `config.json` with inline explanations:

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

> **Note:** Discord, Home Assistant, Slack, Telegram, and all other integration-specific settings have been moved to the [Extensions System](#extensions-system). Each extension has its own `config.json` under `extensions/<name>/`. You can manage them via the WebUI Extensions Manager or by editing the files directly.

---

## Home Assistant & LLM API Integration

### Home Assistant Integration

> **Home Assistant is now an extension.** Configure it in `extensions/home_assistant/config.json` or via the WebUI Extensions Manager. See [Extensions System](#extensions-system) for details.

- **Enable:** Set `"enabled": true` in `extensions/home_assistant/config.json`.
- **Configure:** Set the `url`, `token`, `channel_index`, and `timeout` fields in the extension config.
- **Security (Optional):** Enable `"enable_pin": true` and set `"secure_pin"` in the extension config.
- **Routing:** Messages on the designated channel are forwarded to Home Assistant. When PIN mode is enabled, include your PIN in the format `PIN=XXXX your message`.

### LLM API Integration

Set `"ai_provider"` in `config.json` to one of the 12 supported providers, then fill in the corresponding API key / URL / model fields:

- **LM Studio:** `"ai_provider": "lmstudio"` — configure `lmstudio_url`, and optionally set `lmstudio_chat_model` / `lmstudio_embedding_model` if using multiple models.
- **OpenAI:** `"ai_provider": "openai"` — provide `openai_api_key` and choose a model (default `gpt-4.1-mini`).
- **Ollama:** `"ai_provider": "ollama"` — configure URL, model, and optional generation overrides via `ollama_options`.
- **Claude:** `"ai_provider": "claude"` — provide `claude_api_key` (default model `claude-sonnet-4-20250514`).
- **Gemini:** `"ai_provider": "gemini"` — provide `gemini_api_key` (default model `gemini-2.0-flash`).
- **Grok:** `"ai_provider": "grok"` — provide `grok_api_key` (default model `grok-3`).
- **OpenRouter:** `"ai_provider": "openrouter"` — provide `openrouter_api_key` (default model `openai/gpt-4.1-mini`).
- **Groq:** `"ai_provider": "groq"` — provide `groq_api_key` (default model `llama-3.3-70b-versatile`).
- **DeepSeek:** `"ai_provider": "deepseek"` — provide `deepseek_api_key` (default model `deepseek-chat`).
- **Mistral:** `"ai_provider": "mistral"` — provide `mistral_api_key` (default model `mistral-small-latest`).
- **OpenAI-Compatible:** `"ai_provider": "openai_compatible"` — provide `openai_compatible_url`, `openai_compatible_api_key`, and `openai_compatible_model` for any provider with an OpenAI-compatible API.

All providers have a configurable `_timeout` (default 60 seconds).

---

## Communication Integrations

### Email Integration
- **Enable Email Alerts:**  
  - Set `"enable_smtp": true` in `config.json`.
- **Configure SMTP:**  
  - Provide the following settings in `config.json`:
    - `"smtp_host"` (e.g., `smtp.gmail.com`)
    - `"smtp_port"` (use `465` for SSL or another port for TLS)
    - `"smtp_user"` (your email address)
    - `"smtp_pass"` (your email password or app-specific password)
    - `"alert_email_to"` (recipient email address or list of addresses)
- **Behavior:**  
  - Emergency emails include a clickable Google Maps link (generated from available GPS data) so recipients can quickly view the sender’s location.
- **Note:**  
  - Ensure your SMTP settings are allowed by your email provider (for example, Gmail may require an app password and proper security settings).

---

### Discord Integration: Detailed Setup & Permissions

> **Discord is now an extension.** Configure it in `extensions/discord/config.json` or via the WebUI Extensions Manager. The setup steps below for creating a Discord bot and permissions still apply.

![483177250_1671387500130340_6790017825443843758_n](https://github.com/user-attachments/assets/0042b7a9-8ec9-4492-8668-25ac977a74cd)


#### 1. Create a Discord Bot
- **Access the Developer Portal:**  
  Go to the [Discord Developer Portal](https://discord.com/developers/applications) and sign in with your Discord account.
- **Create a New Application:**  
  Click on "New Application," give it a name (e.g., *MESH-API Bot*), and confirm.
- **Add a Bot to Your Application:**  
  - Select your application, then navigate to the **Bot** tab on the left sidebar.  
  - Click on **"Add Bot"** and confirm by clicking **"Yes, do it!"**  
  - Customize your bot’s username and icon if desired.

#### 2. Set Up Bot Permissions
- **Required Permissions:**  
  Your bot needs a few basic permissions to function correctly:
  - **View Channels:** So it can see messages in the designated channels.
  - **Send Messages:** To post responses and emergency alerts.
  - **Read Message History:** For polling messages from a channel (if polling is enabled).
  - **Manage Messages (Optional):** If you want the bot to delete or manage messages.
- **Permission Calculator:**  
  Use a tool like [Discord Permissions Calculator](https://discordapi.com/permissions.html) to generate the correct permission integer.  
  For minimal functionality, a permission integer of **3072** (which covers "Send Messages," "View Channels," and "Read Message History") is often sufficient.

#### 3. Invite the Bot to Your Server
- **Generate an Invite Link:**  
  Replace `YOUR_CLIENT_ID` with your bot’s client ID (found in the **General Information** tab) in the following URL:
  ```url
  https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=3072&scope=bot
  ```
- **Invite the Bot:**  
  Open the link in your browser, select the server where you want to add the bot, and authorize it. Make sure you have the “Manage Server” permission in that server.

#### 4. Configure Bot Credentials in Extension Config
Update `extensions/discord/config.json` with the following keys (or use the WebUI Extensions Manager):
```json
{
  "enabled": true,
  "webhook_url": "YOUR_DISCORD_WEBHOOK_URL",
  "receive_enabled": true,
  "bot_token": "YOUR_BOT_TOKEN",
  "channel_id": "YOUR_CHANNEL_ID",
  "inbound_channel_index": 1,
  "send_ai": true,
  "send_emergency": true
}
```
- **webhook_url:**  
  Create a webhook in your desired Discord channel (Channel Settings → Integrations → Webhooks) and copy its URL.
- **bot_token & channel_id:**  
  Copy your bot’s token from the Developer Portal and enable message polling by specifying the channel ID where the bot should read messages.  
  To get a channel ID, enable Developer Mode in Discord (User Settings → Advanced → Developer Mode) then right-click the channel and select "Copy ID."

#### 5. Polling Integration (Optional)
- **Enable Message Polling:**  
  Set `"receive_enabled": true` in the extension config to allow the bot to poll for new messages.
- **Routing:**  
  The `"inbound_channel_index"` key determines the mesh channel used by MESH-API for routing incoming Discord messages.

#### 6. Testing Your Discord Setup
- **Restart MESH-API** (or hot-reload via the WebUI Extensions Manager).
- **Check Bot Activity:**  
  Verify that the bot is present in your server, that it can see messages in the designated channel, and that it can send responses.  
- **Emergency Alerts & AI Responses:**  
  Confirm that emergency alerts and AI responses are being posted in Discord as per your extension configuration.

#### 7. Troubleshooting Tips
- **Permissions Issues:**  
  If the bot isn’t responding or reading messages, double-check that its role on your server has the required permissions.
- **Channel IDs & Webhook URLs:**  
  Verify that you’ve copied the correct channel IDs and webhook URLs (ensure no extra spaces or formatting issues).
- **Bot Token Security:**  
  Keep your bot token secure. If it gets compromised, regenerate it immediately from the Developer Portal.

---

### Twilio Integration
- **Enable Twilio:**  
  - Set `"enable_twilio": true` in `config.json`.
- **Configure Twilio Credentials:**  
  - Provide your Twilio settings in `config.json`:
    - `"twilio_sid": "YOUR_TWILIO_SID"`
    - `"twilio_auth_token": "YOUR_TWILIO_AUTH_TOKEN"`
    - `"twilio_from_number": "YOUR_TWILIO_PHONE_NUMBER"`
    - `"alert_phone_number": "DESTINATION_PHONE_NUMBER"` (the number to receive emergency SMS)
- **Usage:**  
  - When an emergency is triggered, the bot sends an SMS containing the alert message (with a Google Maps link if GPS data is available).
- **Tip:**  
  - Follow [Twilio's setup guide](https://www.twilio.com/docs/usage/tutorials/how-to-use-your-free-trial-account) to obtain your SID and Auth Token, and ensure that your phone numbers are verified.

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
  - Baud Rate is optionally set if you need - this is for longer USB runs (roof nodes connected via USB) and bad USB connections.
  
- **Message Routing & Commands:**  
  - Custom commands can be added in `commands_config.json`.
  - The WebUI Dashboard (accessible at [http://localhost:5000/dashboard](http://localhost:5000/dashboard)) displays messages and node status.
  
- **AI Provider Settings:**  
  - Adjust `"ai_provider"` and related API settings (timeouts, models, etc.) for any of the 12 supported providers: LM Studio, OpenAI, Ollama, Claude, Gemini, Grok, OpenRouter, Groq, DeepSeek, Mistral, or any OpenAI-compatible endpoint.
  
- **Extensions:**  
  - Integration-specific settings (Discord, Home Assistant, Slack, Telegram, etc.) are configured per-extension in `extensions/<name>/config.json`. Use the WebUI Extensions Manager to enable, disable, and configure extensions without editing files directly.
  
- **Security:**  
  - If using the Home Assistant extension with PIN protection, follow the specified format (`PIN=XXXX your message`) to ensure messages are accepted.
  
- **Testing:**  
  - You can test SMS sending with your suffixed `/sms-XY` command or trigger an emergency alert to confirm that Twilio and email integrations are functioning.

---


## Contributing & Disclaimer

- **v0.6.0 Full Release:**  
  This is the full v0.6.0 release with community‑driven bug fixes (#53, #51, #44), a redesigned WebUI dashboard, and updated dependencies. The extensions system has been tested but some extensions may still have edge cases. Please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues) so they may be investigated and addressed.
- **Feedback & Contributions:**  
  Report issues or submit pull requests on GitHub. Your input is invaluable.
- **Use Responsibly:**  
  Modifying this code for nefarious purposes is strictly prohibited. Use at your own risk.

---

---

## Conclusion

MESH-API v0.6.0 is here! This full release includes community‑driven bug fixes (thanks @InstigatorX, @droidblastnz, @omgitsgela), an interactive node map, collapsible channel groups, draggable dashboard layout, five notification sounds, and a visual CSS overhaul — all on top of the powerful 25+ extension plugin system, 12 AI providers, and safer defaults. Whether you’re chatting directly with your node, integrating with Home Assistant, or leveraging multi‑channel alerting (Twilio, Email, Discord), this release offers the most comprehensive and extensible off‑grid AI assistant experience yet. Please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues).

**Enjoy tinkering, stay safe, and have fun!**  
Please share your feedback or report issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues).
