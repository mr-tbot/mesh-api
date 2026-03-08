import meshtastic
import meshtastic.serial_interface
from meshtastic import BROADCAST_ADDR
from pubsub import pub
import json
import requests
import time
from datetime import datetime, timedelta, timezone  # Added timezone import
import time
import threading
import os
import smtplib
from email.mime.text import MIMEText
import logging
import traceback
from flask import Flask, request, jsonify, redirect, url_for, stream_with_context, Response, send_file
import sys
import socket  # for socket error checking
import re
import io
import zipfile
import subprocess
import platform
import tempfile
import shutil
import errno
from twilio.rest import Client  # for Twilio SMS support
from unidecode import unidecode   # Added unidecode import for Ollama text normalization
from google.protobuf.message import DecodeError
import re
# Make sure DEBUG_ENABLED exists before any logger/filter classes use it
# -----------------------------
# Global Debug & Noise Patterns
# -----------------------------
# Debug flag loaded later from config.json
DEBUG_ENABLED = False
# Unique AI marker used to identify AI-originated messages (NOT configurable by design)
# Keep this at 3 characters max to minimize payload overhead.
AI_PREFIX_TAG = "m@i- "
# Track nodes that appear to be AI (sent messages starting with AI_PREFIX_TAG)
AI_NODE_IDS = set()
# Suppress these protobuf messages unless DEBUG_ENABLED=True
NOISE_PATTERNS = (
    "Error while parsing FromRadio",
    "Error parsing message with type 'meshtastic.protobuf.FromRadio'",
    "Traceback",
    "meshtastic/stream_interface.py",
    "meshtastic/mesh_interface.py",
)

class _ProtoNoiseFilter(logging.Filter):
    NOISY = (
        "Error while parsing FromRadio",
        "Error parsing message with type 'meshtastic.protobuf.FromRadio'",
    )

    def filter(self, rec: logging.LogRecord) -> bool:
        noisy = any(s in rec.getMessage() for s in self.NOISY)
        return DEBUG_ENABLED or not noisy        # show only in debug mode

root_log       = logging.getLogger()          # the root logger
meshtastic_log = logging.getLogger("meshtastic")

for lg in (root_log, meshtastic_log):
    lg.addFilter(_ProtoNoiseFilter())

def dprint(*args, **kwargs):
    if DEBUG_ENABLED:
        print(*args, **kwargs)

def info_print(*args, **kwargs):
  if not DEBUG_ENABLED:
    print(*args, **kwargs)
# -----------------------------
# Verbose Logging Setup
# -----------------------------
SCRIPT_LOG_FILE = "script.log"
script_logs = []  # In-memory log entries (most recent 200)
server_start_time = datetime.now(timezone.utc)  # Now using UTC time
restart_count = 0

def add_script_log(message):
    # drop protobuf noise if debug is off
    NOISE_PATTERNS = (
        "Error while parsing FromRadio",
        "Error parsing message with type 'meshtastic.protobuf.FromRadio'",
        "Traceback",
        "meshtastic/stream_interface.py",
        "meshtastic/mesh_interface.py",
    )
    if not DEBUG_ENABLED and any(p in message for p in NOISE_PATTERNS):
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log_entry = f"{timestamp} - {message}"
    script_logs.append(log_entry)
    if len(script_logs) > 200:
        script_logs.pop(0)
    try:
        # Truncate file if larger than 100 MB (keep last 100 lines)
        if os.path.exists(SCRIPT_LOG_FILE):
            filesize = os.path.getsize(SCRIPT_LOG_FILE)
            if filesize > 100 * 1024 * 1024:
                with open(SCRIPT_LOG_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                last_lines = lines[-100:] if len(lines) >= 100 else lines
                with open(SCRIPT_LOG_FILE, "w", encoding="utf-8") as f:
                    f.writelines(last_lines)
        with open(SCRIPT_LOG_FILE, "a", encoding="utf-8") as f:
            # append a real newline
            f.write(log_entry + "\n")
    except Exception as e:
        print(f"⚠️ Could not write to {SCRIPT_LOG_FILE}: {e}")
# Redirect stdout and stderr to our log while still printing to terminal.
class StreamToLogger(object):
    def __init__(self, logger_func):
        self.logger_func = logger_func
        self.terminal = sys.__stdout__
        # reuse noise patterns from the Proto filter
        self.noise_patterns = _ProtoNoiseFilter.NOISY if ' _ProtoNoiseFilter' in globals() else []

    def write(self, buf):
        # still print everything to the terminal...
        self.terminal.write(buf)
        text = buf.strip()
        if not text:
            return
        # only log to script_logs if not noisy, or if debug is on
        if DEBUG_ENABLED or not any(p in text for p in self.noise_patterns):
            self.logger_func(text)

    def flush(self):
        self.terminal.flush()

sys.stdout = StreamToLogger(add_script_log)
sys.stderr = StreamToLogger(add_script_log)
# -----------------------------
# Global Connection & Reset Status
# -----------------------------
connection_status = "Disconnected"
last_error_message = ""
reset_event = threading.Event()  # Global event to signal a fatal error and trigger reconnect

# Persistent HTTP session for AI providers (connection pooling)
http_session = requests.Session()
http_session.headers.update({"Content-Type": "application/json"})

# -----------------------------
# Meshtastic and Flask Setup
# -----------------------------
try:
    from meshtastic.tcp_interface import TCPInterface
except ImportError:
    TCPInterface = None

try:
    from meshtastic.ble_interface import BLEInterface
    BLE_INTERFACE_AVAILABLE = True
except ImportError:
    BLEInterface = None
    BLE_INTERFACE_AVAILABLE = False

try:
    from meshtastic.mesh_interface import MeshInterface
    MESH_INTERFACE_AVAILABLE = True
except ImportError:
    MESH_INTERFACE_AVAILABLE = False

log = logging.getLogger('werkzeug')
log.disabled = True

BANNER = (
    "\033[38;5;214m"
    """
███╗   ███╗███████╗███████╗██╗  ██╗       █████╗ ██████╗ ██╗
████╗ ████║██╔════╝██╔════╝██║  ██║      ██╔══██╗██╔══██╗██║
██╔████╔██║█████╗  ███████╗███████║█████╗███████║██████╔╝██║
██║╚██╔╝██║██╔══╝  ╚════██║██╔══██║╚════╝██╔══██║██╔═══╝ ██║
██║ ╚═╝ ██║███████╗███████║██║  ██║      ██║  ██║██║     ██║
╚═╝     ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝      ╚═╝  ╚═╝╚═╝     ╚═╝
                                                            

MESH-API v0.6.0 by: MR_TBOT (https://mr-tbot.com)
https://mesh-api.dev - (https://github.com/mr-tbot/mesh-api/)
    \033[32m 
Messaging Dashboard Access: http://localhost:5000/dashboard \033[38;5;214m
"""
    "\033[0m"
    "\033[31m"
    """
DISCLAIMER: This is beta software - NOT ASSOCIATED with the official Meshtastic (https://meshtastic.org/) project.
It should not be relied upon for mission critical tasks or emergencies.
Modification of this code for nefarious purposes is strictly frowned upon. Please use responsibly.

(Use at your own risk. For feedback or issues, visit https://mesh-api.dev or the links above.)
"""
    "\033[0m"
)
print(BANNER)
add_script_log("Script started.")

# -----------------------------
# Load Config Files
# -----------------------------
CONFIG_FILE = "config.json"
COMMANDS_CONFIG_FILE = "commands_config.json"
MOTD_FILE = "motd.json"
LOG_FILE = "messages.log"
ARCHIVE_FILE = "messages_archive.json"

print("Loading config files...")

def safe_load_json(path, default_value):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ {path} not found. Using defaults.")
    except Exception as e:
        print(f"⚠️ Could not load {path}: {e}")
    return default_value


_BUSY_ERRNOS = {
  errno.EACCES,
  errno.EBUSY,
  errno.EPERM,
  16,   # POSIX EBUSY on some platforms
  26,   # DOS sharing violation equivalents
  32,   # Windows ERROR_SHARING_VIOLATION
}


def _replace_with_retries(src_path: str, dest_path: str, attempts: int = 10, base_delay: float = 0.15):
  """Atomically replace dest_path with src_path, retrying if the destination is busy.

  Windows can momentarily lock files (antivirus, indexing, other processes). We retry a
  few times with incremental backoff before surfacing the original exception. As a last
  resort we fall back to copying the file contents in-place (non-atomic but better than
  failing outright).
  """
  last_exc: OSError | None = None
  for attempt in range(attempts):
    try:
      os.replace(src_path, dest_path)
      return
    except OSError as exc:
      last_exc = exc
      err_no = getattr(exc, "errno", None)
      if err_no not in _BUSY_ERRNOS:
        break
      time.sleep(base_delay * (attempt + 1))

  if last_exc is not None:
    err_no = getattr(last_exc, "errno", None)
    if err_no in _BUSY_ERRNOS:
      try:
        with open(src_path, "rb") as src, open(dest_path, "wb") as dest:
          shutil.copyfileobj(src, dest)
        os.remove(src_path)
        return
      except Exception as fallback_exc:
        last_exc = fallback_exc if isinstance(fallback_exc, OSError) else last_exc
    raise last_exc

  raise RuntimeError("_replace_with_retries reached an impossible state")


def _atomic_write_json(path: str, obj: dict):
  """Write JSON to `path` using a temporary file + atomic replace with retries."""
  dir_name = os.path.dirname(path) or "."
  prefix = os.path.basename(path) + "."
  fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=dir_name)
  try:
    with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
      json.dump(obj, tmp_file, ensure_ascii=False, indent=2)
    _replace_with_retries(tmp_path, path)
  except Exception:
    try:
      os.remove(tmp_path)
    except OSError:
      pass
    raise


def _atomic_write_text(path: str, text: str):
  """Write plain text to `path` atomically with retry-aware replacement."""
  dir_name = os.path.dirname(path) or "."
  prefix = os.path.basename(path) + "."
  fd, tmp_path = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=dir_name)
  try:
    with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
      tmp_file.write(text)
    _replace_with_retries(tmp_path, path)
  except Exception:
    try:
      os.remove(tmp_path)
    except OSError:
      pass
    raise

config = safe_load_json(CONFIG_FILE, {})
commands_config = safe_load_json(COMMANDS_CONFIG_FILE, {"commands": []})
try:
    with open(MOTD_FILE, "r", encoding="utf-8") as f:
        motd_content = f.read()
except FileNotFoundError:
    print(f"⚠️ {MOTD_FILE} not found.")
    motd_content = "No MOTD available."


# Config Editor endpoints are defined after app initialization below



# -----------------------------
# AI Provider & Other Config Vars
# -----------------------------
DEBUG_ENABLED = bool(config.get("debug", False))
AI_PROVIDER = config.get("ai_provider", "lmstudio").lower()
SYSTEM_PROMPT = config.get("system_prompt", "You are a helpful assistant responding to mesh network chats.")
LMSTUDIO_URL = config.get("lmstudio_url", "http://localhost:1234/v1/chat/completions")
LMSTUDIO_TIMEOUT = config.get("lmstudio_timeout", 60)
LMSTUDIO_CHAT_MODEL = config.get(
    "lmstudio_chat_model",
    "llama-3.2-1b-instruct-uncensored",
)
LMSTUDIO_EMBEDDING_MODEL = config.get(
    "lmstudio_embedding_model",
    "text-embedding-nomic-embed-text-v1.5",	
)	
OPENAI_API_KEY = config.get("openai_api_key", "")
OPENAI_MODEL = config.get("openai_model", "gpt-3.5-turbo")
OPENAI_TIMEOUT = config.get("openai_timeout", 30)
OLLAMA_URL = config.get("ollama_url", "http://localhost:11434/api/generate")
OLLAMA_MODEL = config.get("ollama_model", "llama2")
OLLAMA_TIMEOUT = config.get("ollama_timeout", 60)
# Optional advanced Ollama settings to improve stability/quality
OLLAMA_OPTIONS = config.get("ollama_options", {})  # e.g., {"temperature": 0.7}
OLLAMA_KEEP_ALIVE = config.get("ollama_keep_alive", "10m")  # keep model loaded
CLAUDE_API_KEY = config.get("claude_api_key", "")
CLAUDE_MODEL = config.get("claude_model", "claude-sonnet-4-20250514")
CLAUDE_TIMEOUT = config.get("claude_timeout", 60)
GEMINI_API_KEY = config.get("gemini_api_key", "")
GEMINI_MODEL = config.get("gemini_model", "gemini-2.0-flash")
GEMINI_TIMEOUT = config.get("gemini_timeout", 60)
GROK_API_KEY = config.get("grok_api_key", "")
GROK_MODEL = config.get("grok_model", "grok-3")
GROK_TIMEOUT = config.get("grok_timeout", 60)
OPENROUTER_API_KEY = config.get("openrouter_api_key", "")
OPENROUTER_MODEL = config.get("openrouter_model", "openai/gpt-4.1-mini")
OPENROUTER_TIMEOUT = config.get("openrouter_timeout", 60)
GROQ_API_KEY = config.get("groq_api_key", "")
GROQ_MODEL = config.get("groq_model", "llama-3.3-70b-versatile")
GROQ_TIMEOUT = config.get("groq_timeout", 60)
DEEPSEEK_API_KEY = config.get("deepseek_api_key", "")
DEEPSEEK_MODEL = config.get("deepseek_model", "deepseek-chat")
DEEPSEEK_TIMEOUT = config.get("deepseek_timeout", 60)
MISTRAL_API_KEY = config.get("mistral_api_key", "")
MISTRAL_MODEL = config.get("mistral_model", "mistral-small-latest")
MISTRAL_TIMEOUT = config.get("mistral_timeout", 60)
OPENAI_COMPAT_API_KEY = config.get("openai_compatible_api_key", "")
OPENAI_COMPAT_URL = config.get("openai_compatible_url", "")
OPENAI_COMPAT_MODEL = config.get("openai_compatible_model", "")
OPENAI_COMPAT_TIMEOUT = config.get("openai_compatible_timeout", 60)
HOME_ASSISTANT_URL = config.get("home_assistant_url", "")
HOME_ASSISTANT_TOKEN = config.get("home_assistant_token", "")
HOME_ASSISTANT_TIMEOUT = config.get("home_assistant_timeout", 30)
HOME_ASSISTANT_ENABLE_PIN = bool(config.get("home_assistant_enable_pin", False))
HOME_ASSISTANT_SECURE_PIN = str(config.get("home_assistant_secure_pin", "1234"))
HOME_ASSISTANT_ENABLED = bool(config.get("home_assistant_enabled", False))
HOME_ASSISTANT_CHANNEL_INDEX = int(config.get("home_assistant_channel_index", -1))
MAX_CHUNK_SIZE = config.get("chunk_size", 200)
MAX_CHUNKS = int(config.get("max_ai_chunks", 5))
CHUNK_DELAY = config.get("chunk_delay", 10)
MAX_RESPONSE_LENGTH = MAX_CHUNK_SIZE * MAX_CHUNKS
LOCAL_LOCATION_STRING = config.get("local_location_string", "Unknown Location")
AI_NODE_NAME = config.get("ai_node_name", "AI-Bot")
FORCE_NODE_NUM = config.get("force_node_num", None)

ENABLE_DISCORD = config.get("enable_discord", False)
DISCORD_WEBHOOK_URL = config.get("discord_webhook_url", None)
DISCORD_SEND_EMERGENCY = config.get("discord_send_emergency", False)
DISCORD_SEND_AI = config.get("discord_send_ai", False)
DISCORD_SEND_ALL = config.get("discord_send_all", False)
DISCORD_RESPONSE_CHANNEL_INDEX = config.get("discord_response_channel_index", None)
DISCORD_RECEIVE_ENABLED = config.get("discord_receive_enabled", True)
# New variable for inbound routing
DISCORD_INBOUND_CHANNEL_INDEX = config.get("discord_inbound_channel_index", None)
if DISCORD_INBOUND_CHANNEL_INDEX is not None:
    DISCORD_INBOUND_CHANNEL_INDEX = int(DISCORD_INBOUND_CHANNEL_INDEX)
# For polling Discord messages (optional)
DISCORD_BOT_TOKEN = config.get("discord_bot_token", None)
DISCORD_CHANNEL_ID = config.get("discord_channel_id", None)

ENABLE_TWILIO = config.get("enable_twilio", False)
ENABLE_SMTP = config.get("enable_smtp", False)
ALERT_PHONE_NUMBER = config.get("alert_phone_number", None)
TWILIO_SID = config.get("twilio_sid", None)
TWILIO_AUTH_TOKEN = config.get("twilio_auth_token", None)
TWILIO_FROM_NUMBER = config.get("twilio_from_number", None)
SMTP_HOST = config.get("smtp_host", None)
SMTP_PORT = config.get("smtp_port", 587)
SMTP_USER = config.get("smtp_user", None)
SMTP_PASS = config.get("smtp_pass", None)
ALERT_EMAIL_TO = config.get("alert_email_to", None)

SERIAL_PORT = config.get("serial_port", "")
SERIAL_BAUD = int(config.get("serial_baud", 921600))  # ← NEW ● default 921600
USE_WIFI = bool(config.get("use_wifi", False))
WIFI_HOST = config.get("wifi_host", None)
WIFI_PORT = int(config.get("wifi_port", 4403))
USE_BLUETOOTH = bool(config.get("use_bluetooth", False))
BLE_ADDRESS = config.get("ble_address", "")
USE_MESH_INTERFACE = bool(config.get("use_mesh_interface", False))

# Safeguards and network behavior toggles
# - ai_respond_on_longfast: if False (default), the bot will NOT reply on channel 0 (LongFast)
# - respond_to_mqtt_messages: if False (default), the bot will ignore messages received via MQTT
AI_RESPOND_ON_LONGFAST = bool(config.get("ai_respond_on_longfast", False))
RESPOND_TO_MQTT_MESSAGES = bool(config.get("respond_to_mqtt_messages", False))

# Randomized, per-install AI command alias. Generated on first run to reduce collisions
def _ensure_ai_command_alias():
  alias = config.get("ai_command")
  # Enforce a randomized alias; do not allow bare "/ai" as a default
  if isinstance(alias, str) and alias.startswith("/") and len(alias) <= 12:
    # Disallow bare "/ai" and "/ai-"
    if alias.lower() not in ("/ai", "/ai-"):
      return alias
  import random, string
  # Build a short alias like /ai-x7 or /ai5k
  suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=2))
  alias = f"/ai-{suffix}"
  config["ai_command"] = alias
  try:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
      json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"Generated randomized AI command alias: {alias} (saved to {CONFIG_FILE})")
  except Exception as e:
    print(f"⚠️ Could not persist ai_command alias to {CONFIG_FILE}: {e}")
  return alias

AI_COMMAND_ALIAS = _ensure_ai_command_alias()

# Derive unique suffix from the alias
# Support both old style ("/ai9z") and new dashed style ("/ai-9z") for parsing
_m = re.match(r"^(?:/ai-([a-z0-9]+)|/ai([a-z0-9]+))$", AI_COMMAND_ALIAS or "", re.IGNORECASE)
AI_SUFFIX = (_m.group(1) or _m.group(2)) if _m else ""

# Canonical, dashed AI alias for display (always shows as /ai-xx)
AI_ALIAS_CANONICAL = f"/ai-{AI_SUFFIX}" if AI_SUFFIX else AI_COMMAND_ALIAS

# Only dashed suffixed commands are allowed (no bare defaults)
AI_COMMANDS = [
  f"/ai-{AI_SUFFIX}",
  f"/bot-{AI_SUFFIX}",
  f"/query-{AI_SUFFIX}",
  f"/data-{AI_SUFFIX}",
]

# SMS also requires the unique dashed suffix
SMS_COMMAND = f"/sms-{AI_SUFFIX}"

# Other built-ins that must also use the unique dashed suffix
ABOUT_COMMAND = f"/about-{AI_SUFFIX}"
WHEREAMI_COMMAND = f"/whereami-{AI_SUFFIX}"
TEST_COMMAND = None  # /test remains unsuffixed by request
HELP_COMMAND = f"/help-{AI_SUFFIX}"
MOTD_COMMAND = f"/motd-{AI_SUFFIX}"

app = Flask(__name__)
messages = []
interface = None
STARTUP_INFO_PRINTED = False  # guard to avoid duplicate startup prints

lastDMNode = None
lastChannelIndex = None

# -----------------------------
# Extension System Initialisation
# -----------------------------
EXTENSIONS_PATH = config.get("extensions_path", "./extensions")
extension_loader = None  # initialised in main() after helpers are defined

# -----------------------------
# Location Lookup Function
# -----------------------------
def get_node_location(node_id):
    if interface and hasattr(interface, "nodes") and node_id in interface.nodes:
        pos = interface.nodes[node_id].get("position", {})
        lat = pos.get("latitude")
        lon = pos.get("longitude")
        tstamp = pos.get("time")
        return lat, lon, tstamp
    return None, None, None

# -----------------------------
# Config Editor Endpoints (after app creation)
# -----------------------------
@app.route("/config_editor/load", methods=["GET"])
def config_editor_load():
  try:
    cfg = safe_load_json(CONFIG_FILE, {})
    cmds = safe_load_json(COMMANDS_CONFIG_FILE, {"commands": []})
    try:
      with open(MOTD_FILE, "r", encoding="utf-8") as f:
        motd = f.read()
    except FileNotFoundError:
      motd = ""
    return jsonify({"config": cfg, "commands_config": cmds, "motd": motd})
  except Exception as e:
    return jsonify({"message": str(e)}), 500

@app.route("/config_editor/save", methods=["POST"])
def config_editor_save():
  try:
    data = request.get_json(force=True) or {}
    cfg = data.get("config", {})
    cmds = data.get("commands_config", {})
    motd = data.get("motd", "")
    if not isinstance(cfg, dict):
      return jsonify({"message": "config must be a JSON object"}), 400
    if not isinstance(cmds, dict):
      return jsonify({"message": "commands_config must be a JSON object"}), 400
    _atomic_write_json(CONFIG_FILE, cfg)
    _atomic_write_json(COMMANDS_CONFIG_FILE, cmds)
    _atomic_write_text(MOTD_FILE, motd)
    return jsonify({"status": "ok"})
  except Exception as e:
    return jsonify({"message": str(e)}), 500

# --- Config backup: return a ZIP of config and logs that matter ---
@app.route("/config_editor/backup", methods=["GET"])
def config_editor_backup():
  try:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
      # Add core config files if present
      for p in (CONFIG_FILE, COMMANDS_CONFIG_FILE, MOTD_FILE):
        if os.path.exists(p):
          zf.write(p, arcname=f"config/{os.path.basename(p)}")
      # Add last logs if present
      if os.path.exists(LOG_FILE):
        zf.write(LOG_FILE, arcname=f"logs/{os.path.basename(LOG_FILE)}")
      if os.path.exists(SCRIPT_LOG_FILE):
        zf.write(SCRIPT_LOG_FILE, arcname=f"logs/{os.path.basename(SCRIPT_LOG_FILE)}")
      if os.path.exists(ARCHIVE_FILE):
        zf.write(ARCHIVE_FILE, arcname=f"logs/{os.path.basename(ARCHIVE_FILE)}")
    mem.seek(0)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return send_file(mem, as_attachment=True, download_name=f"mesh-api-backup-{ts}.zip", mimetype="application/zip")
  except Exception as e:
    return jsonify({"message": str(e)}), 500

# --- Extension Management API Endpoints ---
@app.route("/extensions/status", methods=["GET"])
def extensions_status():
  """Return status of all extensions (loaded and available)."""
  if not extension_loader:
    return jsonify({"loaded": {}, "available": {}})
  loaded_info = {}
  for slug, ext in extension_loader.loaded.items():
    loaded_info[slug] = {
      "name": ext.name,
      "version": ext.version,
      "enabled": True,
      "commands": list(ext.commands.keys()),
    }
  return jsonify({"loaded": loaded_info, "available": extension_loader.available})

@app.route("/extensions/config/<slug>", methods=["GET"])
def extensions_config_get(slug):
  """Return the config.json for a specific extension."""
  ext_path = os.path.join(os.path.abspath(EXTENSIONS_PATH), slug, "config.json")
  if not os.path.isfile(ext_path):
    return jsonify({"message": f"Extension '{slug}' config not found"}), 404
  try:
    with open(ext_path, "r", encoding="utf-8") as f:
      ext_config = json.load(f)
    return jsonify(ext_config)
  except Exception as e:
    return jsonify({"message": str(e)}), 500

@app.route("/extensions/config/<slug>", methods=["PUT", "POST"])
def extensions_config_save(slug):
  """Save updated config.json for a specific extension."""
  # Validate slug to prevent path traversal
  if "/" in slug or "\\" in slug or ".." in slug:
    return jsonify({"message": "Invalid extension name"}), 400
  ext_path = os.path.join(os.path.abspath(EXTENSIONS_PATH), slug, "config.json")
  if not os.path.isfile(ext_path):
    return jsonify({"message": f"Extension '{slug}' config not found"}), 404
  try:
    data = request.get_json(force=True)
    if not isinstance(data, dict):
      return jsonify({"message": "Config must be a JSON object"}), 400
    _atomic_write_json(ext_path, data)
    add_script_log(f"[WebUI] Extension '{slug}' config saved.")
    return jsonify({"status": "ok"})
  except Exception as e:
    return jsonify({"message": str(e)}), 500

@app.route("/extensions/toggle/<slug>", methods=["POST"])
def extensions_toggle(slug):
  """Toggle an extension's enabled state and return new state."""
  if "/" in slug or "\\" in slug or ".." in slug:
    return jsonify({"message": "Invalid extension name"}), 400
  ext_path = os.path.join(os.path.abspath(EXTENSIONS_PATH), slug, "config.json")
  if not os.path.isfile(ext_path):
    return jsonify({"message": f"Extension '{slug}' config not found"}), 404
  try:
    with open(ext_path, "r", encoding="utf-8") as f:
      ext_config = json.load(f)
    ext_config["enabled"] = not ext_config.get("enabled", False)
    _atomic_write_json(ext_path, ext_config)
    new_state = ext_config["enabled"]
    add_script_log(f"[WebUI] Extension '{slug}' {'enabled' if new_state else 'disabled'}.")
    return jsonify({"status": "ok", "enabled": new_state, "note": "Restart required for changes to take effect."})
  except Exception as e:
    return jsonify({"message": str(e)}), 500

@app.route("/extensions/reload", methods=["POST"])
def extensions_reload():
  """Hot-reload all extensions."""
  if not extension_loader:
    return jsonify({"message": "Extension system not available"}), 503
  try:
    extension_loader.reload()
    add_script_log("[WebUI] Extensions hot-reloaded.")
    return jsonify({"status": "ok"})
  except Exception as e:
    return jsonify({"message": str(e)}), 500

# --- Soft restart: signal reconnect and reload config ---
@app.route("/restart", methods=["POST"])
def restart_service():
  try:
    data = request.get_json(silent=True) or {}
    mode = (data.get("mode") or "soft").lower()
    if mode == "hard":
      add_script_log("Hard restart requested via WebUI.")
      # Spawn a fresh process and exit current one
      python = sys.executable
      args = [python, os.path.abspath(__file__)]
      creationflags = 0
      # On Windows, detach new console to avoid blocking
      if platform.system() == 'Windows':
        creationflags = getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)
      subprocess.Popen(args, close_fds=True, creationflags=creationflags)
      # Delay exit slightly to allow HTTP response to flush
      threading.Timer(0.5, lambda: os._exit(0)).start()
      return jsonify({"status": "hard-restarting"})
    else:
      # Soft restart: signal interface loop to reconnect
      reset_event.set()
      add_script_log("Soft restart requested via WebUI.")
      return jsonify({"status": "soft-restarting"})
  except Exception as e:
    return jsonify({"message": str(e)}), 500

def load_archive():
    global messages
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
                arr = json.load(f)
            if isinstance(arr, list):
                messages = arr
                print(f"Loaded {len(messages)} messages from archive.")
        except Exception as e:
            print(f"⚠️ Could not load archive {ARCHIVE_FILE}: {e}")
    else:
        print("No archive found; starting fresh.")

def save_archive():
    try:
        with open(ARCHIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save archive to {ARCHIVE_FILE}: {e}")

def parse_node_id(node_str_or_int):
    if isinstance(node_str_or_int, int):
        return node_str_or_int
    if isinstance(node_str_or_int, str):
        if node_str_or_int == '^all':
            return BROADCAST_ADDR
        if node_str_or_int.lower() in ['!ffffffff', '!ffffffffl']:
            return BROADCAST_ADDR
        if node_str_or_int.startswith('!'):
            hex_part = node_str_or_int[1:]
            try:
                return int(hex_part, 16)
            except ValueError:
                dprint(f"parse_node_id: Unable to parse hex from {node_str_or_int}")
                return None
        try:
            return int(node_str_or_int)
        except ValueError:
            dprint(f"parse_node_id: {node_str_or_int} not recognized as int or hex.")
            return None
    return None

def get_node_fullname(node_id):
    """Return the full (long) name if available, otherwise the short name."""
    if interface and hasattr(interface, "nodes") and node_id in interface.nodes:
        user_dict = interface.nodes[node_id].get("user", {})
        return user_dict.get("longName", user_dict.get("shortName", f"Node_{node_id}"))
    return f"Node_{node_id}"

def get_node_shortname(node_id):
    if interface and hasattr(interface, "nodes") and node_id in interface.nodes:
        user_dict = interface.nodes[node_id].get("user", {})
        return user_dict.get("shortName", f"Node_{node_id}")
    return f"Node_{node_id}"

def log_message(node_id, text, is_emergency=False, reply_to=None, direct=False, channel_idx=None):
    if node_id != "WebUI":
        display_id = f"{get_node_shortname(node_id)} ({node_id})"
    else:
        display_id = "WebUI"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    entry = {
        "timestamp": timestamp,
        "node": display_id,
        "node_id": None if node_id == "WebUI" else node_id,
        "message": text,
        "emergency": is_emergency,
        "reply_to": reply_to,
        "direct": direct,
        "channel_idx": channel_idx
    }
    messages.append(entry)
    if len(messages) > 100:
        messages.pop(0)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as logf:
            logf.write(f"{timestamp} | {display_id} | EMERGENCY={is_emergency} | {text}\n")
    except Exception as e:
        print(f"⚠️ Could not write to {LOG_FILE}: {e}")
    save_archive()
    return entry

def split_message(text):
    if not text:
        return []
    chunks = []
    remaining = text
    for _ in range(MAX_CHUNKS):
        if not remaining:
            break
        if len(remaining) <= MAX_CHUNK_SIZE:
            chunks.append(remaining)
            break
        # Try to split at a word boundary
        slice_end = MAX_CHUNK_SIZE
        space_idx = remaining.rfind(' ', 0, slice_end)
        if space_idx > slice_end // 2:
            slice_end = space_idx
        chunks.append(remaining[:slice_end].rstrip())
        remaining = remaining[slice_end:].lstrip()
    return chunks

def add_ai_prefix(text: str) -> str:
  """Prefix AI marker if not already present."""
  t = (text or "").lstrip()
  if t.startswith(AI_PREFIX_TAG):
    return text
  # Tag already includes trailing hyphen and space
  return f"{AI_PREFIX_TAG}{text}" if text else text

def sanitize_model_output(text: str) -> str:
  """Remove any 'thinking' style tags/blocks and normalize output for mesh.

  Strips XML-like think tags, fenced blocks labeled as thinking/analysis/etc.,
  bracketed/parenthesized meta notes, YAML/JSON-style reasoning fields, and
  common heading lines like "Thought:". Also normalizes to printable ASCII
  and collapses whitespace.
  """
  if not text:
    return ""
  s = str(text)
  try:
    # XML-like think blocks
    s = re.sub(r"<(?:think|thought|chain[ _\s-]*of[ _\s-]*thought)[^>]*>.*?</(?:think|thought|chain[ _\s-]*of[ _\s-]*thought)>", "", s, flags=re.IGNORECASE | re.DOTALL)
    # Fenced blocks labeled as thinking/meta
    s = re.sub(r"```[ \t]*(?:thinking|analysis|reasoning|plan|thoughts?|cot|chain[ _\s-]*of[ _\s-]*thought|inner(?:\s|-)?monologue|reflection|critique)\b[\s\S]*?```", "", s, flags=re.IGNORECASE)
    # Inline meta markers
    s = re.sub(r"\[(?:\s*(?:think|thinking|thoughts?|reasoning|analysis|plan|critique|reflection)[^\]]*)\]", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\((?:\s*(?:think|thinking|thoughts?|reasoning|analysis|plan|critique|reflection)[^\)]*)\)", "", s, flags=re.IGNORECASE)
    # Fullwidth bracket meta
    s = re.sub(r"【[^】]*】", "", s)
    # Heading lines like "Thought:", "Reasoning:", etc.
    s = re.sub(r"(?mi)^\s*(?:Thoughts?|Thinking|Reasoning|Analysis|Reflection|Critique|Self-critique|Chain\s*of\s*Thought|COT|Inner\s*Monologue|Plan|System|Tool|Action|Observation)\s*:\s*.*$\n?", "", s)
    # YAML-like sections (reasoning: | then indented lines)
    s = re.sub(r"(?mis)^\s*(?:reasoning|analysis|thoughts?|plan|critique|inner[ _-]?monologue|chain[ _-]?of[ _-]?thought|cot)\s*:\s*(?:\|\s*)?(?:\n(?:\s{2,}.+))*", "", s)
    # [BEGIN REASONING] ... [END REASONING]
    s = re.sub(r"\[\s*BEGIN[^\]]*(?:REASONING|THINKING|ANALYSIS)[^\]]*\][\s\S]*?\[\s*END[^\]]*\]", "", s, flags=re.IGNORECASE)
    # JSON-like meta fields
    s = re.sub(r"\"(?:reasoning|analysis|thoughts?|plan|critique|inner[_\s-]?monologue)\"\s*:\s*\"(?:\\\"|[^\"])*\"\s*,?", "", s, flags=re.IGNORECASE)
    # Normalize and collapse
    s = unidecode(s)
    s = ''.join(ch for ch in s if ch.isprintable())
    s = ' '.join(s.split())
    return s
  except Exception:
    return s

def send_broadcast_chunks(interface, text, channelIndex):
    dprint(f"send_broadcast_chunks: text='{text}', channelIndex={channelIndex}")
    info_print(f"[Info] Sending broadcast on channel {channelIndex} → '{text}'")
    if interface is None:
        print("❌ Cannot send broadcast: interface is None.")
        return
    if not text:
        return
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        try:
            interface.sendText(chunk, destinationId=BROADCAST_ADDR, channelIndex=channelIndex, wantAck=True)
            time.sleep(CHUNK_DELAY)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError) as e:
            print(f"❌ Connection error sending broadcast chunk: {e}")
            reset_event.set()
            break
        except Exception as e:
            print(f"❌ Error sending broadcast chunk: {e}")
            error_code = getattr(e, 'errno', None) or getattr(e, 'winerror', None)
            if error_code in (10053, 10054, 10060):
                reset_event.set()
            break
        else:
            info_print(f"[Info] Successfully sent chunk {i+1}/{len(chunks)} on ch={channelIndex}.")

