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

# -----------------------------
# Meshtastic and Flask Setup
# -----------------------------
try:
    from meshtastic.tcp_interface import TCPInterface
except ImportError:
    TCPInterface = None

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
                                                            

MESH-API BETA v0.6.0 (PRE-RELEASE 4) by: MR_TBOT (https://mr-tbot.com)
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
    return [text[i: i + MAX_CHUNK_SIZE] for i in range(0, len(text), MAX_CHUNK_SIZE)][:MAX_CHUNKS]

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
        except Exception as e:
            print(f"❌ Error sending broadcast chunk: {e}")
            # Check both errno and winerror for known connection errors
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

    for attempt in range(2):  # up to 2 attempts
        try:
            r = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
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
    elif AI_PROVIDER == "home_assistant":
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
    ] + AI_COMMANDS + [SMS_COMMAND]
    custom_cmds = [c.get("command") for c in commands_config.get("commands", [])]
    return "Commands:\n" + ", ".join(built_in + custom_cmds)
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
      if is_direct:
        send_direct_chunks(interface, ai_out, sender_node)
      else:
        send_broadcast_chunks(interface, ai_out, ch_idx)
  except OSError as e:
    error_code = getattr(e, 'errno', None) or getattr(e, 'winerror', None)
    print(f"⚠️ OSError detected in on_receive: {e} (error code: {error_code})")
    if error_code in (10053, 10054, 10060):
      print("⚠️ Connection error detected. Restarting interface...")
      global connection_status
      connection_status = "Disconnected"
      reset_event.set()
    # Instead of re-raising, simply return to prevent thread crash
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
            node_gps_info[str(nid)] = {
                "lat": lat,
                "lon": lon,
                "beacon_time": tstr,
                "hops": hops,
            }
    node_gps_info_json = json.dumps(node_gps_info)

    # Get connected node's GPS for distance calculation
    my_lat, my_lon, _ = get_node_location(interface.myNode.nodeNum) if interface and hasattr(interface, "myNode") and interface.myNode else (None, None, None)
    my_gps_json = json.dumps({"lat": my_lat, "lon": my_lon})

    html = """
<html>
<head>
  <title>MESH-API Dashboard</title>
  <style>
  :root { --theme-color: #ffa500; }
  html, body { margin: 0; padding: 0; }
  body { background:#000; color:#fff; font-family: Arial, sans-serif; }
    body { background: #000; color: #fff; font-family: Arial, sans-serif; margin: 0; transition: filter 0.5s linear; }
  #connectionStatus { position: relative; width: 100%; text-align: center; padding: 0; font-size: 14px; font-weight: bold; display: block; min-height: 20px; background: green; margin: 0; border-bottom: 1px solid var(--theme-color); }
  /* Header buttons moved inside Send Form panel */
  #ticker-container { position: relative; width: 100%; display: none; align-items: center; justify-content: center; pointer-events: none; margin: 0; }
    #ticker { background: #111; color: var(--theme-color); white-space: nowrap; overflow: hidden; width: 100%; padding: 5px 0; font-size: 36px; display: none; position: relative; border-bottom: 2px solid var(--theme-color); min-height: 50px; pointer-events: auto; }
    #ticker p { display: inline-block; margin: 0; animation: tickerScroll 30s linear infinite; vertical-align: middle; min-width: 100vw; }
    #ticker .dismiss-btn { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); font-size: 18px; background: #222; color: #fff; border: 1px solid var(--theme-color); border-radius: 4px; cursor: pointer; padding: 2px 10px; z-index: 10; }
    @keyframes tickerScroll { 0% { transform: translateX(100%); } 100% { transform: translateX(-100%); } }
    #sendForm { margin: 20px; padding: 20px; background: #111; border: 2px solid var(--theme-color); border-radius: 10px; position: relative; }
    .panel-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
    .three-col { display: flex; flex-wrap: wrap; gap: 20px; margin: 20px; }
    .three-col .col { flex: 1 1 100%; }
    @media (min-width: 992px) {
      .three-col { flex-wrap: nowrap; }
      .three-col .col { flex: 1 1 0; }
    }
    .lcars-panel { background: #111; padding: 20px; border: 2px solid var(--theme-color); border-radius: 10px; }
    .lcars-panel h2 { color: var(--theme-color); margin-top: 0; }
    .lcars-panel .panel-title-row { display:flex; align-items:center; justify-content: space-between; gap: 10px; }
    .lcars-panel .collapse-btn { background:#222; color:#fff; border:1px solid var(--theme-color); border-radius:4px; padding:2px 8px; cursor:pointer; display:none; }
    @media (max-width: 991px) { .lcars-panel .collapse-btn { display:inline-block; } }
    .lcars-panel .panel-body { overflow-y:auto; max-height: 50vh; }
    @media (min-width: 992px) { .lcars-panel .panel-body { max-height: calc(100vh - 360px); } }
    .message { border: 1px solid var(--theme-color); border-radius: 4px; margin: 5px; padding: 5px; }
    .message.outgoing { background: #222; }
    .message.newMessage { border-color: #00ff00; background: #1a2; }
    .message.recentNode { border-color: #00bfff; background: #113355; }
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
    .nodeItem { margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--theme-color); display: flex; flex-direction: column; align-items: flex-start; flex-wrap: wrap; }
    .nodeItem.recentNode { border-bottom: 2px solid #00bfff; background: #113355; }
    .nodeMainLine { font-weight: bold; font-size: 1.1em; }
    .nodeLongName { color: #aaa; font-size: 0.98em; margin-top: 2px; }
    .nodeInfoLine { margin-top: 2px; font-size: 0.95em; color: #ccc; display: flex; flex-wrap: wrap; gap: 10px; }
    .nodeGPS { margin-left: 0; }
    .nodeBeacon { color: #aaa; font-size: 0.92em; }
    .nodeHops { color: #6cf; font-size: 0.92em; }
    .nodeMapBtn { margin-left: 0; background: #222; color: #fff; border: 1px solid #ffa500; border-radius: 4px; padding: 2px 6px; font-size: 1em; cursor: pointer; text-decoration: none; }
    .nodeMapBtn:hover { background: #ffa500; color: #000; }
    .channel-header { display: flex; align-items: center; gap: 10px; }
    .reply-btn { margin-left: 10px; padding: 2px 8px; font-size: 0.85em; background: #222; color: var(--theme-color); border: 1px solid var(--theme-color); border-radius: 4px; cursor: pointer; }
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
  /* UI Settings panel: hidden by default; shown when open */
  .settings-panel { display: none; background: #111; border: 2px solid var(--theme-color); border-radius: 10px; padding: 20px; margin: 20px; max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }
  .settings-panel.open { display: block; max-height: 70vh; overflow: auto; padding-bottom: 80px; }
  .settings-panel .sticky-actions { position: sticky; bottom: 0; background: #111; padding-top: 10px; padding-bottom: 6px; }
    /* Timezone selector */
    #timezoneSelect { margin-left: 10px; }
  /* Footer link bottom right */
  .footer-right-link { position: fixed; bottom: 10px; right: 10px; z-index: 350; text-align: right; }
  .footer-right-link .btnlink { display:inline-block; color: var(--theme-color); text-decoration: none; font-weight: bold; background: #111; padding: 6px 10px; border: 1px solid var(--theme-color); border-radius: 6px; white-space: pre-line; text-align: center; }
  .footer-right-link .btnlink:hover { background: var(--theme-color); color: #000; }
  /* Footer UI Settings button bottom left */
  .footer-left-link { position: fixed; bottom: 10px; left: 10px; z-index: 350; text-align: left; }
  .footer-left-link .btnlink { display:inline-block; color: var(--theme-color); text-decoration: none; font-weight: bold; background: #111; padding: 6px 10px; border: 1px solid var(--theme-color); border-radius: 6px; white-space: pre-line; text-align: center; cursor: pointer; }
  .footer-left-link .btnlink:hover { background: var(--theme-color); color: #000; }
    /* Suffix chip */
    .suffix-chip { background:#111; color: var(--theme-color); border:1px solid var(--theme-color); padding:6px 10px; border-radius:6px; display:inline-block; }
    /* Modal overlay for Commands */
    .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 500; display: none; align-items: center; justify-content: center; }
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
  /* Theme color tint overlay for logo (masked to logo shape) */
  .masthead .logo-overlay { position: absolute; inset: 0; background: var(--theme-color); opacity: 0.35; pointer-events: none; }
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
      soundURL: ""
    };
    let hueRotateInterval = null;
    let currentHue = 0;

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
  // Ensure hidden state by default
  settingsPanel.classList.remove('open');
  settingsBtn.textContent = "Show UI Settings";
      settingsBtn.addEventListener('click', function(e) {
        e.preventDefault();
        const opening = !settingsPanel.classList.contains('open');
        if (opening) {
          settingsPanel.classList.add('open');
          this.textContent = 'Hide UI Settings';
          // After opening, scroll the page to the bottom to reveal all settings
          requestAnimationFrame(() => {
            window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
          });
        } else {
          settingsPanel.classList.remove('open');
          this.textContent = 'Show UI Settings';
        }
      });
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
      document.getElementById('soundURL').value = uiSettings.soundURL;

      // Apply settings on load
      applyThemeColor(uiSettings.themeColor);
      if (uiSettings.hueRotateEnabled) startHueRotate(uiSettings.hueRotateSpeed);
      setIncomingSound(uiSettings.soundURL);

      // Apply button
      document.getElementById('applySettingsBtn').addEventListener('click', function() {
        // Read values
        uiSettings.themeColor = document.getElementById('uiColorPicker').value;
        uiSettings.hueRotateEnabled = document.getElementById('hueRotateEnabled').checked;
        uiSettings.hueRotateSpeed = parseFloat(document.getElementById('hueRotateSpeed').value);
        // For soundURL, only allow local file path from file input
        var fileInput = document.getElementById('soundFile');
        if (fileInput && fileInput.files.length > 0) {
          var file = fileInput.files[0];
          var url = URL.createObjectURL(file);
          uiSettings.soundURL = url;
          document.getElementById('soundURL').value = file.name;
        }
        saveUISettings();
        applyThemeColor(uiSettings.themeColor);
        if (uiSettings.hueRotateEnabled) {
          startHueRotate(uiSettings.hueRotateSpeed);
        } else {
          stopHueRotate();
        }
        setIncomingSound(uiSettings.soundURL);
        // Save timezone offset
        setTimezoneOffset(document.getElementById('timezoneSelect').value);
        // Keep Apply button visible after changes
        const sticky = document.querySelector('.sticky-actions');
        if (sticky) sticky.scrollIntoView({ behavior: 'smooth', block: 'end' });
        fetchMessagesAndNodes();
      });

      // Listen for file input change to update sound preview
      document.getElementById('soundFile').addEventListener('change', function() {
        if (this.files.length > 0) {
          var file = this.files[0];
          var url = URL.createObjectURL(file);
          uiSettings.soundURL = url;
          document.getElementById('soundURL').value = file.name;
          setIncomingSound(url);
        }
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
    });

    // --- UI Settings Functions ---
    function saveUISettings() {
      // Only persist the file name for sound, not the blob URL
      let settingsToSave = Object.assign({}, uiSettings);
      if (settingsToSave.soundURL && settingsToSave.soundURL.startsWith('blob:')) {
        settingsToSave.soundURL = document.getElementById('soundURL').value;
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
    function startHueRotate(speed) {
      stopHueRotate();
      hueRotateInterval = setInterval(function() {
        currentHue = (currentHue + 1) % 360;
        const root = document.getElementById('appRoot') || document.body;
        root.style.filter = `hue-rotate(${currentHue}deg)`;
        // Ensure logo overlay tint remains constant (not hue-rotated)
        const logoOverlay = document.querySelector('.masthead .logo-overlay');
        if (logoOverlay) {
          logoOverlay.style.filter = 'none';
        }
      }, Math.max(5, 1000 / Math.max(1, speed)));
    }
    function stopHueRotate() {
      if (hueRotateInterval) clearInterval(hueRotateInterval);
      hueRotateInterval = null;
      const root = document.getElementById('appRoot') || document.body;
      root.style.filter = "";
      currentHue = 0;
      const logoOverlay = document.querySelector('.masthead .logo-overlay');
      if (logoOverlay) {
        logoOverlay.style.filter = 'none';
      }
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
    }

    function dmToNode(nodeId, shortName, replyToTs) {
      toggleMode('direct');
      document.getElementById('destNode').value = nodeId;
      if (replyToTs) {
        // Prefill with quoted message if replying to a thread
        let threadMsg = allMessages.find(m => m.timestamp === replyToTs);
        let quoted = threadMsg ? `> ${threadMsg.message}\n` : '';
        document.getElementById('messageBox').value = quoted + '@' + shortName + ': ';
      } else {
        document.getElementById('messageBox').value = '@' + shortName + ': ';
      }
      updateCharCounter();
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
      } else {
        alert("No broadcast channel target available.");
      }
    }

    // Data fetch & UI updates
    const CHANNEL_NAMES = """ + json.dumps(channel_names) + """;

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
        updateMessagesUI(msgs);
        updateNodesUI(nodes, false);
        updateNodesUI(nodes, true);
        updateDirectMessagesUI(msgs, nodes);
        highlightRecentNodes(nodes);
        showLatestMessageTicker(msgs);
        updateDiscordMessagesUI(msgs);
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
    }
    async function loadConfigFiles(){
      try{
        const r = await fetch('/config_editor/load');
        if(!r.ok){ throw new Error('Load failed'); }
        const data = await r.json();
        document.getElementById('cfgEditor').value = JSON.stringify(data.config || {}, null, 2);
        document.getElementById('cmdEditor').value = JSON.stringify(data.commands_config || {}, null, 2);
        document.getElementById('motdEditor').value = data.motd || '';
      }catch(e){ alert('Error loading config files: '+e.message); }
    }
    async function saveConfigFiles(){
      try{
        let cfgText = document.getElementById('cfgEditor').value;
        let cmdText = document.getElementById('cmdEditor').value;
        let motdText = document.getElementById('motdEditor').value;
        let cfgJson = {};
        let cmdJson = {};
        try{ cfgJson = JSON.parse(cfgText); cfgText = JSON.stringify(cfgJson, null, 2); document.getElementById('cfgEditor').value = cfgText; } catch(e){ return alert('config.json is not valid JSON: '+e.message); }
        try{ cmdJson = JSON.parse(cmdText); cmdText = JSON.stringify(cmdJson, null, 2); document.getElementById('cmdEditor').value = cmdText; } catch(e){ return alert('commands_config.json is not valid JSON: '+e.message); }
        const r = await fetch('/config_editor/save', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ config: cfgJson, commands_config: cmdJson, motd: motdText }) });
        const res = await r.json();
        if(!r.ok){ throw new Error(res.message||'Save failed'); }
        alert('Saved. Some changes require restarting the service to take effect.');
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
      Object.keys(groups).sort().forEach(ch => {
        const name = CHANNEL_NAMES[ch] || `Channel ${ch}`;
        // Channel header with reply and mark all as read button
        const headerWrap = document.createElement("div");
        headerWrap.className = "channel-header";
        const header = document.createElement("h3");
        header.textContent = `${ch} – ${name}`;
        header.style.margin = 0;
        headerWrap.appendChild(header);

        // Add reply button for channel
        const replyBtn = document.createElement("button");
        replyBtn.textContent = "Send to Channel";
        replyBtn.className = "reply-btn";
        replyBtn.onclick = function() {
          replyToMessage('broadcast', ch);
        };
        headerWrap.appendChild(replyBtn);

        // Mark all as read for this channel
        const markAllBtn = document.createElement("button");
        markAllBtn.textContent = "Mark all as read";
        markAllBtn.className = "mark-all-read-btn";
        markAllBtn.onclick = function() {
          markChannelAsRead(ch);
        };
        headerWrap.appendChild(markAllBtn);

        channelDiv.appendChild(headerWrap);

        groups[ch].forEach(m => {
          if (isChannelMsgRead(m.timestamp, ch)) return; // Hide read messages
          const wrap = document.createElement("div");
          wrap.className = "message";
          if (isRecent(m.timestamp, 60)) wrap.classList.add("newMessage");
          const ts = document.createElement("div");
          ts.className = "timestamp";
          ts.textContent = `📢 ${getTZAdjusted(m.timestamp)} | ${m.node}`;
          const body = document.createElement("div");
          body.textContent = m.message;
          wrap.append(ts, body);

          // Mark as read button
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

          // React button and emoji picker
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

          channelDiv.appendChild(wrap);
        });
        channelDiv.appendChild(document.createElement("hr"));
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
        const shortName = node ? node.shortName : nodeId;
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

          // Main line: Short name and ID
          const mainLine = document.createElement("div");
          mainLine.className = "nodeMainLine";
          mainLine.innerHTML = `<span>${n.shortName || ""}</span> <span style="color:#ffa500;">(${n.id})</span>`;
          d.appendChild(mainLine);

          // Long name (if present)
          if (n.longName && n.longName !== n.shortName) {
            const longName = document.createElement("div");
            longName.className = "nodeLongName";
            longName.textContent = n.longName;
            d.appendChild(longName);
          }

          // Info line 1: GPS/map, DM button, distance
          const infoLine1 = document.createElement("div");
          infoLine1.className = "nodeInfoLine";
          let gps = nodeGPSInfo[String(n.id)];
          if (gps && gps.lat != null && gps.lon != null) {
            // Map button (emoji)
            const mapA = document.createElement("a");
            mapA.href = `https://www.google.com/maps/search/?api=1&query=${gps.lat},${gps.lon}`;
            mapA.target = "_blank";
            mapA.className = "nodeMapBtn";
            mapA.title = "Show on Google Maps";
            mapA.innerHTML = "🗺️";
            infoLine1.appendChild(mapA);

            // DM button next to Map
            const dmBtn = document.createElement("button");
            dmBtn.textContent = "DM";
            dmBtn.className = "reply-btn";
            dmBtn.style.marginLeft = "6px";
            dmBtn.onclick = () => dmToNode(n.id, n.shortName);
            infoLine1.appendChild(dmBtn);

            // Distance
            if (myGPS && myGPS.lat != null && myGPS.lon != null) {
              let dist = calcDistance(myGPS.lat, myGPS.lon, gps.lat, gps.lon);
              if (dist < 99999) {
                const distSpan = document.createElement("span");
                distSpan.className = "nodeGPS";
                distSpan.title = "Approximate distance from connected node";
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

          // Info line 3 (last): Beacon/reporting time
          const infoLine2 = document.createElement("div");
          infoLine2.className = "nodeInfoLine";
          if (gps && gps.beacon_time) {
            const beacon = document.createElement("span");
            beacon.className = "nodeBeacon";
            beacon.title = "Last beacon/reporting time";
            beacon.innerHTML = `🕒 ${getTZAdjusted(gps.beacon_time)}`;
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
      <img id="mastheadLogo" src="https://mr-tbot.com/wp-content/uploads/2026/02/MESH-API.png" alt="MESH-API Logo" loading="lazy">
      <span class="logo-overlay"></span>
    </span>
    <div class="masthead-actions">
      <span class="suffix-chip" title="Current AI alias and suffix">""" + f"{AI_ALIAS_CANONICAL} (suffix: {AI_SUFFIX})" + """</span>
      <button type="button" onclick="openCommandsModal()">Commands</button>
      <button type="button" onclick="openConfigModal()">Config</button>
      <a href="/logs" target="_blank">Logs</a>
    </div>
  </div>

  <div class="lcars-panel" id="sendForm">
    <div class="panel-header">
      <h2>Send a Message</h2>
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
  <button type="submit" class="reply-btn">Send</button>
  <button type="button" class="reply-btn" onclick="replyToLastDM()">Reply to Last DM</button>
  <button type="button" class="reply-btn" onclick="replyToLastChannel()">Reply to Last Channel</button>
    </form>
  </div>

  <div class="three-col">
    <div class="col">
      <div class="lcars-panel">
        <div class="panel-title-row">
          <h2>Direct Messages</h2>
          <button class="collapse-btn" onclick="togglePanel(this)">Collapse</button>
        </div>
        <div class="panel-body">
          <div id="dmMessagesDiv"></div>
        </div>
      </div>
    </div>
    <div class="col">
      <div class="lcars-panel">
        <div class="panel-title-row">
          <h2>Channel Messages</h2>
          <button class="collapse-btn" onclick="togglePanel(this)">Collapse</button>
        </div>
        <div class="panel-body">
          <div id="channelDiv"></div>
        </div>
      </div>
    </div>
    <div class="col">
      <div class="lcars-panel">
        <div class="panel-title-row">
          <h2>Available Nodes</h2>
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

  <div class="lcars-panel" id="discordSection" style="margin:20px;">
    <h2>Discord Messages</h2>
    <div id="discordMessagesDiv"></div>
  </div>
  <div class="footer-right-link"><a class="btnlink" href="https://mesh-api.dev" target="_blank">MESH-API v0.6.0 PR4\nby: MR-TBOT</a></div>
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
    <div class="modal-content">
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
        </div>
        <div style="background:#1a1a1a; border:1px solid var(--theme-color); padding:10px; border-radius:8px; margin-bottom:10px; color:#ccc;">
          <strong>Note:</strong> Changes to providers, connectivity (Wi‑Fi/Serial/Mesh), or Discord/Twilio credentials usually require a restart. Use the <em>Restart</em> button above after saving.
        </div>
        <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:8px;">
          <button class="reply-btn" onclick="showConfigTab('cfg')">config.json</button>
          <button class="reply-btn" onclick="showConfigTab('cmd')">commands_config.json</button>
          <button class="reply-btn" onclick="showConfigTab('motd')">motd.json</button>
        </div>
        <div id="cfgTab" style="display:block;">
          <textarea id="cfgEditor" style="width:100%; height:40vh; background:#000; color:#0f0; border:1px solid var(--theme-color);"></textarea>
          <div style="margin-top:8px; color:#bbb; font-size:0.95em; line-height:1.4;">
            <details open>
              <summary style="color:#ffa500; cursor:pointer;">config.json options help</summary>
              <ul>
                <li><code>ai_provider</code>: lmstudio | openai | ollama — selects the AI backend.</li>
                <li><code>system_prompt</code>: System role text sent to the AI.</li>
                <li><code>lmstudio_url</code>, <code>lmstudio_chat_model</code>, <code>lmstudio_timeout</code>: LM Studio settings.</li>
                <li><code>openai_api_key</code>, <code>openai_model</code>, <code>openai_timeout</code>: OpenAI settings.</li>
                <li><code>ollama_url</code>, <code>ollama_model</code>, <code>ollama_timeout</code>, <code>ollama_keep_alive</code>, <code>ollama_options</code>: Ollama settings.</li>
                <li><code>reply_in_channels</code>, <code>reply_in_directs</code>, <code>ai_respond_on_longfast</code>: Reply policy.</li>
                <li><code>chunk_size</code> and <code>max_ai_chunks</code>: Max characters per chunk and number of chunks sent.</li>
                <li><code>use_wifi</code>, <code>wifi_host</code>/<code>wifi_port</code>; <code>serial_port</code>/<code>serial_baud</code>; <code>use_mesh_interface</code>: Connectivity modes.</li>
                <li><code>home_assistant_*</code>: Enable and secure Home Assistant routing on a dedicated channel.</li>
                <li><code>enable_discord</code>, <code>discord_webhook_url</code>, <code>discord_*</code>: Send/receive via Discord.</li>
                <li><code>enable_twilio</code> and <code>enable_smtp</code>: Emergency SMS/Email alerts.</li>
              </ul>
            </details>
          </div>
        </div>
        <div id="cmdTab" style="display:none;">
          <textarea id="cmdEditor" style="width:100%; height:40vh; background:#000; color:#0ff; border:1px solid var(--theme-color);"></textarea>
        </div>
        <div id="motdTab" style="display:none;">
          <textarea id="motdEditor" style="width:100%; height:40vh; background:#000; color:#ffa; border:1px solid var(--theme-color);"></textarea>
        </div>
        <div style="margin-top:8px; color:#ccc;">
          Tip: Ensure valid JSON for config and commands. The editor will try to pretty-format on save.
        </div>
      </div>
    </div>
  </div>
  <div class="settings-panel" id="settingsPanel">
    <h2>UI Settings</h2>
    <label for="uiColorPicker">Theme Color:</label>
    <input type="color" id="uiColorPicker" value="#ffa500"><br><br>
    <label for="hueRotateEnabled">Enable Hue Rotation:</label>
    <input type="checkbox" id="hueRotateEnabled"><br><br>
    <label for="hueRotateSpeed">Hue Rotation Speed:</label>
    <input type="range" id="hueRotateSpeed" min="5" max="60" step="0.1" value="10"><br><br>
    <label for="soundFile">Incoming Message Sound (local file):</label>
    <input type="file" id="soundFile" accept="audio/*"><br>
    <input type="text" id="soundURL" placeholder="No file selected" readonly style="background:#222;color:#fff;border:none;"><br><br>
    <label for="timezoneSelect">Timezone Offset (hours):</label>
    <select id="timezoneSelect">
"""
    # Timezone selector: -12 to +14
    for tz in range(-12, 15):
        html += f'      <option value="{tz}">{tz:+d}</option>\n'
    html += """    </select><br><br>
    <div class=\"sticky-actions\">
      <button id=\"applySettingsBtn\" type=\"button\">Apply Settings</button>
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

def connect_interface():
    """Return a Meshtastic interface with the baud rate from config.

    Resolution order:
      1. Wi‑Fi TCP bridge
      2. Local MeshInterface()
      3. USB SerialInterface (explicit path or auto‑detect)
    """
    global connection_status, last_error_message
    try:
        # 1️⃣  Wi‑Fi bridge -------------------------------------------------
        if USE_WIFI and WIFI_HOST and TCPInterface is not None:
            print(f"TCPInterface → {WIFI_HOST}:{WIFI_PORT}")
            connection_status, last_error_message = "Connected", ""
            return TCPInterface(hostname=WIFI_HOST, portNumber=WIFI_PORT)

        # 2️⃣  Local mesh interface ---------------------------------------
        if USE_MESH_INTERFACE and MESH_INTERFACE_AVAILABLE:
            print("MeshInterface() for direct‑radio mode")
            connection_status, last_error_message = "Connected", ""
            return MeshInterface()

        # 3️⃣  USB serial --------------------------------------------------
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

@app.route("/connection_status", methods=["GET"])
def connection_status_route():
    return jsonify({"status": connection_status, "error": last_error_message})

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
