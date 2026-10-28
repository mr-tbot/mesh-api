# MESH-API v0.7.5.4 Beta — Meshtastic + MeshCore Mesh Router & API / AI Bridge

> ## 🎉 Now with full MeshCore support (since v0.7.0)
>
> **You can run MESH-API with EITHER a Meshtastic node, a MeshCore node — or BOTH at the same time, with MESH-API handling cross-network routing between them.** MeshCore is a **first-class, core-owned radio** on equal footing with Meshtastic. Slash commands, the AI assistant, and *every* extension work across both networks, and the WebUI adapts to whichever radios you have connected.
>
> **⚠️ These features are widely untested and I am actively seeking community feedback.** If you run a Meshtastic-only, MeshCore-only, or dual-radio setup, please tell me what works, what breaks, and what you'd like to see — open a [GitHub Issue](https://github.com/mr-tbot/mesh-api/issues). Your real-world reports directly shape the MeshCore implementation going forward.
>
> Also included: a built-in **MCP (Model Context Protocol) server** that turns MESH-API into an agentic backend for AI tools, and a **firmware/software update system**. See the dedicated sections below.

> ### 🆕 What's new
>
> **v0.7.5.0** matures the **MeshCore Bluetooth / Wi-Fi / USB** connection paths: a configured **`ble_pin` now actually pairs** (MESH-API auto-registers a BlueZ pairing agent that supplies it), `ble_pin` is now in the **⚙️ Config** editor and **Setup Wizard**, and the connection banner now shows **why** MeshCore isn't connected (BLE **signal strength**, node-seen-in-scan, and a plain-language hint). It also rolls up a batch of fixes — the **#60 WebUI-save startup crash**, a path-traversal hole, node-name XSS, restored **`/emergency` on LongFast**, plus **Home Assistant `agent_id`** (#61) and opt-in **commands from Telegram** (#59). Building on: **v0.7.4.1** revamps the dashboard **Send a Message** composer — Broadcast/Direct mode tabs, per-network broadcast checkboxes (📡 Meshtastic, 🟣 MeshCore, 🌉 Bridged), and a bridged channel dropdown that now shows **both** routed channels (e.g. `0 → 📡 LongFast + 🟣 Public`) — adds a **Previously Seen** node section with an adjustable staleness threshold, and fixes **MeshCore presence** so addressable contacts no longer drop out of the live node list (activity-based last-heard). **v0.7.4** updated the **first-start Setup Wizard** to walk you through **MeshCore** as well as Meshtastic: a dedicated MeshCore step (serial / TCP / BLE, adverts, channel bridging), a toggle to run a **MeshCore-only / standalone node**, and a **default send-network** selector. The prior **v0.7.3.7** ensured **all extensions route to MeshCore** (GitHub [#59](https://github.com/mr-tbot/mesh-api/issues/59)), and **v0.7.3.6** added a **token-free heartbeat** for named AI endpoints.
>
> 📜 **See the full version history in [CHANGELOG.md](CHANGELOG.md).**

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



<img width="1151" height="251" alt="MESH-API-HEADER" src="https://github.com/user-attachments/assets/53d213fe-fd3d-4d24-b62d-5620a0c81791" />



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

> **v0.7.4.1 Beta:**  
> The 0.7.x line makes MeshCore a first-class radio and adds the MCP server and firmware-update system; v0.7.4.1 revamps the **Send a Message** composer (broadcast/direct mode tabs, multi-network broadcast targeting, bridged dropdown showing both channels), adds a **Previously Seen** node section, and fixes **MeshCore node presence**, building on v0.7.4's MeshCore Setup Wizard and v0.7.3.7's fix so **every extension routes outbound messages to MeshCore as well as Meshtastic**. **These features are still relatively untested in the field — I am actively seeking community feedback.** Run it with a Meshtastic node, a MeshCore node, or both, and please report what works and what breaks. Avoid relying on it for mission‑critical tasks or emergencies; always keep backup communication methods available and use responsibly.  

>  
> *I am one robot using other robots to write this code. Some features are still untested in the field. Check the GitHub issues for fixes or feedback!*

---