def send_direct_chunks(interface, text, destinationId):
    dprint(f"send_direct_chunks: text='{text}', destId={destinationId}")
    info_print(f"[Info] Sending direct message to node {destinationId} => '{text}'")
    if interface is None:
        print("❌ Cannot send direct message: interface is None.")
        return
    if not text:
        return
    ephemeral_ok = hasattr(interface, "sendDirectText")
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        try:
            if ephemeral_ok:
                interface.sendDirectText(destinationId, chunk, wantAck=True)
            else:
                interface.sendText(chunk, destinationId=destinationId, wantAck=True)
            time.sleep(CHUNK_DELAY)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError) as e:
            print(f"❌ Connection error sending direct chunk: {e}")
            reset_event.set()
            break
        except Exception as e:
            print(f"❌ Error sending direct chunk: {e}")
            error_code = getattr(e, 'errno', None) or getattr(e, 'winerror', None)
            if error_code in (10053, 10054, 10060):
                reset_event.set()
            break
        else:
            info_print(f"[Info] Direct chunk {i+1}/{len(chunks)} to {destinationId} sent.")

def send_to_lmstudio(user_message: str):
    """Chat/completion request to LM Studio with explicit model name."""
    dprint(f"send_to_lmstudio: user_message='{user_message}'")
    info_print("[Info] Routing user message to LMStudio…")
    payload = {
        "model": LMSTUDIO_CHAT_MODEL,  # **mandatory when multiple models loaded**
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        "max_tokens": MAX_RESPONSE_LENGTH,
    }
    try:
        response = requests.post(LMSTUDIO_URL, json=payload, timeout=LMSTUDIO_TIMEOUT)
        if response.status_code == 200:
            j = response.json()
            dprint(f"LMStudio raw ⇒ {j}")
            ai_resp = (
                j.get("choices", [{}])[0]
                  .get("message", {})
                  .get("content", "🤖 [No response]")
            )
            ai_resp = sanitize_model_output(ai_resp)
            return ai_resp[:MAX_RESPONSE_LENGTH]
        else:
            print(f"⚠️ LMStudio error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"⚠️ LMStudio request failed: {e}")
        return None
def lmstudio_embed(text: str):
    """Return an embedding vector (if you ever need it)."""
    payload = {
        "model": LMSTUDIO_EMBEDDING_MODEL,
        "input": text,
															   
    }
    try:
        r = requests.post(
            "http://localhost:1234/v1/embeddings",
            json=payload,
            timeout=LMSTUDIO_TIMEOUT,
        )
        if r.status_code == 200:
            vec = r.json().get("data", [{}])[0].get("embedding")
            return vec
        else:
            dprint(f"LMStudio embed error {r.status_code}: {r.text}")
					   
    except Exception as exc:
        dprint(f"LMStudio embed exception: {exc}")
    return None
def send_to_openai(user_message):
    dprint(f"send_to_openai: user_message='{user_message}'")
    info_print("[Info] Routing user message to OpenAI...")
    if not OPENAI_API_KEY:
        print("⚠️ No OpenAI API key provided.")
        return None
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": MAX_RESPONSE_LENGTH
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=OPENAI_TIMEOUT)
        if r.status_code == 200:
            jr = r.json()
            dprint(f"OpenAI raw => {jr}")
            content = (
                jr.get("choices", [{}])[0]
                  .get("message", {})
                  .get("content", "🤖 [No response]")
            )
            content = sanitize_model_output(content)
            return content[:MAX_RESPONSE_LENGTH]
        else:
            print(f"⚠️ OpenAI error: {r.status_code} => {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ OpenAI request failed: {e}")
        return None

def send_to_ollama(user_message):
    dprint(f"send_to_ollama: user_message='{user_message}'")
    info_print("[Info] Routing user message to Ollama...")
    # Normalize text for non-ASCII characters using unidecode
    user_message = unidecode(user_message)
    combined_prompt = f"{SYSTEM_PROMPT}\n{user_message}"
    payload = {
        "prompt": combined_prompt,
        "model": OLLAMA_MODEL,
        "stream": False,  # Disable streaming responses for simpler parsing
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "options": OLLAMA_OPTIONS,
    }

    # Simple retry for transient failures
    def _sanitize(text: str) -> str:
        try:
            t = text or ""
            # Normalize weird unicode and strip control chars
            t = unidecode(t)
            t = ''.join(ch for ch in t if ch.isprintable())
            # Collapse excessive whitespace
            return ' '.join(t.split())
        except Exception:
            return text or ""

    # Hint Ollama to limit token generation to avoid wasting time on text that gets truncated
    payload["options"] = dict(payload.get("options") or {})
    payload["options"].setdefault("num_predict", MAX_RESPONSE_LENGTH)

    for attempt in range(2):  # up to 2 attempts
        try:
            r = http_session.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
            if r.status_code == 200:
                jr = r.json()
                dprint(f"Ollama raw => {jr}")
                resp = jr.get("response", "")
                clean = sanitize_model_output(_sanitize(resp))
                return (clean if clean else "🤖 [No response]")[:MAX_RESPONSE_LENGTH]
            else:
                print(f"⚠️ Ollama error: {r.status_code} => {r.text}")
        except Exception as e:
            print(f"⚠️ Ollama request failed (attempt {attempt+1}): {e}")
        time.sleep(0.5 * (attempt + 1))
    return None

def send_to_claude(user_message):
    dprint(f"send_to_claude: user_message='{user_message}'")
    info_print("[Info] Routing user message to Claude...")
    if not CLAUDE_API_KEY:
        print("⚠️ No Claude API key provided.")
        return None
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": MAX_RESPONSE_LENGTH,
        "system": SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": user_message}
        ],
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=CLAUDE_TIMEOUT)
        if r.status_code == 200:
            jr = r.json()
            dprint(f"Claude raw => {jr}")
            content_blocks = jr.get("content", [])
            text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            content = " ".join(text_parts) if text_parts else "🤖 [No response]"
            content = sanitize_model_output(content)
            return content[:MAX_RESPONSE_LENGTH]
        else:
            print(f"⚠️ Claude error: {r.status_code} => {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ Claude request failed: {e}")
        return None

def send_to_gemini(user_message):
    dprint(f"send_to_gemini: user_message='{user_message}'")
    info_print("[Info] Routing user message to Gemini...")
    if not GEMINI_API_KEY:
        print("⚠️ No Gemini API key provided.")
        return None
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {"role": "user", "parts": [{"text": user_message}]}
        ],
        "generationConfig": {
            "maxOutputTokens": MAX_RESPONSE_LENGTH,
        },
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=GEMINI_TIMEOUT)
        if r.status_code == 200:
            jr = r.json()
            dprint(f"Gemini raw => {jr}")
            candidates = jr.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                content = " ".join(p.get("text", "") for p in parts)
            else:
                content = "🤖 [No response]"
            content = sanitize_model_output(content)
            return content[:MAX_RESPONSE_LENGTH]
        else:
            print(f"⚠️ Gemini error: {r.status_code} => {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ Gemini request failed: {e}")
        return None

# -----------------------------
# Generic OpenAI-Compatible Helper
# -----------------------------
def _send_to_openai_compatible(user_message, provider_name, api_key, base_url, model, timeout):
    """Shared helper for any provider with an OpenAI-compatible chat/completions API."""
    dprint(f"send_to_{provider_name}: user_message='{user_message}'")
    info_print(f"[Info] Routing user message to {provider_name}...")
    if not api_key:
        print(f"⚠️ No {provider_name} API key provided.")
        return None
    url = base_url.rstrip("/") + "/chat/completions" if "/chat/completions" not in base_url else base_url
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": MAX_RESPONSE_LENGTH,
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if r.status_code == 200:
            jr = r.json()
            dprint(f"{provider_name} raw => {jr}")
            content = (
                jr.get("choices", [{}])[0]
                  .get("message", {})
                  .get("content", "🤖 [No response]")
            )
            content = sanitize_model_output(content)
            return content[:MAX_RESPONSE_LENGTH]
        else:
            print(f"⚠️ {provider_name} error: {r.status_code} => {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ {provider_name} request failed: {e}")
        return None

def send_to_grok(user_message):
    return _send_to_openai_compatible(
        user_message, "Grok", GROK_API_KEY,
        "https://api.x.ai/v1/chat/completions", GROK_MODEL, GROK_TIMEOUT)

def send_to_openrouter(user_message):
    return _send_to_openai_compatible(
        user_message, "OpenRouter", OPENROUTER_API_KEY,
        "https://openrouter.ai/api/v1/chat/completions", OPENROUTER_MODEL, OPENROUTER_TIMEOUT)

def send_to_groq(user_message):
    return _send_to_openai_compatible(
        user_message, "Groq", GROQ_API_KEY,
        "https://api.groq.com/openai/v1/chat/completions", GROQ_MODEL, GROQ_TIMEOUT)

def send_to_deepseek(user_message):
    return _send_to_openai_compatible(
        user_message, "DeepSeek", DEEPSEEK_API_KEY,
        "https://api.deepseek.com/v1/chat/completions", DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT)

def send_to_mistral(user_message):
    return _send_to_openai_compatible(
        user_message, "Mistral", MISTRAL_API_KEY,
        "https://api.mistral.ai/v1/chat/completions", MISTRAL_MODEL, MISTRAL_TIMEOUT)

def send_to_openai_compatible(user_message):
    if not OPENAI_COMPAT_URL:
        print("⚠️ No openai_compatible_url configured.")
        return None
    return _send_to_openai_compatible(
        user_message, "OpenAI-Compatible", OPENAI_COMPAT_API_KEY,
        OPENAI_COMPAT_URL, OPENAI_COMPAT_MODEL, OPENAI_COMPAT_TIMEOUT)

def send_to_home_assistant(user_message):
    dprint(f"send_to_home_assistant: user_message='{user_message}'")
    info_print("[Info] Routing user message to Home Assistant...")
    if not HOME_ASSISTANT_URL:
        return None
    headers = {"Content-Type": "application/json"}
    if HOME_ASSISTANT_TOKEN:
        headers["Authorization"] = f"Bearer {HOME_ASSISTANT_TOKEN}"
    payload = {"text": user_message}
    try:
        r = requests.post(HOME_ASSISTANT_URL, json=payload, headers=headers, timeout=HOME_ASSISTANT_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            dprint(f"HA raw => {data}")
            speech = data.get("response", {}).get("speech", {})
            answer = speech.get("plain", {}).get("speech")
            if answer:
                answer = sanitize_model_output(answer)
                return answer[:MAX_RESPONSE_LENGTH]
            return "🤖 [No response from Home Assistant]"
        else:
            print(f"⚠️ HA error: {r.status_code} => {r.text}")
            return None
    except Exception as e:
        print(f"⚠️ HA request failed: {e}")
        return None

def get_ai_response(prompt):
    if AI_PROVIDER == "lmstudio":
        return send_to_lmstudio(prompt)
    elif AI_PROVIDER == "openai":
        return send_to_openai(prompt)
    elif AI_PROVIDER == "ollama":
        return send_to_ollama(prompt)
    elif AI_PROVIDER == "claude":
        return send_to_claude(prompt)
    elif AI_PROVIDER == "gemini":
        return send_to_gemini(prompt)
    elif AI_PROVIDER == "grok":
        return send_to_grok(prompt)
    elif AI_PROVIDER == "openrouter":
        return send_to_openrouter(prompt)
    elif AI_PROVIDER == "groq":
        return send_to_groq(prompt)
    elif AI_PROVIDER == "deepseek":
        return send_to_deepseek(prompt)
    elif AI_PROVIDER == "mistral":
        return send_to_mistral(prompt)
    elif AI_PROVIDER == "openai_compatible":
        return send_to_openai_compatible(prompt)
    elif AI_PROVIDER == "home_assistant":
        # Delegate to the Home Assistant extension if loaded, else fall back to built-in
        if extension_loader:
            ha_ext = extension_loader.get_ai_provider("home_assistant")
            if ha_ext:
                return ha_ext.get_ai_response(prompt)
        return send_to_home_assistant(prompt)
    else:
        print(f"⚠️ Unknown AI provider: {AI_PROVIDER}")
        return None

def send_discord_message(content):
    if not (ENABLE_DISCORD and DISCORD_WEBHOOK_URL):
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": content})
    except Exception as e:
        print(f"⚠️ Discord webhook error: {e}")

# -----------------------------
# Revised Emergency Notification Function
# -----------------------------
def send_emergency_notification(node_id, user_msg, lat=None, lon=None, position_time=None):
    info_print("[Info] Sending emergency notification...")

    sn = get_node_shortname(node_id)
    fullname = get_node_fullname(node_id)
    full_msg = f"EMERGENCY from {sn} ({fullname}) [Node {node_id}]:\n"
    if lat is not None and lon is not None:
        maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        full_msg += f" - Location: {maps_url}\n"
    if position_time:
        full_msg += f" - Last GPS time: {position_time}\n"
    if user_msg:
        full_msg += f" - Message: {user_msg}\n"
    
    # Attempt to send SMS via Twilio if configured.
    try:
        if ENABLE_TWILIO and TWILIO_SID and TWILIO_AUTH_TOKEN and ALERT_PHONE_NUMBER and TWILIO_FROM_NUMBER:
            client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=full_msg,
                from_=TWILIO_FROM_NUMBER,
                to=ALERT_PHONE_NUMBER
            )
            print("✅ Emergency SMS sent via Twilio.")
        else:
            print("Twilio not properly configured for SMS.")
    except Exception as e:
        print(f"⚠️ Twilio error: {e}")

    # Attempt to send email via SMTP if configured.
    try:
        if ENABLE_SMTP and SMTP_HOST and SMTP_USER and SMTP_PASS and ALERT_EMAIL_TO:
            if isinstance(ALERT_EMAIL_TO, list):
                email_to = ", ".join(ALERT_EMAIL_TO)
            else:
                email_to = ALERT_EMAIL_TO
            msg = MIMEText(full_msg)
            msg["Subject"] = f"EMERGENCY ALERT from {sn} ({fullname}) [Node {node_id}]"
            msg["From"] = SMTP_USER
            msg["To"] = email_to
            if SMTP_PORT == 465:
                s = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
            else:
                s = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
                s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, email_to, msg.as_string())
            s.quit()
            print("✅ Emergency email sent via SMTP.")
        else:
            print("SMTP not properly configured for email alerts.")
    except Exception as e:
        print(f"⚠️ SMTP error: {e}")

    # Attempt to post emergency alert to Discord if enabled.
    try:
        if DISCORD_SEND_EMERGENCY and ENABLE_DISCORD and DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": full_msg})
            print("✅ Emergency alert posted to Discord.")
        else:
            print("Discord emergency notifications disabled or not configured.")
    except Exception as e:
        print(f"⚠️ Discord webhook error: {e}")

    # Broadcast emergency to all loaded extensions
    if extension_loader:
        gps = None
        if lat is not None and lon is not None:
            gps = {"lat": lat, "lon": lon, "time": str(position_time) if position_time else None}
        try:
            extension_loader.broadcast_emergency(full_msg, gps)
        except Exception as e:
            print(f"⚠️ Extension emergency broadcast error: {e}")

# -----------------------------
# Helper: Validate/Strip PIN (for Home Assistant)
# -----------------------------
def pin_is_valid(text):
    lower = text.lower()
    if "pin=" not in lower:
        return False
    idx = lower.find("pin=") + 4
    candidate = lower[idx:idx+4]
    return (candidate == HOME_ASSISTANT_SECURE_PIN.lower())

def strip_pin(text):
    lower = text.lower()
    idx = lower.find("pin=")
    if idx == -1:
        return text
    return text[:idx].strip() + " " + text[idx+8:].strip()

def route_message_text(user_message, channel_idx):
    if HOME_ASSISTANT_ENABLED and channel_idx == HOME_ASSISTANT_CHANNEL_INDEX:
        info_print("[Info] Routing to Home Assistant channel.")
        if HOME_ASSISTANT_ENABLE_PIN:
            if not pin_is_valid(user_message):
                return "Security code missing/invalid. Format: 'PIN=XXXX your msg'"
            user_message = strip_pin(user_message)
        ha_response = send_to_home_assistant(user_message)
        return ha_response if ha_response else "🤖 [No response from Home Assistant]"
    else:
        info_print(f"[Info] Using default AI provider: {AI_PROVIDER}")
        resp = get_ai_response(user_message)
        return resp if resp else "🤖 [No AI response]"

# -----------------------------
# Revised Command Handler (Case-Insensitive)
# -----------------------------
def handle_command(cmd, full_text, sender_id):
  cmd = cmd.lower()
  dprint(f"handle_command => cmd='{cmd}', full_text='{full_text}', sender_id={sender_id}")
  # --- Extension command routing (runs before built-ins) ---
  if cmd == "/extensions":
    if extension_loader:
      return extension_loader.list_extensions()
    return "Extension system not initialised."
  if extension_loader:
    node_info = {"node_id": sender_id, "shortname": get_node_shortname(sender_id)}
    ext_args = full_text[len(cmd):].strip()
    ext_result = extension_loader.route_command(cmd, ext_args, node_info)
    if ext_result is not None:
      return ext_result
  # --- Built-in commands ---
  if cmd == ABOUT_COMMAND:
    return "MESH-API Off Grid Chat Bot - By: MR-TBOT.com"
  elif cmd in AI_COMMANDS:
    user_prompt = full_text[len(cmd):].strip()
    if AI_PROVIDER == "home_assistant" and HOME_ASSISTANT_ENABLE_PIN:
      if not pin_is_valid(user_prompt):
        return "Security code missing or invalid. Use 'PIN=XXXX'"
      user_prompt = strip_pin(user_prompt)
    ai_answer = get_ai_response(user_prompt)
    return ai_answer if ai_answer else "🤖 [No AI response]"
  elif cmd == WHEREAMI_COMMAND:
    lat, lon, tstamp = get_node_location(sender_id)
    sn = get_node_shortname(sender_id)
    if lat is None or lon is None:
      return f"🤖 Sorry {sn}, I have no GPS fix for your node."
    tstr = str(tstamp) if tstamp else "Unknown"
    return f"Node {sn} GPS: {lat}, {lon} (time: {tstr})"
  elif cmd in ["/emergency", "/911"]:
    lat, lon, tstamp = get_node_location(sender_id)
    user_msg = full_text[len(cmd):].strip()
    send_emergency_notification(sender_id, user_msg, lat, lon, tstamp)
    log_message(sender_id, f"EMERGENCY TRIGGERED: {full_text}", is_emergency=True)
    return "🚨 Emergency alert sent. Stay safe."
  elif cmd == "/ping":
    return "pong"
  elif cmd == "/test":
    sn = get_node_shortname(sender_id)
    return f"Hello {sn}! Received {LOCAL_LOCATION_STRING} by {AI_NODE_NAME}."
  elif cmd == HELP_COMMAND:
    # Show only suffixed commands to avoid collisions (except emergency/911)
    built_in = [
      ABOUT_COMMAND,
      WHEREAMI_COMMAND,
      "/emergency",
      "/911",
      "/ping",
      "/test",
      MOTD_COMMAND,
      "/extensions",
    ] + AI_COMMANDS + [SMS_COMMAND]
    custom_cmds = [c.get("command") for c in commands_config.get("commands", [])]
    ext_cmds = []
    if extension_loader:
      ext_cmds = [cmd for cmd, _ in extension_loader.list_extension_commands()]
    return "Commands:\n" + ", ".join(built_in + custom_cmds + ext_cmds)
  elif cmd == MOTD_COMMAND:
    return motd_content
  elif cmd == SMS_COMMAND:
    parts = full_text.split(" ", 2)
    if len(parts) < 3:
      return f"Invalid syntax. Use: {SMS_COMMAND} <phone_number> <message>"
    phone_number = parts[1]
    message_text = parts[2]
    try:
      client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
      client.messages.create(
        body=message_text,
        from_=TWILIO_FROM_NUMBER,
        to=phone_number
      )
      print(f"✅ SMS sent to {phone_number}")
      return "SMS sent successfully."
    except Exception as e:
      print(f"⚠️ Failed to send SMS: {e}")
      return "Failed to send SMS."
  for c in commands_config.get("commands", []):
    if c.get("command").lower() == cmd:
      if "ai_prompt" in c:
        user_input = full_text[len(cmd):].strip()
        custom_text = c["ai_prompt"].replace("{user_input}", user_input)
        if AI_PROVIDER == "home_assistant" and HOME_ASSISTANT_ENABLE_PIN:
          if not pin_is_valid(custom_text):
            return "Security code missing or invalid."
          custom_text = strip_pin(custom_text)
        ans = get_ai_response(custom_text)
        return ans if ans else "🤖 [No AI response]"
      elif "response" in c:
        return c["response"]
      return "No configured response for this command."
  return None

# -----------------------------
# Commands inventory helpers (for /help, /commands page, and startup logs)
# -----------------------------
def get_available_commands_list():
  """Return a list of (command, description) for built-ins, AI, SMS, and custom commands."""
  desc = {}
  # Built-ins
  desc[ABOUT_COMMAND] = "About this bot"
  desc[WHEREAMI_COMMAND] = "Show your node's GPS coordinates (if available)"
  desc[MOTD_COMMAND] = "Show the Message of the Day"
  desc[HELP_COMMAND] = "List available commands"
  desc["/emergency"] = "Send an emergency alert (Twilio/Email/Discord if enabled)"
  desc["/911"] = "Alias for /emergency"
  desc["/ping"] = "Health check (returns 'pong')"
  desc["/test"] = "Test greeting"
  # AI
  for c in AI_COMMANDS:
    desc[c] = "Ask the AI (requires your unique dashed suffix)"
  # SMS
  desc[SMS_COMMAND] = "Send an SMS: /sms-XY <+15555555555> <message>"
  # Custom commands
  for c in commands_config.get("commands", []):
    cmd = c.get("command")
    if not cmd:
      continue
    if c.get("description"):
      d = c["description"]
    elif c.get("ai_prompt"):
      d = "Custom AI command"
    elif c.get("response"):
      d = "Custom canned response"
    else:
      d = "Custom command"
    desc[cmd] = d
  # Return stable ordering: group by category similar to /help
  built_in = [
    ABOUT_COMMAND,
    WHEREAMI_COMMAND,
    "/emergency",
    "/911",
    "/ping",
    "/test",
    MOTD_COMMAND,
  ]
  all_cmds = []
  for c in built_in:
    if c in desc:
      all_cmds.append((c, desc[c]))
  for c in AI_COMMANDS:
    all_cmds.append((c, desc[c]))
  all_cmds.append((SMS_COMMAND, desc[SMS_COMMAND]))
  # Append custom at the end sorted by name
  custom_items = [(k, v) for k, v in desc.items() if k not in {x for x, _ in all_cmds} and k.startswith("/")]
  for k, v in sorted(custom_items, key=lambda kv: kv[0].lower()):
    all_cmds.append((k, v))
  return all_cmds

def get_available_commands_text():
  """One-line string of commands for logs/terminal."""
  return ", ".join(cmd for cmd, _ in get_available_commands_list())

def parse_incoming_text(text, sender_id, is_direct, channel_idx):
  dprint(f"parse_incoming_text => text='{text}' is_direct={is_direct} channel={channel_idx}")
  info_print(f"[Info] Received from node {sender_id} (direct={is_direct}, ch={channel_idx}) => '{text}'")
  text = text.strip()
  if not text:
    return None
  # Ignore messages that look like they came from an AI node
  if text.startswith(AI_PREFIX_TAG):
    AI_NODE_IDS.add(sender_id)
    dprint(f"Ignoring AI-tagged message from {sender_id}.")
    return None
  # If we've previously seen this sender use the AI tag, don't respond to any of its messages
  if sender_id in AI_NODE_IDS:
    dprint(f"Ignoring message from known AI node {sender_id}.")
    return None
  if is_direct and not config.get("reply_in_directs", True):
    return None
  if (not is_direct) and channel_idx != HOME_ASSISTANT_CHANNEL_INDEX and not config.get("reply_in_channels", True):
    return None
  if text.startswith("/"):
    cmd = text.split()[0]
    resp = handle_command(cmd, text, sender_id)
    return resp
  if is_direct:
    return get_ai_response(text)
  if HOME_ASSISTANT_ENABLED and channel_idx == HOME_ASSISTANT_CHANNEL_INDEX:
    return route_message_text(text, channel_idx)
  return None

def on_receive(packet=None, interface=None, **kwargs):
  dprint(f"on_receive => packet={packet}")
  if not packet or 'decoded' not in packet:
    dprint("No decoded packet => ignoring.")
    return
  if packet['decoded']['portnum'] != 'TEXT_MESSAGE_APP':
    dprint("Not TEXT_MESSAGE_APP => ignoring.")
    return
  try:
    text_raw = packet['decoded']['payload']
    text = text_raw.decode('utf-8', errors='replace')
    sender_node = packet.get('fromId', None)
    raw_to = packet.get('toId', None)
    to_node_int = parse_node_id(raw_to)
    ch_idx = packet.get('channel', 0)

    # MQTT gating: ignore MQTT-originated traffic if configured to do so
    via_mqtt = bool(packet.get('viaMqtt') or packet.get('rxViaMqtt') or packet.get('decoded', {}).get('viaMqtt'))
    if via_mqtt and not RESPOND_TO_MQTT_MESSAGES:
      dprint("Message received via MQTT; RESPOND_TO_MQTT_MESSAGES is False. Ignoring.")
      # Still log the message for visibility
      log_message(sender_node, text, direct=(to_node_int != BROADCAST_ADDR), channel_idx=(None if to_node_int != BROADCAST_ADDR else ch_idx))
      return

    dprint(f"[MSG] from {sender_node} to {raw_to} (ch={ch_idx}): {text}")
    entry = log_message(sender_node, text, direct=(to_node_int != BROADCAST_ADDR), channel_idx=(None if to_node_int != BROADCAST_ADDR else ch_idx))

    # Notify all loaded extensions about the inbound message
    if extension_loader:
        try:
            msg_meta = {
                "sender_id": sender_node,
                "sender_info": f"{get_node_shortname(sender_node)} ({sender_node})",
                "channel_idx": ch_idx,
                "is_direct": (to_node_int != BROADCAST_ADDR),
                "via_mqtt": via_mqtt,
            }
            extension_loader.broadcast_on_message(text, msg_meta)
        except Exception as e:
            dprint(f"Extension on_message error: {e}")

    global lastDMNode, lastChannelIndex
    if to_node_int != BROADCAST_ADDR:
      lastDMNode = sender_node
    else:
      lastChannelIndex = ch_idx

    # Only forward messages on the configured Discord inbound channel to Discord.
    if ENABLE_DISCORD and DISCORD_SEND_ALL and DISCORD_INBOUND_CHANNEL_INDEX is not None and ch_idx == DISCORD_INBOUND_CHANNEL_INDEX:
      sender_info = f"{get_node_shortname(sender_node)} ({sender_node})"
      disc_content = f"**{sender_info}**: {text}"
      send_discord_message(disc_content)

    my_node_num = None
    if FORCE_NODE_NUM is not None:
      my_node_num = FORCE_NODE_NUM
    else:
      if hasattr(interface, "myNode") and interface.myNode:
        my_node_num = interface.myNode.nodeNum
      elif hasattr(interface, "localNode") and interface.localNode:
        my_node_num = interface.localNode.nodeNum

    if to_node_int == BROADCAST_ADDR:
      is_direct = False
    elif my_node_num is not None and to_node_int == my_node_num:
      is_direct = True
    else:
      is_direct = (my_node_num == to_node_int)

    # LongFast gating: do not respond on channel 0 unless explicitly enabled
    if (not is_direct) and ch_idx == 0 and not AI_RESPOND_ON_LONGFAST:
      dprint("AI_RESPOND_ON_LONGFAST=False; not responding on LongFast (ch 0).")
      return

    # Ignore AI-tagged messages and known AI nodes before parsing
    if text.strip().startswith(AI_PREFIX_TAG):
      AI_NODE_IDS.add(sender_node)
      dprint("Inbound message is AI-tagged; skipping response.")
      return
    if sender_node in AI_NODE_IDS:
      dprint("Sender is a known AI node; skipping response.")
      return

    resp = parse_incoming_text(text, sender_node, is_direct, ch_idx)
    if resp:
      info_print("[Info] Wait 10s before responding to reduce collisions.")
      time.sleep(10)
      ai_out = add_ai_prefix(resp)
      log_message(AI_NODE_NAME, ai_out, reply_to=entry['timestamp'])
      # If message originated on Discord inbound channel, also send the AI response back to Discord.
      if ENABLE_DISCORD and DISCORD_SEND_AI and DISCORD_INBOUND_CHANNEL_INDEX is not None and ch_idx == DISCORD_INBOUND_CHANNEL_INDEX:
        disc_msg = f"🤖 **{AI_NODE_NAME}**: {ai_out}"
        send_discord_message(disc_msg)
      # Notify extensions about the AI response
      if extension_loader:
        try:
          ai_meta = {
            "is_ai_response": True,
            "channel_idx": ch_idx,
            "sender_id": sender_node,
            "is_direct": is_direct,
          }
          extension_loader.broadcast_message(ai_out, ai_meta)
        except Exception as e:
          dprint(f"Extension send_message error: {e}")
      if is_direct:
        info_print(f"[Info] Dispatching AI reply as DM to {sender_node}")
        send_direct_chunks(interface, ai_out, sender_node)
      else:
        info_print(f"[Info] Dispatching AI reply as broadcast on channel {ch_idx}")
        send_broadcast_chunks(interface, ai_out, ch_idx)
  except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError) as e:
    print(f"⚠️ Connection error in on_receive: {e}")
    global connection_status
    connection_status = "Disconnected"
    reset_event.set()
    return
  except OSError as e:
    error_code = getattr(e, 'errno', None) or getattr(e, 'winerror', None)
    print(f"⚠️ OSError detected in on_receive: {e} (error code: {error_code})")
    if error_code in (10053, 10054, 10060):
      print("⚠️ Connection error detected. Restarting interface...")
      connection_status = "Disconnected"
      reset_event.set()
    return
  except Exception as e:
    print(f"⚠️ Unexpected error in on_receive: {e}")
    return

@app.route("/messages", methods=["GET"])
def get_messages_api():
    dprint("GET /messages => returning current messages")
    return jsonify(messages)

@app.route("/nodes", methods=["GET"])
def get_nodes_api():
    node_list = []
    if interface and hasattr(interface, "nodes"):
        for nid in interface.nodes:
            sn = get_node_shortname(nid)
            ln = get_node_fullname(nid)
            node_list.append({
                "id": nid,
                "shortName": sn,
                "longName": ln
            })
    return jsonify(node_list)

@app.route("/api/channels", methods=["GET"])
def get_channels_api():
    """Return channel names from the connected Meshtastic node."""
    channels = {}
    try:
        if interface and hasattr(interface, "localNode") and interface.localNode:
            node = interface.localNode
            if hasattr(node, "channels") and node.channels:
                for i, ch in enumerate(node.channels):
                    if ch and hasattr(ch, "settings") and ch.settings:
                        name = ch.settings.name if hasattr(ch.settings, "name") else ""
                        role = ch.role if hasattr(ch, "role") else 0
                        if role > 0 or i == 0:  # Primary or secondary channels
                            channels[str(i)] = name if name else ("Primary" if i == 0 else f"Channel {i}")
    except Exception as e:
        dprint(f"Error reading channels: {e}")
    return jsonify(channels)

@app.route("/connection_status", methods=["GET"], endpoint="connection_status_info")
def connection_status_info():
    return jsonify({"status": connection_status, "error": last_error_message})

@app.route("/logs_stream")
def logs_stream():
    def generate():
        last_index = 0
        while True:
            # apply your noise filter
            visible = [
                line for line in script_logs
                if DEBUG_ENABLED or not any(p in line for p in _ProtoNoiseFilter.NOISY)
            ]
            # send only the new lines
            if last_index < len(visible):
                for line in visible[last_index:]:
                    # each SSE “data:” is one log line
                    yield f"data: {line}\n\n"
                last_index = len(visible)
            time.sleep(0.5)

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"   # for nginx, disables proxy buffering
    }
    return Response(
        stream_with_context(generate()),
        headers=headers,
        mimetype="text/event-stream"
    )

@app.route("/logs", methods=["GET"])
def logs():
    uptime = datetime.now(timezone.utc) - server_start_time
    uptime_str = str(uptime).split('.')[0]

    # build a regex that matches any protobuf noise
    noise_re = re.compile(r"protobuf|DecodeError|ParseFromString", re.IGNORECASE)

    # include only non-noisy lines unless DEBUG_ENABLED
    visible = [
        line for line in script_logs
        if DEBUG_ENABLED or not noise_re.search(line)
    ]
    log_text = "\n".join(visible)

    html = f"""<html>
  <head>
    <meta http-equiv="refresh" content="1">
    <title>MESH-API Logs</title>
    <style>
      body {{ background:#000; color:#fff; font-family:monospace; padding:20px; }}
      pre {{ white-space: pre-wrap; word-break: break-word; }}
    </style>
  </head>
  <body>
    <h1>Script Logs</h1>
    <div><strong>Uptime:</strong> {uptime_str}</div>
    <div><strong>Restarts:</strong> {restart_count}</div>
    <pre id="logbox">{log_text}</pre>
    <script>
      // once the page renders, scroll to the bottom
      document.addEventListener("DOMContentLoaded", () => {{
        window.scrollTo(0, document.body.scrollHeight);
      }});
    </script>
  </body>
</html>"""
    return html
