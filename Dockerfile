FROM python:3.13-slim-bookworm

# ------------------------------------------------------------
# System packages
# ------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl git ca-certificates \
        bluez bluez-tools && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
# bluez + bluez-tools provide bluetoothctl / bt-agent so a configured MeshCore
# ble_pin can auto-pair. BLE from a container also needs host access at runtime
# (run with --net=host and mount /var/run/dbus, plus a powered host adapter).

# ------------------------------------------------------------
# Application
# ------------------------------------------------------------
# NOTE: meshtastic (and its matching protobuf) is pinned in requirements.txt and
# installed below. A previous git-HEAD meshtastic install here was overwritten by
# the requirements pin, leaving meshtastic and protobuf on mismatched versions —
# which caused FromRadio protobuf DecodeError at runtime. Pin both together.
WORKDIR /app
COPY mesh-api.py .
COPY meshcore_core.py .
COPY mcp_server.py .
COPY firmware_updater.py .
COPY version.py .
COPY requirements.txt .
COPY config.json .
COPY commands_config.json .
COPY motd.json .
COPY extensions/ ./extensions/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD ["python", "mesh-api.py"]
