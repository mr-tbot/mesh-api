# MESH-API Extensions Reference (v0.6.0)

Complete reference for all built-in extensions included with MESH-API.  
Each extension is a self-contained plugin in the `extensions/` directory with its own `config.json`, `extension.py`, and `__init__.py`.

**Quick start:** Enable any extension by setting `"enabled": true` in its `config.json` file and restarting MESH-API.

---

## Table of Contents

- **[Communication Extensions](#communication-extensions):** [Discord](#discord) · [Slack](#slack) · [Telegram](#telegram) · [Matrix](#matrix) · [Signal](#signal) · [WhatsApp](#whatsapp) · [Mattermost](#mattermost) · [Zello](#zello) · [MQTT](#mqtt) · [Webhook Generic](#webhook-generic) · [IMAP](#imap) · [Mastodon](#mastodon) · [n8n](#n8n)
- **[Notification Extensions](#notification-extensions):** [Apprise](#apprise) · [Ntfy](#ntfy) · [Pushover](#pushover) · [PagerDuty](#pagerduty) · [OpsGenie](#opsgenie)
- **[Emergency & Weather Extensions](#emergency--weather-extensions):** [NWS Alerts](#nws-alerts) · [OpenWeatherMap](#openweathermap) · [USGS Earthquakes](#usgs-earthquakes) · [GDACS](#gdacs) · [Amber Alerts](#amber-alerts) · [NASA Space Weather](#nasa-space-weather)
- **[Ham Radio & Off-Grid Extensions](#ham-radio--off-grid-extensions):** [Winlink](#winlink) · [APRS](#aprs) · [BBS](#bbs)
- **[Smart Home Extensions](#smart-home-extensions):** [Home Assistant](#home-assistant)
- **[Mesh Bridging Extensions](#mesh-bridging-extensions):** [MeshCore](#meshcore)
- **[AI Agent Extensions](#ai-agent-extensions):** [OpenClaw](#openclaw)

---

## Communication Extensions

### Discord

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

### Slack

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

### Telegram

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

### Matrix

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

### Signal

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

### WhatsApp

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

### Mattermost

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

### Zello

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

### MQTT

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

### Webhook Generic

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

### IMAP

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

### Mastodon

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

### n8n

Bidirectional [n8n](https://n8n.io) workflow automation bridge — forward mesh messages and emergencies to n8n webhook triggers, receive workflow outputs on the mesh, list active workflows, and trigger them via slash commands.

**Commands:**
| Command | Description |
|---------|-------------|
| `/n8n` | Show n8n integration status |
| `/n8n trigger <id>` | Trigger an n8n workflow by ID |
| `/n8n workflows` | List active n8n workflows |

**Config (`extensions/n8n/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `webhook_url` | string | `""` | n8n webhook URL for outbound messages |
| `webhook_secret` | string | `""` | HMAC secret for outbound webhook |
| `api_base_url` | string | `"http://localhost:5678"` | n8n API base URL |
| `api_key` | string | `""` | n8n API key |
| `send_emergency` | bool | `true` | Forward emergency alerts to n8n |
| `send_ai` | bool | `false` | Forward AI responses to n8n |
| `send_all` | bool | `false` | Forward all mesh messages to n8n |
| `receive_enabled` | bool | `true` | Accept inbound messages from n8n |
| `receive_endpoint` | string | `"/n8n/webhook"` | Flask endpoint for inbound n8n messages |
| `receive_secret` | string | `""` | Secret for inbound webhook verification |
| `inbound_channel_index` | int\|null | `null` | Mesh channel filter for outbound |
| `message_field` | string | `"message"` | JSON field name for the message body |
| `sender_field` | string | `"sender"` | JSON field name for the sender |
| `include_metadata` | bool | `true` | Include node metadata in outbound payloads |
| `poll_executions` | bool | `false` | Poll n8n for recent execution outputs |
| `poll_interval_seconds` | int | `60` | Polling interval |
| `broadcast_channel_index` | int | `0` | Mesh channel index for inbound messages |
| `bot_name` | string | `"MESH-API"` | Bot display name in n8n payloads |

**API Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/n8n/webhook` | POST | Receive messages from n8n workflows |

**Hooks:** `on_message`, `send_message`, `on_emergency`, Flask route for inbound.

---

## Notification Extensions

### Apprise

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

### Ntfy

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

### Pushover

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

### PagerDuty

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

### OpsGenie

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

## Emergency & Weather Extensions

### NWS Alerts

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

### OpenWeatherMap

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

### USGS Earthquakes

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

### GDACS

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

### Amber Alerts

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

### NASA Space Weather

NASA DONKI (Space Weather Database Of Notifications, Knowledge, Information) integration — tracks geomagnetic storms, solar flares, coronal mass ejections, and other space weather events. Auto-broadcasts significant events to the mesh with configurable Kp index and flare class thresholds.

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
| `api_key` | string | `"DEMO_KEY"` | NASA API key (get one free at api.nasa.gov) |
| `poll_interval_seconds` | int | `600` | Polling interval for new events |
| `auto_broadcast` | bool | `true` | Auto-broadcast significant events to mesh |
| `broadcast_channel_index` | int | `0` | Mesh channel index |
| `event_types` | array | `["GST", "FLR", "CME", "IPS", "SEP", "RBE"]` | Event types to monitor |
| `min_kp_index` | int | `5` | Minimum Kp index to report geomagnetic storms |
| `min_flare_class` | string | `"M"` | Minimum flare class to report (`C`, `M`, `X`) |
| `lookback_days` | int | `3` | How many days back to query |
| `max_alert_length` | int | `300` | Max alert text length |
| `max_results` | int | `5` | Max results per query |

Event type codes: **GST** = Geomagnetic Storm, **FLR** = Solar Flare, **CME** = Coronal Mass Ejection, **IPS** = Interplanetary Shock, **SEP** = Solar Energetic Particle, **RBE** = Radiation Belt Enhancement.

**Hooks:** `on_load()` (starts background poller).

---

## Ham Radio & Off-Grid Extensions

### Winlink

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

### APRS

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

### BBS

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

## Smart Home Extensions

### Home Assistant

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

## Mesh Bridging Extensions

### MeshCore

Bidirectional bridge between the Meshtastic mesh network and a [MeshCore](https://meshcore.co.uk/) mesh network. Requires a separate MeshCore companion-firmware device connected via USB serial or TCP/WiFi.

**Commands:**
| Command | Description |
|---------|-------------|
| `/meshcore` | Show MeshCore bridge status (connected device, bridge state, channel map) |

**Config (`extensions/meshcore/config.json`):**
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable the extension |
| `connection_type` | string | `"serial"` | `"serial"` or `"tcp"` |
| `serial_port` | string | `"/dev/ttyUSB1"` | Serial port for the MeshCore companion device |
| `serial_baud` | int | `115200` | Serial baud rate |
| `tcp_host` | string | `"192.168.1.100"` | TCP/WiFi host |
| `tcp_port` | int | `5000` | TCP port |
| `auto_reconnect` | bool | `true` | Auto-reconnect on disconnect |
| `max_reconnect_attempts` | int | `0` | Max reconnect attempts (0 = unlimited) |
| `reconnect_interval_sec` | int | `30` | Seconds between reconnect attempts |
| `bridge_enabled` | bool | `true` | Enable bidirectional channel bridging |
| `bridge_meshcore_channel_to_meshtastic_channel` | object | `{"0": 1}` | Map MeshCore channel → Meshtastic channel |
| `bridge_meshtastic_channels_to_meshcore_channel` | object | `{"1": 0}` | Map Meshtastic channel → MeshCore channel |
| `bridge_direct_messages` | bool | `false` | Bridge direct messages between networks |
| `commands_enabled` | bool | `true` | Allow MeshCore users to issue `/commands` |
| `command_prefix` | string | `"/"` | Command prefix for MeshCore messages |
| `meshcore_to_meshtastic_tag` | string | `"[MC]"` | Tag prepended to messages from MeshCore |
| `meshtastic_to_meshcore_tag` | string | `"[MT]"` | Tag prepended to messages from Meshtastic |
| `ai_commands_enabled` | bool | `true` | Allow MeshCore users to send AI queries |
| `ignore_own_messages` | bool | `true` | Prevent echo loops between networks |
| `max_message_length` | int | `200` | Max characters per bridged message |

**Hooks:** `on_message()` (Meshtastic→MeshCore bridging), `on_emergency()`, `handle_command()`, Flask route `/api/meshcore/status`.

---

## AI Agent Extensions

### OpenClaw

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

**Companion Skill:** A MESH-API skill file for OpenClaw is included at `skills/mesh-api/SKILL.md` — copy it to `~/.openclaw/skills/mesh-api/SKILL.md` to teach an OpenClaw agent how to interact with MESH-API's REST API.

**Hooks:** `handle_command()` (query agent), `on_emergency()` (forward alerts), `send_message()` (relay tagged messages), `receive_message()` (poll queue).

---

## Extension Management

### Listing Extensions

Use the `/extensions` command on the mesh to see all loaded extensions and their status.

### Enabling/Disabling

Edit the extension's `config.json` and set `"enabled": true` or `"enabled": false`, then restart MESH-API.

### Extension Loading

Extensions are automatically discovered from the `extensions_path` directory (default: `./extensions`). Each subfolder containing an `extension.py` file is loaded. Folders starting with `_` (like `_example`) are skipped.

---

## See Also

- [DEVELOPING_EXTENSIONS.md](DEVELOPING_EXTENSIONS.md) — Guide for building custom extensions
- [README.md](README.md) — Main project documentation