# -----------------------------
# Revised Discord Webhook Route for Inbound Messages
# -----------------------------
@app.route("/discord_webhook", methods=["POST"])
def discord_webhook():
    if not DISCORD_RECEIVE_ENABLED:
        return jsonify({"status": "disabled", "message": "Discord receive is disabled"}), 200
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No JSON payload provided"}), 400

    # Extract the username (default if not provided)
    username = data.get("username", "DiscordUser")
    channel_index = DISCORD_INBOUND_CHANNEL_INDEX
    message_text = data.get("message")
    if message_text is None:
        return jsonify({"status": "error", "message": "Missing message"}), 400

    # Prepend username to the message
    formatted_message = f"**{username}**: {message_text}"

    try:
        log_message("Discord", formatted_message, direct=False, channel_idx=int(channel_index))
        if interface is None:
            print("❌ Cannot route Discord message: interface is None.")
        else:
            send_broadcast_chunks(interface, formatted_message, int(channel_index))
        print(f"✅ Routed Discord message back on channel {channel_index}")
        return jsonify({"status": "sent", "channel_index": channel_index, "message": formatted_message})
    except Exception as e:
        print(f"⚠️ Discord webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# -----------------------------
# New Twilio SMS Webhook Route for Inbound SMS
# -----------------------------
@app.route("/twilio_webhook", methods=["POST"])
def twilio_webhook():
    sms_body = request.form.get("Body")
    from_number = request.form.get("From")
    if not sms_body:
        return "No SMS body received", 400
    target = config.get("twilio_inbound_target", "channel")
    if target == "channel":
        channel_index = config.get("twilio_inbound_channel_index")
        if channel_index is None:
            return "No inbound channel index configured", 400
        log_message("Twilio", f"From {from_number}: {sms_body}", direct=False, channel_idx=int(channel_index))
        send_broadcast_chunks(interface, sms_body, int(channel_index))
        print(f"✅ Routed incoming SMS from {from_number} to channel {channel_index}")
    elif target == "node":
        node_id = config.get("twilio_inbound_node")
        if node_id is None:
            return "No inbound node configured", 400
        log_message("Twilio", f"From {from_number}: {sms_body}", direct=True)
        send_direct_chunks(interface, sms_body, node_id)
        print(f"✅ Routed incoming SMS from {from_number} to node {node_id}")
    else:
        return "Invalid twilio_inbound_target config", 400
    return "SMS processed", 200

@app.route("/dashboard", methods=["GET"])
def dashboard():
    channel_names = config.get("channel_names", {})
    channel_names_json = json.dumps(channel_names)

    # Prepare node GPS and beacon info for JS
    node_gps_info = {}
    if interface and hasattr(interface, "nodes"):
        for nid, ninfo in interface.nodes.items():
            pos = ninfo.get("position", {})
            lat = pos.get("latitude")
            lon = pos.get("longitude")
            tstamp = pos.get("time")
            # Try all possible hop keys, fallback to None
            hops = (
                ninfo.get("hopLimit")
                or ninfo.get("hop_count")
                or ninfo.get("hopCount")
                or ninfo.get("numHops")
                or ninfo.get("num_hops")
                or ninfo.get("hops")
                or None
            )
            # Convert tstamp (epoch) to readable UTC if present
            if tstamp:
                try:
                    dt = datetime.fromtimestamp(tstamp, timezone.utc)
                    tstr = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    tstr = str(tstamp)
            else:
                tstr = None
            # Last heard time from Meshtastic node info
            last_heard_epoch = ninfo.get("lastHeard") or ninfo.get("last_heard")
            last_heard_str = None
            if last_heard_epoch:
                try:
                    lh_dt = datetime.fromtimestamp(last_heard_epoch, timezone.utc)
                    last_heard_str = lh_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
                except Exception:
                    last_heard_str = str(last_heard_epoch)
            node_gps_info[str(nid)] = {
                "lat": lat,
                "lon": lon,
                "beacon_time": tstr,
                "hops": hops,
                "lastHeard": last_heard_str,
            }
    node_gps_info_json = json.dumps(node_gps_info)

    # Get connected node's GPS for distance calculation
    my_lat, my_lon, _ = get_node_location(interface.myNode.nodeNum) if interface and hasattr(interface, "myNode") and interface.myNode else (None, None, None)
    my_gps_json = json.dumps({"lat": my_lat, "lon": my_lon})

    html = """
<html>
<head>
  <title>MESH-API Dashboard</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js"></script>
  <style>
  :root { --theme-color: #ffa500; --bg-primary: #000; --bg-panel: #111; --bg-input: #222; --text-primary: #fff; --text-muted: #aaa; --border-radius: 10px; --color-map: #ffa500; --color-send: #ffa500; --color-dm: #ffa500; --color-channel: #ffa500; --color-nodes: #ffa500; --color-discord: #ffa500; }
  html, body { margin: 0; padding: 0; }
  /* Beta Disclaimer Modal */
  #disclaimerOverlay { position:fixed; inset:0; background:rgba(0,0,0,0.92); z-index:100000; display:flex; align-items:center; justify-content:center; }
  #disclaimerOverlay .disclaimer-box { background:#111; border:2px solid var(--theme-color); border-radius:12px; max-width:560px; width:90%; padding:32px; text-align:center; }
  #disclaimerOverlay h2 { color:var(--theme-color); margin-top:0; font-size:1.5em; }
  #disclaimerOverlay .disclaimer-text { color:#ccc; font-size:0.95em; line-height:1.6; margin:16px 0 24px; text-align:left; }
  #disclaimerOverlay .disclaimer-btns { display:flex; gap:16px; justify-content:center; }
  #disclaimerOverlay .btn-accept { background:#2e7d32; color:#fff; border:none; padding:12px 32px; border-radius:8px; font-size:1em; font-weight:bold; cursor:pointer; }
  #disclaimerOverlay .btn-accept:hover { background:#388e3c; }
  body { background: var(--bg-primary); color: var(--text-primary); font-family: 'Segoe UI', Arial, sans-serif; margin: 0; transition: filter 0.5s linear; }
  #connectionStatus { position: relative; width: 100%; text-align: center; padding: 0; font-size: 14px; font-weight: bold; display: block; min-height: 20px; background: green; margin: 0; border-bottom: 1px solid var(--theme-color); }
  /* Header buttons moved inside Send Form panel */
  #ticker-container { position: relative; width: 100%; display: none; align-items: center; justify-content: center; pointer-events: none; margin: 0; }
    #ticker { background: #111; color: var(--theme-color); white-space: nowrap; overflow: hidden; width: 100%; padding: 5px 0; font-size: 36px; display: none; position: relative; border-bottom: 2px solid var(--theme-color); min-height: 50px; pointer-events: auto; }
    #ticker p { display: inline-block; margin: 0; animation: tickerScroll 30s linear infinite; vertical-align: middle; min-width: 100vw; }
    #ticker .dismiss-btn { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); font-size: 18px; background: #222; color: #fff; border: 1px solid var(--theme-color); border-radius: 4px; cursor: pointer; padding: 2px 10px; z-index: 10; }
    @keyframes tickerScroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
    #sendForm { margin: 20px; padding: 20px; background: var(--bg-panel); border: 2px solid var(--color-send); border-radius: var(--border-radius); position: relative; }
    #sendForm h2 { color: var(--color-send); }
    #nodeMapPanel { border-color: var(--color-map); }
    #nodeMapPanel h2 { color: var(--color-map); }
    #nodeMapPanel .collapse-btn { border-color: var(--color-map); }
    [data-col="dm"] .lcars-panel { border-color: var(--color-dm); }
    [data-col="dm"] .lcars-panel h2 { color: var(--color-dm); }
    [data-col="dm"] .collapse-btn { border-color: var(--color-dm); }
    [data-col="channel"] .lcars-panel { border-color: var(--color-channel); }
    [data-col="channel"] .lcars-panel h2 { color: var(--color-channel); }
    [data-col="channel"] .collapse-btn { border-color: var(--color-channel); }
    [data-col="nodes"] .lcars-panel { border-color: var(--color-nodes); }
    [data-col="nodes"] .lcars-panel h2 { color: var(--color-nodes); }
    [data-col="nodes"] .collapse-btn { border-color: var(--color-nodes); }
    #discordSection { border-color: var(--color-discord); }
    #discordSection h2 { color: var(--color-discord); }
    .panel-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
    .three-col { display: flex; flex-wrap: wrap; gap: 20px; margin: 20px; }
    .three-col .col { flex: 1 1 100%; min-width: 0; }
    @media (min-width: 992px) {
      .three-col { flex-wrap: nowrap; }
      .three-col .col { flex: 1 1 0; min-width: 0; }
    }
    .three-col .col .drag-handle { cursor: grab; display: inline-block; margin-right: 6px; color: #666; font-size: 1em; user-select: none; }
    .three-col .col .drag-handle:hover { color: var(--theme-color); }
    .lcars-panel { background: var(--bg-panel); padding: 20px; border: 2px solid var(--theme-color); border-radius: var(--border-radius); transition: box-shadow 0.2s; }
    .lcars-panel:hover { box-shadow: 0 0 8px rgba(255,165,0,0.15); }
    .lcars-panel h2 { color: var(--theme-color); margin-top: 0; font-size: 1.15em; }
    .lcars-panel .panel-title-row { display:flex; align-items:center; justify-content: space-between; gap: 10px; }
    .lcars-panel .collapse-btn { background:var(--bg-input); color:#fff; border:1px solid var(--theme-color); border-radius:4px; padding:2px 8px; cursor:pointer; display:inline-block; font-size:0.85em; }
    .lcars-panel .panel-body { overflow-y:auto; max-height: 50vh; }
    @media (min-width: 992px) { .lcars-panel .panel-body { max-height: calc(100vh - 360px); } }
    .message { border: 1px solid var(--theme-color); border-radius: 6px; margin: 6px 0; padding: 8px 10px; transition: background 0.2s; }
    .message:hover { background: #1a1a1a; }
    .message.outgoing { background: var(--bg-input); }
    .message.newMessage { border-color: #00ff00; background: rgba(0,170,34,0.15); }
    .message.recentNode { border-color: #00bfff; background: rgba(17,51,85,0.6); }
    .timestamp { font-size: 0.8em; color: #666; }
    .btn { margin-left: 10px; padding: 2px 6px; font-size: 0.8em; cursor: pointer; }
    .switch { position: relative; display: inline-block; width: 60px; height: 34px; vertical-align: middle; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #ccc; transition: .4s; }
    .slider:before { position: absolute; content: ""; height: 26px; width: 26px; left: 4px; bottom: 4px; background-color: white; transition: .4s; }
    input:checked + .slider { background-color: #2196F3; }
    input:focus + .slider { box-shadow: 0 0 1px #2196F3; }
    input:checked + .slider:before { transform: translateX(26px); }
    .slider.round { border-radius: 34px; }
    .slider.round:before { border-radius: 50%; }
    #charCounter { font-size: 0.9em; color: #ccc; text-align: right; margin-top: 5px; }
    .nodeItem { margin-bottom: 10px; padding: 8px; border: 1px solid #333; border-radius: 6px; display: flex; flex-direction: column; align-items: flex-start; flex-wrap: wrap; transition: background 0.15s; }
    .nodeItem:hover { background: #1a1a1a; }
    .nodeItem.recentNode { border-color: #00bfff; background: rgba(17,51,85,0.5); }
    .nodeMainLine { font-weight: bold; font-size: 1.1em; }
    .nodeLongName { color: #aaa; font-size: 0.98em; margin-top: 2px; }
    .nodeInfoLine { margin-top: 2px; font-size: 0.95em; color: #ccc; display: flex; flex-wrap: wrap; gap: 10px; }
    .nodeGPS { margin-left: 0; }
    .nodeBeacon { color: #aaa; font-size: 0.92em; }
    .nodeHops { color: #6cf; font-size: 0.92em; }
    .nodeMapBtn { margin-left: 0; background: #222; color: #fff; border: 1px solid #ffa500; border-radius: 4px; padding: 2px 6px; font-size: 1em; cursor: pointer; text-decoration: none; }
    .nodeMapBtn:hover { background: #ffa500; color: #000; }
    .channel-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    /* Collapsible channel groups */
    .channel-group { border: 1px solid #333; border-radius: 8px; margin-bottom: 12px; overflow: hidden; }
    .channel-group-header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 8px 12px; background: var(--bg-input); cursor: pointer; user-select: none; border-bottom: 1px solid #333; }
    .channel-group-header:hover { background: #2a2a2a; }
    .channel-group-header h3 { margin: 0; font-size: 1em; }
    .channel-group-header .ch-toggle { font-size: 0.85em; transition: transform 0.2s; }
    .channel-group-header .ch-toggle.collapsed { transform: rotate(-90deg); }
    .channel-group-body { padding: 6px 10px; }
    .channel-group-body.collapsed { display: none; }
    .reply-btn { margin-left: 10px; padding: 4px 10px; font-size: 0.85em; background: var(--bg-input); color: var(--theme-color); border: 1px solid var(--theme-color); border-radius: 5px; cursor: pointer; transition: background 0.15s, color 0.15s; }
    .reply-btn:hover { background: var(--theme-color); color: #000; }
    .btn-send { background: #1b5e20; color: #fff; border-color: #388e3c; }
    .btn-send:hover { background: #388e3c; color: #fff; }
    .btn-reply-dm { background: #0d47a1; color: #fff; border-color: #1565c0; }
    .btn-reply-dm:hover { background: #1565c0; color: #fff; }
    .btn-reply-channel { background: #4a148c; color: #fff; border-color: #7b1fa2; }
    .btn-reply-channel:hover { background: #7b1fa2; color: #fff; }
    .mark-read-btn { margin-left: 10px; padding: 2px 8px; font-size: 0.85em; background: #222; color: #0f0; border: 1px solid #0f0; border-radius: 4px; cursor: pointer; }
    .mark-all-read-btn { margin-left: 10px; padding: 2px 8px; font-size: 0.85em; background: #222; color: #ff0; border: 1px solid #ff0; border-radius: 4px; cursor: pointer; }
  /* React / Emoji */
  .react-btn { margin-left: 10px; padding: 2px 8px; font-size: 0.85em; background: #222; color: #0ff; border: 1px solid #0ff; border-radius: 4px; cursor: pointer; }
  .react-btn.sending { opacity: 0.6; pointer-events: none; }
  .react-btn.sent { color: #0f0; border-color: #0f0; }
  .react-btn.error { color: #f66; border-color: #f66; }
  .emoji-picker { margin-top: 6px; display: none; gap: 6px; flex-wrap: wrap; }
  .emoji-btn { font-size: 1.1em; padding: 2px 6px; cursor: pointer; background: #111; border: 1px solid #444; border-radius: 6px; }
  .emoji-btn:hover { background: #222; }
    /* Threaded DM styles */
    .dm-thread { margin-bottom: 16px; border-left: 3px solid var(--theme-color); padding-left: 10px; }
    .dm-thread .message { margin-left: 0; }
    .dm-thread .reply-btn { margin-top: 5px; }
    .dm-thread .thread-replies { margin-left: 30px; border-left: 2px dashed #555; padding-left: 10px; }
    /* Hide Discord section by default */
    #discordSection { display: none; }
    /* Node sort controls */
    .nodeSortBar { margin-bottom: 10px; }
    .nodeSortBar label { margin-right: 8px; }
    .nodeSortBar select { background: #222; color: #fff; border: 1px solid var(--theme-color); border-radius: 4px; padding: 2px 8px; }
    /* Full width search bar for nodes */
    #nodeSearch { width: 100%; margin-bottom: 10px; font-size: 1em; padding: 6px; box-sizing: border-box; }
  /* UI Settings panel: fixed overlay */
  .settings-panel { display:none; position:fixed; top:0; right:0; bottom:0; width:min(90vw,900px); background:var(--bg-panel); border-left:2px solid var(--theme-color); z-index:50000; overflow-y:auto; padding:24px; box-shadow:-4px 0 30px rgba(0,0,0,0.7); transition:transform 0.3s ease; }
  .settings-panel.open { display:block; }
  .settings-panel .sticky-actions { position:sticky; bottom:0; background:#111; padding:12px 0 6px; z-index:1; }
  .settings-panel .settings-two-col { display:grid; grid-template-columns:1fr 1fr; gap:0 32px; }
  .settings-panel .settings-two-col > div { min-width:0; }
  @media (max-width:768px) { .settings-panel { width:100vw; } .settings-panel .settings-two-col { grid-template-columns:1fr; } }
  .settings-panel h3 { color:var(--theme-color); margin:16px 0 8px; font-size:1em; }
  #applySettingsBtn { background:var(--theme-color); color:#000; border:none; padding:10px 28px; border-radius:6px; font-weight:bold; font-size:1em; cursor:pointer; transition:background 0.15s,transform 0.1s; }
  #applySettingsBtn:hover { filter:brightness(1.15); transform:scale(1.02); }
  #applySettingsBtn:active { transform:scale(0.98); }
  .settings-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:49999; }
  .settings-overlay.open { display:block; }
    /* Timezone selector */
    #timezoneSelect { margin-left: 10px; }
  /* Footer link bottom right (version only) */
  .footer-right-link { position: fixed; bottom: 10px; right: 10px; z-index: 10000; text-align: right; }
  /* Centered footer bar for Support + Bug buttons */
  .footer-center-bar { position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%); z-index: 10000; display: flex; gap: 8px; align-items: center; justify-content: center; }
  .footer-center-bar .btnlink { display:inline-block; color:#fff; text-decoration:none; font-weight:bold; padding:6px 10px; border:1px solid var(--theme-color); border-radius:6px; white-space:nowrap; text-align:center; cursor:pointer; font-size:0.85em; }
  .footer-center-bar .btnlink:hover { filter:brightness(1.2); }
  /* Node map panel */
  #nodeMapPanel { margin: 20px; }
  #nodeMapPanel .panel-body { overflow: hidden; }
  #nodeMapPanel.collapsed .panel-body { display: none; }
  #nodeMap { width: 100%; height: 400px; background: var(--bg-input); border-radius: 6px; position: relative; }
  /* Shortname labels on map markers */
  .leaflet-marker-label { background: rgba(0,0,0,0.75); color: #fff; font-size: 11px; padding: 1px 5px; border-radius: 3px; white-space: nowrap; border: 1px solid var(--theme-color); }
  /* Mini DM box floating over the map */
  #mapDmBox { display:none; position:absolute; bottom:12px; left:50%; transform:translateX(-50%); z-index:10001; background:var(--bg-panel); border:2px solid var(--theme-color); border-radius:10px; padding:12px 16px; min-width:280px; max-width:90%; box-shadow:0 4px 20px rgba(0,0,0,0.6); }
  #mapDmBox .mapDm-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
  #mapDmBox .mapDm-header h4 { margin:0; color:var(--theme-color); font-size:0.95em; }
  #mapDmBox .mapDm-header button { background:none; border:none; color:#aaa; font-size:1.2em; cursor:pointer; }
  #mapDmBox textarea { width:100%; min-height:48px; background:var(--bg-input); color:var(--text-primary); border:1px solid #444; border-radius:6px; padding:6px 8px; font-size:0.9em; resize:vertical; box-sizing:border-box; }
  #mapDmBox .mapDm-send { margin-top:6px; background:var(--theme-color); color:#000; border:none; padding:6px 18px; border-radius:6px; font-weight:bold; cursor:pointer; }
  #mapDmBox .mapDm-send:hover { filter:brightness(0.85); }
  /* Draggable sections — flex layout for side-by-side */
  #sortableContainer { display: flex; flex-wrap: wrap; align-items: stretch; }
  #sortableContainer > div { position: relative; box-sizing: border-box; }
  /* Map and Send side by side at half width */
  #sortableContainer > div[data-section="nodeMapPanel"],
  #sortableContainer > div[data-section="sendForm"] { flex: 1 1 50%; min-width: 320px; display: flex; flex-direction: column; }
  #sortableContainer > div[data-section="nodeMapPanel"] > .lcars-panel,
  #sortableContainer > div[data-section="sendForm"] > .lcars-panel { flex: 1; display: flex; flex-direction: column; }
  #sortableContainer > div[data-section="sendForm"] > .lcars-panel > form { flex: 1; display: flex; flex-direction: column; }
  /* Full width for three-col and discord */
  #sortableContainer > div[data-section="threeCol"],
  #sortableContainer > div[data-section="discordSection"] { flex: 1 1 100%; }
  /* Resizable panels — only on panels that handle overflow safely (not the map) */
  #sendForm { resize: horizontal; overflow: auto; }
  .three-col .lcars-panel { resize: horizontal; overflow: auto; }
  #discordSection { resize: horizontal; overflow: auto; }
  /* Section hide button */
  .section-hide-btn { background:none; border:1px solid #666; color:#aaa; font-size:0.85em; cursor:pointer; border-radius:4px; padding:1px 7px; margin-left:6px; }
  .section-hide-btn:hover { color:#f66; border-color:#f66; }
  @media (max-width: 600px) {
    #nodeMap { height: 280px; }
    .masthead { flex-direction: column; text-align: center; }
    .masthead-actions { justify-content: center; }
    .footer-center-bar { flex-direction: row; gap: 4px; bottom: 50px; }
    .footer-left-link { bottom: auto; top: auto; }
    #sendForm { margin: 10px; padding: 12px; resize: none; }
    .three-col { margin: 10px; gap: 12px; }
    .three-col .lcars-panel { resize: none; }
    #discordSection { resize: none; }
    #sortableContainer > div[data-section="nodeMapPanel"],
    #sortableContainer > div[data-section="sendForm"] { flex: 1 1 100%; min-width: 0; }
  }
  .drag-handle { cursor: grab; display: inline-block; margin-right: 8px; color: #666; font-size: 1.1em; user-select: none; vertical-align: middle; }
  .drag-handle:hover { color: var(--theme-color); }
  .sortable-ghost { opacity: 0.4; }
  .sortable-chosen { box-shadow: 0 0 12px var(--theme-color); }
  .footer-right-link .btnlink { display:inline-block; color: var(--theme-color); text-decoration: none; font-weight: bold; background: #111; padding: 6px 10px; border: 1px solid var(--theme-color); border-radius: 6px; white-space: pre-line; text-align: center; }
  .footer-right-link .btnlink:hover { background: var(--theme-color); color: #000; }
  /* Footer UI Settings button bottom left */
  .footer-left-link { position: fixed; bottom: 10px; left: 10px; z-index: 10000; text-align: left; }
  .footer-left-link .btnlink { display:inline-block; color: var(--theme-color); text-decoration: none; font-weight: bold; background: #111; padding: 6px 10px; border: 1px solid var(--theme-color); border-radius: 6px; white-space: pre-line; text-align: center; cursor: pointer; }
  .footer-left-link .btnlink:hover { background: var(--theme-color); color: #000; }
    /* Suffix chip */
    .suffix-chip { background:#111; color: var(--theme-color); border:1px solid var(--theme-color); padding:6px 10px; border-radius:6px; display:inline-block; }
    /* Modal overlay for Commands */
    .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 60000; display: none; align-items: center; justify-content: center; }
    .modal-content { background:#111; border:2px solid var(--theme-color); border-radius:10px; width: 80vw; max-width: 1000px; max-height: 80vh; overflow:auto; box-shadow: 0 0 20px rgba(0,0,0,0.6); }
    .modal-header { display:flex; align-items:center; justify-content: space-between; padding:10px 14px; background:#222; border-bottom:2px solid var(--theme-color); }
    .modal-header h3 { margin:0; color: var(--theme-color); }
    .modal-close { background:#222; color:#fff; border:1px solid var(--theme-color); border-radius:4px; padding:4px 8px; cursor:pointer; }
    .modal-body { padding: 10px 14px; }
    .commands-table { width:100%; border-collapse: collapse; }
    .commands-table th { text-align:left; padding:8px 10px; background:#222; border-bottom:2px solid var(--theme-color); }
    .commands-table td { padding:8px 10px; border-bottom:1px solid #333; }
    .commands-table code { color:#0ff; }
  /* Masthead logo above Send a Message */
  .masthead { display:flex; flex-wrap:wrap; align-items:center; justify-content: space-between; gap: 16px; margin: 20px 20px 0 20px; }
  .masthead .logo-wrap { position: relative; display: inline-block; flex: 0 0 auto; }
  .masthead img { width: clamp(140px, 20vw, 260px); height:auto; display:block; }
  /* Logo overlay — fixed color, NOT affected by theme/color settings */
  .masthead .logo-overlay { position: absolute; inset: 0; background: #ffa500; opacity: 0.35; pointer-events: none; }
  .masthead-actions { display:flex; flex-wrap:wrap; align-items:center; justify-content:flex-end; gap: 10px; margin-left: auto; }
  .masthead-actions button { background: #222; color: var(--theme-color); padding: 8px 12px; border:1px solid var(--theme-color); border-radius: 4px; font-weight: bold; cursor:pointer; font-size: 0.95em; }
  .masthead-actions a { background: var(--theme-color); color: #000; padding: 8px 12px; text-decoration: none; border-radius: 4px; font-weight: bold; font-size: 0.95em; border: 1px solid var(--theme-color); }
  .masthead-actions button:hover, .masthead-actions a:hover { filter: brightness(0.9); }
  @media (max-width: 768px) {
    .masthead { flex-direction: column; align-items: flex-start; }
    .masthead-actions { width: 100%; justify-content: flex-start; }
  }
  /* Content flows naturally; no offset needed */
  #appRoot { padding-top: 0; }
  </style>

  <script>
    // --- Mark as Read/Unread State ---
    // Ensure logo tint overlay is clipped to the logo shape
    document.addEventListener('DOMContentLoaded', function(){
      const logo = document.getElementById('mastheadLogo');
      const overlay = document.querySelector('.masthead .logo-overlay');
      function applyLogoMask(){
        if (!logo || !overlay) return;
        const url = getComputedStyle(logo).getPropertyValue('content'); // placeholder
        // Use the logo src as mask
        const src = logo.getAttribute('src');
        if (src) {
          overlay.style.webkitMaskImage = `url(${src})`;
          overlay.style.maskImage = `url(${src})`;
          overlay.style.webkitMaskSize = 'contain';
          overlay.style.maskSize = 'contain';
          overlay.style.webkitMaskRepeat = 'no-repeat';
          overlay.style.maskRepeat = 'no-repeat';
          overlay.style.webkitMaskPosition = 'center';
          overlay.style.maskPosition = 'center';
        }
      }
      if (logo.complete) applyLogoMask();
      else logo.addEventListener('load', applyLogoMask);
    });
    function togglePanel(btn) {
      const panel = btn.closest('.lcars-panel');
      const body = panel.querySelector('.panel-body');
      if (!body) return;
      const isHidden = body.style.display === 'none';
      body.style.display = isHidden ? '' : 'none';
      btn.textContent = isHidden ? 'Collapse' : 'Expand';
    }

    let readDMs = JSON.parse(localStorage.getItem("readDMs") || "[]");
    let readChannels = JSON.parse(localStorage.getItem("readChannels") || "{}");

    function saveReadDMs() {
      localStorage.setItem("readDMs", JSON.stringify(readDMs));
    }
    function saveReadChannels() {
      localStorage.setItem("readChannels", JSON.stringify(readChannels));
    }
    function markDMAsRead(ts) {
      if (!readDMs.includes(ts)) {
        readDMs.push(ts);
        saveReadDMs();
        fetchMessagesAndNodes();
      }
    }
    function markAllDMsAsRead() {
      if (!confirm("Are you sure you want to mark ALL direct messages as read?")) return;
      let dms = allMessages.filter(m => m.direct);
      readDMs = dms.map(m => m.timestamp);
      saveReadDMs();
      fetchMessagesAndNodes();
    }
    function markChannelAsRead(channelIdx) {
      if (!confirm("Are you sure you want to mark ALL messages in this channel as read?")) return;
      const key = String(channelIdx);
      let msgs = allMessages.filter(m => !m.direct && m.channel_idx != null && String(m.channel_idx) === key);
      if (!readChannels) readChannels = {};
      readChannels[key] = msgs.map(m => m.timestamp);
      saveReadChannels();
      fetchMessagesAndNodes();
    }
    function isDMRead(ts) {
      return readDMs.includes(ts);
    }
    function isChannelMsgRead(ts, channelIdx) {
      const key = String(channelIdx);
      return readChannels && readChannels[key] && readChannels[key].includes(ts);
    }

    // --- Ticker Dismissal State ---
    function loadDismissedSet() {
      try { return JSON.parse(localStorage.getItem('tickerDismissedSet') || '[]'); } catch(e) { return []; }
    }
    function saveDismissedSet(arr) {
      // keep it from growing forever
      const trimmed = arr.slice(-200);
      localStorage.setItem('tickerDismissedSet', JSON.stringify(trimmed));
    }
    function setTickerDismissed(ts) {
      const set = loadDismissedSet();
      if (!set.includes(ts)) { set.push(ts); saveDismissedSet(set); }
    }
    function isTickerDismissed(ts) {
      const set = loadDismissedSet();
      return set.includes(ts);
    }

    // --- Timezone Offset State ---
    function getTimezoneOffset() {
      let tz = localStorage.getItem("meshtastic_ui_tz_offset");
      if (tz === null || isNaN(Number(tz))) return 0;
      return Number(tz);
    }
    function setTimezoneOffset(val) {
      localStorage.setItem("meshtastic_ui_tz_offset", String(val));
    }

    // Globals for reply targets
    var lastDMTarget = null;
    var lastChannelTarget = null;
    let allNodes = [];
    let allMessages = [];
    // --- Emoji helpers ---
    const COMMON_EMOJIS = ["👍","❤️","😂","🔥","🎉","🙏","✅","❓","👏","😮","👀","💡","📍","🆘"];

    function setReactState(btn, state) {
      if (!btn) return;
      btn.classList.remove('sending','sent','error');
      btn.disabled = false;
      if (state === 'sending') {
        btn.disabled = true;
        btn.classList.add('sending');
        btn.textContent = 'Sending…';
      } else if (state === 'sent') {
        btn.classList.add('sent');
        btn.textContent = 'Sent ✓';
      } else if (state === 'error') {
        btn.classList.add('error');
        btn.textContent = 'Failed ✖';
      } else {
        btn.textContent = 'React';
      }
    }

    function handleReactSend(reactBtn, picker, sendFn) {
      try {
        if (reactBtn && reactBtn.disabled) return;
        setReactState(reactBtn, 'sending');
        if (picker) picker.style.display = 'none';
        Promise.resolve().then(() => sendFn())
          .then(() => {
            setReactState(reactBtn, 'sent');
            setTimeout(() => setReactState(reactBtn, 'idle'), 1000);
          })
          .catch(err => {
            console.error(err);
            setReactState(reactBtn, 'error');
            setTimeout(() => setReactState(reactBtn, 'idle'), 1200);
            alert('Failed to send reaction: ' + (err && err.message ? err.message : err));
          });
      } catch (e) {
        console.error(e);
        setReactState(reactBtn, 'error');
        setTimeout(() => setReactState(reactBtn, 'idle'), 1200);
      }
    }

    function renderEmojiPicker(container, onSelect) {
      container.innerHTML = "";
      COMMON_EMOJIS.forEach(e => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'emoji-btn';
        b.textContent = e;
        b.onclick = () => { onSelect(e); container.style.display = 'none'; };
        container.appendChild(b);
      });
      // Add a small close control
      const close = document.createElement('button');
      close.type = 'button';
      close.className = 'emoji-btn';
      close.textContent = '✖';
      close.title = 'Close';
      close.onclick = () => { container.style.display = 'none'; };
      container.appendChild(close);
    }

    async function sendEmojiDirect(nodeId, emoji) {
      try {
        const res = await fetch('/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: emoji, node_id: nodeId, direct: true })
        });
        const j = await res.json();
        if (j.status !== 'sent') throw new Error(j.message || 'Failed');
        fetchMessagesAndNodes();
      } catch(e) { alert('Failed to send reaction: ' + e.message); }
    }

    async function sendEmojiChannel(channelIdx, emoji) {
      try {
        const res = await fetch('/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: emoji, channel_index: channelIdx, direct: false })
        });
        const j = await res.json();
        if (j.status !== 'sent') throw new Error(j.message || 'Failed');
        fetchMessagesAndNodes();
      } catch(e) { alert('Failed to send reaction: ' + e.message); }
    }

    function quickSendEmojiFromForm(emoji) {
      // Insert emoji into the message box at the cursor position, do not auto-send
      const ta = document.getElementById('messageBox');
      if (!ta) return;
      const start = ta.selectionStart ?? ta.value.length;
      const end = ta.selectionEnd ?? ta.value.length;
      const insert = emoji + ' ';
      ta.value = ta.value.slice(0, start) + insert + ta.value.slice(end);
      const newPos = start + insert.length;
      ta.selectionStart = ta.selectionEnd = newPos;
      ta.focus();
      updateCharCounter();
    }
    let lastMessageTimestamp = null;
    let tickerTimeout = null;
    let tickerLastShownTimestamp = null;
    let nodeGPSInfo = """ + node_gps_info_json + """;
    let myGPS = """ + my_gps_json + """;
    // Override myGPS with manual lat/lon from UI settings if set
    function getEffectiveMyGPS() {
      if (uiSettings.myLat !== '' && uiSettings.myLon !== '' && uiSettings.myLat != null && uiSettings.myLon != null) {
        return { lat: parseFloat(uiSettings.myLat), lon: parseFloat(uiSettings.myLon) };
      }
      return myGPS;
    }

    // --- Node Sorting ---
    let nodeSortKey = localStorage.getItem("nodeSortKey") || "name";
    let nodeSortDir = localStorage.getItem("nodeSortDir") || "asc";

    function setNodeSort(key, dir) {
      nodeSortKey = key;
      nodeSortDir = dir;
      localStorage.setItem("nodeSortKey", key);
      localStorage.setItem("nodeSortDir", dir);
      updateNodesUI(allNodes, false);
    }

    function compareNodes(a, b) {
      // Favorites always first
      const aFav = isFavoriteNode(a.id) ? 0 : 1;
      const bFav = isFavoriteNode(b.id) ? 0 : 1;
      if (aFav !== bFav) return aFav - bFav;
      // Helper for null/undefined
      function safe(v) { return v === undefined || v === null ? "" : v; }
      // For distance, use haversine if both have GPS, else sort GPS-enabled first
      if (nodeSortKey === "distance") {
        let aGPS = nodeGPSInfo[String(a.id)];
        let bGPS = nodeGPSInfo[String(b.id)];
        let aHas = aGPS && aGPS.lat != null && aGPS.lon != null;
        let bHas = bGPS && bGPS.lat != null && bGPS.lon != null;
        if (!aHas && !bHas) return 0;
        if (aHas && !bHas) return -1;
        if (!aHas && bHas) return 1;
        let distA = calcDistance(myGPS.lat, myGPS.lon, aGPS.lat, aGPS.lon);
        let distB = calcDistance(myGPS.lat, myGPS.lon, bGPS.lat, bGPS.lon);
        return (distA - distB) * (nodeSortDir === "asc" ? 1 : -1);
      }
      if (nodeSortKey === "gps") {
        let aGPS = nodeGPSInfo[String(a.id)];
        let bGPS = nodeGPSInfo[String(b.id)];
        let aHas = aGPS && aGPS.lat != null && aGPS.lon != null;
        let bHas = bGPS && bGPS.lat != null && bGPS.lon != null;
        if (aHas && !bHas) return nodeSortDir === "asc" ? -1 : 1;
        if (!aHas && bHas) return nodeSortDir === "asc" ? 1 : -1;
        return 0;
      }
      if (nodeSortKey === "name") {
        let cmp = safe(a.shortName).localeCompare(safe(b.shortName), undefined, {sensitivity:"base"});
        return cmp * (nodeSortDir === "asc" ? 1 : -1);
      }
      if (nodeSortKey === "beacon") {
        let aGPS = nodeGPSInfo[String(a.id)];
        let bGPS = nodeGPSInfo[String(b.id)];
        let aTime = aGPS && aGPS.beacon_time ? Date.parse(aGPS.beacon_time.replace(" UTC","Z")) : 0;
        let bTime = bGPS && bGPS.beacon_time ? Date.parse(bGPS.beacon_time.replace(" UTC","Z")) : 0;
        return (bTime - aTime) * (nodeSortDir === "asc" ? -1 : 1);
      }
      if (nodeSortKey === "hops") {
        let aGPS = nodeGPSInfo[String(a.id)];
        let bGPS = nodeGPSInfo[String(b.id)];
        let aH = aGPS && aGPS.hops != null ? aGPS.hops : 99;
        let bH = bGPS && bGPS.hops != null ? bGPS.hops : 99;
        return (aH - bH) * (nodeSortDir === "asc" ? 1 : -1);
      }
      return 0;
    }

    // Haversine formula (km)
    function calcDistance(lat1, lon1, lat2, lon2) {
      if (
        lat1 == null || lon1 == null ||
        lat2 == null || lon2 == null
      ) return 99999;
      let toRad = x => x * Math.PI / 180;
      let R = 6371;
      let dLat = toRad(lat2 - lat1);
      let dLon = toRad(lon2 - lon1);
      let a = Math.sin(dLat/2) * Math.sin(dLat/2) +
              Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
              Math.sin(dLon/2) * Math.sin(dLon/2);
      let c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
      return R * c;
    }

    // --- UI Settings State ---
    let uiSettings = {
      themeColor: "#ffa500",
      hueRotateEnabled: false,
      hueRotateSpeed: 10,
      mapStyle: "carto-light",
      soundEnabled: true,
      soundVolume: 0.7,
      soundType: "two-tone",
      soundTypeDm: "two-tone",
      soundTypeChannel: "two-tone",
      soundURL: "",
      customSounds: {},
      nodeSounds: {},
      colorMap: "#ffa500",
      colorSend: "#ffa500",
      colorDm: "#ffa500",
      colorChannel: "#ffa500",
      colorNodes: "#ffa500",
      colorDiscord: "#ffa500",
      myLat: "",
      myLon: "",
      channelNames: {}
    };
    let hueRotateInterval = null;
    let currentHue = 0;
    let seenMessageTimestamps = new Set();
    let initialLoadDone = false;

    // --- Favorites & Custom Node Names ---
    function getFavoriteNodes() {
      try { return JSON.parse(localStorage.getItem('meshapi_favorite_nodes') || '[]'); } catch(e) { return []; }
    }
    function setFavoriteNodes(arr) {
      localStorage.setItem('meshapi_favorite_nodes', JSON.stringify(arr));
    }
    function toggleFavoriteNode(nodeId) {
      let favs = getFavoriteNodes();
      const nid = String(nodeId);
      if (favs.includes(nid)) favs = favs.filter(f => f !== nid);
      else favs.push(nid);
      setFavoriteNodes(favs);
      updateNodesUI(allNodes, false);
    }
    function isFavoriteNode(nodeId) {
      return getFavoriteNodes().includes(String(nodeId));
    }
    function getCustomNodeNames() {
      try { return JSON.parse(localStorage.getItem('meshapi_custom_node_names') || '{}'); } catch(e) { return {}; }
    }
    function setCustomNodeName(nodeId, name) {
      let names = getCustomNodeNames();
      if (name && name.trim()) names[String(nodeId)] = name.trim();
      else delete names[String(nodeId)];
      localStorage.setItem('meshapi_custom_node_names', JSON.stringify(names));
      updateNodesUI(allNodes, false);
    }
    function getCustomNodeName(nodeId) {
      return (getCustomNodeNames())[String(nodeId)] || '';
    }
    function promptCustomNodeName(nodeId, currentName) {
      const name = prompt('Set a custom name for this node (leave blank to clear):', currentName || '');
      if (name !== null) setCustomNodeName(nodeId, name);
    }

    // --- Built-in notification sounds using Web Audio API ---
    let audioCtx = null;
    function getAudioCtx() {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      return audioCtx;
    }
    function playTone(ctx, freq, startTime, duration, vol, type) {
      const g = ctx.createGain();
      g.connect(ctx.destination);
      g.gain.setValueAtTime(vol * 0.3, startTime);
      g.gain.exponentialRampToValueAtTime(0.001, startTime + duration);
      const o = ctx.createOscillator();
      o.type = type || 'sine';
      o.frequency.setValueAtTime(freq, startTime);
      o.connect(g);
      o.start(startTime);
      o.stop(startTime + duration);
    }
    // Sound: Two-tone beep (original)
    function playBeepTwoTone(vol) {
      try {
        const ctx = getAudioCtx();
        if (ctx.state === 'suspended') ctx.resume();
        playTone(ctx, 880, ctx.currentTime, 0.15, vol, 'sine');
        playTone(ctx, 1320, ctx.currentTime + 0.15, 0.4, vol, 'sine');
      } catch (e) { console.warn('Sound failed:', e); }
    }
    // Sound: Triple chirp
    function playTripleChirp(vol) {
      try {
        const ctx = getAudioCtx();
        if (ctx.state === 'suspended') ctx.resume();
        playTone(ctx, 1200, ctx.currentTime, 0.1, vol, 'sine');
        playTone(ctx, 1500, ctx.currentTime + 0.12, 0.1, vol, 'sine');
        playTone(ctx, 1800, ctx.currentTime + 0.24, 0.15, vol, 'sine');
      } catch (e) { console.warn('Sound failed:', e); }
    }
    // Sound: Alert chime
    function playAlertChime(vol) {
      try {
        const ctx = getAudioCtx();
        if (ctx.state === 'suspended') ctx.resume();
        playTone(ctx, 523, ctx.currentTime, 0.2, vol, 'triangle');
        playTone(ctx, 659, ctx.currentTime + 0.2, 0.2, vol, 'triangle');
        playTone(ctx, 784, ctx.currentTime + 0.4, 0.3, vol, 'triangle');
      } catch (e) { console.warn('Sound failed:', e); }
    }
    // Sound: Sonar ping
    function playSonarPing(vol) {
      try {
        const ctx = getAudioCtx();
        if (ctx.state === 'suspended') ctx.resume();
        const g = ctx.createGain();
        g.connect(ctx.destination);
        g.gain.setValueAtTime(vol * 0.4, ctx.currentTime);
        g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
        const o = ctx.createOscillator();
        o.type = 'sine';
        o.frequency.setValueAtTime(1000, ctx.currentTime);
        o.frequency.exponentialRampToValueAtTime(500, ctx.currentTime + 0.8);
        o.connect(g);
        o.start(ctx.currentTime);
        o.stop(ctx.currentTime + 0.8);
      } catch (e) { console.warn('Sound failed:', e); }
    }
    // Sound: Radio blip
    function playRadioBlip(vol) {
      try {
        const ctx = getAudioCtx();
        if (ctx.state === 'suspended') ctx.resume();
        playTone(ctx, 600, ctx.currentTime, 0.08, vol, 'square');
        playTone(ctx, 800, ctx.currentTime + 0.1, 0.08, vol, 'square');
      } catch (e) { console.warn('Sound failed:', e); }
    }

    const builtinSounds = {
      'two-tone': playBeepTwoTone,
      'triple-chirp': playTripleChirp,
      'alert-chime': playAlertChime,
      'sonar-ping': playSonarPing,
      'radio-blip': playRadioBlip
    };

    function playSoundByType(type, vol) {
      // Check custom sounds library first (type starts with 'custom:')
      if (type && type.startsWith('custom:')) {
        const customName = type.slice(7);
        const customData = (uiSettings.customSounds || {})[customName];
        if (customData) {
          const audio = new Audio(customData);
          audio.volume = vol;
          audio.play().catch(e => console.warn('Custom sound play blocked:', e));
          return;
        }
      }
      // Legacy single custom sound
      if (type === 'custom' && uiSettings.soundURL) {
        let audio = document.getElementById('incomingSound');
        if (audio && audio.src) {
          audio.volume = vol;
          audio.currentTime = 0;
          audio.play().catch(e => console.warn('Sound play blocked:', e));
        }
      } else if (builtinSounds[type]) {
        builtinSounds[type](vol);
      } else {
        playBeepTwoTone(vol);
      }
    }
    function getSoundOptionsList() {
      const opts = [
        { value: 'two-tone', label: 'Two-Tone Beep' },
        { value: 'triple-chirp', label: 'Triple Chirp' },
        { value: 'alert-chime', label: 'Alert Chime' },
        { value: 'sonar-ping', label: 'Sonar Ping' },
        { value: 'radio-blip', label: 'Radio Blip' }
      ];
      Object.keys(uiSettings.customSounds || {}).forEach(name => {
        opts.push({ value: 'custom:' + name, label: '🎵 ' + name });
      });
      return opts;
    }
    function populateSoundSelect(selEl, selectedVal) {
      const prev = selEl.value;
      selEl.innerHTML = '';
      getSoundOptionsList().forEach(o => {
        const opt = document.createElement('option');
        opt.value = o.value; opt.textContent = o.label;
        selEl.appendChild(opt);
      });
      selEl.value = selectedVal || prev || 'two-tone';
      if (!selEl.value) selEl.value = 'two-tone';
    }
    function refreshAllSoundSelects() {
      const ids = ['soundTypeSelect','soundTypeDmSelect','soundTypeChannelSelect'];
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) populateSoundSelect(el, el.value);
      });
      // Refresh per-node sound dropdowns too
      document.querySelectorAll('#nodeSoundEntries .node-sound-type').forEach(sel => {
        populateSoundSelect(sel, sel.value);
      });
    }
    function renderCustomSoundsLibrary() {
      const container = document.getElementById('customSoundsLibrary');
      if (!container) return;
      container.innerHTML = '';
      const cs = uiSettings.customSounds || {};
      Object.keys(cs).forEach(name => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:4px;';
        const label = document.createElement('span');
        label.textContent = '🎵 ' + name;
        label.style.cssText = 'flex:1;color:#ccc;font-size:0.85em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;';
        const testBtn = document.createElement('button');
        testBtn.textContent = '▶'; testBtn.title = 'Test';
        testBtn.style.cssText = 'background:#333;color:#fff;border:1px solid #555;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:0.85em;';
        testBtn.onclick = () => { const vol = parseFloat(document.getElementById('soundVolume').value)||0.7; playSoundByType('custom:'+name, vol); };
        const delBtn = document.createElement('button');
        delBtn.textContent = '✕'; delBtn.title = 'Remove';
        delBtn.style.cssText = 'background:#611;color:#fff;border:1px solid #933;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:0.85em;';
        delBtn.onclick = () => { delete uiSettings.customSounds[name]; saveUISettings(); renderCustomSoundsLibrary(); refreshAllSoundSelects(); };
        row.appendChild(label); row.appendChild(testBtn); row.appendChild(delBtn);
        container.appendChild(row);
      });
      if (Object.keys(cs).length === 0) {
        container.innerHTML = '<p style="color:#666;font-size:0.8em;margin:0;">No custom sounds uploaded yet.</p>';
      }
    }
    function uploadCustomSound() {
      const fileInput = document.getElementById('customSoundUpload');
      if (!fileInput || !fileInput.files.length) { alert('Please select an audio file first.'); return; }
      const file = fileInput.files[0];
      const name = file.name.replace(/\\.[^.]+$/, '');
      if (!uiSettings.customSounds) uiSettings.customSounds = {};
      // Convert to base64 data URL for persistence in localStorage
      const reader = new FileReader();
      reader.onload = function(e) {
        uiSettings.customSounds[name] = e.target.result;
        saveUISettings();
        renderCustomSoundsLibrary();
        refreshAllSoundSelects();
        fileInput.value = '';
      };
      reader.readAsDataURL(file);
    }

    function playIncomingSound(isDm, nodeId) {
      if (!uiSettings.soundEnabled) return;
      const vol = uiSettings.soundVolume || 0.7;
      // Per-node override
      if (nodeId && uiSettings.nodeSounds && uiSettings.nodeSounds[String(nodeId)]) {
        playSoundByType(uiSettings.nodeSounds[String(nodeId)], vol);
        return;
      }
      // Per-type sound
      if (isDm) {
        playSoundByType(uiSettings.soundTypeDm || uiSettings.soundType || 'two-tone', vol);
      } else {
        playSoundByType(uiSettings.soundTypeChannel || uiSettings.soundType || 'two-tone', vol);
      }
    }

    function testSelectedSound() {
      const sel = document.getElementById('soundTypeSelect');
      const vol = parseFloat(document.getElementById('soundVolume').value) || 0.7;
      const type = sel ? sel.value : 'two-tone';
      playSoundByType(type, vol);
    }
    function testSoundSelect(selId) {
      const sel = document.getElementById(selId);
      const vol = parseFloat(document.getElementById('soundVolume').value) || 0.7;
      const type = sel ? sel.value : 'two-tone';
      playSoundByType(type, vol);
    }

    function checkForNewMessages(messages) {
      if (!initialLoadDone) {
        messages.forEach(m => seenMessageTimestamps.add(m.timestamp));
        initialLoadDone = true;
        return;
      }
      let latestNewMsg = null;
      messages.forEach(m => {
        if (!seenMessageTimestamps.has(m.timestamp)) {
          seenMessageTimestamps.add(m.timestamp);
          if (m.node !== 'WebUI' && m.node !== 'Discord' && m.node !== 'Twilio' &&
              m.node !== 'DiscordPoll') {
            playIncomingSound(!!m.direct, m.node_id);
            latestNewMsg = m;
          }
        }
      });
      // For the most recent new message, fly map to sender and open reply UI
      try {
        if (latestNewMsg && latestNewMsg.node_id) {
          let nid = String(latestNewMsg.node_id);
          // Fly to the node on map if it has a marker
          if (nodeMarkerLookup[nid]) {
            flyToNode(nid);
          }
          // Open reply box: DM box on map for DMs, or scroll to send form for channels
          if (latestNewMsg.direct) {
            let node = allNodes.find(n => String(n.id) === nid);
            let shortName = node ? (node.shortName || nid) : nid;
            openMapDm(nid, shortName);
          }
        }
      } catch(e) { console.warn('Map fly/reply error:', e); }
    }

    function toggleMode(force) {
      if (typeof force !== "undefined") {
        document.getElementById('modeSwitch').checked = force === 'direct';
      }
      const dm = document.getElementById('modeSwitch').checked;
      document.getElementById('dmField').style.display = dm ? 'block' : 'none';
      document.getElementById('channelField').style.display = dm ? 'none' : 'block';
      document.getElementById('modeLabel').textContent = dm ? 'Direct' : 'Broadcast';
    }

    document.addEventListener("DOMContentLoaded", function() {
      document.getElementById('modeSwitch').addEventListener('change', function() {
        toggleMode();
      });
      const settingsBtn = document.getElementById('settingsFloatBtn');
      const settingsPanel = document.getElementById('settingsPanel');
      const settingsOverlay = document.getElementById('settingsOverlay');
  settingsPanel.classList.remove('open');
  settingsBtn.textContent = "Show UI Settings";
      function openSettings() {
        settingsPanel.classList.add('open');
        settingsOverlay.classList.add('open');
        settingsBtn.textContent = 'Hide UI Settings';
        updateSectionVisibilityCheckboxes();
      }
      function closeSettings() {
        settingsPanel.classList.remove('open');
        settingsOverlay.classList.remove('open');
        settingsBtn.textContent = 'Show UI Settings';
      }
      settingsBtn.addEventListener('click', function(e) {
        e.preventDefault();
        settingsPanel.classList.contains('open') ? closeSettings() : openSettings();
      });
      settingsOverlay.addEventListener('click', closeSettings);
      document.getElementById('nodeSearch').addEventListener('input', function() {
        filterNodes(this.value, false);
      });
      document.getElementById('destNodeSearch').addEventListener('input', function() {
        filterNodes(this.value, true);
      });

      // Node sort controls
      document.getElementById('nodeSortKey').addEventListener('change', function() {
        setNodeSort(this.value, nodeSortDir);
      });
      document.getElementById('nodeSortDir').addEventListener('change', function() {
        setNodeSort(nodeSortKey, this.value);
      });

      // --- UI Settings: Load from localStorage ---
      loadUISettings();

      // Set initial values in settings panel
      document.getElementById('uiColorPicker').value = uiSettings.themeColor;
      document.getElementById('hueRotateEnabled').checked = uiSettings.hueRotateEnabled;
      document.getElementById('hueRotateSpeed').value = uiSettings.hueRotateSpeed;
      document.getElementById('mapStyleSelect').value = uiSettings.mapStyle || 'carto-light';
      // Populate map style select
      (function() {
        const msel = document.getElementById('mapStyleSelect');
        msel.innerHTML = '';
        Object.keys(mapTileProviders).forEach(k => {
          const o = document.createElement('option');
          o.value = k; o.textContent = mapTileProviders[k].name;
          msel.appendChild(o);
        });
        msel.value = uiSettings.mapStyle || 'carto-light';
      })();
      // Populate offline map bounds from saved data
      (function() {
        const offData = getOfflineMapData();
        if (offData && offData.bounds) {
          document.getElementById('offlineMapNorth').value = offData.bounds.north;
          document.getElementById('offlineMapSouth').value = offData.bounds.south;
          document.getElementById('offlineMapWest').value = offData.bounds.west;
          document.getElementById('offlineMapEast').value = offData.bounds.east;
        }
      })();
      // Populate sound selects with built-in + custom sounds
      populateSoundSelect(document.getElementById('soundTypeSelect'), uiSettings.soundType || 'two-tone');
      populateSoundSelect(document.getElementById('soundTypeDmSelect'), uiSettings.soundTypeDm || 'two-tone');
      populateSoundSelect(document.getElementById('soundTypeChannelSelect'), uiSettings.soundTypeChannel || 'two-tone');
      // Render custom sounds library
      renderCustomSoundsLibrary();
      document.getElementById('soundEnabled').checked = uiSettings.soundEnabled !== false;
      document.getElementById('soundVolume').value = uiSettings.soundVolume || 0.7;
      document.getElementById('soundVolumeVal').textContent = Math.round((uiSettings.soundVolume || 0.7) * 100) + '%';
      // Render per-node sound entries
      renderNodeSoundEntries();
      // Set section color pickers
      document.getElementById('colorMapPicker').value = uiSettings.colorMap || '#ffa500';
      document.getElementById('colorSendPicker').value = uiSettings.colorSend || '#ffa500';
      document.getElementById('colorDmPicker').value = uiSettings.colorDm || '#ffa500';
      document.getElementById('colorChannelPicker').value = uiSettings.colorChannel || '#ffa500';
      document.getElementById('colorNodesPicker').value = uiSettings.colorNodes || '#ffa500';
      document.getElementById('colorDiscordPicker').value = uiSettings.colorDiscord || '#ffa500';
      // Set manual GPS fields
      document.getElementById('myLatInput').value = uiSettings.myLat || '';
      document.getElementById('myLonInput').value = uiSettings.myLon || '';
      // Populate channel names list
      populateChannelNamesList();

      // Apply settings on load
      applyThemeColor(uiSettings.themeColor);
      applySectionColors();
      if (uiSettings.hueRotateEnabled) startHueRotate(uiSettings.hueRotateSpeed);
      setIncomingSound(uiSettings.soundURL);

      // Apply button
      document.getElementById('applySettingsBtn').addEventListener('click', function() {
        // Read values
        uiSettings.themeColor = document.getElementById('uiColorPicker').value;
        uiSettings.hueRotateEnabled = document.getElementById('hueRotateEnabled').checked;
        uiSettings.hueRotateSpeed = parseFloat(document.getElementById('hueRotateSpeed').value);
        // Map style
        uiSettings.mapStyle = document.getElementById('mapStyleSelect').value;
        // Sound settings
        uiSettings.soundEnabled = document.getElementById('soundEnabled').checked;
        uiSettings.soundVolume = parseFloat(document.getElementById('soundVolume').value);
        uiSettings.soundType = document.getElementById('soundTypeSelect').value;
        applyThemeColor(uiSettings.themeColor);
        if (uiSettings.hueRotateEnabled) {
          startHueRotate(uiSettings.hueRotateSpeed);
        } else {
          stopHueRotate();
        }
        setIncomingSound(uiSettings.soundURL);
        applyMapTileLayer();
        // DM / Channel sound types
        uiSettings.soundTypeDm = document.getElementById('soundTypeDmSelect').value;
        uiSettings.soundTypeChannel = document.getElementById('soundTypeChannelSelect').value;
        // Per-node sounds
        uiSettings.nodeSounds = collectNodeSoundEntries();
        // Section colors
        uiSettings.colorMap = document.getElementById('colorMapPicker').value;
        uiSettings.colorSend = document.getElementById('colorSendPicker').value;
        uiSettings.colorDm = document.getElementById('colorDmPicker').value;
        uiSettings.colorChannel = document.getElementById('colorChannelPicker').value;
        uiSettings.colorNodes = document.getElementById('colorNodesPicker').value;
        uiSettings.colorDiscord = document.getElementById('colorDiscordPicker').value;
        applySectionColors();
        // Manual GPS
        uiSettings.myLat = document.getElementById('myLatInput').value;
        uiSettings.myLon = document.getElementById('myLonInput').value;
        // Channel name overrides
        let chOverrides = {};
        document.querySelectorAll('#channelNamesList input[data-ch]').forEach(inp => {
          const ch = inp.getAttribute('data-ch');
          const v = inp.value.trim();
          if (v) chOverrides[ch] = v;
        });
        uiSettings.channelNames = chOverrides;
        // Save timezone offset
        setTimezoneOffset(document.getElementById('timezoneSelect').value);
        saveUISettings();
        fetchMessagesAndNodes();
      });

      // Set initial sort controls
      document.getElementById('nodeSortKey').value = nodeSortKey;
      document.getElementById('nodeSortDir').value = nodeSortDir;

      // Set timezone selector
      let tzSel = document.getElementById('timezoneSelect');
      let tz = getTimezoneOffset();
      tzSel.value = tz;

      // --- Init char/chunk counter ---
      initCharChunkCounter();

      // --- Init draggable sections ---
      initSortableLayout();
    });

    // --- UI Settings Functions ---
    function saveUISettings() {
      let settingsToSave = Object.assign({}, uiSettings);
      // Don't persist blob URLs (they're session-only)
      if (settingsToSave.soundURL && settingsToSave.soundURL.startsWith('blob:')) {
        settingsToSave.soundURL = '';
      }
      localStorage.setItem("meshtastic_ui_settings", JSON.stringify(settingsToSave));
    }
    function loadUISettings() {
      try {
        let s = localStorage.getItem("meshtastic_ui_settings");
        if (s) {
          let parsed = JSON.parse(s);
          Object.assign(uiSettings, parsed);
        }
      } catch (e) {}
    }
    function applyThemeColor(color) {
      document.documentElement.style.setProperty('--theme-color', color);
    }
    function applySectionColors() {
      const r = document.documentElement.style;
      r.setProperty('--color-map', uiSettings.colorMap || uiSettings.themeColor);
      r.setProperty('--color-send', uiSettings.colorSend || uiSettings.themeColor);
      r.setProperty('--color-dm', uiSettings.colorDm || uiSettings.themeColor);
      r.setProperty('--color-channel', uiSettings.colorChannel || uiSettings.themeColor);
      r.setProperty('--color-nodes', uiSettings.colorNodes || uiSettings.themeColor);
      r.setProperty('--color-discord', uiSettings.colorDiscord || uiSettings.themeColor);
    }
    function startHueRotate(speed) {
      stopHueRotate();
      hueRotateInterval = setInterval(function() {
        currentHue = (currentHue + 1) % 360;
        const sortable = document.getElementById('sortableContainer');
        if (sortable) sortable.style.filter = `hue-rotate(${currentHue}deg)`;
      }, Math.max(5, 1000 / Math.max(1, speed)));
    }
    function stopHueRotate() {
      if (hueRotateInterval) clearInterval(hueRotateInterval);
      hueRotateInterval = null;
      const sortable = document.getElementById('sortableContainer');
      if (sortable) sortable.style.filter = '';
      currentHue = 0;
    }
    // Per-node sound management
    function renderNodeSoundEntries() {
      const container = document.getElementById('nodeSoundEntries');
      if (!container) return;
      container.innerHTML = '';
      const ns = uiSettings.nodeSounds || {};
      Object.keys(ns).forEach(nodeId => {
        addNodeSoundRow(container, nodeId, ns[nodeId]);
      });
    }
    function addNodeSoundRow(container, nodeId, soundType) {
      const row = document.createElement('div');
      row.className = 'node-sound-row';
      row.style.cssText = 'display:flex;gap:6px;align-items:center;margin-bottom:4px;';
      const inp = document.createElement('select');
      inp.className = 'node-sound-id';
      inp.style.cssText = 'flex:1;background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px 6px;font-size:0.85em;';
      // Blank default option
      const blankOpt = document.createElement('option');
      blankOpt.value = ''; blankOpt.textContent = '-- Select Node --';
      inp.appendChild(blankOpt);
      // Populate from allNodes
      (allNodes || []).forEach(n => {
        const o = document.createElement('option');
        o.value = n.id;
        o.textContent = (n.shortName || '') + ' (' + n.id + ')';
        if (String(n.id) === String(nodeId)) o.selected = true;
        inp.appendChild(o);
      });
      // If nodeId is set but not in allNodes, add it as an option
      if (nodeId && !Array.from(inp.options).some(o => o.value === String(nodeId))) {
        const o = document.createElement('option');
        o.value = nodeId; o.textContent = nodeId; o.selected = true;
        inp.appendChild(o);
      }
      const sel = document.createElement('select');
      sel.className = 'node-sound-type';
      sel.style.cssText = 'background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;font-size:0.85em;';
      getSoundOptionsList().forEach(v => {
        const o = document.createElement('option'); o.value = v.value;
        o.textContent = v.label;
        if (v.value === soundType) o.selected = true;
        sel.appendChild(o);
      });
      const testBtn = document.createElement('button');
      testBtn.textContent = '▶'; testBtn.title = 'Test';
      testBtn.style.cssText = 'background:#333;color:#fff;border:1px solid #555;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:0.85em;';
      testBtn.onclick = () => { const vol = parseFloat(document.getElementById('soundVolume').value)||0.7; playSoundByType(sel.value, vol); };
      const delBtn = document.createElement('button');
      delBtn.textContent = '✕'; delBtn.title = 'Remove';
      delBtn.style.cssText = 'background:#611;color:#fff;border:1px solid #933;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:0.85em;';
      delBtn.onclick = () => row.remove();
      row.appendChild(inp); row.appendChild(sel); row.appendChild(testBtn); row.appendChild(delBtn);
      container.appendChild(row);
    }
    function collectNodeSoundEntries() {
      const result = {};
      document.querySelectorAll('#nodeSoundEntries .node-sound-row').forEach(row => {
        const id = row.querySelector('.node-sound-id').value.trim();
        const type = row.querySelector('.node-sound-type').value;
        if (id) result[id] = type;
      });
      return result;
    }
    function toggleHueRotate(enabled, speed) {
      uiSettings.hueRotateEnabled = enabled;
      uiSettings.hueRotateSpeed = speed;
      saveUISettings();
      if (enabled) startHueRotate(speed);
      else stopHueRotate();
    }
    function setIncomingSound(url) {
      let audio = document.getElementById('incomingSound');
      audio.src = url || "";
      uiSettings.soundURL = url;
      saveUISettings();
    }

    // --- Draggable section layout ---
    function initSortableLayout() {
      const container = document.getElementById('sortableContainer');
      if (!container || typeof Sortable === 'undefined') return;
      Sortable.create(container, {
        handle: '.drag-handle',
        animation: 150,
        ghostClass: 'sortable-ghost',
        chosenClass: 'sortable-chosen',
        filter: '.col-drag',
        onEnd: function() {
          saveSectionOrder();
        }
      });
      loadSectionOrder();
      // Also make the three columns sortable
      const colContainer = document.getElementById('threeColContainer');
      if (colContainer) {
        Sortable.create(colContainer, {
          handle: '.col-drag',
          animation: 150,
          ghostClass: 'sortable-ghost',
          chosenClass: 'sortable-chosen',
          onEnd: function() {
            saveColumnOrder();
          }
        });
        loadColumnOrder();
      }
      // Init map since it's shown by default
      initNodeMapOnLoad();
      // Apply hidden sections from saved state
      applyHiddenSections();
      updateSectionVisibilityCheckboxes();
    }
    const mapTileProviders = {
      'osm': { name: 'OpenStreetMap', url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', attr: '&copy; OpenStreetMap contributors', maxZoom: 19 },
      'carto-light': { name: 'Carto Positron (Light)', url: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', attr: '&copy; CARTO &copy; OpenStreetMap', maxZoom: 20 },
      'carto-dark': { name: 'Carto Dark Matter', url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', attr: '&copy; CARTO &copy; OpenStreetMap', maxZoom: 20 },
      'carto-voyager': { name: 'Carto Voyager', url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', attr: '&copy; CARTO &copy; OpenStreetMap', maxZoom: 20 },
      'carto-light-nolabels': { name: 'Carto Light (No Labels)', url: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png', attr: '&copy; CARTO &copy; OpenStreetMap', maxZoom: 20 },
      'carto-dark-nolabels': { name: 'Carto Dark (No Labels)', url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png', attr: '&copy; CARTO &copy; OpenStreetMap', maxZoom: 20 },
      'osm-topo': { name: 'OpenTopoMap', url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', attr: '&copy; OpenTopoMap &copy; OpenStreetMap', maxZoom: 17 },
      'esri-world': { name: 'Esri World Street Map', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri', maxZoom: 19, noSub: true },
      'esri-satellite': { name: 'Esri World Imagery', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri', maxZoom: 18, noSub: true },
      'esri-topo': { name: 'Esri World Topo', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri', maxZoom: 19, noSub: true },
      'esri-natgeo': { name: 'Esri National Geographic', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri &copy; National Geographic', maxZoom: 16, noSub: true },
      'esri-gray': { name: 'Esri Light Gray Canvas', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri', maxZoom: 16, noSub: true },
      'esri-darkgray': { name: 'Esri Dark Gray Canvas', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri', maxZoom: 16, noSub: true },
      'esri-ocean': { name: 'Esri Ocean Basemap', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}', attr: '&copy; Esri', maxZoom: 13, noSub: true },
      'stamen-terrain': { name: 'Stadia Stamen Terrain', url: 'https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; Stamen Design &copy; OpenStreetMap', maxZoom: 18, noSub: true },
      'stamen-toner': { name: 'Stadia Stamen Toner', url: 'https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; Stamen Design &copy; OpenStreetMap', maxZoom: 20, noSub: true },
      'stamen-toner-lite': { name: 'Stadia Stamen Toner Lite', url: 'https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; Stamen Design &copy; OpenStreetMap', maxZoom: 20, noSub: true },
      'stamen-watercolor': { name: 'Stadia Stamen Watercolor', url: 'https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg', attr: '&copy; Stadia Maps &copy; Stamen Design &copy; OpenStreetMap', maxZoom: 16, noSub: true },
      'stadia-alidade': { name: 'Stadia Alidade Smooth', url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; OpenStreetMap', maxZoom: 20, noSub: true },
      'stadia-alidade-dark': { name: 'Stadia Alidade Dark', url: 'https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; OpenStreetMap', maxZoom: 20, noSub: true },
      'stadia-outdoors': { name: 'Stadia Outdoors', url: 'https://tiles.stadiamaps.com/tiles/outdoors/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; OpenStreetMap', maxZoom: 20, noSub: true },
      'stadia-osm-bright': { name: 'Stadia OSM Bright', url: 'https://tiles.stadiamaps.com/tiles/osm_bright/{z}/{x}/{y}{r}.png', attr: '&copy; Stadia Maps &copy; OpenStreetMap', maxZoom: 20, noSub: true },
      'osm-humanitarian': { name: 'Humanitarian OSM', url: 'https://{s}.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png', attr: '&copy; OpenStreetMap contributors, HOT', maxZoom: 19 },
      'osm-cycle': { name: 'CyclOSM (Cycling)', url: 'https://{s}.tile-cyclosm.openstreetmap.fr/cyclosm/{z}/{x}/{y}.png', attr: '&copy; CyclOSM &copy; OpenStreetMap', maxZoom: 20 },
      'osm-opnv': { name: 'OPNVKarte (Transport)', url: 'https://tileserver.memomaps.de/tilegen/{z}/{x}/{y}.png', attr: '&copy; OpenStreetMap &copy; memomaps.de', maxZoom: 18, noSub: true },
      'offline-image': { name: '📴 Offline Image', offline: true }
    };
    function getMapTileConfig() {
      const style = uiSettings.mapStyle || 'carto-light';
      return mapTileProviders[style] || mapTileProviders['carto-light'];
    }
    let currentTileLayer = null;
    let currentOfflineOverlay = null;
    function applyMapTileLayer() {
      if (!nodeMapInstance) return;
      const cfg = getMapTileConfig();
      if (currentTileLayer) { nodeMapInstance.removeLayer(currentTileLayer); currentTileLayer = null; }
      if (currentOfflineOverlay) { nodeMapInstance.removeLayer(currentOfflineOverlay); currentOfflineOverlay = null; }
      if (cfg.offline) {
        // Offline image overlay mode
        const offData = getOfflineMapData();
        if (offData && offData.image && offData.bounds) {
          const b = offData.bounds;
          const imgBounds = [[b.south, b.west], [b.north, b.east]];
          currentOfflineOverlay = L.imageOverlay(offData.image, imgBounds).addTo(nodeMapInstance);
          nodeMapInstance.fitBounds(imgBounds);
        } else {
          alert('No offline map image configured. Upload one in Settings > Offline Map Image.');
          // Fallback to default
          uiSettings.mapStyle = 'carto-light';
          applyMapTileLayer();
          return;
        }
      } else {
        const tileOpts = { attribution: cfg.attr, maxZoom: cfg.maxZoom || 19, errorTileUrl: '' };
        if (!cfg.noSub) tileOpts.subdomains = 'abc';
        currentTileLayer = L.tileLayer(cfg.url, tileOpts).addTo(nodeMapInstance);
      }
      updateMapOfflineNotice();
    }
    function getOfflineMapData() {
      try { return JSON.parse(localStorage.getItem('meshapi_offline_map') || 'null'); } catch(e) { return null; }
    }
    function uploadOfflineMapImage() {
      const fileInput = document.getElementById('offlineMapUpload');
      const north = parseFloat(document.getElementById('offlineMapNorth').value);
      const south = parseFloat(document.getElementById('offlineMapSouth').value);
      const west = parseFloat(document.getElementById('offlineMapWest').value);
      const east = parseFloat(document.getElementById('offlineMapEast').value);
      if (!fileInput || !fileInput.files.length) { alert('Select a map image file first.'); return; }
      if (isNaN(north) || isNaN(south) || isNaN(west) || isNaN(east)) { alert('Please fill in all four lat/lon bounds.'); return; }
      if (north <= south) { alert('North latitude must be greater than South.'); return; }
      if (east <= west) { alert('East longitude must be greater than West.'); return; }
      const reader = new FileReader();
      reader.onload = function(e) {
        const data = { image: e.target.result, bounds: { north, south, west, east } };
        try {
          localStorage.setItem('meshapi_offline_map', JSON.stringify(data));
          alert('Offline map image saved! Select "Offline Image" in Map Style to use it.');
          fileInput.value = '';
        } catch(err) {
          alert('Failed to save — image may be too large for localStorage. Try a smaller/compressed image.');
        }
      };
      reader.readAsDataURL(fileInput.files[0]);
    }
    function clearOfflineMapImage() {
      localStorage.removeItem('meshapi_offline_map');
      document.getElementById('offlineMapNorth').value = '';
      document.getElementById('offlineMapSouth').value = '';
      document.getElementById('offlineMapWest').value = '';
      document.getElementById('offlineMapEast').value = '';
      if (uiSettings.mapStyle === 'offline-image') {
        uiSettings.mapStyle = 'carto-light';
        if (nodeMapInstance) applyMapTileLayer();
      }
      alert('Offline map image cleared.');
    }
    function updateMapOfflineNotice() {
      let notice = document.getElementById('mapOfflineNotice');
      if (!navigator.onLine) {
        if (!notice) {
          notice = document.createElement('div');
          notice.id = 'mapOfflineNotice';
          notice.style.cssText = 'position:absolute;top:10px;left:50%;transform:translateX(-50%);z-index:1000;background:rgba(0,0,0,0.85);color:#ffa500;padding:8px 16px;border-radius:6px;border:1px solid #ffa500;font-size:0.85em;pointer-events:none;';
          notice.textContent = '📡 Offline — Map tiles unavailable. Node positions still shown.';
          const mapEl = document.getElementById('nodeMap');
          if (mapEl) mapEl.style.position = 'relative';
          if (mapEl) mapEl.appendChild(notice);
        }
        notice.style.display = 'block';
      } else if (notice) {
        notice.style.display = 'none';
      }
    }
    window.addEventListener('online', function() { updateMapOfflineNotice(); if (nodeMapInstance) applyMapTileLayer(); });
    window.addEventListener('offline', updateMapOfflineNotice);
    function initNodeMapOnLoad() {
      const panel = document.getElementById('nodeMapPanel');
      if (panel && !panel.classList.contains('collapsed')) {
        setTimeout(function() {
          if (!nodeMapInstance) {
            nodeMapInstance = L.map('nodeMap').setView([0, 0], 2);
            nodeMapInstance.on('zoomstart dragstart', function() { mapUserInteracted = true; });
            applyMapTileLayer();
          }
          nodeMapInstance.invalidateSize();
          updateNodeMap();
          // Second invalidateSize after flex layout fully settles
          setTimeout(function() {
            if (nodeMapInstance) nodeMapInstance.invalidateSize();
          }, 500);
        }, 300);
      }
    }
    function saveSectionOrder() {
      const container = document.getElementById('sortableContainer');
      if (!container) return;
      const order = Array.from(container.children)
        .map(el => el.getAttribute('data-section'))
        .filter(Boolean);
      localStorage.setItem('meshtastic_layout_order', JSON.stringify(order));
    }
    function loadSectionOrder() {
      try {
        const saved = localStorage.getItem('meshtastic_layout_order');
        if (!saved) return;
        const order = JSON.parse(saved);
        const container = document.getElementById('sortableContainer');
        if (!container || !Array.isArray(order)) return;
        order.forEach(sectionId => {
          const el = container.querySelector('[data-section="' + sectionId + '"]');
          if (el) container.appendChild(el);
        });
      } catch (e) { console.warn('Failed to load layout:', e); }
    }
    function saveColumnOrder() {
      const container = document.getElementById('threeColContainer');
      if (!container) return;
      const order = Array.from(container.children)
        .map(el => el.getAttribute('data-col'))
        .filter(Boolean);
      localStorage.setItem('meshtastic_col_order', JSON.stringify(order));
    }
    function loadColumnOrder() {
      try {
        const saved = localStorage.getItem('meshtastic_col_order');
        if (!saved) return;
        const order = JSON.parse(saved);
        const container = document.getElementById('threeColContainer');
        if (!container || !Array.isArray(order)) return;
        order.forEach(colId => {
          const el = container.querySelector('[data-col="' + colId + '"]');
          if (el) container.appendChild(el);
        });
      } catch (e) { console.warn('Failed to load col order:', e); }
    }

    function scrollToSend() {
      const sf = document.getElementById('sendForm');
      if (sf) sf.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(function() { const mb = document.getElementById('messageBox'); if (mb) mb.focus(); }, 400);
    }

    // --- Section Hide/Show ---
    function getHiddenSections() {
      try {
        let saved = localStorage.getItem('meshtastic_hidden_sections');
        return saved ? JSON.parse(saved) : [];
      } catch(e) { return []; }
    }
    function saveHiddenSections(arr) {
      localStorage.setItem('meshtastic_hidden_sections', JSON.stringify(arr));
    }
    function hideSection(sectionId) {
      let el = document.querySelector('#sortableContainer [data-section="' + sectionId + '"]');
      if (el) el.style.display = 'none';
      let hidden = getHiddenSections();
      if (!hidden.includes(sectionId)) hidden.push(sectionId);
      saveHiddenSections(hidden);
      updateSectionVisibilityCheckboxes();
    }
    function showSection(sectionId) {
      let el = document.querySelector('#sortableContainer [data-section="' + sectionId + '"]');
      if (el) {
        el.style.display = '';
        // Special case: discord is hidden by default
        if (sectionId === 'discordSection') {
          let inner = el.querySelector('#discordSection');
          if (inner) inner.style.display = 'block';
        }
      }
      let hidden = getHiddenSections();
      hidden = hidden.filter(s => s !== sectionId);
      saveHiddenSections(hidden);
      // Re-init map if showing map panel
      if (sectionId === 'nodeMapPanel') {
        setTimeout(function() { initNodeMapOnLoad(); }, 200);
      }
      updateSectionVisibilityCheckboxes();
    }
    function applyHiddenSections() {
      let hidden = getHiddenSections();
      hidden.forEach(function(sectionId) {
        let el = document.querySelector('#sortableContainer [data-section="' + sectionId + '"]');
        if (el) el.style.display = 'none';
      });
    }
    const SECTION_LABELS = {
      nodeMapPanel: '🗺️ Node Map',
      sendForm: '✉️ Send a Message',
      threeCol: '💬 Message Panels',
      discordSection: '🎮 Discord Messages'
    };
    function updateSectionVisibilityCheckboxes() {
      let container = document.getElementById('sectionVisibilityList');
      if (!container) return;
      container.innerHTML = '';
      let hidden = getHiddenSections();
      Object.keys(SECTION_LABELS).forEach(function(sid) {
        let row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:4px;';
        let cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !hidden.includes(sid);
        cb.onchange = function() {
          if (this.checked) showSection(sid);
          else hideSection(sid);
        };
        let lbl = document.createElement('label');
        lbl.textContent = SECTION_LABELS[sid];
        lbl.style.color = '#fff';
        row.appendChild(cb);
        row.appendChild(lbl);
        container.appendChild(row);
      });
    }

    function replyToMessage(mode, target) {
      toggleMode(mode);
      if (mode === 'direct') {
        const dest = document.getElementById('destNode');
        dest.value = target;
        const name = dest.selectedOptions[0] ? dest.selectedOptions[0].text.split(' (')[0] : '';
        document.getElementById('messageBox').value = '@' + name + ': ';
      } else {
        const ch = document.getElementById('channelSel');
        ch.value = target;
        document.getElementById('messageBox').value = '';
      }
      updateCharCounter();
      scrollToSend();
    }

    function dmToNode(nodeId, shortName, replyToTs) {
      toggleMode('direct');
      document.getElementById('destNode').value = nodeId;
      if (replyToTs) {
        let threadMsg = allMessages.find(m => m.timestamp === replyToTs);
        let quoted = threadMsg ? `> ${threadMsg.message}\n` : '';
        document.getElementById('messageBox').value = quoted + '@' + shortName + ': ';
      } else {
        document.getElementById('messageBox').value = '@' + shortName + ': ';
      }
      updateCharCounter();
      scrollToSend();
    }

    function replyToLastDM() {
      if (lastDMTarget !== null) {
        const opt = document.querySelector(`#destNode option[value="${lastDMTarget}"]`);
        const shortName = opt ? opt.text.split(' (')[0] : '';
        dmToNode(lastDMTarget, shortName);
      } else {
        alert("No direct message target available.");
      }
    }

    function replyToLastChannel() {
      if (lastChannelTarget !== null) {
        toggleMode('broadcast');
        document.getElementById('channelSel').value = lastChannelTarget;
        document.getElementById('messageBox').value = '';
        updateCharCounter();
        scrollToSend();
      } else {
        alert("No broadcast channel target available.");
      }
    }

    // --- Extensions Modal ---
    let extensionsData = { loaded: {}, available: {} };
    let activeExtConfigSlug = null;

    function openExtensionsModal() {
      document.getElementById('extensionsModal').style.display = 'flex';
      loadExtensionsStatus();
    }
    function closeExtensionsModal() {
      document.getElementById('extensionsModal').style.display = 'none';
      activeExtConfigSlug = null;
    }
    async function loadExtensionsStatus() {
      try {
        const r = await fetch('/extensions/status');
        extensionsData = await r.json();
        renderExtensionsList();
      } catch (e) { console.error('Failed to load extensions:', e); }
    }
    function renderExtensionsList() {
      const container = document.getElementById('extensionsListBody');
      container.innerHTML = '';
      const allSlugs = Object.keys(extensionsData.available || {});
      if (allSlugs.length === 0) {
        container.innerHTML = '<div style="color:#ccc;padding:10px;">No extensions found.</div>';
        return;
      }
      allSlugs.sort().forEach(slug => {
        const info = extensionsData.available[slug];
        const isLoaded = slug in (extensionsData.loaded || {});
        const row = document.createElement('div');
        row.className = 'ext-row';
        row.style.cssText = 'display:flex; align-items:center; gap:10px; padding:8px 10px; border-bottom:1px solid #333; flex-wrap:wrap;';

        const statusDot = document.createElement('span');
        statusDot.style.cssText = 'width:12px; height:12px; border-radius:50%; display:inline-block; flex-shrink:0;';
        statusDot.style.background = isLoaded ? '#0f0' : (info.enabled ? '#ff0' : '#666');
        statusDot.title = isLoaded ? 'Active' : (info.enabled ? 'Enabled (not loaded)' : 'Disabled');
        row.appendChild(statusDot);

        const nameSpan = document.createElement('span');
        nameSpan.style.cssText = 'font-weight:bold; color:var(--theme-color); min-width:120px;';
        nameSpan.textContent = info.name + ' v' + info.version;
        row.appendChild(nameSpan);

        const statusLabel = document.createElement('span');
        statusLabel.style.cssText = 'font-size:0.85em; color:#aaa; min-width:80px;';
        statusLabel.textContent = isLoaded ? 'Active' : (info.enabled ? 'Enabled' : 'Disabled');
        row.appendChild(statusLabel);

        if (info.commands && info.commands.length > 0) {
          const cmds = document.createElement('span');
          cmds.style.cssText = 'font-size:0.85em; color:#0ff;';
          cmds.textContent = info.commands.join(', ');
          row.appendChild(cmds);
        }

        const btnGroup = document.createElement('span');
        btnGroup.style.cssText = 'margin-left:auto; display:flex; gap:6px;';

        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'reply-btn';
        toggleBtn.textContent = info.enabled ? 'Disable' : 'Enable';
        toggleBtn.style.fontSize = '0.85em';
        toggleBtn.onclick = async () => {
          try {
            const r = await fetch('/extensions/toggle/' + slug, { method:'POST' });
            const j = await r.json();
            if (r.ok) { loadExtensionsStatus(); }
            else { alert(j.message || 'Toggle failed'); }
          } catch (e) { alert('Error: ' + e.message); }
        };
        btnGroup.appendChild(toggleBtn);

        const cfgBtn = document.createElement('button');
        cfgBtn.className = 'reply-btn';
        cfgBtn.textContent = 'Config';
        cfgBtn.style.fontSize = '0.85em';
        cfgBtn.onclick = () => openExtensionConfig(slug, info.name);
        btnGroup.appendChild(cfgBtn);

        row.appendChild(btnGroup);
        container.appendChild(row);
      });
    }

    async function openExtensionConfig(slug, name) {
      activeExtConfigSlug = slug;
      document.getElementById('extConfigTitle').textContent = name + ' Configuration';
      document.getElementById('extConfigSlug').textContent = slug;
      document.getElementById('extConfigPanel').style.display = 'block';
      document.getElementById('extConfigEditor').value = 'Loading...';
      try {
        const r = await fetch('/extensions/config/' + slug);
        if (!r.ok) throw new Error('Failed to load config');
        const data = await r.json();
        document.getElementById('extConfigEditor').value = JSON.stringify(data, null, 2);
      } catch (e) {
        document.getElementById('extConfigEditor').value = '// Error loading config: ' + e.message;
      }
    }
    async function saveExtensionConfig() {
      if (!activeExtConfigSlug) return;
      const text = document.getElementById('extConfigEditor').value;
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch (e) {
        alert('Invalid JSON: ' + e.message);
        return;
      }
      try {
        const r = await fetch('/extensions/config/' + activeExtConfigSlug, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(parsed)
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.message || 'Save failed');
        alert('Config saved. Changes may require a reload or restart.');
        document.getElementById('extConfigEditor').value = JSON.stringify(parsed, null, 2);
        loadExtensionsStatus();
      } catch (e) { alert('Error saving: ' + e.message); }
    }
    async function reloadExtensions() {
      if (!confirm('Hot-reload all extensions? Active connections may be briefly interrupted.')) return;
      try {
        const r = await fetch('/extensions/reload', { method:'POST' });
        const j = await r.json();
        if (!r.ok) throw new Error(j.message || 'Reload failed');
        alert('Extensions reloaded successfully.');
        loadExtensionsStatus();
      } catch (e) { alert('Reload failed: ' + e.message); }
    }

    // Data fetch & UI updates
    let CHANNEL_NAMES = """ + json.dumps(channel_names) + """;
    // Override with UI-renamed channels from settings
    function getChannelName(ch) {
      if (uiSettings.channelNames && uiSettings.channelNames[String(ch)]) return uiSettings.channelNames[String(ch)];
      return CHANNEL_NAMES[String(ch)] || 'Channel ' + ch;
    }
    // Pull channel names from the connected node
    async function fetchNodeChannels() {
      try {
        const r = await fetch('/api/channels');
        if (!r.ok) return;
        const data = await r.json();
        if (data && Object.keys(data).length > 0) {
          Object.keys(data).forEach(k => {
            if (data[k] && !CHANNEL_NAMES[k]) CHANNEL_NAMES[k] = data[k];
            else if (data[k] && CHANNEL_NAMES[k] === 'Channel ' + k) CHANNEL_NAMES[k] = data[k];
          });
        }
      } catch(e) { console.log('Could not fetch node channels:', e); }
    }
    fetchNodeChannels();

    function populateChannelNamesList() {
      const container = document.getElementById('channelNamesList');
      if (!container) return;
      container.innerHTML = '';
      // Show channels 0-7 (standard Meshtastic range)
      for (let i = 0; i <= 7; i++) {
        const label = document.createElement('label');
        label.textContent = 'Ch ' + i;
        label.style.cssText = 'color:#ccc;font-size:0.9em;';
        const input = document.createElement('input');
        input.type = 'text';
        input.setAttribute('data-ch', String(i));
        input.placeholder = CHANNEL_NAMES[i] || ('Channel ' + i);
        input.value = uiSettings.channelNames && uiSettings.channelNames[String(i)] ? uiSettings.channelNames[String(i)] : '';
        input.style.cssText = 'background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;box-sizing:border-box;';
        container.appendChild(label);
        container.appendChild(input);
      }
    }

    function getNowUTC() {
      return new Date(new Date().toISOString().slice(0, 19) + "Z");
    }

    function getTZAdjusted(tsStr) {
      // tsStr is "YYYY-MM-DD HH:MM:SS UTC"
      let tz = getTimezoneOffset();
      if (!tsStr) return "";
      let dt = new Date(tsStr.replace(" UTC", "Z"));
      if (isNaN(dt.getTime())) return tsStr;
      dt.setHours(dt.getHours() + tz);
      let pad = n => n < 10 ? "0" + n : n;
      return dt.getFullYear() + "-" + pad(dt.getMonth()+1) + "-" + pad(dt.getDate()) + " " +
             pad(dt.getHours()) + ":" + pad(dt.getMinutes()) + ":" + pad(dt.getSeconds()) +
             (tz === 0 ? " UTC" : (tz > 0 ? " UTC+" + tz : " UTC" + tz));
    }

    function isRecent(tsStr, minutes) {
      if (!tsStr) return false;
      let now = getNowUTC();
      let msgTime = new Date(tsStr.replace(" UTC", "Z"));
      return (now - msgTime) < minutes * 60 * 1000;
    }

    async function fetchMessagesAndNodes() {
      try {
        let msgs = await (await fetch("/messages")).json();
        allMessages = msgs;
        let nodes = await (await fetch("/nodes")).json();
        allNodes = nodes;
        checkForNewMessages(msgs);
        updateMessagesUI(msgs);
        updateNodesUI(nodes, false);
        updateNodesUI(nodes, true);
        updateDirectMessagesUI(msgs, nodes);
        highlightRecentNodes(nodes);
        showLatestMessageTicker(msgs);
        updateDiscordMessagesUI(msgs);
        updateNodeMap();
      } catch (e) { console.error(e); }
    }

    // --- Commands Modal ---
    async function openCommandsModal() {
      try {
        const res = await fetch('/commands_info');
        const data = await res.json();
        const tbody = document.getElementById('commandsTableBody');
        tbody.innerHTML = '';
        data.forEach(item => {
          const tr = document.createElement('tr');
          const tdCmd = document.createElement('td');
          const tdDesc = document.createElement('td');
          tdCmd.innerHTML = `<code>${item.command}</code>`;
          tdDesc.textContent = item.description || '';
          tr.appendChild(tdCmd);
          tr.appendChild(tdDesc);
          tbody.appendChild(tr);
        });
        document.getElementById('commandsModal').style.display = 'flex';
      } catch (e) { console.error(e); }
    }
    function closeCommandsModal() {
      document.getElementById('commandsModal').style.display = 'none';
    }

    // --- Config Modal ---
    function openConfigModal() { document.getElementById('configModal').style.display = 'flex'; loadConfigFiles(); }
    function closeConfigModal() { document.getElementById('configModal').style.display = 'none'; }
    function showConfigTab(which){
      document.getElementById('cfgTab').style.display = (which==='cfg')?'block':'none';
      document.getElementById('cmdTab').style.display = (which==='cmd')?'block':'none';
      document.getElementById('motdTab').style.display = (which==='motd')?'block':'none';
      document.getElementById('cfgRawTab').style.display = (which==='cfgraw')?'block':'none';
    }
    // --- Commands Form Builder ---
    function addCommandRow(cmd) {
      const container = document.getElementById('cmdFormRows');
      const row = document.createElement('div');
      row.className = 'cmd-form-row';
      row.style.cssText = 'border:1px solid #333;border-radius:8px;padding:10px;margin-bottom:8px;background:#111;position:relative;';
      const isAI = cmd && cmd.ai_prompt;
      row.innerHTML = `
        <button type="button" onclick="this.parentElement.remove()" style="position:absolute;top:6px;right:8px;background:none;border:none;color:#f66;cursor:pointer;font-size:1.1em;" title="Remove command">&times;</button>
        <div style="display:grid;grid-template-columns:auto 1fr;gap:6px 10px;align-items:center;">
          <label style="color:#ccc;font-size:0.85em;">Command</label>
          <input type="text" class="cmd-trigger" value="${cmd ? cmd.command.replace(/"/g,'&quot;') : ''}" placeholder="/mycommand" style="background:#222;color:#0ff;border:1px solid #555;border-radius:4px;padding:4px;font-family:monospace;width:100%;box-sizing:border-box;">
          <label style="color:#ccc;font-size:0.85em;">Type</label>
          <select class="cmd-type" onchange="cmdTypeChanged(this)" style="background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:4px;">
            <option value="static" ${!isAI ? 'selected' : ''}>Static Response</option>
            <option value="ai" ${isAI ? 'selected' : ''}>AI Prompt</option>
          </select>
          <label style="color:#ccc;font-size:0.85em;" class="cmd-resp-label">${isAI ? 'AI Prompt' : 'Response'}</label>
          <textarea class="cmd-resp-value" rows="2" placeholder="${isAI ? 'Give me a fun fact about {user_input}' : 'Pong!'}" style="background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:4px;font-family:monospace;width:100%;box-sizing:border-box;resize:vertical;">${cmd ? (isAI ? cmd.ai_prompt : cmd.response || '').replace(/</g,'&lt;') : ''}</textarea>
          <label style="color:#ccc;font-size:0.85em;">Description</label>
          <input type="text" class="cmd-desc" value="${cmd ? (cmd.description || '').replace(/"/g,'&quot;') : ''}" placeholder="What does this command do?" style="background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:4px;width:100%;box-sizing:border-box;">
        </div>`;
      container.appendChild(row);
    }
    function cmdTypeChanged(sel) {
      const row = sel.closest('.cmd-form-row');
      const label = row.querySelector('.cmd-resp-label');
      const textarea = row.querySelector('.cmd-resp-value');
      if (sel.value === 'ai') {
        label.textContent = 'AI Prompt';
        textarea.placeholder = 'Give me a fun fact about {user_input}';
      } else {
        label.textContent = 'Response';
        textarea.placeholder = 'Pong!';
      }
    }
    function populateCommandForm(cmds) {
      const container = document.getElementById('cmdFormRows');
      container.innerHTML = '';
      if (cmds && cmds.length) {
        cmds.forEach(c => addCommandRow(c));
      }
    }
    function collectCommandForm() {
      const rows = document.querySelectorAll('#cmdFormRows .cmd-form-row');
      const commands = [];
      rows.forEach(row => {
        const trigger = row.querySelector('.cmd-trigger').value.trim();
        if (!trigger) return;
        const type = row.querySelector('.cmd-type').value;
        const value = row.querySelector('.cmd-resp-value').value;
        const desc = row.querySelector('.cmd-desc').value.trim();
        const obj = { command: trigger, description: desc };
        if (type === 'ai') obj.ai_prompt = value;
        else obj.response = value;
        commands.push(obj);
      });
      return { commands: commands };
    }

    let _loadedConfig = {};
    function cfgVal(id) { const el = document.getElementById(id); if (!el) return undefined; if (el.type === 'checkbox') return el.checked; if (el.type === 'number') { const v = el.value; return v === '' ? null : Number(v); } return el.value; }
    function setCfgVal(id, val) { const el = document.getElementById(id); if (!el) return; if (el.type === 'checkbox') el.checked = !!val; else el.value = (val == null) ? '' : val; }
    function showProviderFields() {
      document.querySelectorAll('.ai-provider-section').forEach(s => s.style.display = 'none');
      const p = document.getElementById('cfg_ai_provider').value;
      const sec = document.getElementById('ai_sec_' + p);
      if (sec) sec.style.display = 'block';
    }
    function populateConfigForm(cfg) {
      _loadedConfig = cfg;
      // Connection
      setCfgVal('cfg_use_mesh_interface', cfg.use_mesh_interface);
      setCfgVal('cfg_use_wifi', cfg.use_wifi);
      setCfgVal('cfg_wifi_host', cfg.wifi_host);
      setCfgVal('cfg_wifi_port', cfg.wifi_port);
      setCfgVal('cfg_use_bluetooth', cfg.use_bluetooth);
      setCfgVal('cfg_ble_address', cfg.ble_address);
      setCfgVal('cfg_serial_port', cfg.serial_port);
      setCfgVal('cfg_serial_baud', cfg.serial_baud);
      setCfgVal('cfg_debug', cfg.debug);
      // AI Provider
      const provVal = (cfg.ai_provider || '').split(',')[0].trim();
      const provSelect = document.getElementById('cfg_ai_provider');
      if (provSelect) { for (let o of provSelect.options) { if (o.value === provVal) { provSelect.value = provVal; break; } } }
      showProviderFields();
      // Per-provider fields
      const providers = ['lmstudio','openai','ollama','claude','gemini','grok','openrouter','groq','deepseek','mistral','openai_compatible'];
      providers.forEach(p => {
        if (p === 'lmstudio') { setCfgVal('cfg_lmstudio_url', cfg.lmstudio_url); setCfgVal('cfg_lmstudio_chat_model', cfg.lmstudio_chat_model); setCfgVal('cfg_lmstudio_embedding_model', cfg.lmstudio_embedding_model); setCfgVal('cfg_lmstudio_timeout', cfg.lmstudio_timeout); }
        else if (p === 'ollama') { setCfgVal('cfg_ollama_url', cfg.ollama_url); setCfgVal('cfg_ollama_model', cfg.ollama_model); setCfgVal('cfg_ollama_timeout', cfg.ollama_timeout); setCfgVal('cfg_ollama_keep_alive', cfg.ollama_keep_alive); setCfgVal('cfg_ollama_max_parallel', cfg.ollama_max_parallel); }
        else if (p === 'openai_compatible') { setCfgVal('cfg_openai_compatible_url', cfg.openai_compatible_url); setCfgVal('cfg_openai_compatible_api_key', cfg.openai_compatible_api_key); setCfgVal('cfg_openai_compatible_model', cfg.openai_compatible_model); setCfgVal('cfg_openai_compatible_timeout', cfg.openai_compatible_timeout); }
        else { setCfgVal('cfg_'+p+'_api_key', cfg[p+'_api_key']); setCfgVal('cfg_'+p+'_model', cfg[p+'_model']); setCfgVal('cfg_'+p+'_timeout', cfg[p+'_timeout']); }
      });
      // Behavior
      setCfgVal('cfg_system_prompt', cfg.system_prompt);
      setCfgVal('cfg_ai_command', cfg.ai_command);
      setCfgVal('cfg_reply_in_channels', cfg.reply_in_channels);
      setCfgVal('cfg_reply_in_directs', cfg.reply_in_directs);
      setCfgVal('cfg_ai_respond_on_longfast', cfg.ai_respond_on_longfast);
      setCfgVal('cfg_respond_to_mqtt_messages', cfg.respond_to_mqtt_messages);
      // Chunking
      setCfgVal('cfg_chunk_size', cfg.chunk_size);
      setCfgVal('cfg_max_ai_chunks', cfg.max_ai_chunks);
      setCfgVal('cfg_chunk_delay', cfg.chunk_delay);
      // Node Identity
      setCfgVal('cfg_ai_node_name', cfg.ai_node_name);
      setCfgVal('cfg_local_location_string', cfg.local_location_string);
      setCfgVal('cfg_force_node_num', cfg.force_node_num);
      setCfgVal('cfg_nodes_online_window_sec', cfg.nodes_online_window_sec);
      setCfgVal('cfg_max_message_log', cfg.max_message_log);
      // Channels
      const chNames = cfg.channel_names || {};
      for (let i = 0; i <= 9; i++) setCfgVal('cfg_ch_' + i, chNames[String(i)] || '');
      // Alerts
      setCfgVal('cfg_enable_twilio', cfg.enable_twilio);
      setCfgVal('cfg_twilio_sid', cfg.twilio_sid);
      setCfgVal('cfg_twilio_auth_token', cfg.twilio_auth_token);
      setCfgVal('cfg_twilio_from_number', cfg.twilio_from_number);
      setCfgVal('cfg_alert_phone_number', cfg.alert_phone_number);
      setCfgVal('cfg_twilio_inbound_target', cfg.twilio_inbound_target);
      setCfgVal('cfg_twilio_inbound_channel_index', cfg.twilio_inbound_channel_index);
      setCfgVal('cfg_twilio_inbound_node', cfg.twilio_inbound_node);
      setCfgVal('cfg_enable_smtp', cfg.enable_smtp);
      setCfgVal('cfg_smtp_host', cfg.smtp_host);
      setCfgVal('cfg_smtp_port', cfg.smtp_port);
      setCfgVal('cfg_smtp_user', cfg.smtp_user);
      setCfgVal('cfg_smtp_pass', cfg.smtp_pass);
      setCfgVal('cfg_alert_email_to', cfg.alert_email_to);
    }
    function collectConfigForm() {
      const cfg = Object.assign({}, _loadedConfig);
      cfg.debug = cfgVal('cfg_debug');
      cfg.use_mesh_interface = cfgVal('cfg_use_mesh_interface');
      cfg.use_wifi = cfgVal('cfg_use_wifi');
      cfg.wifi_host = cfgVal('cfg_wifi_host');
      cfg.wifi_port = cfgVal('cfg_wifi_port');
      cfg.use_bluetooth = cfgVal('cfg_use_bluetooth');
      cfg.ble_address = cfgVal('cfg_ble_address');
      cfg.serial_port = cfgVal('cfg_serial_port');
      cfg.serial_baud = cfgVal('cfg_serial_baud');
      cfg.ai_provider = cfgVal('cfg_ai_provider');
      // Per-provider
      const providers = ['lmstudio','openai','ollama','claude','gemini','grok','openrouter','groq','deepseek','mistral','openai_compatible'];
      providers.forEach(p => {
        if (p === 'lmstudio') { cfg.lmstudio_url = cfgVal('cfg_lmstudio_url'); cfg.lmstudio_chat_model = cfgVal('cfg_lmstudio_chat_model'); cfg.lmstudio_embedding_model = cfgVal('cfg_lmstudio_embedding_model'); cfg.lmstudio_timeout = cfgVal('cfg_lmstudio_timeout'); }
        else if (p === 'ollama') { cfg.ollama_url = cfgVal('cfg_ollama_url'); cfg.ollama_model = cfgVal('cfg_ollama_model'); cfg.ollama_timeout = cfgVal('cfg_ollama_timeout'); cfg.ollama_keep_alive = cfgVal('cfg_ollama_keep_alive'); cfg.ollama_max_parallel = cfgVal('cfg_ollama_max_parallel'); }
        else if (p === 'openai_compatible') { cfg.openai_compatible_url = cfgVal('cfg_openai_compatible_url'); cfg.openai_compatible_api_key = cfgVal('cfg_openai_compatible_api_key'); cfg.openai_compatible_model = cfgVal('cfg_openai_compatible_model'); cfg.openai_compatible_timeout = cfgVal('cfg_openai_compatible_timeout'); }
        else { cfg[p+'_api_key'] = cfgVal('cfg_'+p+'_api_key'); cfg[p+'_model'] = cfgVal('cfg_'+p+'_model'); cfg[p+'_timeout'] = cfgVal('cfg_'+p+'_timeout'); }
      });
      cfg.system_prompt = cfgVal('cfg_system_prompt');
      cfg.ai_command = cfgVal('cfg_ai_command');
      cfg.reply_in_channels = cfgVal('cfg_reply_in_channels');
      cfg.reply_in_directs = cfgVal('cfg_reply_in_directs');
      cfg.ai_respond_on_longfast = cfgVal('cfg_ai_respond_on_longfast');
      cfg.respond_to_mqtt_messages = cfgVal('cfg_respond_to_mqtt_messages');
      cfg.chunk_size = cfgVal('cfg_chunk_size');
      cfg.max_ai_chunks = cfgVal('cfg_max_ai_chunks');
      cfg.chunk_delay = cfgVal('cfg_chunk_delay');
      cfg.ai_node_name = cfgVal('cfg_ai_node_name');
      cfg.local_location_string = cfgVal('cfg_local_location_string');
      cfg.force_node_num = cfgVal('cfg_force_node_num');
      cfg.nodes_online_window_sec = cfgVal('cfg_nodes_online_window_sec');
      cfg.max_message_log = cfgVal('cfg_max_message_log');
      const chNames = {};
      for (let i = 0; i <= 9; i++) chNames[String(i)] = cfgVal('cfg_ch_' + i) || ('Channel ' + i);
      cfg.channel_names = chNames;
      cfg.enable_twilio = cfgVal('cfg_enable_twilio');
      cfg.twilio_sid = cfgVal('cfg_twilio_sid');
      cfg.twilio_auth_token = cfgVal('cfg_twilio_auth_token');
      cfg.twilio_from_number = cfgVal('cfg_twilio_from_number');
      cfg.alert_phone_number = cfgVal('cfg_alert_phone_number');
      cfg.twilio_inbound_target = cfgVal('cfg_twilio_inbound_target');
      cfg.twilio_inbound_channel_index = cfgVal('cfg_twilio_inbound_channel_index');
      cfg.twilio_inbound_node = cfgVal('cfg_twilio_inbound_node');
      cfg.enable_smtp = cfgVal('cfg_enable_smtp');
      cfg.smtp_host = cfgVal('cfg_smtp_host');
      cfg.smtp_port = cfgVal('cfg_smtp_port');
      cfg.smtp_user = cfgVal('cfg_smtp_user');
      cfg.smtp_pass = cfgVal('cfg_smtp_pass');
      cfg.alert_email_to = cfgVal('cfg_alert_email_to');
      return cfg;
    }
    async function loadConfigFiles(){
      try{
        const r = await fetch('/config_editor/load');
        if(!r.ok){ throw new Error('Load failed'); }
        const data = await r.json();
        populateConfigForm(data.config || {});
        document.getElementById('cfgRawEditor').value = JSON.stringify(data.config || {}, null, 2);
        // Populate commands form + hidden textarea fallback
        const cmdData = data.commands_config || {};
        populateCommandForm(cmdData.commands || []);
        document.getElementById('cmdEditor').value = JSON.stringify(cmdData, null, 2);
        // MOTD: strip surrounding quotes if server sends JSON-encoded string
        let motdVal = data.motd || '';
        if (typeof motdVal === 'string' && motdVal.startsWith('"') && motdVal.endsWith('"')) {
          try { motdVal = JSON.parse(motdVal); } catch(e) {}
        }
        document.getElementById('motdEditor').value = motdVal;
      }catch(e){ alert('Error loading config files: '+e.message); }
    }
    async function saveConfigFiles(){
      try{
        let activeTab = document.getElementById('cfgTab').style.display !== 'none' ? 'form' : (document.getElementById('cfgRawTab').style.display !== 'none' ? 'raw' : 'form');
        let cfgJson;
        if (activeTab === 'raw') {
          let cfgText = document.getElementById('cfgRawEditor').value;
          try{ cfgJson = JSON.parse(cfgText); } catch(e){ return alert('config.json is not valid JSON: '+e.message); }
        } else {
          cfgJson = collectConfigForm();
        }
        // Collect commands from form
        let cmdJson = collectCommandForm();
        let motdText = document.getElementById('motdEditor').value;
        const r = await fetch('/config_editor/save', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ config: cfgJson, commands_config: cmdJson, motd: motdText }) });
        const res = await r.json();
        if(!r.ok){ throw new Error(res.message||'Save failed'); }
        alert('Saved. Some changes require restarting the service to take effect.');
        loadConfigFiles();
      }catch(e){ alert('Error saving: '+e.message); }
    }

    function updateMessagesUI(messages) {
      // Reverse the order to show the newest messages first
      const groups = {};
      messages.slice().reverse().forEach(m => {
        if (!m.direct && m.channel_idx != null) {
          (groups[m.channel_idx] = groups[m.channel_idx] || []).push(m);
        }
      });

      const channelDiv = document.getElementById("channelDiv");
      channelDiv.innerHTML = "";
      // Track collapsed state per channel
      if (!window._channelCollapsed) window._channelCollapsed = {};
      Object.keys(groups).sort().forEach(ch => {
        const name = getChannelName(ch);
        const unreadCount = groups[ch].filter(m => !isChannelMsgRead(m.timestamp, ch)).length;

        // Collapsible channel group container
        const groupDiv = document.createElement("div");
        groupDiv.className = "channel-group";

        // Channel group header (clickable to collapse)
        const headerWrap = document.createElement("div");
        headerWrap.className = "channel-group-header";
        const toggleIcon = document.createElement("span");
        toggleIcon.className = "ch-toggle" + (window._channelCollapsed[ch] ? " collapsed" : "");
        toggleIcon.textContent = "▼";
        headerWrap.appendChild(toggleIcon);
        const header = document.createElement("h3");
        header.innerHTML = `📻 ${ch} – ${name}` + (unreadCount > 0 ? ` <span style="background:var(--theme-color);color:#000;border-radius:10px;padding:1px 7px;font-size:0.8em;margin-left:6px;">${unreadCount}</span>` : '');
        headerWrap.appendChild(header);

        // Add reply button for channel
        const replyBtn = document.createElement("button");
        replyBtn.textContent = "Send";
        replyBtn.className = "reply-btn";
        replyBtn.onclick = function(e) { e.stopPropagation(); replyToMessage('broadcast', ch); };
        headerWrap.appendChild(replyBtn);

        // PING button for channel
        const chPingBtn = document.createElement("button");
        chPingBtn.textContent = "📡 PING";
        chPingBtn.className = "reply-btn";
        chPingBtn.title = "Send /PING to this channel";
        chPingBtn.onclick = function(e) { e.stopPropagation(); sendPingToChannel(ch); };
        headerWrap.appendChild(chPingBtn);

        // PONG button for channel
        const chPongBtn = document.createElement("button");
        chPongBtn.textContent = "🏓 PONG";
        chPongBtn.className = "reply-btn";
        chPongBtn.title = "Send /PONG to this channel";
        chPongBtn.onclick = function(e) { e.stopPropagation(); sendPongToChannel(ch); };
        headerWrap.appendChild(chPongBtn);

        // Mark all as read for this channel
        const markAllBtn = document.createElement("button");
        markAllBtn.textContent = "Mark all read";
        markAllBtn.className = "mark-all-read-btn";
        markAllBtn.onclick = function(e) { e.stopPropagation(); markChannelAsRead(ch); };
        headerWrap.appendChild(markAllBtn);

        // Toggle collapse on header click
        headerWrap.onclick = function() {
          window._channelCollapsed[ch] = !window._channelCollapsed[ch];
          bodyDiv.classList.toggle('collapsed');
          toggleIcon.classList.toggle('collapsed');
        };
        groupDiv.appendChild(headerWrap);

        // Channel body (messages)
        const bodyDiv = document.createElement("div");
        bodyDiv.className = "channel-group-body" + (window._channelCollapsed[ch] ? " collapsed" : "");

        groups[ch].forEach(m => {
          if (isChannelMsgRead(m.timestamp, ch)) return;
          const wrap = document.createElement("div");
          wrap.className = "message";
          if (isRecent(m.timestamp, 60)) wrap.classList.add("newMessage");
          const ts = document.createElement("div");
          ts.className = "timestamp";
          ts.textContent = `📢 ${getTZAdjusted(m.timestamp)} | ${m.node}`;
          const body = document.createElement("div");
          body.textContent = m.message;
          wrap.append(ts, body);

          const markBtn = document.createElement("button");
          markBtn.textContent = "Mark as read";
          markBtn.className = "mark-read-btn";
          markBtn.onclick = function() {
            if (!readChannels[ch]) readChannels[ch] = [];
            if (!readChannels[ch].includes(m.timestamp)) {
              readChannels[ch].push(m.timestamp);
              saveReadChannels();
              fetchMessagesAndNodes();
            }
          };
          wrap.appendChild(markBtn);

          const reactBtn = document.createElement('button');
          reactBtn.type = 'button';
          reactBtn.textContent = 'React';
          reactBtn.className = 'react-btn';
          const picker = document.createElement('div');
          picker.className = 'emoji-picker';
          renderEmojiPicker(picker, (emoji) => handleReactSend(reactBtn, picker, () => sendEmojiChannel(ch, emoji)));
          reactBtn.onclick = function() {
            if (reactBtn.disabled) return;
            picker.style.display = (picker.style.display === 'flex') ? 'none' : 'flex';
          };
          wrap.appendChild(reactBtn);
          wrap.appendChild(picker);

          bodyDiv.appendChild(wrap);
        });
        groupDiv.appendChild(bodyDiv);
        channelDiv.appendChild(groupDiv);
      });

      // Update global reply targets
      lastDMTarget = null;
      lastChannelTarget = null;
      for (const m of messages) {
        if (m.direct && m.node_id != null && lastDMTarget === null) {
          lastDMTarget = m.node_id;
        }
        if (!m.direct && m.channel_idx != null && lastChannelTarget === null) {
          lastChannelTarget = m.channel_idx;
        }
        if (lastDMTarget != null && lastChannelTarget != null) break;
      }
    }

    // --- DM Threaded UI ---
    function updateDirectMessagesUI(messages, nodes) {
      // Group DMs by node_id, then by thread (reply_to)
      const dmDiv = document.getElementById("dmMessagesDiv");
      dmDiv.innerHTML = "";

      // Only direct messages, newest first
      let dms = messages.filter(m => m.direct && !isDMRead(m.timestamp)).slice().reverse();

      // Group by node_id
      let threads = {};
      dms.forEach(m => {
        if (!threads[m.node_id]) threads[m.node_id] = [];
        threads[m.node_id].push(m);
      });

      // Mark all as read button for DMs
      if (dms.length > 0) {
        const markAllBtn = document.createElement("button");
        markAllBtn.textContent = "Mark all as read";
        markAllBtn.className = "mark-all-read-btn";
        markAllBtn.onclick = function() {
          markAllDMsAsRead();
        };
        dmDiv.appendChild(markAllBtn);
      }

      Object.keys(threads).forEach(nodeId => {
        const node = allNodes.find(n => n.id == nodeId);
        const shortName = node ? (node.shortName || node.longName || nodeId) : nodeId;
        const threadDiv = document.createElement("div");
        threadDiv.className = "dm-thread";

        // Find root messages (no reply_to)
        let rootMsgs = threads[nodeId].filter(m => !m.reply_to);

        rootMsgs.forEach(rootMsg => {
          const wrap = document.createElement("div");
          wrap.className = "message";
          if (isRecent(rootMsg.timestamp, 60)) wrap.classList.add("newMessage");
          const ts = document.createElement("div");
          ts.className = "timestamp";
          ts.textContent = `📩 ${getTZAdjusted(rootMsg.timestamp)} | ${rootMsg.node}`;
          const body = document.createElement("div");
          body.textContent = rootMsg.message;
          wrap.append(ts, body);

          // Add reply button for root
          const replyBtn = document.createElement("button");
          replyBtn.textContent = "Reply";
          replyBtn.className = "reply-btn";
          replyBtn.onclick = function() {
            dmToNode(nodeId, shortName, rootMsg.timestamp);
          };
          wrap.appendChild(replyBtn);

          // Mark as read button for root
          const markBtn = document.createElement("button");
          markBtn.textContent = "Mark as read";
          markBtn.className = "mark-read-btn";
          markBtn.onclick = function() {
            markDMAsRead(rootMsg.timestamp);
          };
          wrap.appendChild(markBtn);

          // React button and picker for root DM
          const reactBtn = document.createElement('button');
          reactBtn.type = 'button';
          reactBtn.textContent = 'React';
          reactBtn.className = 'react-btn';
          const picker = document.createElement('div');
          picker.className = 'emoji-picker';
          renderEmojiPicker(picker, (emoji) => handleReactSend(reactBtn, picker, () => sendEmojiDirect(nodeId, emoji)));
          reactBtn.onclick = function() {
            if (reactBtn.disabled) return;
            picker.style.display = (picker.style.display === 'flex') ? 'none' : 'flex';
          };
          wrap.appendChild(reactBtn);
          wrap.appendChild(picker);

          threadDiv.appendChild(wrap);

          // Find replies to this root
          let replies = threads[nodeId].filter(m => m.reply_to === rootMsg.timestamp);
          if (replies.length) {
            const repliesDiv = document.createElement("div");
            repliesDiv.className = "thread-replies";
            replies.forEach(replyMsg => {
              const replyWrap = document.createElement("div");
              replyWrap.className = "message";
              if (isRecent(replyMsg.timestamp, 60)) replyWrap.classList.add("newMessage");
              const rts = document.createElement("div");
              rts.className = "timestamp";
              rts.textContent = `↪️ ${getTZAdjusted(replyMsg.timestamp)} | ${replyMsg.node}`;
              const rbody = document.createElement("div");
              rbody.textContent = replyMsg.message;
              replyWrap.append(rts, rbody);

              // Reply to reply (threaded)
              const replyBtn2 = document.createElement("button");
              replyBtn2.textContent = "Reply";
              replyBtn2.className = "reply-btn";
              replyBtn2.onclick = function() {
                dmToNode(nodeId, shortName, replyMsg.timestamp);
              };
              replyWrap.appendChild(replyBtn2);

              // Mark as read button for reply
              const markBtn2 = document.createElement("button");
              markBtn2.textContent = "Mark as read";
              markBtn2.className = "mark-read-btn";
              markBtn2.onclick = function() {
                markDMAsRead(replyMsg.timestamp);
              };
              replyWrap.appendChild(markBtn2);

              // React for reply
              const reactBtn2 = document.createElement('button');
              reactBtn2.type = 'button';
              reactBtn2.textContent = 'React';
              reactBtn2.className = 'react-btn';
              const picker2 = document.createElement('div');
              picker2.className = 'emoji-picker';
              renderEmojiPicker(picker2, (emoji) => handleReactSend(reactBtn2, picker2, () => sendEmojiDirect(nodeId, emoji)));
              reactBtn2.onclick = function() {
                if (reactBtn2.disabled) return;
                picker2.style.display = (picker2.style.display === 'flex') ? 'none' : 'flex';
              };
              replyWrap.appendChild(reactBtn2);
              replyWrap.appendChild(picker2);

              repliesDiv.appendChild(replyWrap);
            });
            threadDiv.appendChild(repliesDiv);
          }
        });

        dmDiv.appendChild(threadDiv);
      });
    }

    function updateNodesUI(nodes, isDest) {
      // isDest: false = available nodes panel, true = destination node dropdown
      if (!isDest) {
        const list = document.getElementById("nodeListDiv");
        let filter = document.getElementById('nodeSearch').value.toLowerCase();
        list.innerHTML = "";
        let filtered = nodes.filter(n =>
          (n.shortName && n.shortName.toLowerCase().includes(filter)) ||
          (n.longName && n.longName.toLowerCase().includes(filter)) ||
          String(n.id).toLowerCase().includes(filter)
        );
        // Sort
        filtered.sort(compareNodes);

        filtered.forEach(n => {
          const d = document.createElement("div");
          d.className = "nodeItem";
          if (isRecentNode(n.id)) d.classList.add("recentNode");

          // Main line: Star (favorite) + custom name or short name + ID
          const mainLine = document.createElement("div");
          mainLine.className = "nodeMainLine";
          const isFav = isFavoriteNode(n.id);
          const customName = getCustomNodeName(n.id);

          const starBtn = document.createElement("span");
          starBtn.textContent = isFav ? '⭐' : '☆';
          starBtn.title = isFav ? 'Remove from favorites' : 'Add to favorites';
          starBtn.style.cssText = 'cursor:pointer;margin-right:4px;font-size:1.1em;';
          starBtn.onclick = (e) => { e.stopPropagation(); toggleFavoriteNode(n.id); };
          mainLine.appendChild(starBtn);

          if (customName) {
            const cName = document.createElement('span');
            cName.textContent = customName;
            cName.style.cssText = 'color:#0ff;font-weight:bold;';
            mainLine.appendChild(cName);
            const origName = document.createElement('span');
            origName.innerHTML = ` <span style="color:#888;font-size:0.85em;">(${n.shortName || ''})</span> <span style="color:#ffa500;">(${n.id})</span>`;
            mainLine.appendChild(origName);
          } else {
            const nameSpan = document.createElement('span');
            nameSpan.innerHTML = `${n.shortName || ''} <span style="color:#ffa500;">(${n.id})</span>`;
            mainLine.appendChild(nameSpan);
          }

          const editNameBtn = document.createElement('span');
          editNameBtn.textContent = '✏️';
          editNameBtn.title = 'Set custom name';
          editNameBtn.style.cssText = 'cursor:pointer;margin-left:6px;font-size:0.85em;opacity:0.6;';
          editNameBtn.onmouseenter = () => editNameBtn.style.opacity = '1';
          editNameBtn.onmouseleave = () => editNameBtn.style.opacity = '0.6';
          editNameBtn.onclick = (e) => { e.stopPropagation(); promptCustomNodeName(n.id, customName); };
          mainLine.appendChild(editNameBtn);

          d.appendChild(mainLine);

          // Long name (if present)
          if (n.longName && n.longName !== n.shortName) {
            const longName = document.createElement("div");
            longName.className = "nodeLongName";
            longName.textContent = n.longName;
            d.appendChild(longName);
          }

          // Info line 1: DM button (always), GPS/map, distance
          const infoLine1 = document.createElement("div");
          infoLine1.className = "nodeInfoLine";
          let gps = nodeGPSInfo[String(n.id)];

          // DM button - always available for all nodes
          const dmBtn = document.createElement("button");
          dmBtn.textContent = "💬 DM";
          dmBtn.className = "reply-btn";
          dmBtn.onclick = () => dmToNode(n.id, n.shortName || n.longName || n.id);
          infoLine1.appendChild(dmBtn);

          // PING button
          const pingBtn = document.createElement("button");
          pingBtn.textContent = "📡 PING";
          pingBtn.className = "reply-btn";
          pingBtn.title = "Send /PING to this node";
          pingBtn.onclick = () => sendPingToNode(n.id, n.shortName || n.longName || n.id);
          infoLine1.appendChild(pingBtn);

          // PONG button
          const pongBtn = document.createElement("button");
          pongBtn.textContent = "🏓 PONG";
          pongBtn.className = "reply-btn";
          pongBtn.title = "Send /PONG to this node";
          pongBtn.onclick = () => sendPongToNode(n.id, n.shortName || n.longName || n.id);
          infoLine1.appendChild(pongBtn);

          if (gps && gps.lat != null && gps.lon != null) {
            // Map buttons container - keep Show on Map and Google Maps on same line
            const mapBtns = document.createElement("span");
            mapBtns.style.cssText = "display:inline-flex;gap:6px;align-items:center;";

            // Show on Map button - fly to node on the Leaflet map
            const showMapBtn = document.createElement("button");
            showMapBtn.textContent = "📍 Show on Map";
            showMapBtn.className = "reply-btn";
            showMapBtn.title = "Highlight this node on the map";
            showMapBtn.onclick = () => flyToNode(n.id);
            mapBtns.appendChild(showMapBtn);

            // Google Maps link
            const mapA = document.createElement("a");
            mapA.href = `https://www.google.com/maps/search/?api=1&query=${gps.lat},${gps.lon}`;
            mapA.target = "_blank";
            mapA.className = "nodeMapBtn";
            mapA.title = "Open in Google Maps";
            mapA.innerHTML = "🗺️ Google Maps";
            mapBtns.appendChild(mapA);

            infoLine1.appendChild(mapBtns);

            // Distance
            let effectiveGPS = getEffectiveMyGPS();
            if (effectiveGPS && effectiveGPS.lat != null && effectiveGPS.lon != null) {
              let dist = calcDistance(effectiveGPS.lat, effectiveGPS.lon, gps.lat, gps.lon);
              if (dist < 99999) {
                const distSpan = document.createElement("span");
                distSpan.className = "nodeGPS";
                distSpan.title = "Approximate distance";
                distSpan.innerHTML = `📏 ${dist.toFixed(2)} km`;
                infoLine1.appendChild(distSpan);
              }
            }
          }
          d.appendChild(infoLine1);

          // Info line 2: Hops
          const infoLine3 = document.createElement("div");
          infoLine3.className = "nodeInfoLine";
          // Only show hops if available and not null/undefined/""
          if (gps && gps.hops != null && gps.hops !== "" && gps.hops !== undefined) {
            const hops = document.createElement("span");
            hops.className = "nodeHops";
            hops.title = "Hops from this node";
            hops.innerHTML = `⛓️ ${gps.hops} hop${gps.hops==1?"":"s"}`;
            infoLine3.appendChild(hops);
            d.appendChild(infoLine3);
          }
          // If hops is not available, do not show this section at all

          // Info line 3 (last): Beacon/reporting time and last heard
          const infoLine2 = document.createElement("div");
          infoLine2.className = "nodeInfoLine";
          if (gps && gps.lastHeard) {
            const lastHeard = document.createElement("span");
            lastHeard.className = "nodeBeacon";
            lastHeard.title = "Last heard from this node";
            lastHeard.innerHTML = `📡 Last heard: ${getTZAdjusted(gps.lastHeard)}`;
            infoLine2.appendChild(lastHeard);
          }
          if (gps && gps.beacon_time) {
            const beacon = document.createElement("span");
            beacon.className = "nodeBeacon";
            beacon.title = "Last beacon/reporting time";
            beacon.innerHTML = `🕒 Beacon: ${getTZAdjusted(gps.beacon_time)}`;
            infoLine2.appendChild(beacon);
          }
          d.appendChild(infoLine2);

          list.appendChild(d);
        });
      } else {
        const sel  = document.getElementById("destNode");
        const prevNode = sel.value;
        sel.innerHTML  = "<option value=''>--Select Node--</option>";
        let filter = document.getElementById('destNodeSearch').value.toLowerCase();
        let filtered = nodes.filter(n =>
          (n.shortName && n.shortName.toLowerCase().includes(filter)) ||
          (n.longName && n.longName.toLowerCase().includes(filter)) ||
          String(n.id).toLowerCase().includes(filter)
        );
        filtered.forEach(n => {
          const opt = document.createElement("option");
          opt.value = n.id;
          opt.innerHTML = `${n.shortName} (${n.id})`;
          sel.append(opt);
        });
        sel.value = prevNode;
      }
    }

    function filterNodes(val, isDest) {
      updateNodesUI(allNodes, isDest);
    }

    // --- Node Map (Leaflet) ---
    let nodeMapInstance = null;
    let nodeMapMarkers = [];
    let mapUserInteracted = false;
    let mapLastNodeCount = 0;
    function toggleNodeMap(btn) {
      const panel = document.getElementById('nodeMapPanel');
      const isCollapsed = panel.classList.toggle('collapsed');
      btn.textContent = isCollapsed ? 'Show Map' : 'Hide Map';
      if (!isCollapsed) {
        setTimeout(function() {
          if (!nodeMapInstance) {
            nodeMapInstance = L.map('nodeMap').setView([0, 0], 2);
            nodeMapInstance.on('zoomstart dragstart', function() { mapUserInteracted = true; });
            applyMapTileLayer();
          }
          nodeMapInstance.invalidateSize();
          updateNodeMap();
        }, 100);
      }
    }
    // Map DM mini-box state
    let mapDmTargetId = null;
    let mapDmTargetName = '';
    function openMapDm(nodeId, shortName) {
      mapDmTargetId = nodeId;
      mapDmTargetName = shortName;
      document.getElementById('mapDmTo').textContent = '💬 DM to ' + shortName;
      document.getElementById('mapDmMsg').value = '@' + shortName + ': ';
      document.getElementById('mapDmBox').style.display = 'block';
      document.getElementById('mapDmMsg').focus();
    }
    function closeMapDm() {
      document.getElementById('mapDmBox').style.display = 'none';
      mapDmTargetId = null;
    }
    function sendMapDm() {
      let msg = document.getElementById('mapDmMsg').value.trim();
      if (!msg || !mapDmTargetId) return;
      fetch('/ui_send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'message=' + encodeURIComponent(msg) + '&destination_node=' + encodeURIComponent(mapDmTargetId)
      }).then(r => { if (r.ok) { closeMapDm(); } else { alert('Send failed'); } }).catch(e => alert('Error: ' + e));
    }

    function sendPingToNode(nodeId, shortName) {
      if (!nodeId) return;
      fetch('/ui_send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'message=' + encodeURIComponent('/PING') + '&destination_node=' + encodeURIComponent(nodeId)
      }).then(r => {
        if (r.ok) { alert('PING sent to ' + (shortName || nodeId)); }
        else { alert('PING failed'); }
      }).catch(e => alert('Error: ' + e));
    }

    function sendPongToNode(nodeId, shortName) {
      if (!nodeId) return;
      fetch('/ui_send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'message=' + encodeURIComponent('/PONG') + '&destination_node=' + encodeURIComponent(nodeId)
      }).then(r => {
        if (r.ok) { alert('PONG sent to ' + (shortName || nodeId)); }
        else { alert('PONG failed'); }
      }).catch(e => alert('Error: ' + e));
    }

    // Wrapper functions for mapDmBox inline handlers
    function sendMapPing() { sendPingToNode(mapDmTargetId, mapDmTargetName); }
    function sendMapPong() { sendPongToNode(mapDmTargetId, mapDmTargetName); }

    function sendPingToChannel(channelIdx) {
      fetch('/ui_send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'message=' + encodeURIComponent('/PING') + '&channel_index=' + encodeURIComponent(channelIdx)
      }).then(r => {
        if (r.ok) { alert('PING sent to channel ' + channelIdx); }
        else { alert('PING failed'); }
      }).catch(e => alert('Error: ' + e));
    }

    function sendPongToChannel(channelIdx) {
      fetch('/ui_send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'message=' + encodeURIComponent('/PONG') + '&channel_index=' + encodeURIComponent(channelIdx)
      }).then(r => {
        if (r.ok) { alert('PONG sent to channel ' + channelIdx); }
        else { alert('PONG failed'); }
      }).catch(e => alert('Error: ' + e));
    }

    // Node-to-marker lookup for fly-to from Available Nodes list
    let nodeMarkerLookup = {};

    function flyToNode(nodeId) {
      let marker = nodeMarkerLookup[String(nodeId)];
      if (!marker || !nodeMapInstance) return;
      // Ensure map panel is visible (uncollapse if needed)
      let panel = document.getElementById('nodeMapPanel');
      if (panel && panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        setTimeout(function() {
          if (nodeMapInstance) nodeMapInstance.invalidateSize();
          updateNodeMap();
        }, 100);
      }
      // Scroll map into view
      panel.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setTimeout(function() {
        nodeMapInstance.invalidateSize();
        nodeMapInstance.flyTo(marker.getLatLng(), 15, { duration: 1 });
        setTimeout(function() { marker.openPopup(); }, 600);
      }, 300);
    }

    function updateNodeMap() {
      if (!nodeMapInstance) return;
      // Clear existing markers
      nodeMapMarkers.forEach(m => nodeMapInstance.removeLayer(m));
      nodeMapMarkers = [];
      nodeMarkerLookup = {};
      let bounds = [];
      // Add markers for all nodes with GPS
      for (let nid in nodeGPSInfo) {
        let gps = nodeGPSInfo[nid];
        if (gps && gps.lat != null && gps.lon != null) {
          let node = allNodes.find(n => String(n.id) === nid);
          let name = node ? (node.shortName || nid) : nid;
          let longName = node && node.longName ? node.longName : '';
          let cName = getCustomNodeName(nid);
          let favStar = isFavoriteNode(nid) ? '⭐ ' : '';
          // Build popup with DM + Google Maps buttons
          let displayName = cName ? `${cName} <span style="color:#888;font-size:0.85em;">(${name})</span>` : name;
          let popup = `<b>${favStar}${displayName}</b>`;
          if (longName) popup += `<br>${longName}`;
          popup += `<br>ID: ${nid}`;
          popup += `<br>📍 ${gps.lat.toFixed(5)}, ${gps.lon.toFixed(5)}`;
          if (gps.lastHeard) popup += `<br>Last heard: ${gps.lastHeard}`;
          if (gps.hops != null) popup += `<br>Hops: ${gps.hops}`;
          popup += `<br><div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;align-items:center;">`;
          popup += `<button onclick="openMapDm('${nid}','${name.replace(/'/g,"\\\'")}')" style="background:var(--theme-color);color:#000;border:none;padding:4px 8px;border-radius:5px;cursor:pointer;font-weight:bold;font-size:0.85em;">💬 DM</button>`;
          popup += `<button onclick="sendPingToNode('${nid}','${name.replace(/'/g,"\\\'")}')" style="background:#2196f3;color:#fff;border:none;padding:4px 8px;border-radius:5px;cursor:pointer;font-weight:bold;font-size:0.85em;">📡 PING</button>`;
          popup += `<button onclick="sendPongToNode('${nid}','${name.replace(/'/g,"\\\'")}')" style="background:#9c27b0;color:#fff;border:none;padding:4px 8px;border-radius:5px;cursor:pointer;font-weight:bold;font-size:0.85em;">🏓 PONG</button>`;
          popup += `<a href='https://www.google.com/maps/search/?api=1&query=${gps.lat},${gps.lon}' target='_blank' style='background:#34a853;color:#fff;border:none;padding:4px 8px;border-radius:5px;text-decoration:none;font-weight:bold;font-size:0.85em;'>🗺️ Maps</a>`;
          popup += `</div>`;
          // Create marker with permanent shortname tooltip
          let marker = L.marker([gps.lat, gps.lon]).bindPopup(popup, {maxWidth: 400});
          marker.bindTooltip(cName || name, { permanent: true, direction: 'right', offset: [12, 0], className: 'leaflet-marker-label' });
          marker.addTo(nodeMapInstance);
          nodeMapMarkers.push(marker);
          nodeMarkerLookup[nid] = marker;
          bounds.push([gps.lat, gps.lon]);
        }
      }
      // Add connected node marker
      let effGPS = getEffectiveMyGPS();
      if (effGPS && effGPS.lat != null && effGPS.lon != null) {
        let myMarker = L.circleMarker([effGPS.lat, effGPS.lon], {
          radius: 8, color: '#00ff00', fillColor: '#00ff00', fillOpacity: 0.8
        }).bindPopup('<b>Connected Node (You)</b><br>📍 ' + effGPS.lat.toFixed(5) + ', ' + effGPS.lon.toFixed(5));
        myMarker.bindTooltip('You', { permanent: true, direction: 'right', offset: [12, 0], className: 'leaflet-marker-label' });
        myMarker.addTo(nodeMapInstance);
        nodeMapMarkers.push(myMarker);
        bounds.push([effGPS.lat, effGPS.lon]);
      }
      if (bounds.length > 0 && (!mapUserInteracted || bounds.length !== mapLastNodeCount)) {
        nodeMapInstance.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
        mapLastNodeCount = bounds.length;
      }
    }

    // Track recently discovered nodes (seen in last hour)
    function isRecentNode(nodeId) {
      // Find the latest message from this node
      let found = allMessages.slice().reverse().find(m => m.node_id == nodeId);
      if (!found) return false;
      return isRecent(found.timestamp, 60);
    }

    function highlightRecentNodes(nodes) {
      // Called after updateNodesUI
      // No-op: handled by .recentNode class in updateNodesUI
    }

    // Show latest inbound message in ticker, dismissable, timeout after 30s, and persist dismiss across refreshes
    function showLatestMessageTicker(messages) {
      // Show both channel and direct inbound messages, but not outgoing (WebUI, Discord, Twilio, DiscordPoll, AI_NODE_NAME)
      // and not AI responses (reply_to is not null)
      let inbound = messages.filter(m =>
        m.node !== "WebUI" &&
        m.node !== "Discord" &&
        m.node !== "Twilio" &&
        m.node !== "DiscordPoll" &&
        m.node !== """ + json.dumps(AI_NODE_NAME) + """ &&
        (!m.reply_to) && // Only show original messages, not replies (AI responses)
        (
          // For DMs: not marked as read
          (m.direct && !isDMRead(m.timestamp)) ||
          // For channel messages: not marked as read
          (!m.direct && m.channel_idx != null && !isChannelMsgRead(m.timestamp, m.channel_idx))
        )
      );
      if (!inbound.length) return hideTicker();
      let latest = inbound[inbound.length - 1];
      if (!latest || !latest.message) return hideTicker();

      // If dismissed, don't show
      if (isTickerDismissed(latest.timestamp)) return hideTicker();

      // Only show ticker if not already shown for this message
      if (tickerLastShownTimestamp === latest.timestamp) return;
      tickerLastShownTimestamp = latest.timestamp;

  let ticker = document.getElementById('ticker');
  let tContainer = document.getElementById('ticker-container');
      let tickerMsg = ticker.querySelector('p');
      tickerMsg.textContent = latest.message;
  if (tContainer) tContainer.style.display = 'flex';
  ticker.style.display = 'block';

      // Show dismiss button at far right, on top
      let dismissBtn = ticker.querySelector('.dismiss-btn');
      if (!dismissBtn) {
        dismissBtn = document.createElement('button');
        dismissBtn.textContent = "Dismiss";
        dismissBtn.className = "dismiss-btn";
        dismissBtn.onclick = function(e) {
          e.stopPropagation();
          ticker.style.display = 'none';
          if (tContainer) tContainer.style.display = 'none';
          setTickerDismissed(latest.timestamp);
          if (tickerTimeout) clearTimeout(tickerTimeout);
        };
        ticker.appendChild(dismissBtn);
      } else {
        // Always update dismiss button to dismiss this message
        dismissBtn.onclick = function(e) {
          e.stopPropagation();
          ticker.style.display = 'none';
          if (tContainer) tContainer.style.display = 'none';
          setTickerDismissed(latest.timestamp);
          if (tickerTimeout) clearTimeout(tickerTimeout);
        };
      }

      // Remove after 30s and persist dismiss (persist across refresh)
      if (tickerTimeout) clearTimeout(tickerTimeout);
      tickerTimeout = setTimeout(() => {
        ticker.style.display = 'none';
        if (tContainer) tContainer.style.display = 'none';
        setTickerDismissed(latest.timestamp);
        tickerLastShownTimestamp = null;
      }, 30000);
    }

    function hideTicker() {
      let ticker = document.getElementById('ticker');
      let tContainer = document.getElementById('ticker-container');
      ticker.style.display = 'none';
      if (tContainer) tContainer.style.display = 'none';
      tickerLastShownTimestamp = null;
      if (tickerTimeout) {
        clearTimeout(tickerTimeout);
        tickerTimeout = null;
      }
    }

    function pollStatus() {
      fetch("/connection_status")
        .then(r => r.json())
        .then(d => {
          const s = document.getElementById("connectionStatus");
          if (d.status !== "Connected") {
            s.style.display = "block";
            s.style.background = "red";
            s.style.minHeight = "28px";
            s.textContent = `Connection Error: ${d.error || 'Disconnected'}`;
          } else {
            s.style.display = "block";
            s.style.background = "green";
            s.style.minHeight = "20px";
            s.textContent = "Connected";
          }
        })
        .catch(e => console.error(e));
    }
    setInterval(pollStatus, 5000);

    function onPageLoad() {
      setInterval(fetchMessagesAndNodes, 10000);
      fetchMessagesAndNodes();
      toggleMode(); // Set initial mode
      // Populate quick emoji bar
      const bar = document.getElementById('quickEmojiBar');
      if (bar) {
        bar.innerHTML = '';
        COMMON_EMOJIS.forEach(e => {
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'emoji-btn';
          b.textContent = e;
          b.title = 'Insert emoji ' + e;
          b.setAttribute('aria-label', 'Insert emoji ' + e);
          b.onclick = () => quickSendEmojiFromForm(e);
          bar.appendChild(b);
        });
      }
      // Populate map DM emoji bar
      const mapBar = document.getElementById('mapDmEmojiBar');
      if (mapBar) {
        mapBar.innerHTML = '';
        COMMON_EMOJIS.forEach(e => {
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'emoji-btn';
          b.textContent = e;
          b.title = 'Insert emoji ' + e;
          b.style.fontSize = '0.85em';
          b.style.padding = '2px 4px';
          b.onclick = () => {
            const ta = document.getElementById('mapDmMsg');
            if (!ta) return;
            const start = ta.selectionStart ?? ta.value.length;
            const end = ta.selectionEnd ?? ta.value.length;
            ta.value = ta.value.slice(0, start) + e + ' ' + ta.value.slice(end);
            ta.selectionStart = ta.selectionEnd = start + e.length + 1;
            ta.focus();
          };
          mapBar.appendChild(b);
        });
      }
      initCharChunkCounter();
    }
  window.addEventListener("load", () => { onPageLoad(); pollStatus(); });

    // --- Discord Messages Section ---
    function updateDiscordMessagesUI(messages) {
      // Only show Discord messages if any exist
      let discordMsgs = messages.filter(m => m.node === "Discord" || m.node === "DiscordPoll");
      let discordSection = document.getElementById("discordSection");
      let discordDiv = document.getElementById("discordMessagesDiv");
      if (discordMsgs.length === 0) {
        discordSection.style.display = "none";
        discordDiv.innerHTML = "";
        return;
      }
      discordSection.style.display = "block";
      discordDiv.innerHTML = "";
      discordMsgs.forEach(m => {
        const wrap = document.createElement("div");
        wrap.className = "message";
        if (isRecent(m.timestamp, 60)) wrap.classList.add("newMessage");
        const ts = document.createElement("div");
        ts.className = "timestamp";
        ts.textContent = `💬 ${getTZAdjusted(m.timestamp)} | ${m.node}`;
        const body = document.createElement("div");
        body.textContent = m.message;
        wrap.append(ts, body);
        discordDiv.appendChild(wrap);
      });
    }
  </script>
  <script>
    // Char/Chunk counter for Send a Message
    const MAX_CHUNK_SIZE_JS = """ + str(MAX_CHUNK_SIZE) + """;
    const MAX_CHUNKS_JS = """ + str(MAX_CHUNKS) + """;
    function updateCharCounter() {
      const ta = document.getElementById('messageBox');
      if (!ta) return;
      const text = ta.value || '';
      const chars = text.length;
      const chunks = Math.min(MAX_CHUNKS_JS, Math.ceil(chars / MAX_CHUNK_SIZE_JS) || 0);
      const maxChars = MAX_CHUNK_SIZE_JS * MAX_CHUNKS_JS;
      const cc = document.getElementById('charCounter');
      if (cc) {
        cc.textContent = `Characters: ${chars}/${maxChars}, Chunks: ${chunks}/${MAX_CHUNKS_JS}`;
      }
    }
    function initCharChunkCounter() {
      const ta = document.getElementById('messageBox');
      if (!ta) return;
      if (!ta.dataset.counterBound) {
        ['input','change','keyup','paste'].forEach(evt => ta.addEventListener(evt, updateCharCounter));
        ta.dataset.counterBound = 'true';
      }
      updateCharCounter();
    }

    // Config backup and restart helpers
    function downloadConfigBackup() {
      // Navigate to endpoint to trigger browser download
      window.open('/config_editor/backup', '_blank');
    }
    async function restartMeshAI() {
      if (!confirm('Restart MESH-API now?')) return;
      // Ask for type of restart
      const hard = confirm('Click OK for a full (hard) restart or Cancel for a quick (soft) restart.');
      try {
        const r = await fetch('/restart', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mode: hard ? 'hard' : 'soft' }) });
        const j = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(j.message || 'Failed');
        alert('Restart requested (' + (hard ? 'hard' : 'soft') + '). The connection may drop briefly.');
      } catch (e) {
        alert('Restart failed: ' + e.message);
      }
    }
  </script>
</head>
<body>

<div id="disclaimerOverlay">
  <div class="disclaimer-box" style="max-width:640px;">
    <!-- Step 1: Welcome -->
    <div id="wizStep1" class="wiz-step">
      <h2>🚀 Welcome to MESH-API</h2>
      <div class="disclaimer-text">
        <p>Thank you for using <strong>MESH-API</strong> — a powerful API and WebUI for <a href="https://meshtastic.org/" target="_blank" style="color:var(--theme-color);">Meshtastic</a> and <a href="https://meshcore.net/" target="_blank" style="color:var(--theme-color);">MeshCore</a> mesh networking devices.</p>
        <p style="color:#888;font-size:0.85em;">This is beta software under active development. It is <strong>NOT ASSOCIATED</strong> with the official Meshtastic or MeshCore projects. Use at your own risk.</p>
        <p>Let's get your node configured in a few quick steps.</p>
      </div>
      <div class="disclaimer-btns">
        <button class="btn-accept" onclick="wizNext(2)">Get Started →</button>
        <button class="btn-accept" style="background:#555;" onclick="acceptDisclaimer()">Skip Setup</button>
      </div>
    </div>
    <!-- Step 2: Connection -->
    <div id="wizStep2" class="wiz-step" style="display:none;">
      <h2>🔌 Step 1: Connection</h2>
      <div class="disclaimer-text" style="text-align:left;">
        <p>How is your Meshtastic device connected?</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0;">
          <div><label style="color:#ccc;font-size:0.9em;">Serial Port</label><input type="text" id="wiz_serial_port" value="/dev/ttyUSB0" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
          <div><label style="color:#ccc;font-size:0.9em;">Serial Baud</label><input type="number" id="wiz_serial_baud" value="460800" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
        </div>
        <div style="margin:8px 0;color:#aaa;font-size:0.85em;">— or use Wi-Fi / Bluetooth —</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div style="display:flex;align-items:center;gap:6px;"><input type="checkbox" id="wiz_use_wifi" style="accent-color:var(--theme-color);width:18px;height:18px;"><label for="wiz_use_wifi" style="color:#ccc;font-size:0.9em;">Use Wi-Fi</label></div>
          <div></div>
          <div><label style="color:#ccc;font-size:0.9em;">Wi-Fi Host</label><input type="text" id="wiz_wifi_host" placeholder="192.168.x.x" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
          <div><label style="color:#ccc;font-size:0.9em;">Wi-Fi Port</label><input type="number" id="wiz_wifi_port" value="4403" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
          <div style="display:flex;align-items:center;gap:6px;grid-column:1/-1;"><input type="checkbox" id="wiz_use_bluetooth" style="accent-color:var(--theme-color);width:18px;height:18px;"><label for="wiz_use_bluetooth" style="color:#ccc;font-size:0.9em;">Use Bluetooth</label></div>
          <div style="grid-column:1/-1;"><label style="color:#ccc;font-size:0.9em;">BLE Address</label><input type="text" id="wiz_ble_address" placeholder="" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
        </div>
      </div>
      <div class="disclaimer-btns"><button class="btn-accept" style="background:#555;" onclick="wizNext(1)">← Back</button><button class="btn-accept" onclick="wizNext(3)">Next →</button></div>
    </div>
    <!-- Step 3: AI Provider -->
    <div id="wizStep3" class="wiz-step" style="display:none;">
      <h2>🤖 Step 2: AI Provider</h2>
      <div class="disclaimer-text" style="text-align:left;">
        <p>Select your AI backend (you can change this later in Settings).</p>
        <div style="margin:10px 0;"><label style="color:#ccc;font-size:0.9em;">Provider</label>
          <select id="wiz_ai_provider" onchange="wizShowProvider()" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;">
            <option value="">None / Skip</option>
            <option value="lmstudio">LM Studio</option><option value="openai">OpenAI</option><option value="ollama">Ollama</option>
            <option value="claude">Claude</option><option value="gemini">Gemini</option><option value="grok">Grok</option>
            <option value="openrouter">OpenRouter</option><option value="groq">Groq</option><option value="deepseek">DeepSeek</option>
            <option value="mistral">Mistral</option><option value="openai_compatible">OpenAI Compatible</option>
          </select>
        </div>
        <div id="wizProviderFields" style="display:grid;grid-template-columns:1fr;gap:8px;margin-top:10px;"></div>
      </div>
      <div class="disclaimer-btns"><button class="btn-accept" style="background:#555;" onclick="wizNext(2)">← Back</button><button class="btn-accept" onclick="wizNext(4)">Next →</button></div>
    </div>
    <!-- Step 4: Node Identity -->
    <div id="wizStep4" class="wiz-step" style="display:none;">
      <h2>📻 Step 3: Node Identity</h2>
      <div class="disclaimer-text" style="text-align:left;">
        <p>Give your node a name and location.</p>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0;">
          <div><label style="color:#ccc;font-size:0.9em;">Node Name</label><input type="text" id="wiz_node_name" placeholder="Mesh-API-Alpha" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
          <div><label style="color:#ccc;font-size:0.9em;">Location</label><input type="text" id="wiz_location" placeholder="@ My Location" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
        </div>
        <div style="margin:10px 0;"><label style="color:#ccc;font-size:0.9em;">Channel 0 Name</label><input type="text" id="wiz_ch0" value="LongFast" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;"></div>
      </div>
      <div class="disclaimer-btns"><button class="btn-accept" style="background:#555;" onclick="wizNext(3)">← Back</button><button class="btn-accept" onclick="wizFinish()">Finish Setup ✓</button></div>
    </div>
  </div>
</div>
<div id="disclaimerDeclined" style="display:none;"></div>
<script>
  const wizProviderMeta = {
    lmstudio: [{id:'wiz_lmstudio_url',label:'URL',ph:'http://localhost:1234/v1/chat/completions'},{id:'wiz_lmstudio_model',label:'Model',ph:'model-identifier'}],
    openai: [{id:'wiz_openai_api_key',label:'API Key',ph:'sk-...',pw:true},{id:'wiz_openai_model',label:'Model',ph:'gpt-4.1-mini'}],
    ollama: [{id:'wiz_ollama_url',label:'URL',ph:'http://localhost:11434/api/generate'},{id:'wiz_ollama_model',label:'Model',ph:'llama3'}],
    claude: [{id:'wiz_claude_api_key',label:'API Key',ph:'sk-ant-...',pw:true},{id:'wiz_claude_model',label:'Model',ph:'claude-sonnet-4-20250514'}],
    gemini: [{id:'wiz_gemini_api_key',label:'API Key',ph:'',pw:true},{id:'wiz_gemini_model',label:'Model',ph:'gemini-2.0-flash'}],
    grok: [{id:'wiz_grok_api_key',label:'API Key',ph:'',pw:true},{id:'wiz_grok_model',label:'Model',ph:'grok-3'}],
    openrouter: [{id:'wiz_openrouter_api_key',label:'API Key',ph:'',pw:true},{id:'wiz_openrouter_model',label:'Model',ph:'openai/gpt-4.1-mini'}],
    groq: [{id:'wiz_groq_api_key',label:'API Key',ph:'',pw:true},{id:'wiz_groq_model',label:'Model',ph:'llama-3.3-70b-versatile'}],
    deepseek: [{id:'wiz_deepseek_api_key',label:'API Key',ph:'',pw:true},{id:'wiz_deepseek_model',label:'Model',ph:'deepseek-chat'}],
    mistral: [{id:'wiz_mistral_api_key',label:'API Key',ph:'',pw:true},{id:'wiz_mistral_model',label:'Model',ph:'mistral-small-latest'}],
    openai_compatible: [{id:'wiz_oc_url',label:'URL',ph:''},{id:'wiz_oc_key',label:'API Key',ph:'',pw:true},{id:'wiz_oc_model',label:'Model',ph:''}],
  };
  function wizShowProvider() {
    const p = document.getElementById('wiz_ai_provider').value;
    const c = document.getElementById('wizProviderFields');
    c.innerHTML = '';
    if (!p || !wizProviderMeta[p]) return;
    wizProviderMeta[p].forEach(f => {
      const d = document.createElement('div');
      d.innerHTML = `<label style="color:#ccc;font-size:0.9em;">${f.label}</label><input type="${f.pw?'password':'text'}" id="${f.id}" placeholder="${f.ph}" style="width:100%;background:#222;color:#eee;border:1px solid #555;border-radius:4px;padding:6px;box-sizing:border-box;">`;
      c.appendChild(d);
    });
  }
  function wizNext(step) {
    document.querySelectorAll('.wiz-step').forEach(s => s.style.display = 'none');
    document.getElementById('wizStep' + step).style.display = '';
  }
  async function wizFinish() {
    try {
      const r = await fetch('/config_editor/load');
      if (!r.ok) throw new Error('Load failed');
      const data = await r.json();
      const cfg = data.config || {};
      // Connection
      const gv = (id) => { const el = document.getElementById(id); return el ? el.value : ''; };
      const gb = (id) => { const el = document.getElementById(id); return el ? el.checked : false; };
      cfg.serial_port = gv('wiz_serial_port') || cfg.serial_port;
      cfg.serial_baud = parseInt(gv('wiz_serial_baud')) || cfg.serial_baud;
      cfg.use_wifi = gb('wiz_use_wifi');
      cfg.wifi_host = gv('wiz_wifi_host') || cfg.wifi_host;
      cfg.wifi_port = parseInt(gv('wiz_wifi_port')) || cfg.wifi_port;
      cfg.use_bluetooth = gb('wiz_use_bluetooth');
      cfg.ble_address = gv('wiz_ble_address') || cfg.ble_address;
      // AI Provider
      const prov = gv('wiz_ai_provider');
      if (prov) {
        cfg.ai_provider = prov;
        const meta = wizProviderMeta[prov] || [];
        meta.forEach(f => {
          const v = gv(f.id);
          if (!v) return;
          // Map wizard field ids to config keys
          const keyMap = {
            wiz_lmstudio_url:'lmstudio_url', wiz_lmstudio_model:'lmstudio_chat_model',
            wiz_openai_api_key:'openai_api_key', wiz_openai_model:'openai_model',
            wiz_ollama_url:'ollama_url', wiz_ollama_model:'ollama_model',
            wiz_claude_api_key:'claude_api_key', wiz_claude_model:'claude_model',
            wiz_gemini_api_key:'gemini_api_key', wiz_gemini_model:'gemini_model',
            wiz_grok_api_key:'grok_api_key', wiz_grok_model:'grok_model',
            wiz_openrouter_api_key:'openrouter_api_key', wiz_openrouter_model:'openrouter_model',
            wiz_groq_api_key:'groq_api_key', wiz_groq_model:'groq_model',
            wiz_deepseek_api_key:'deepseek_api_key', wiz_deepseek_model:'deepseek_model',
            wiz_mistral_api_key:'mistral_api_key', wiz_mistral_model:'mistral_model',
            wiz_oc_url:'openai_compatible_url', wiz_oc_key:'openai_compatible_api_key', wiz_oc_model:'openai_compatible_model',
          };
          if (keyMap[f.id]) cfg[keyMap[f.id]] = v;
        });
      }
      // Node identity
      cfg.ai_node_name = gv('wiz_node_name') || cfg.ai_node_name;
      cfg.local_location_string = gv('wiz_location') || cfg.local_location_string;
      if (gv('wiz_ch0')) { cfg.channel_names = cfg.channel_names || {}; cfg.channel_names['0'] = gv('wiz_ch0'); }
      // Save
      const sr = await fetch('/config_editor/save', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ config: cfg, commands_config: data.commands_config, motd: data.motd }) });
      if (!sr.ok) { const j = await sr.json(); throw new Error(j.message || 'Save failed'); }
      acceptDisclaimer();
      alert('Setup complete! You may want to restart the service for connection changes to take effect.');
    } catch(e) { alert('Error saving wizard config: ' + e.message); }
  }
  async function populateWizardFromConfig() {
    try {
      const r = await fetch('/config_editor/load');
      if (!r.ok) return;
      const data = await r.json();
      const cfg = data.config || {};
      const sv = (id, v) => { const el = document.getElementById(id); if (el && v != null && v !== '') el.value = v; };
      const sb = (id, v) => { const el = document.getElementById(id); if (el) el.checked = !!v; };
      // Connection
      sv('wiz_serial_port', cfg.serial_port);
      sv('wiz_serial_baud', cfg.serial_baud);
      sb('wiz_use_wifi', cfg.use_wifi);
      sv('wiz_wifi_host', cfg.wifi_host);
      sv('wiz_wifi_port', cfg.wifi_port);
      sb('wiz_use_bluetooth', cfg.use_bluetooth);
      sv('wiz_ble_address', cfg.ble_address);
      // AI Provider
      if (cfg.ai_provider) {
        sv('wiz_ai_provider', cfg.ai_provider);
        wizShowProvider();
        // Wait for fields to render, then populate
        setTimeout(() => {
          const keyMap = {
            lmstudio_url:'wiz_lmstudio_url', lmstudio_chat_model:'wiz_lmstudio_model',
            openai_api_key:'wiz_openai_api_key', openai_model:'wiz_openai_model',
            ollama_url:'wiz_ollama_url', ollama_model:'wiz_ollama_model',
            claude_api_key:'wiz_claude_api_key', claude_model:'wiz_claude_model',
            gemini_api_key:'wiz_gemini_api_key', gemini_model:'wiz_gemini_model',
            grok_api_key:'wiz_grok_api_key', grok_model:'wiz_grok_model',
            openrouter_api_key:'wiz_openrouter_api_key', openrouter_model:'wiz_openrouter_model',
            groq_api_key:'wiz_groq_api_key', groq_model:'wiz_groq_model',
            deepseek_api_key:'wiz_deepseek_api_key', deepseek_model:'wiz_deepseek_model',
            mistral_api_key:'wiz_mistral_api_key', mistral_model:'wiz_mistral_model',
            openai_compatible_url:'wiz_oc_url', openai_compatible_api_key:'wiz_oc_key', openai_compatible_model:'wiz_oc_model',
          };
          Object.keys(keyMap).forEach(cfgKey => { if (cfg[cfgKey]) sv(keyMap[cfgKey], cfg[cfgKey]); });
        }, 50);
      }
      // Node identity
      sv('wiz_node_name', cfg.ai_node_name);
      sv('wiz_location', cfg.local_location_string);
      if (cfg.channel_names && cfg.channel_names['0']) sv('wiz_ch0', cfg.channel_names['0']);
    } catch(e) { console.log('Could not pre-populate wizard:', e); }
  }
  function openWizard() {
    // Reset to step 1
    document.querySelectorAll('.wiz-step').forEach(s => s.style.display = 'none');
    document.getElementById('wizStep1').style.display = '';
    document.getElementById('disclaimerOverlay').style.display = '';
    populateWizardFromConfig();
  }
  function acceptDisclaimer() {
    localStorage.setItem('meshapi_disclaimer_accepted', 'true');
    localStorage.setItem('meshapi_wizard_completed', 'true');
    document.getElementById('disclaimerOverlay').style.display = 'none';
  }
  (function() {
    // Allow clearing wizard state via URL param: ?resetWizard=1
    if (new URLSearchParams(window.location.search).get('resetWizard') === '1') {
      localStorage.removeItem('meshapi_disclaimer_accepted');
      localStorage.removeItem('meshapi_wizard_completed');
      window.history.replaceState({}, '', window.location.pathname);
    }
    if (localStorage.getItem('meshapi_disclaimer_accepted') === 'true') {
      document.getElementById('disclaimerOverlay').style.display = 'none';
    } else {
      populateWizardFromConfig();
    }
  })();
</script>

  <div id="appRoot">
  <div id="connectionStatus"></div>
  """ + f"""
  
  """ + """
  <div id="ticker-container">
    <div id="ticker"><p></p></div>
  </div>
  <audio id="incomingSound"></audio>

  <div class="masthead">
    <span class="logo-wrap">
      <a href="https://mesh-api.dev" target="_blank" style="display:inline-block;"><img id="mastheadLogo" src="https://mr-tbot.com/wp-content/uploads/2026/02/MESH-API.png" alt="MESH-API Logo" loading="lazy"></a>
      <span class="logo-overlay"></span>
    </span>
    <div class="masthead-actions">
      <span class="suffix-chip" title="Current AI alias and suffix">""" + f"{AI_ALIAS_CANONICAL} (suffix: {AI_SUFFIX})" + """</span>
      <button type="button" onclick="openCommandsModal()">⌘ Commands</button>
      <button type="button" onclick="openExtensionsModal()">🧩 Extensions</button>
      <button type="button" onclick="openConfigModal()">⚙️ Config</button>
      <a href="/logs" target="_blank">📜 Logs</a>
    </div>
  </div>

  <div id="sortableContainer">
  <div data-section="nodeMapPanel">
  <div class="lcars-panel" id="nodeMapPanel">
    <div class="panel-title-row">
      <h2><span class="drag-handle" title="Drag to reorder">&#x2630;</span> 🗺️ Node Map</h2>
      <div><button class="section-hide-btn" onclick="hideSection('nodeMapPanel')" title="Hide this section">✕</button></div>
    </div>
    <div class="panel-body" style="position:relative;">
      <div id="nodeMap"></div>
      <div id="mapDmBox">
        <div class="mapDm-header">
          <h4 id="mapDmTo">💬 DM to ...</h4>
          <button onclick="closeMapDm()">&times;</button>
        </div>
        <textarea id="mapDmMsg" placeholder="Type a message..."></textarea>
        <div id="mapDmEmojiBar" style="margin:4px 0; display:flex; flex-wrap:wrap; gap:4px;"></div>
        <div style="display:flex;gap:6px;align-items:center;margin-top:6px;">
          <button class="mapDm-send" onclick="sendMapDm()" style="margin:0;">Send</button>
          <button onclick="sendMapPing()" style="background:#2196f3;color:#fff;border:none;padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer;font-size:0.85em;">📡 PING</button>
          <button onclick="sendMapPong()" style="background:#9c27b0;color:#fff;border:none;padding:6px 12px;border-radius:6px;font-weight:bold;cursor:pointer;font-size:0.85em;">🏓 PONG</button>
        </div>
      </div>
    </div>
  </div>
  </div>

  <div data-section="sendForm">
  <div class="lcars-panel" id="sendForm">
    <div class="panel-header">
      <h2><span class="drag-handle" title="Drag to reorder">&#x2630;</span> ✉️ Send a Message</h2>
      <button class="section-hide-btn" onclick="hideSection('sendForm')" title="Hide this section">✕</button>
    </div>
    <form method="POST" action="/ui_send">
  <label>Message Mode:</label>
      <label class="switch">
        <input type="checkbox" id="modeSwitch">
        <span class="slider round"></span>
      </label>
      <span id="modeLabel">Broadcast</span><br><br>

      <div id="dmField" style="display:none;">
        <label>Destination Node:</label><br>
        <input type="text" id="destNodeSearch" placeholder="Search destination nodes..."><br>
        <select id="destNode" name="destination_node"></select><br><br>
      </div>

      <div id="channelField" style="display:block;">
        <label>Channel:</label><br>
        <select id="channelSel" name="channel_index">
"""
    for i in range(8):
        name = channel_names.get(str(i), f"Channel {i}")
        html += f"          <option value='{i}'>{i} - {name}</option>\n"
    html += """        </select><br><br>
      </div>

      <label>Message:</label><br>
      <textarea id="messageBox" name="message" rows="3" style="width:80%;"></textarea>
  <div id="quickEmojiBar" style="margin:6px 0; display:flex; flex-wrap:wrap; gap:6px;"></div>
  <div id="charCounter">Characters: 0/""" + str(MAX_RESPONSE_LENGTH) + """, Chunks: 0/""" + str(MAX_CHUNKS) + """</div><br>
  <button type="submit" class="reply-btn btn-send">Send</button>
  <button type="button" class="reply-btn btn-reply-dm" onclick="replyToLastDM()">Reply to Last DM</button>
  <button type="button" class="reply-btn btn-reply-channel" onclick="replyToLastChannel()">Reply to Last Channel</button>
    </form>
  </div>
  </div>

  <div data-section="threeCol">
  <div style="margin:20px 20px 0; color:#666; font-size:0.85em; display:flex; align-items:center; gap:6px;"><span class="drag-handle" title="Drag to reorder">&#x2630;</span> 💬 Message Panels <button class="section-hide-btn" onclick="hideSection('threeCol')" title="Hide this section">✕</button></div>
  <div class="three-col" id="threeColContainer">
    <div class="col" data-col="dm">
      <div class="lcars-panel">
        <div class="panel-title-row">
          <h2><span class="drag-handle col-drag" title="Drag to reorder">&#x2630;</span> 📨 Direct Messages</h2>
          <button class="collapse-btn" onclick="togglePanel(this)">Collapse</button>
        </div>
        <div class="panel-body">
          <div id="dmMessagesDiv"></div>
        </div>
      </div>
    </div>
    <div class="col" data-col="channel">
      <div class="lcars-panel">
        <div class="panel-title-row">
          <h2><span class="drag-handle col-drag" title="Drag to reorder">&#x2630;</span> 📡 Channel Messages</h2>
          <button class="collapse-btn" onclick="togglePanel(this)">Collapse</button>
        </div>
        <div class="panel-body">
          <div id="channelDiv"></div>
        </div>
      </div>
    </div>
    <div class="col" data-col="nodes">
      <div class="lcars-panel">
        <div class="panel-title-row">
          <h2><span class="drag-handle col-drag" title="Drag to reorder">&#x2630;</span> 📋 Available Nodes</h2>
          <button class="collapse-btn" onclick="togglePanel(this)">Collapse</button>
        </div>
        <div class="panel-body">
          <input type="text" id="nodeSearch" placeholder="Search nodes by name, id, or long name...">
          <div class="nodeSortBar">
            <label for="nodeSortKey">Sort by:</label>
            <select id="nodeSortKey">
              <option value="name">Name</option>
              <option value="beacon">Last Reporting Time</option>
              <option value="hops">Number of Hops</option>
              <option value="gps">GPS Enabled</option>
              <option value="distance">Distance</option>
            </select>
            <label for="nodeSortDir">Order:</label>
            <select id="nodeSortDir">
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
          <div id="nodeListDiv"></div>
        </div>
      </div>
    </div>
  </div>
  </div>

  <div data-section="discordSection">
  <div class="lcars-panel" id="discordSection" style="margin:20px;">
    <h2><span class="drag-handle" title="Drag to reorder">&#x2630;</span> 🎮 Discord Messages <button class="section-hide-btn" onclick="hideSection('discordSection')" title="Hide this section">✕</button></h2>
    <div id="discordMessagesDiv"></div>
  </div>
  </div>
  </div>
  <div class="footer-center-bar">
    <a class="btnlink" href="https://www.paypal.com/donate/?business=7DQWLBARMM3FE&no_recurring=0&item_name=Support+the+development+and+growth+of+innovative+MR_TBOT+projects.&currency_code=USD" target="_blank" style="background:#0070ba; border-color:#0070ba; color:#fff;">❤️ Support Development</a>
    <a class="btnlink" href="https://github.com/mr-tbot/mesh-api/issues" target="_blank" style="background:#c62828; border-color:#c62828; color:#fff;">🐛 Report a Bug</a>
  </div>
  <div class="footer-right-link">
    <a class="btnlink" href="https://mr-tbot.com" target="_blank">MESH-API v0.6.0\nby: MR-TBOT</a>
  </div>
  <div class="footer-left-link"><a class="btnlink" href="#" id="settingsFloatBtn">Show UI Settings</a></div>
  <div id="commandsModal" class="modal-overlay" onclick="if(event.target===this) closeCommandsModal()">
    <div class="modal-content">
      <div class="modal-header">
        <h3>Available Commands</h3>
        <button class="modal-close" onclick="closeCommandsModal()">Close</button>
      </div>
      <div class="modal-body">
        <table class="commands-table">
          <thead><tr><th>Command</th><th>Description</th></tr></thead>
          <tbody id="commandsTableBody"></tbody>
        </table>
        <div style="margin-top:8px;color:#ccc;">Most built-ins require your unique dashed suffix. Exceptions: /emergency, /911, /ping, /test.</div>
      </div>
    </div>
  </div>
  <div id="configModal" class="modal-overlay" onclick="if(event.target===this) closeConfigModal()">
    <div class="modal-content" style="max-width:800px;">
      <div class="modal-header">
        <h3>Configuration Editor</h3>
        <button class="modal-close" onclick="closeConfigModal()">Close</button>
      </div>
      <div class="modal-body">
        <div style="margin-bottom:8px;">
          <button class="reply-btn" onclick="loadConfigFiles()">Reload from Disk</button>
          <button class="mark-read-btn" onclick="saveConfigFiles()">Save All</button>
          <button class="reply-btn" onclick="downloadConfigBackup()">Download Backup</button>
          <button class="mark-read-btn" onclick="restartMeshAI()" title="Applies settings that require restart">Restart Service</button>
          <button class="reply-btn" onclick="closeConfigModal(); openWizard();" title="Re-run the first start setup wizard">🧙 Run Setup Wizard</button>
        </div>
        <div style="background:#1a1a1a; border:1px solid var(--theme-color); padding:10px; border-radius:8px; margin-bottom:10px; color:#ccc;">
          <strong>Note:</strong> Changes to providers, connectivity (Wi&#x2011;Fi/Serial/Mesh), or Twilio credentials usually require a restart. Use the <em>Restart</em> button above after saving.
          <br><strong>Extensions</strong> (Discord, Telegram, Slack, MQTT, etc.) are now configured via the <em>Extensions</em> button in the top bar.
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px;">
          <button class="reply-btn" onclick="showConfigTab('cfg')">⚙️ config.json</button>
          <button class="reply-btn" onclick="showConfigTab('cfgraw')">📝 Raw JSON</button>
          <button class="reply-btn" onclick="showConfigTab('cmd')">commands_config.json</button>
          <button class="reply-btn" onclick="showConfigTab('motd')">motd.json</button>
        </div>
        <div id="cfgTab" style="display:block; max-height:55vh; overflow-y:auto; padding-right:6px;">
          <style>
            .cfg-section { border:1px solid #333; border-radius:8px; margin-bottom:10px; overflow:hidden; }
            .cfg-section-hdr { background:#1a1a1a; padding:8px 12px; cursor:pointer; display:flex; align-items:center; gap:8px; font-weight:bold; color:var(--theme-color); user-select:none; }
            .cfg-section-hdr:hover { background:#222; }
            .cfg-section-hdr .cfg-arrow { transition:transform 0.2s; }
            .cfg-section-hdr.collapsed .cfg-arrow { transform:rotate(-90deg); }
            .cfg-section-body { padding:10px 12px; display:grid; grid-template-columns:1fr 1fr; gap:8px 16px; }
            .cfg-section-body.hidden { display:none; }
            .cfg-field { display:flex; flex-direction:column; gap:2px; }
            .cfg-field.full { grid-column:1/-1; }
            .cfg-field label { color:#aaa; font-size:0.85em; }
            .cfg-field input[type=text], .cfg-field input[type=number], .cfg-field input[type=password], .cfg-field select, .cfg-field textarea {
              background:#111; color:#eee; border:1px solid #444; border-radius:4px; padding:6px 8px; font-size:0.9em; font-family:inherit;
            }
            .cfg-field input:focus, .cfg-field select:focus, .cfg-field textarea:focus { border-color:var(--theme-color); outline:none; }
            .cfg-field .cfg-check { display:flex; align-items:center; gap:8px; flex-direction:row; }
            .cfg-field .cfg-check input { width:18px; height:18px; accent-color:var(--theme-color); }
            .ai-provider-section { display:none; grid-column:1/-1; }
            .ai-provider-section .cfg-section-body { padding:8px 0 0 0; }
            @media (max-width:600px) { .cfg-section-body { grid-template-columns:1fr; } }
          </style>
          <script>
          function toggleCfgSection(el) {
            el.classList.toggle('collapsed');
            el.nextElementSibling.classList.toggle('hidden');
          }
          </script>

          <!-- Connection -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 🔌 Connection</div>
            <div class="cfg-section-body">
              <div class="cfg-field"><label>Serial Port</label><input type="text" id="cfg_serial_port" placeholder="/dev/ttyUSB0"></div>
              <div class="cfg-field"><label>Serial Baud</label><input type="number" id="cfg_serial_baud" placeholder="460800"></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_use_wifi"><label for="cfg_use_wifi">Use Wi-Fi</label></div></div>
              <div class="cfg-field"><label>Wi-Fi Host</label><input type="text" id="cfg_wifi_host" placeholder="192.168.x.x"></div>
              <div class="cfg-field"><label>Wi-Fi Port</label><input type="number" id="cfg_wifi_port" placeholder="4403"></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_use_bluetooth"><label for="cfg_use_bluetooth">Use Bluetooth</label></div></div>
              <div class="cfg-field"><label>BLE Address</label><input type="text" id="cfg_ble_address" placeholder="BLE address"></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_use_mesh_interface"><label for="cfg_use_mesh_interface">Use Mesh Interface</label></div></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_debug"><label for="cfg_debug">Debug Mode</label></div></div>
            </div>
          </div>

          <!-- AI Provider -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 🤖 AI Provider</div>
            <div class="cfg-section-body">
              <div class="cfg-field full"><label>Provider</label>
                <select id="cfg_ai_provider" onchange="showProviderFields()">
                  <option value="">-- Select --</option>
                  <option value="lmstudio">LM Studio</option>
                  <option value="openai">OpenAI</option>
                  <option value="ollama">Ollama</option>
                  <option value="claude">Claude (Anthropic)</option>
                  <option value="gemini">Gemini (Google)</option>
                  <option value="grok">Grok (xAI)</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="groq">Groq</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="mistral">Mistral</option>
                  <option value="openai_compatible">OpenAI Compatible</option>
                </select>
              </div>
              <!-- LM Studio -->
              <div id="ai_sec_lmstudio" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field full"><label>LM Studio URL</label><input type="text" id="cfg_lmstudio_url" placeholder="http://localhost:1234/v1/chat/completions"></div>
                <div class="cfg-field"><label>Chat Model</label><input type="text" id="cfg_lmstudio_chat_model"></div>
                <div class="cfg-field"><label>Embedding Model</label><input type="text" id="cfg_lmstudio_embedding_model"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_lmstudio_timeout"></div>
              </div></div>
              <!-- OpenAI -->
              <div id="ai_sec_openai" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_openai_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_openai_model" placeholder="gpt-4.1-mini"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_openai_timeout"></div>
              </div></div>
              <!-- Ollama -->
              <div id="ai_sec_ollama" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field full"><label>Ollama URL</label><input type="text" id="cfg_ollama_url" placeholder="http://localhost:11434/api/generate"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_ollama_model" placeholder="llama3"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_ollama_timeout"></div>
                <div class="cfg-field"><label>Keep Alive</label><input type="text" id="cfg_ollama_keep_alive" placeholder="10m"></div>
                <div class="cfg-field"><label>Max Parallel</label><input type="number" id="cfg_ollama_max_parallel"></div>
              </div></div>
              <!-- Claude -->
              <div id="ai_sec_claude" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_claude_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_claude_model" placeholder="claude-sonnet-4-20250514"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_claude_timeout"></div>
              </div></div>
              <!-- Gemini -->
              <div id="ai_sec_gemini" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_gemini_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_gemini_model" placeholder="gemini-2.0-flash"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_gemini_timeout"></div>
              </div></div>
              <!-- Grok -->
              <div id="ai_sec_grok" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_grok_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_grok_model" placeholder="grok-3"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_grok_timeout"></div>
              </div></div>
              <!-- OpenRouter -->
              <div id="ai_sec_openrouter" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_openrouter_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_openrouter_model" placeholder="openai/gpt-4.1-mini"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_openrouter_timeout"></div>
              </div></div>
              <!-- Groq -->
              <div id="ai_sec_groq" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_groq_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_groq_model" placeholder="llama-3.3-70b-versatile"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_groq_timeout"></div>
              </div></div>
              <!-- DeepSeek -->
              <div id="ai_sec_deepseek" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_deepseek_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_deepseek_model" placeholder="deepseek-chat"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_deepseek_timeout"></div>
              </div></div>
              <!-- Mistral -->
              <div id="ai_sec_mistral" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_mistral_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_mistral_model" placeholder="mistral-small-latest"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_mistral_timeout"></div>
              </div></div>
              <!-- OpenAI Compatible -->
              <div id="ai_sec_openai_compatible" class="ai-provider-section"><div class="cfg-section-body">
                <div class="cfg-field full"><label>API URL</label><input type="text" id="cfg_openai_compatible_url"></div>
                <div class="cfg-field"><label>API Key</label><input type="password" id="cfg_openai_compatible_api_key"></div>
                <div class="cfg-field"><label>Model</label><input type="text" id="cfg_openai_compatible_model"></div>
                <div class="cfg-field"><label>Timeout (sec)</label><input type="number" id="cfg_openai_compatible_timeout"></div>
              </div></div>
            </div>
          </div>

          <!-- AI Behavior -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 💬 AI Behavior</div>
            <div class="cfg-section-body">
              <div class="cfg-field full"><label>System Prompt</label><textarea id="cfg_system_prompt" rows="3" style="resize:vertical;"></textarea></div>
              <div class="cfg-field"><label>AI Command Prefix</label><input type="text" id="cfg_ai_command" placeholder="e.g. /ai"></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_reply_in_channels"><label for="cfg_reply_in_channels">Reply in Channels</label></div></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_reply_in_directs"><label for="cfg_reply_in_directs">Reply in Direct Messages</label></div></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_ai_respond_on_longfast"><label for="cfg_ai_respond_on_longfast">AI Respond on LongFast</label></div></div>
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_respond_to_mqtt_messages"><label for="cfg_respond_to_mqtt_messages">Respond to MQTT Messages</label></div></div>
            </div>
          </div>

          <!-- Chunking -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> ✂️ Message Chunking</div>
            <div class="cfg-section-body">
              <div class="cfg-field"><label>Chunk Size (chars)</label><input type="number" id="cfg_chunk_size" placeholder="200"></div>
              <div class="cfg-field"><label>Max AI Chunks</label><input type="number" id="cfg_max_ai_chunks" placeholder="5"></div>
              <div class="cfg-field"><label>Chunk Delay (sec)</label><input type="number" id="cfg_chunk_delay" placeholder="10"></div>
            </div>
          </div>

          <!-- Node Identity -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 📻 Node Identity</div>
            <div class="cfg-section-body">
              <div class="cfg-field"><label>AI Node Name</label><input type="text" id="cfg_ai_node_name" placeholder="Mesh-API-Alpha"></div>
              <div class="cfg-field"><label>Location String</label><input type="text" id="cfg_local_location_string" placeholder="@ YOUR LOCATION"></div>
              <div class="cfg-field"><label>Force Node Num</label><input type="text" id="cfg_force_node_num" placeholder="null = auto"></div>
              <div class="cfg-field"><label>Nodes Online Window (sec)</label><input type="number" id="cfg_nodes_online_window_sec" placeholder="7200"></div>
              <div class="cfg-field"><label>Max Message Log</label><input type="number" id="cfg_max_message_log" placeholder="0 = unlimited"></div>
            </div>
          </div>

          <!-- Channels -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 📡 Channel Names</div>
            <div class="cfg-section-body">
              <div class="cfg-field"><label>Ch 0</label><input type="text" id="cfg_ch_0" placeholder="LongFast"></div>
              <div class="cfg-field"><label>Ch 1</label><input type="text" id="cfg_ch_1" placeholder="Channel 1"></div>
              <div class="cfg-field"><label>Ch 2</label><input type="text" id="cfg_ch_2" placeholder="Channel 2"></div>
              <div class="cfg-field"><label>Ch 3</label><input type="text" id="cfg_ch_3" placeholder="Channel 3"></div>
              <div class="cfg-field"><label>Ch 4</label><input type="text" id="cfg_ch_4" placeholder="Channel 4"></div>
              <div class="cfg-field"><label>Ch 5</label><input type="text" id="cfg_ch_5" placeholder="Channel 5"></div>
              <div class="cfg-field"><label>Ch 6</label><input type="text" id="cfg_ch_6" placeholder="Channel 6"></div>
              <div class="cfg-field"><label>Ch 7</label><input type="text" id="cfg_ch_7" placeholder="Channel 7"></div>
              <div class="cfg-field"><label>Ch 8</label><input type="text" id="cfg_ch_8" placeholder="Channel 8"></div>
              <div class="cfg-field"><label>Ch 9</label><input type="text" id="cfg_ch_9" placeholder="Channel 9"></div>
            </div>
          </div>

          <!-- Twilio Alerts -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 📱 Twilio SMS Alerts</div>
            <div class="cfg-section-body">
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_enable_twilio"><label for="cfg_enable_twilio">Enable Twilio</label></div></div>
              <div class="cfg-field"><label>Twilio SID</label><input type="password" id="cfg_twilio_sid"></div>
              <div class="cfg-field"><label>Auth Token</label><input type="password" id="cfg_twilio_auth_token"></div>
              <div class="cfg-field"><label>From Number</label><input type="text" id="cfg_twilio_from_number" placeholder="+14444444444"></div>
              <div class="cfg-field"><label>Alert Phone Number</label><input type="text" id="cfg_alert_phone_number" placeholder="+15555555555"></div>
              <div class="cfg-field"><label>Inbound Target</label>
                <select id="cfg_twilio_inbound_target">
                  <option value="channel">Channel</option>
                  <option value="node">Node</option>
                </select>
              </div>
              <div class="cfg-field"><label>Inbound Channel Index</label><input type="number" id="cfg_twilio_inbound_channel_index" placeholder="1"></div>
              <div class="cfg-field"><label>Inbound Node</label><input type="text" id="cfg_twilio_inbound_node" placeholder="!FFFFFFFF"></div>
            </div>
          </div>

          <!-- SMTP Alerts -->
          <div class="cfg-section">
            <div class="cfg-section-hdr" onclick="toggleCfgSection(this)"><span class="cfg-arrow">▼</span> 📧 SMTP Email Alerts</div>
            <div class="cfg-section-body">
              <div class="cfg-field"><div class="cfg-check"><input type="checkbox" id="cfg_enable_smtp"><label for="cfg_enable_smtp">Enable SMTP</label></div></div>
              <div class="cfg-field"><label>SMTP Host</label><input type="text" id="cfg_smtp_host"></div>
              <div class="cfg-field"><label>SMTP Port</label><input type="number" id="cfg_smtp_port" placeholder="465"></div>
              <div class="cfg-field"><label>SMTP User</label><input type="text" id="cfg_smtp_user"></div>
              <div class="cfg-field"><label>SMTP Password</label><input type="password" id="cfg_smtp_pass"></div>
              <div class="cfg-field"><label>Alert Email To</label><input type="text" id="cfg_alert_email_to"></div>
            </div>
          </div>
        </div>
        <div id="cfgRawTab" style="display:none;">
          <textarea id="cfgRawEditor" style="width:100%; height:40vh; background:#000; color:#0f0; border:1px solid var(--theme-color); font-family:monospace;"></textarea>
          <div style="margin-top:6px; color:#888; font-size:0.85em;">Edit raw JSON directly. Saving from this tab overwrites the form values.</div>
        </div>
        <div id="cmdTab" style="display:none; max-height:55vh; overflow-y:auto; padding-right:6px;">
          <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center;">
            <button class="reply-btn" onclick="addCommandRow()">+ Add Command</button>
            <span style="color:#888;font-size:0.8em;">Each command needs a <strong>/trigger</strong>, a response type, and a description.</span>
          </div>
          <div id="cmdFormRows"></div>
          <textarea id="cmdEditor" style="display:none;"></textarea>
        </div>
        <div id="motdTab" style="display:none;">
          <label style="color:#ccc;font-weight:bold;display:block;margin-bottom:6px;">Message of the Day</label>
          <p style="color:#888;font-size:0.8em;margin:0 0 8px;">This message is shown to users when they connect. Keep it short and welcoming.</p>
          <textarea id="motdEditor" style="width:100%; height:80px; background:#000; color:#ffa; border:1px solid var(--theme-color); font-family:monospace; border-radius:4px; padding:8px; box-sizing:border-box;" placeholder="Welcome message..."></textarea>
        </div>
        <div style="margin-top:8px; color:#ccc;">
          Tip: Use the form view for easy editing, or Raw JSON for advanced changes.
        </div>
      </div>
    </div>
  </div>
  <div id="extensionsModal" class="modal-overlay" onclick="if(event.target===this) closeExtensionsModal()">
    <div class="modal-content" style="max-width:1100px;">
      <div class="modal-header">
        <h3>Extensions Manager</h3>
        <button class="modal-close" onclick="closeExtensionsModal()">Close</button>
      </div>
      <div class="modal-body">
        <div style="margin-bottom:10px; display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <button class="reply-btn" onclick="loadExtensionsStatus()">Refresh</button>
          <button class="mark-read-btn" onclick="reloadExtensions()">Hot-Reload Extensions</button>
          <span style="color:#888; font-size:0.9em;">Enable/disable changes require a reload or restart.</span>
        </div>
        <div style="margin-bottom:12px; border:1px solid var(--theme-color); border-radius:8px; overflow:hidden;">
          <div style="background:#222; padding:8px 12px; border-bottom:1px solid var(--theme-color); display:flex; gap:20px; font-weight:bold; color:var(--theme-color); font-size:0.9em;">
            <span style="width:14px;"></span>
            <span style="min-width:180px;">Extension</span>
            <span style="min-width:80px;">Status</span>
            <span style="flex:1;">Commands</span>
            <span>Actions</span>
          </div>
          <div id="extensionsListBody" style="max-height:35vh; overflow:auto;"></div>
        </div>
        <div id="extConfigPanel" style="display:none; border:1px solid var(--theme-color); border-radius:8px; padding:12px; background:#0a0a0a;">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
            <h4 id="extConfigTitle" style="margin:0; color:var(--theme-color);">Extension Config</h4>
            <span style="color:#888; font-size:0.85em;" id="extConfigSlug"></span>
          </div>
          <textarea id="extConfigEditor" style="width:100%; height:30vh; background:#000; color:#0f0; border:1px solid var(--theme-color); font-family:monospace; font-size:0.95em;"></textarea>
          <div style="margin-top:8px; display:flex; gap:10px;">
            <button class="mark-read-btn" onclick="saveExtensionConfig()">Save Config</button>
            <button class="reply-btn" onclick="document.getElementById('extConfigPanel').style.display='none'; activeExtConfigSlug=null;">Close Editor</button>
          </div>
          <div style="margin-top:6px; color:#888; font-size:0.85em;">Changes are saved to disk. A reload or restart is needed for most settings to take effect.</div>
        </div>
      </div>
    </div>
  </div>
  <div id="settingsOverlay" class="settings-overlay"></div>
  <div class="settings-panel" id="settingsPanel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
      <h2 style="margin:0;">⚙️ UI Settings</h2>
      <button onclick="document.getElementById('settingsPanel').classList.remove('open');document.getElementById('settingsOverlay').classList.remove('open');document.getElementById('settingsFloatBtn').textContent='Show UI Settings';" style="background:none;border:1px solid #666;color:#fff;font-size:1.2em;cursor:pointer;border-radius:4px;padding:2px 10px;" title="Close">&times;</button>
    </div>
    <div class="settings-two-col">
      <div>
        <h3>🎨 Appearance</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; align-items:center;">
          <label for="uiColorPicker">Button Theme Color</label>
          <input type="color" id="uiColorPicker" value="#ffa500">

          <label for="hueRotateEnabled">Hue Rotation</label>
          <input type="checkbox" id="hueRotateEnabled">

          <label for="hueRotateSpeed">Rotation Speed</label>
          <input type="range" id="hueRotateSpeed" min="5" max="60" step="0.1" value="10" style="width:100%;">

          <label for="mapStyleSelect">Map Style</label>
          <select id="mapStyleSelect" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;">
          </select>
        </div>

        <h3>🗺️ Offline Map Image</h3>
        <div style="display:grid; grid-template-columns:auto 1fr; gap:8px 12px; align-items:center;">
          <label>Image File</label>
          <input type="file" id="offlineMapUpload" accept="image/*" style="font-size:0.85em;">
          <label>North Lat</label>
          <input type="number" id="offlineMapNorth" step="0.001" placeholder="e.g. 40.0" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;">
          <label>South Lat</label>
          <input type="number" id="offlineMapSouth" step="0.001" placeholder="e.g. 39.0" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;">
          <label>West Lon</label>
          <input type="number" id="offlineMapWest" step="0.001" placeholder="e.g. -105.0" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;">
          <label>East Lon</label>
          <input type="number" id="offlineMapEast" step="0.001" placeholder="e.g. -104.0" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;">
          <div style="grid-column:1/-1;display:flex;gap:8px;">
            <button type="button" onclick="uploadOfflineMapImage()" style="background:#2196f3;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-weight:bold;cursor:pointer;">Upload & Save</button>
            <button type="button" onclick="clearOfflineMapImage()" style="background:#611;color:#fff;border:none;padding:6px 14px;border-radius:6px;font-weight:bold;cursor:pointer;">Clear</button>
          </div>
          <p style="grid-column:1/-1;color:#888;font-size:0.75em;margin:0;">Upload a map image and set lat/lon bounds. Select "Offline Image" in Map Style to use it. The image is stored in your browser.</p>
        </div>

        <h3>🎨 Section Colors</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; align-items:center;">
          <label for="colorMapPicker">🗺️ Node Map</label>
          <input type="color" id="colorMapPicker" value="#ffa500">
          <label for="colorSendPicker">✉️ Send Message</label>
          <input type="color" id="colorSendPicker" value="#ffa500">
          <label for="colorDmPicker">📨 Direct Messages</label>
          <input type="color" id="colorDmPicker" value="#ffa500">
          <label for="colorChannelPicker">📡 Channel Messages</label>
          <input type="color" id="colorChannelPicker" value="#ffa500">
          <label for="colorNodesPicker">📋 Available Nodes</label>
          <input type="color" id="colorNodesPicker" value="#ffa500">
          <label for="colorDiscordPicker">🎮 Discord</label>
          <input type="color" id="colorDiscordPicker" value="#ffa500">
        </div>

        <h3>🌐 Timezone</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; align-items:center;">
          <label for="timezoneSelect">Timezone</label>
          <select id="timezoneSelect" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;">
            <option value="-12">UTC-12 (Baker Island)</option>
            <option value="-11">UTC-11 (Samoa)</option>
            <option value="-10">UTC-10 (Hawaii)</option>
            <option value="-9">UTC-9 (Alaska)</option>
            <option value="-8">UTC-8 (Pacific)</option>
            <option value="-7">UTC-7 (Mountain)</option>
            <option value="-6">UTC-6 (Central)</option>
            <option value="-5">UTC-5 (Eastern)</option>
            <option value="-4">UTC-4 (Atlantic)</option>
            <option value="-3">UTC-3 (Buenos Aires)</option>
            <option value="-2">UTC-2 (Mid-Atlantic)</option>
            <option value="-1">UTC-1 (Azores)</option>
            <option value="0">UTC+0 (London / GMT)</option>
            <option value="1">UTC+1 (Berlin / CET)</option>
            <option value="2">UTC+2 (Cairo / EET)</option>
            <option value="3">UTC+3 (Moscow)</option>
            <option value="4">UTC+4 (Dubai)</option>
            <option value="5">UTC+5 (Karachi)</option>
            <option value="6">UTC+6 (Dhaka)</option>
            <option value="7">UTC+7 (Bangkok)</option>
            <option value="8">UTC+8 (Singapore)</option>
            <option value="9">UTC+9 (Tokyo)</option>
            <option value="10">UTC+10 (Sydney)</option>
            <option value="11">UTC+11 (Solomon Is.)</option>
            <option value="12">UTC+12 (Auckland)</option>
            <option value="13">UTC+13 (Tonga)</option>
            <option value="14">UTC+14 (Line Islands)</option>
          </select>
        </div>

        <h3>📦 Section Visibility</h3>
        <p style="color:#888;font-size:0.8em;margin:0 0 6px;">Toggle sections on/off. Hidden sections can be restored here.</p>
        <div id="sectionVisibilityList"></div>

        <h3>📍 My Location (Manual GPS)</h3>
        <p style="color:#888;font-size:0.8em;margin:0 0 6px;">Set your latitude and longitude manually for distance calculations when your node has no GPS.</p>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; align-items:center;">
          <label for="myLatInput">Latitude</label>
          <input type="number" id="myLatInput" step="0.00001" placeholder="e.g. 40.7128" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;box-sizing:border-box;">
          <label for="myLonInput">Longitude</label>
          <input type="number" id="myLonInput" step="0.00001" placeholder="e.g. -74.0060" style="background:#222;color:#fff;border:1px solid #555;border-radius:4px;padding:4px;width:100%;box-sizing:border-box;">
          <div style="grid-column:1/-1;color:#666;font-size:0.75em;">Leave blank to use the connected node's GPS. Manual values override node GPS for distance and map "You" marker.</div>
        </div>

        <h3>📡 Channel Names</h3>
        <p style="color:#888;font-size:0.8em;margin:0 0 6px;">Rename channels in the UI. Names are pulled from your node automatically. Override them here.</p>
        <div id="channelNamesList" style="display:grid; grid-template-columns:auto 1fr; gap:4px 8px; align-items:center;"></div>
      </div>
      <div>
        <h3>🔊 Notification Sounds</h3>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 12px; align-items:center;">
          <label for="soundEnabled">Sound Enabled</label>
          <input type="checkbox" id="soundEnabled" checked>

          <label for="soundVolume">Volume <span id="soundVolumeVal" style="color:#aaa;">70%</span></label>
          <input type="range" id="soundVolume" min="0" max="1" step="0.05" value="0.7" oninput="document.getElementById('soundVolumeVal').textContent=Math.round(this.value*100)+'%'" style="width:100%;">

          <label for="soundTypeSelect">Default Sound</label>
          <div>
            <select id="soundTypeSelect" style="width:100%;"></select>
            <button type="button" class="reply-btn" onclick="testSelectedSound()" style="margin-top:4px; font-size:0.85em;">Test</button>
          </div>

          <label for="soundTypeDmSelect">DM Sound</label>
          <div>
            <select id="soundTypeDmSelect" style="width:100%;"></select>
            <button type="button" class="reply-btn" onclick="testSoundSelect('soundTypeDmSelect')" style="margin-top:4px; font-size:0.85em;">Test</button>
          </div>

          <label for="soundTypeChannelSelect">Channel Sound</label>
          <div>
            <select id="soundTypeChannelSelect" style="width:100%;"></select>
            <button type="button" class="reply-btn" onclick="testSoundSelect('soundTypeChannelSelect')" style="margin-top:4px; font-size:0.85em;">Test</button>
          </div>
        </div>

        <h3>🎵 Custom Sound Library</h3>
        <p style="color:#888;font-size:0.8em;margin:0 0 6px;">Upload audio files to use as custom notification sounds for any section or node.</p>
        <div id="customSoundsLibrary"></div>
        <div style="margin-top:6px;display:flex;gap:6px;align-items:center;">
          <input type="file" id="customSoundUpload" accept="audio/*" style="font-size:0.85em;">
          <button type="button" class="reply-btn" style="font-size:0.85em;" onclick="uploadCustomSound()">+ Add Sound</button>
        </div>

        <h3>📡 Per-Node Sounds</h3>
        <p style="color:#888;font-size:0.8em;margin:0 0 6px;">Assign unique sounds to specific nodes from the list of available nodes.</p>
        <div id="nodeSoundEntries"></div>
        <button type="button" class="reply-btn" style="margin-top:6px;font-size:0.85em;" onclick="addNodeSoundRow(document.getElementById('nodeSoundEntries'),'','two-tone')">+ Add Node Sound</button>
      </div>
    </div>
    <div style="margin-top:16px;padding:12px;border-top:1px solid #444;">
      <h3>ℹ️ About</h3>
      <p style="color:#ccc;font-size:0.85em;margin:4px 0;"><strong>MESH-API v0.6.0</strong></p>
      <p style="color:#aaa;font-size:0.8em;margin:4px 0;">A powerful API and WebUI for <a href="https://meshtastic.org/" target="_blank" style="color:var(--theme-color);">Meshtastic</a> and <a href="https://meshcore.net/" target="_blank" style="color:var(--theme-color);">MeshCore</a> mesh networking devices.</p>
      <p style="color:#aaa;font-size:0.8em;margin:4px 0;">Created by <a href="https://mr-tbot.com" target="_blank" style="color:var(--theme-color);">MR-TBOT</a></p>
      <p style="color:#aaa;font-size:0.8em;margin:4px 0;"><a href="https://mesh-api.dev" target="_blank" style="color:var(--theme-color);">mesh-api.dev</a> &bull; <a href="https://github.com/mr-tbot/mesh-api" target="_blank" style="color:var(--theme-color);">GitHub</a> &bull; <a href="https://github.com/mr-tbot/mesh-api/issues" target="_blank" style="color:var(--theme-color);">Report a Bug</a></p>
    </div>
    <div class="sticky-actions" style="margin-top:12px;">
      <button id="applySettingsBtn" type="button">Apply Settings</button>
    </div>
  </div>
</div>
</body>
</html>
"""
    return html

# -----------------------------
# Commands page route
# -----------------------------
@app.route("/commands", methods=["GET"])
def commands_page():
    cmds = get_available_commands_list()
    items_html = "\n".join(
        f"<tr><td style='padding:6px 10px; border-bottom:1px solid #333;'><code>{cmd}</code></td>"
        f"<td style='padding:6px 10px; border-bottom:1px solid #333;'>{desc}</td></tr>" for cmd, desc in cmds
    )
    html = f"""
<html>
  <head>
    <title>MESH-API Commands</title>
    <style>
      body {{ background:#000; color:#fff; font-family: Arial, sans-serif; padding:20px; }}
      h1 {{ color:#ffa500; }}
      table {{ width:100%; border-collapse: collapse; background:#111; border: 2px solid #ffa500; border-radius: 8px; overflow:hidden; }}
      th {{ text-align:left; padding:10px; background:#222; border-bottom:2px solid #ffa500; }}
      code {{ color:#0ff; }}
      .note {{ color:#ccc; margin-top:10px; }}
      .alias {{ position: fixed; top: 10px; right: 10px; background:#111; border:1px solid #ffa500; color:#ffa500; padding:6px 10px; border-radius:6px; }}
    </style>
  </head>
  <body>
  <div class="alias">Alias: {AI_ALIAS_CANONICAL} (suffix: {AI_SUFFIX})</div>
    <h1>Available Commands</h1>
    <table>
      <thead>
        <tr><th>Command</th><th>Description</th></tr>
      </thead>
      <tbody>
        {items_html}
      </tbody>
    </table>
    <div class="note">Most built-ins require your unique dashed suffix. Exceptions: /emergency, /911, /ping, /test.</div>
  </body>
</html>
"""
    return html
@app.route("/ui_send", methods=["POST"])
def ui_send():
    message = request.form.get("message", "").strip()
    mode = "direct" if request.form.get("destination_node", "") != "" else "broadcast"
    if mode == "direct":
        dest_node = request.form.get("destination_node", "").strip()
    else:
        dest_node = None
    if mode == "broadcast":
        channel_idx = int(request.form.get("channel_index", "0"))
    else:
        channel_idx = None
    if not message:
        return redirect(url_for("dashboard"))
    try:
        if mode == "direct" and dest_node:
            dest_info = f"{get_node_shortname(dest_node)} ({dest_node})"
            log_message("WebUI", f"{message} [to: {dest_info}]", direct=True)
            info_print(f"[UI] Direct message to node {dest_info} => '{message}'")
            send_direct_chunks(interface, message, dest_node)
        else:
            log_message("WebUI", f"{message} [to: Broadcast Channel {channel_idx}]", direct=False, channel_idx=channel_idx)
            info_print(f"[UI] Broadcast on channel {channel_idx} => '{message}'")
            send_broadcast_chunks(interface, message, channel_idx)
    except Exception as e:
        print(f"⚠️ /ui_send error: {e}")
    return redirect(url_for("dashboard"))

@app.route("/send", methods=["POST"])
def send_message():
    dprint("POST /send => manual JSON send")
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "No JSON payload"}), 400
    message = data.get("message")
    node_id = data.get("node_id")
    # Accept both legacy "channel_index" and newer "channel" keys
    if "channel_index" in data:
        channel_idx = data.get("channel_index")
    else:
        channel_idx = data.get("channel")
    if channel_idx is None:
        channel_idx = 0
    direct = data.get("direct", False)
    # Validate inputs: allow either Direct (requires node_id) or Broadcast (requires channel_index)
    if not message:
        return jsonify({"status": "error", "message": "Missing 'message'"}), 400
    try:
        if direct:
            if node_id is None:
                return jsonify({"status": "error", "message": "Missing 'node_id' for direct send"}), 400
            log_message("WebUI", f"{message} [to: {get_node_shortname(node_id)} ({node_id})]", direct=True)
            info_print(f"[Info] Direct send to node {node_id} => '{message}'")
            send_direct_chunks(interface, message, node_id)
            return jsonify({"status": "sent", "to": node_id, "direct": True, "message": message})
        else:
            # channel_idx may come as string; ensure int and default to 0 if invalid
            try:
                channel_idx = int(channel_idx)
            except (TypeError, ValueError):
                channel_idx = 0
            log_message("WebUI", f"{message} [to: Broadcast Channel {channel_idx}]", direct=False, channel_idx=channel_idx)
            info_print(f"[Info] Broadcast on ch={channel_idx} => '{message}'")
            send_broadcast_chunks(interface, message, channel_idx)
            return jsonify({"status": "sent", "to": f"channel {channel_idx}", "message": message})
    except Exception as e:
        print(f"⚠️ Failed to send: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Lightweight JSON endpoint for commands list (used by modal overlay)
@app.route("/commands_info", methods=["GET"])
def commands_info():
  cmds = [{"command": c, "description": d} for c, d in get_available_commands_list()]
  return jsonify(cmds)

@app.route("/shutdown", methods=["POST"])
def shutdown_server():
    """Shut down the MESH-API server (triggered when disclaimer is declined)."""
    add_script_log("Server shutdown requested via disclaimer decline.")
    func = request.environ.get("werkzeug.server.shutdown")
    if func:
        func()
    else:
        import os, signal
        os.kill(os.getpid(), signal.SIGTERM)
    return "Server shutting down...", 200

def connect_interface():
    """Return a Meshtastic interface with the baud rate from config.

    Resolution order:
      1. Wi‑Fi TCP bridge
      2. Bluetooth Low Energy (BLE)
      3. Local MeshInterface()
      4. USB SerialInterface (explicit path or auto‑detect)
    """
    global connection_status, last_error_message
    try:
        # 1️⃣  Wi‑Fi bridge -------------------------------------------------
        if USE_WIFI and WIFI_HOST and TCPInterface is not None:
            print(f"TCPInterface → {WIFI_HOST}:{WIFI_PORT}")
            connection_status, last_error_message = "Connected", ""
            return TCPInterface(hostname=WIFI_HOST, portNumber=WIFI_PORT)

        # 2️⃣  Bluetooth Low Energy ----------------------------------------
        if USE_BLUETOOTH and BLE_INTERFACE_AVAILABLE:
            if BLE_ADDRESS:
                print(f"BLEInterface → {BLE_ADDRESS}")
                iface = BLEInterface(BLE_ADDRESS)
            else:
                print("BLEInterface auto‑scan (no address specified) …")
                iface = BLEInterface(None)
            connection_status, last_error_message = "Connected", ""
            return iface

        if USE_BLUETOOTH and not BLE_INTERFACE_AVAILABLE:
            print("⚠️ Bluetooth requested but BLE support is not available. "
                  "Install the 'bleak' package: pip install bleak")
            print("Falling through to next connection method…")

        # 3️⃣  Local mesh interface ---------------------------------------
        if USE_MESH_INTERFACE and MESH_INTERFACE_AVAILABLE:
            print("MeshInterface() for direct‑radio mode")
            connection_status, last_error_message = "Connected", ""
            return MeshInterface()

        # 4️⃣  USB serial --------------------------------------------------
        if SERIAL_PORT:
            print(f"SerialInterface on '{SERIAL_PORT}' (default baud, will switch to {SERIAL_BAUD}) …")
            iface = meshtastic.serial_interface.SerialInterface(devPath=SERIAL_PORT)
        else:
            print(f"SerialInterface auto‑detect (default baud, will switch to {SERIAL_BAUD}) …")
            iface = meshtastic.serial_interface.SerialInterface()

        # Attempt to change baudrate after opening
        try:
            ser = getattr(iface, "_serial", None)
            if ser is not None and hasattr(ser, "baudrate"):
                ser.baudrate = SERIAL_BAUD
                print(f"Baudrate switched to {SERIAL_BAUD}")
        except Exception as e:
            print(f"⚠️ could not set baudrate to {SERIAL_BAUD}: {e}")

        connection_status, last_error_message = "Connected", ""
        return iface

    except Exception as exc:
        connection_status, last_error_message = "Disconnected", str(exc)
        add_script_log(f"Connection error: {exc}")
        raise

def thread_excepthook(args):
    logging.error(f"Meshtastic thread error: {args.exc_value}")
    traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback)
    global connection_status
    connection_status = "Disconnected"
    reset_event.set()

