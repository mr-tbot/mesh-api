FROM python:3.13-slim-bookworm

# ------------------------------------------------------------
# System packages
# ------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl git ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Install always-latest Meshtastic Python (pulls matching protobufs)
# ------------------------------------------------------------
RUN pip install --no-cache-dir --upgrade \
    "meshtastic @ git+https://github.com/meshtastic/meshtastic-python.git"

# ------------------------------------------------------------
# Application
# ------------------------------------------------------------
WORKDIR /app
COPY mesh-api.py .
COPY requirements.txt .
COPY config.json .
COPY commands_config.json .
COPY motd.json .
COPY extensions/ ./extensions/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD ["python", "mesh-api.py"]