[![image](https://github.com/user-attachments/assets/bdf08934-3a80-4dc6-8a91-78e33c34db59)](https://meshtastic.org)
The Meshtastic logo trademark is the trademark of Meshtastic LLC.



## Features

- **Multi-Radio: Meshtastic, MeshCore, or Both** *(New in v0.7.0)*
  - **MeshCore is a first-class, core-owned radio** (not an extension) on equal footing with Meshtastic, connecting over serial / TCP / BLE.
  - Run a **Meshtastic radio only**, a **MeshCore radio only** (fully standalone — no Meshtastic device required), or **one of each** with MESH-API as a cross-network man-in-the-middle.
  - Slash commands, the AI assistant, and **every extension work across both networks**. Send to one network or both at once.
  - **WebUI adapts** — per-network connection banner, node **network filter** with collapsible Meshtastic/MeshCore sections, network badges on nodes & messages, distinct map markers, MeshCore group/private channels in the send form, and DMs to MeshCore contacts.
- **MCP (Model Context Protocol) Server** *(New in v0.7.0)*
  - Exposes MESH-API core functions **and** extensions as MCP **tools** at `POST /mcp`, so external AI agents (Claude, Perplexity, Hermes, custom) can drive the mesh as an agentic backend. Disabled by default; bearer-token auth. See **[MCP Server](#mcp-server-model-context-protocol)**.
- **Firmware & Software Updates** *(New in v0.7.0)*
  - Detects your connected Meshtastic/MeshCore device and notifies you (🔄 Updates badge) when newer **Meshtastic firmware**, **MeshCore firmware**, or **MESH-API** is available, with **stable / beta / alpha** release-channel selection. Optional ESP32 over-USB flashing (off by default).
- **Plugin-Based Extensions System** *(New in v0.6.0)*  
  - 30 built-in extensions across 7 categories: Communication, Notifications, Emergency/Weather, Ham Radio/Off-Grid, Smart Home, Mesh Bridging, and AI Agents.
  - Drop-in plugin architecture — add or remove extensions by copying a folder. No core code changes required.
  - Extensions can register slash commands, react to emergencies, observe messages, expose HTTP endpoints, and run background services.
  - **WebUI Extensions Manager** — view, enable/disable, and configure extensions from the dashboard.
  - See the [Extensions Reference](#extensions-reference) section below for full details on all built-in extensions, or [Developing Custom Extensions](#developing-custom-extensions) to build your own.
- **Multiple AI Providers**  
  - Support for **Local** models (LM Studio, Ollama), **OpenAI**, **Claude**, **Gemini**, **Grok**, **OpenRouter**, **Groq**, **DeepSeek**, **Mistral**, **Hermes** (Nous Research), generic OpenAI-compatible endpoints, and **Home Assistant** integration.
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

### MeshCore (First-Class Radio — v0.7.0)

[MeshCore](https://meshcore.co.uk/) is a lightweight, multi-hop LoRa mesh firmware focused on embedded packet routing. **As of v0.7.0, MeshCore is a first-class radio owned by the MESH-API core** (`meshcore_core.py`) — *not* an extension. It connects directly to a MeshCore companion-firmware device over **USB serial, TCP, or BLE**, and its inbound traffic flows through the **same network-agnostic pipeline** as Meshtastic, so commands, AI, and every extension work on it natively.

> ⬆️ **Upgrading from an earlier build?** The old `extensions/meshcore` bridge plugin is **deprecated** and automatically defers to the core when the core MeshCore radio is enabled — you do not need (and should not use) the extension anymore. Move your settings into the `meshcore` block of `config.json` (see below).

You can run **one Meshtastic radio, one MeshCore radio, or one of each.** With both connected, MESH-API acts as the man-in-the-middle, optionally bridging chat between the two networks. See **[Running With Meshtastic, MeshCore, or Both](#running-with-meshtastic-meshcore-or-both-v070)** just below for the full configuration, topologies, and WebUI behavior.

**Quick start:**

1. `pip install meshcore` *(already in `requirements.txt`)*.
2. Flash a companion device with MeshCore **Companion** firmware (USB‑serial, BLE, or TCP variant) from [https://flasher.meshcore.co.uk](https://flasher.meshcore.co.uk).
3. Enable and configure the radio in the **`meshcore`** block of [config.json](config.json) (set `enabled: true`, pick `connection_type`, and the port/host/address).
4. Restart MESH-API. The 🟣 MeshCore status appears in the connection banner, MeshCore nodes show on the harmonized map, and you can send to MeshCore (or both networks) from the dashboard.

---

<img width="2543" height="1271" alt="image" src="https://github.com/user-attachments/assets/d2091bab-cbdf-4b4d-b424-10d59d812f22" />

The latest v0.7.5.4 Beta Web-UI!  NEW MAPS FEATURES AND TONS OF NEW GOODIES!

---

## Running With Meshtastic, MeshCore, or Both (v0.7.0)

MESH-API v0.7.0 treats **MeshCore as a first-class radio** managed by the core
(`meshcore_core.py`), feeding inbound messages through the *same* network-agnostic
pipeline as Meshtastic. You can run any of three topologies:

| Topology | How |
|----------|-----|
| **Meshtastic only** (classic) | Leave `meshcore.enabled: false`. Nothing changes. |
| **MeshCore only** (standalone) | Set `meshtastic_enabled: false` and `meshcore.enabled: true`. No Meshtastic device required. |
| **Both** (cross-network router) | `meshtastic_enabled: true` + `meshcore.enabled: true`. MESH-API bridges traffic between the two networks. |

Configure MeshCore in the `meshcore` block of [config.json](config.json):

```jsonc
"meshtastic_enabled": true,            // set false to run MeshCore-only
"default_send_network": "auto",        // auto | meshtastic | meshcore | both
"meshcore": {
  "enabled": true,
  "connection_type": "serial",         // serial | tcp | ble
  "serial_port": "/dev/ttyUSB1",       // or tcp_host/tcp_port, or ble_address
  "serial_baud": 115200,
  "bridge_enabled": true,              // mirror chat between networks when both present
  "bridge_meshcore_channel_to_meshtastic_channel": { "0": 0 },
  "bridge_meshtastic_channel_to_meshcore_channel": { "0": 0 }
}
```

**What works across both networks:** slash commands, the AI assistant, every
extension/plugin, the harmonized node map, DMs, channel/group messaging, and
emergency broadcasts. The WebUI adapts automatically — a per-network connection
banner, a node **network filter** with collapsible Meshtastic/MeshCore sections,
network badges (📡 MT / 🟣 MC) on nodes and messages, distinct map markers, and a
**Network** selector in the send form (Auto / Meshtastic / MeshCore / Both) that
appears when both radios are present.

> ⚠️ MeshCore support is brand new and widely untested — please report your
> experience (any topology) on [GitHub](https://github.com/mr-tbot/mesh-api/issues).

---

## MCP Server (Model Context Protocol)

v0.7.0 ships a built-in **MCP server** that exposes MESH-API's core functions
**and** its extensions as callable *tools*, so external AI agents and services —
**Claude, Perplexity, Hermes, custom agents, OpenClaw, etc.** — can drive your
Meshtastic and/or MeshCore networks as an **agentic backend**. This enables
advanced workflows: an agent can read the mesh, decide, and act (send messages,
run commands, trigger extensions) over LoRa.

### How it works

- **Transport:** Streamable HTTP / JSON-RPC 2.0 at a single endpoint, `POST /mcp`.
  Implemented directly in Flask (no async/uvicorn dependency — runs fine on a Pi
  Zero). Compatible with MCP clients that speak HTTP directly, or with stdio-only
  clients (e.g. Claude Desktop) via the [`mcp-remote`](https://github.com/geelen/mcp-remote) bridge.
- **Disabled by default.** Enable it in the `mcp` block of [config.json](config.json):

  ```jsonc
  "mcp": {
    "enabled": true,
    "require_auth": true,        // bearer token (auto-generated + printed on first start)
    "auth_token": "",            // leave blank to auto-generate; also accepted as X-API-Key
    "allowed_origins": ["*"],    // DNS-rebinding allowlist
    "allow_emergency": false,    // gate the emergency tool
    "rate_limit_per_min": 120
  }
  ```

  On first start with auth enabled, a token like `mesh-mcp-XXXX` is generated,
  saved to config, and printed to the log. Pass it as `Authorization: Bearer <token>`.

### Connecting a client

Point any MCP client at `http://<host>:5000/mcp` with the bearer token. For
Claude Desktop / stdio clients:

```jsonc
{
  "mcpServers": {
    "mesh-api": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://<host>:5000/mcp",
               "--header", "Authorization: Bearer mesh-mcp-YOURTOKEN"]
    }
  }
}
```

### Built-in core tools

| Tool | Purpose |
|------|---------|
| `mesh_send_message` | Send to a network (meshtastic / meshcore / both / auto), broadcast or DM |
| `mesh_list_nodes` | List nodes across both networks (filterable) |
| `mesh_get_messages` | Read the recent mesh chat log |
| `mesh_network_status` | Status of both radios |
| `mesh_list_channels` | Meshtastic + MeshCore channels |
| `mesh_ai_query` | Ask the configured AI provider |
| `mesh_list_commands` / `mesh_run_command` | List / run any slash command |
| `meshcore_list_contacts` | MeshCore DM targets |
| `mesh_send_emergency` | Emergency broadcast (gated by `allow_emergency`) |

### Extensions as MCP tools

**Every loaded extension's slash command is auto-exposed** as an `ext_cmd_<command>`
tool — no work required. Extensions can additionally provide **richer, typed
tools** by implementing two optional, duck-typed methods (no base-class change):

```python
def get_mcp_tools(self) -> list[dict]:
    return [{
        "name": "lookup_city",          # exposed as ext_<slug>_lookup_city
        "description": "Look up weather for a city",
        "inputSchema": {"type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"]},
    }]

def call_mcp_tool(self, name: str, arguments: dict) -> str:
    if name == "lookup_city":
        return self._weather_for(arguments.get("city", ""))
    return f"Unknown tool: {name}"
```

The tool list is rebuilt on every `tools/list`, so enabling/reloading an
extension surfaces its tools without restarting MESH-API. See
[DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md#mcp-tools-v070) for details.

### Security

Tool calls can send mesh traffic and trigger actions, so the server validates
inputs, requires a bearer token by default, validates the `Origin` header,
rate-limits calls, clamps output size, and gates the emergency tool. Treat the
token like a password. There should always be a human in the loop for sensitive
operations.

---

## Firmware & Software Updates

v0.7.0 adds a comprehensive, **safe-by-default** update system (`firmware_updater.py`):

- **Detection** — identifies the connected Meshtastic device (hardware model +
  firmware variant `pioEnv` + version) and the MeshCore device (model + version).
- **Update notifications** — a 🔄 **Updates** button in the WebUI masthead shows a
  badge when a newer **Meshtastic firmware**, **MeshCore firmware**, or **MESH-API**
  release is available (checked against GitHub on a periodic timer + on demand).
- **Release channels** — pick **stable / beta / alpha** independently for
  Meshtastic and MeshCore firmware. Beta/alpha track GitHub pre-releases; the
  WebUI shows the newest matching version for the channel you choose. (Your device
  is not always a Heltec V3 — detection adapts to whatever is connected.)
- **Flashing (optional, off by default)** — for ESP32-class Meshtastic devices,
  the latest firmware can be downloaded and flashed over USB serial via `esptool`.
  nRF52/UF2 devices and MeshCore companions fall back to guided
  [web-flasher](https://flasher.meshtastic.org/) instructions (unattended flashing
  there is unsafe). Enable with `firmware.allow_flashing: true`; optional
  `firmware.auto_update: true` flashes ESP32 Meshtastic devices unattended.

```jsonc
"firmware": {
  "auto_check": true,
  "check_interval_sec": 86400,
  "allow_flashing": false,          // master gate for flashing
  "auto_update": false,             // never flashes unattended unless true
  "meshtastic_channel": "stable",   // stable | beta | alpha
  "meshcore_channel": "stable",
  "meshtastic_fw_repo": "meshtastic/firmware",
  "meshcore_fw_repo": "meshcore-dev/MeshCore",
  "mesh_api_repo": "mr-tbot/mesh-api"
}
```

> ⚠️ Flashing can brick a radio. Always keep a backup device, and prefer the web
> flasher unless you understand the risks. The radio goes offline during flashing.

---

## Channel Agents — Assign a Channel to an Agent

v0.7.0 generalizes the old Home Assistant per-channel routing into **Channel
Agents**: assign any mesh channel to a specific agent, and all plain-text
(non-command) traffic on that channel is handled by it. Use it to dedicate a
channel to **OpenClaw**, **Hermes**, **Home Assistant**, or any AI provider —
on either Meshtastic or MeshCore.

Configure it in the top-level `channel_agents` block of [config.json](config.json),
mapping a channel index (as seen by MESH-API) to an agent spec:

```jsonc
"channel_agents": {
  "6": { "agent": "ai", "provider": "hermes" },          // ch6 → Hermes
  "7": { "agent": "extension", "slug": "openclaw" },      // ch7 → OpenClaw agent
  "5": { "agent": "ai", "provider": "home_assistant" },   // ch5 → Home Assistant
  "8": { "agent": "ai", "provider": "openai", "require_pin": true }
}
```

- **`agent: "ai"`** routes the channel to a named AI provider (`openai`, `hermes`,
  `ollama`, `claude`, `home_assistant`, etc.) — independent of the global
  `ai_provider`, so different channels can use different models.
- **`agent: "extension"`** routes to a loaded extension (e.g. `openclaw`) via its
  `handle_channel_message()` hook, falling back to `get_ai_response()` or a
  configured `command`. See [DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md#channel-agents-v070).
- **`require_pin: true`** gates the channel behind a `PIN=XXXX` prefix (like the
  Home Assistant secure mode).
- Channels with an assigned agent **always respond**, bypassing the global
  `reply_in_channels` setting. Slash commands still work normally there.
- The legacy `home_assistant_channel_index` setting continues to work and is
  surfaced via `GET /api/channel_agents`.

> Channel indices differ between physical MeshCore devices — assign the agent to
> the index **as MESH-API receives it** (visible in the logs / message panel).

---

## Extensions Reference

> **Note:** The extensions system and all corresponding extensions are **new and largely untested**. Please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues) so they may be investigated and addressed.

MESH-API ships with 30 built-in extensions across 7 categories — Communication
(Discord, Slack, Telegram, Matrix, Signal, WhatsApp, Mattermost, Zello, MQTT,
Webhook, IMAP, Mastodon, n8n), Notifications (Apprise, Ntfy, Pushover, PagerDuty,
OpsGenie), Emergency & Weather (NWS Alerts, OpenWeatherMap, USGS Earthquakes,
GDACS, Amber Alerts, NASA Space Weather), Ham Radio & Off-Grid (Winlink, APRS,
BBS), Smart Home (Home Assistant), Mesh Bridging (MeshCore — *deprecated, now a
core radio*), and AI Agents (OpenClaw).

Each extension is a self-contained plugin in the `extensions/` directory with its
own `config.json`, `extension.py`, and `__init__.py`. **Quick start:** enable any
extension by setting `"enabled": true` in its `config.json` and restarting MESH-API.

📦 **Full per-extension command lists, config keys, and hooks are documented in
[EXTENSIONS.md](EXTENSIONS.md).** To build your own, see
[Developing Custom Extensions](#developing-custom-extensions) and
[DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md).

---

## Developing Custom Extensions

> 🧩 **The full extension-development guide now lives in its own file:
> [DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md).**

MESH-API uses a plugin-based extension system where each extension is a
self-contained Python package in the `extensions/` directory. Extensions can
register slash commands, send/receive mesh messages, react to emergencies,
observe all inbound traffic, expose Flask HTTP endpoints, run background
polling threads, and act as AI providers — all auto-discovered at startup with
no changes to core code.

**To build one:**

1. Copy the template: `cp -r extensions/_example extensions/my_extension`
2. Edit the three files — `__init__.py` (empty), `config.json` (must include `"enabled": true`), and `extension.py` (subclass `BaseExtension`).
3. Restart MESH-API — it's auto-discovered and loaded.
4. Send `/extensions` on the mesh to verify it's listed.

📚 **Full reference** — the complete Base Class API, every lifecycle/message
hook, the `app_context` dict, a step-by-step tutorial, background-thread and
Flask-route patterns, best practices, and troubleshooting are all documented in
**[DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md)**. For the catalog of the
30 built-in extensions and their config keys, see
**[EXTENSIONS.md](EXTENSIONS.md)**.

---

## Roadmap

- **API Integration Workflow (Planned)**
  - A guided workflow for adding new API integrations, including configuration templates, validation checks, and safe test routes before production use.
  - Goal: make it easier to connect external services without editing core code.

- **MeshCore Routing Support (Initial Implementation — v0.6.0)**
  - MeshCore extension added with bidirectional bridge, command support, and AI integration.
  - Supports USB serial and TCP/WiFi connections to MeshCore companion devices.
  - *(Superseded in v0.7.0 — MeshCore is now a first-class core radio; see [Running With Meshtastic, MeshCore, or Both](#running-with-meshtastic-meshcore-or-both-v070).)*

---

## Changelog

📜 **The full version history has moved to [CHANGELOG.md](CHANGELOG.md)** to keep
this README short. It covers every release from v0.1 through the current
v0.7.4.1 Beta, with both per-release summaries and detailed notes.

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
  - Use the dashboard’s send‑message form to reach the mesh. See [Web UI / Dashboard](#web-ui--dashboard) below for the full breakdown of broadcast/direct modes and multi‑network targeting.

### Web UI / Dashboard

The dashboard at `http://<host>:5000/dashboard` is the primary control surface.
Key panels:

- **📤 Send a Message** — a two‑mode composer:
  - **Broadcast mode** lets you target one or more networks at once via
    checkboxes. Each enabled network shows its own channel picker:
    - 📡 **Meshtastic** — pick a Meshtastic channel.
    - 🟣 **MeshCore** — pick a MeshCore channel.
    - 🌉 **Bridged** — a single selection that fans out to *both* radios; the
      dropdown shows the paired routing, e.g. `0 → 📡 LongFast + 🟣 Public`,
      so you can see exactly which Meshtastic and MeshCore channels a bridged
      send will hit.
  - **Direct mode** searches your node list (across both networks) and sends a
    DM; a hint shows which network the selected node lives on.
- **🟢 Nodes** — live node list grouped by network, plus a **Previously Seen**
  section for nodes that have gone stale (with an adjustable staleness
  threshold). Favorites can be pinned so they stay in the main list. MeshCore
  contacts use activity‑based presence (message activity), since MeshCore nodes
  advertise only occasionally rather than beaconing continuously.
- **🗺️ Map** — node positions using live GPS or your manual location.
- **📈 Traffic Monitor** — recent mesh message feed across both networks.
- **🤖 Channel Agents** — assign a dedicated AI persona/provider per channel.
- **🛠️ Config Editor / Setup Wizard** — edit `config.json`,
  `commands_config.json`, and `motd.json` from the browser (see below).

### WebUI Config Editor (new)

- Open the dashboard and click the “Config” button in the header (next to Commands/Logs).
- A tabbed editor appears with four views:
  - **⚙️ config.json** — a form-based editor for all core app settings (providers, timeouts, routing, integrations, etc.)
  - **📝 Raw JSON** — direct JSON editing for advanced users
  - **commands_config.json** — a form-based command builder. Add, edit, or remove slash commands. Each command has a trigger (`/mycommand`), a type (Static Response or AI Prompt), a response/prompt value, and a description. No manual JSON editing needed.
  - **motd.json** — a simple text field for the Message of the Day string
- Make edits and click Save. The editor validates data before saving and writes changes atomically.
- **🧙 Run Setup Wizard** — re-run the first-start wizard at any time from the Config Editor header. The wizard walks you through your **Meshtastic radio**, your **MeshCore radio** (serial / TCP / BLE, adverts, channel bridging — or a MeshCore-only/standalone node), your **AI provider**, and **node identity** (including the default send-network). It pre-populates every field from the existing configuration so you can review and update settings without starting from scratch.
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

> ⚙️ **The full configuration reference now lives in
> [CONFIGURATION.md](CONFIGURATION.md).**

Core MESH-API settings live in [config.json](config.json) — connection, AI
provider, messaging, and emergency alerts. Most people never hand-edit it: the
dashboard's **⚙️ Config** editor and re-runnable **🧙 Setup Wizard** cover every
core setting (see [Web UI / Dashboard](#web-ui--dashboard)).

[CONFIGURATION.md](CONFIGURATION.md) documents the complete annotated default
`config.json`, the multi-radio blocks (`meshtastic_enabled`,
`default_send_network`, `meshcore`, `mcp`, `firmware`), and the other
operational settings (logging, device connection, message routing, AI provider
selection).

> **Note:** Integration-specific settings (Discord, Home Assistant, Slack,
> Telegram, etc.) are configured **per-extension** in
> `extensions/<name>/config.json`, not in the core config — see
> [INTEGRATIONS.md](INTEGRATIONS.md) and [EXTENSIONS.md](EXTENSIONS.md).

---

## Integrations

> 🔌 **Integration setup guides now live in
> [INTEGRATIONS.md](INTEGRATIONS.md).**

MESH-API connects to external services for AI, alerting, and chat bridging:

- **Home Assistant** — forward a channel to the HA conversation API (with
  optional PIN security).
- **LLM API** — 12 AI providers (LM Studio, OpenAI, Ollama, Claude, Gemini,
  Grok, OpenRouter, Groq, DeepSeek, Mistral, OpenAI-compatible).
- **Email (SMTP)** and **Twilio SMS** — emergency alerting with a Google Maps
  link.
- **Discord** — full bot + webhook bridge (detailed bot/permissions setup).

Step-by-step setup for each lives in **[INTEGRATIONS.md](INTEGRATIONS.md)**.
Chat-bridge integrations (Discord, Telegram, Matrix, Mattermost, etc.) are
extensions — see **[EXTENSIONS.md](EXTENSIONS.md)**.

---

## Contributing & Disclaimer

- **v0.7.4.1 Beta:**  
  The 0.7.x line makes MeshCore a first-class radio and adds the MCP server, firmware-update system, token-free AI-endpoint heartbeat monitoring (v0.7.3.6), the all-extensions-to-MeshCore fix (v0.7.3.7), and the v0.7.4 MeshCore Setup Wizard; v0.7.4.1 revamps the **Send a Message** composer (mode tabs, multi-network broadcast targeting, bridged dropdown showing both routed channels), adds a **Previously Seen** node section, and fixes **MeshCore presence** (activity-based last-heard). These features are still relatively untested in the field — please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues) so they may be investigated and addressed.
- **Feedback & Contributions:**  
  Report issues or submit pull requests on GitHub. Your input is invaluable.
- **Use Responsibly:**  
  Modifying this code for nefarious purposes is strictly prohibited. Use at your own risk.

---

## Conclusion

MESH-API v0.7.4.1 Beta is here! The 0.7.x line treats **MeshCore as a first-class radio** alongside Meshtastic, adds a built-in **MCP server** for external AI agents, a **firmware/software update manager**, token-free AI-endpoint heartbeat monitoring (v0.7.3.6), the all-extensions-to-MeshCore routing fix (v0.7.3.7), the v0.7.4 **MeshCore Setup Wizard**, and — new in v0.7.4.1 — a revamped **Send a Message** composer (broadcast/direct tabs, multi-network targeting, a bridged dropdown showing both routed channels), a **Previously Seen** node section, and a **MeshCore presence** fix. All on top of the powerful 30-extension plugin system, 12 AI providers, and safer defaults. Whether you’re chatting directly with your node, integrating with Home Assistant, or leveraging multi‑channel alerting (Twilio, Email, Discord), this release offers the most comprehensive and extensible off‑grid AI assistant experience yet. Please report any issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues).

**Enjoy tinkering, stay safe, and have fun!**  
Please share your feedback or report issues on [GitHub](https://github.com/mr-tbot/mesh-api/issues).