threading.excepthook = thread_excepthook

def main():
    global interface, restart_count, server_start_time, reset_event, STARTUP_INFO_PRINTED
    server_start_time = server_start_time or datetime.now(timezone.utc)
    restart_count += 1
    add_script_log(f"Server restarted. Restart count: {restart_count}")
    print("Starting MESH-API server...")
    # Print example AI suffix (alias) and commands immediately after startup banner
    if not STARTUP_INFO_PRINTED:
        try:
            print(f"example AI command Suffix (Alias): -{AI_SUFFIX} (can be set in config)")
            print(f"Commands: {get_available_commands_text()}")
        except Exception as e:
            print(f"⚠️ Could not print commands list: {e}")
        STARTUP_INFO_PRINTED = True
    load_archive()
        # Additional startup info:
    if ENABLE_DISCORD:
        print(f"Discord configuration enabled: Inbound channel index: {DISCORD_INBOUND_CHANNEL_INDEX}, Webhook URL is {'set' if DISCORD_WEBHOOK_URL else 'not set'}, Bot Token is {'set' if DISCORD_BOT_TOKEN else 'not set'}, Channel ID is {'set' if DISCORD_CHANNEL_ID else 'not set'}.")
    else:
        print("Discord configuration disabled.")
    if ENABLE_TWILIO:
        if TWILIO_SID and TWILIO_AUTH_TOKEN and ALERT_PHONE_NUMBER and TWILIO_FROM_NUMBER:
            print("Twilio is configured for emergency SMS.")
        else:
            print("Twilio is not properly configured for emergency SMS.")
    else:
        print("Twilio is disabled.")
    if ENABLE_SMTP:
        if SMTP_HOST and SMTP_USER and SMTP_PASS and ALERT_EMAIL_TO:
            print("SMTP is configured for emergency email alerts.")
        else:
            print("SMTP is not properly configured for emergency email alerts.")
    else:
        print("SMTP is disabled.")
    # -----------------------------
    # Extension System Startup
    # -----------------------------
    global extension_loader
    app_context = None
    try:
        from extensions.loader import ExtensionLoader
        app_context = {
            "interface": interface,
            "flask_app": app,
            "send_broadcast_chunks": send_broadcast_chunks,
            "send_direct_chunks": send_direct_chunks,
            "add_script_log": add_script_log,
            "get_node_shortname": get_node_shortname,
            "get_node_fullname": get_node_fullname,
            "get_node_location": get_node_location,
            "config": config,
            "sanitize_model_output": sanitize_model_output,
            "log_message": log_message,
            "add_ai_prefix": add_ai_prefix,
            "handle_command": handle_command,
            "parse_incoming_text": parse_incoming_text,
            "get_ai_response": get_ai_response,
            "MAX_RESPONSE_LENGTH": MAX_RESPONSE_LENGTH,
            "MAX_CHUNK_SIZE": MAX_CHUNK_SIZE,
            "CHUNK_DELAY": CHUNK_DELAY,
            "SYSTEM_PROMPT": SYSTEM_PROMPT,
            "AI_NODE_NAME": AI_NODE_NAME,
            "AI_PREFIX_TAG": AI_PREFIX_TAG,
            "server_start_time": server_start_time,
        }
        extension_loader = ExtensionLoader(EXTENSIONS_PATH, app_context)
        extension_loader.load_all()
    except Exception as e:
        print(f"⚠️ Extension system failed to initialise: {e}")
        extension_loader = None
    print("Launching Flask in the background on port 5000...")
    api_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": 5000, "debug": False},
        daemon=True
    )
    api_thread.start()
    # If Discord polling is configured, start that thread.
    if DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID:
        threading.Thread(target=poll_discord_channel, daemon=True).start()
    while True:
        try:
            print("---------------------------------------------------")
            print("Attempting to connect to Meshtastic device...")
            try:
                pub.unsubscribe(on_receive, "meshtastic.receive")
            except Exception:
                pass
            try:
                if interface:
                    interface.close()
            except Exception:
                pass
            interface = connect_interface()
            # Update app_context so extensions always see the current interface
            if app_context is not None:
                app_context["interface"] = interface
            print("Subscribing to on_receive callback...")
            pub.subscribe(on_receive, "meshtastic.receive")
            print(f"AI provider set to: {AI_PROVIDER}")
            if HOME_ASSISTANT_ENABLED:
                print(f"Home Assistant multi-mode is ENABLED. Channel index: {HOME_ASSISTANT_CHANNEL_INDEX}")
                if HOME_ASSISTANT_ENABLE_PIN:
                    print("Home Assistant secure PIN protection is ENABLED.")
            print("Connection successful. Running until error or Ctrl+C.")
            add_script_log("Connection established successfully.")
            # Inner loop: periodically check if a reset has been signaled
            while not reset_event.is_set():
                time.sleep(1)
            raise OSError("Reset event triggered due to connection loss")
        except KeyboardInterrupt:
            print("User interrupted the script. Shutting down.")
            add_script_log("Server shutdown via KeyboardInterrupt.")
            break
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError, TimeoutError) as e:
            print(f"⚠️ Connection error: {e}. Attempting to reconnect...")
            add_script_log(f"Connection error: {e}")
            time.sleep(5)
            reset_event.clear()
            continue
        except OSError as e:
            error_code = getattr(e, 'errno', None) or getattr(e, 'winerror', None)
            if error_code in (10053, 10054, 10060):
                print("⚠️ Connection was forcibly closed. Attempting to reconnect...")
                add_script_log(f"Connection forcibly closed: {e} (error code: {error_code})")
                time.sleep(5)
                reset_event.clear()
                continue
        except Exception as e:
            logging.error(f"⚠️ Connection/runtime error: {e}")
            add_script_log(f"Error: {e}")
            print("Will attempt reconnect in 30 seconds...")
            try:
                interface.close()
            except Exception:
                pass
            time.sleep(30)
            reset_event.clear()
            continue

def connection_monitor(initial_delay=30):
    global connection_status
    time.sleep(initial_delay)
    while True:
        if connection_status == "Disconnected":
            print("⚠️ Connection lost! Triggering reconnect...")
            reset_event.set()
        time.sleep(5)

# Start the watchdog thread after 20 seconds to give node a chance to connect
def poll_discord_channel():
    """Polls the Discord channel for new messages using the Discord API."""
    # Wait a short period for interface to be set up
    time.sleep(5)
    last_message_id = None
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    url = f"https://discord.com/api/v9/channels/{DISCORD_CHANNEL_ID}/messages"
    while True:
        try:
            params = {"limit": 10}
            if last_message_id:
                params["after"] = last_message_id
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                msgs = response.json()
                msgs = sorted(msgs, key=lambda m: int(m["id"]))
                for msg in msgs:
                    if msg["author"].get("bot"):
                        continue
                    # Only process messages that arrived after the script started
                    if last_message_id is None:
                        msg_timestamp_str = msg.get("timestamp")
                        if msg_timestamp_str:
                            msg_time = datetime.fromisoformat(msg_timestamp_str.replace("Z", "+00:00"))
                            if msg_time < server_start_time:
                                continue
                    username = msg["author"].get("username", "DiscordUser")
                    content = msg.get("content")
                    if content:
                        formatted = f"**{username}**: {content}"
                        log_message("DiscordPoll", formatted, direct=False, channel_idx=DISCORD_INBOUND_CHANNEL_INDEX)
                        if interface is None:
                            print("❌ Cannot send polled Discord message: interface is None.")
                        else:
                            send_broadcast_chunks(interface, formatted, DISCORD_INBOUND_CHANNEL_INDEX)
                        print(f"Polled and routed Discord message: {formatted}")
                        last_message_id = msg["id"]
            else:
                print(f"Discord poll error: {response.status_code} {response.text}")
        except Exception as e:
            print(f"Error polling Discord: {e}")
        time.sleep(10)

if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("User interrupted the script. Exiting.")
            add_script_log("Server exited via KeyboardInterrupt.")
            break
        except Exception as e:
            logging.error(f"Unhandled error in main: {e}")
            add_script_log(f"Unhandled error: {e}")
            print("Encountered an error. Restarting in 30 seconds...")
            time.sleep(30)
