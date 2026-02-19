FROM debian:bookworm-slim

# ------------------------------------------------------------
# Versions / variables
# ------------------------------------------------------------
ENV PYTHON_VERSION=3.13.2

# ------------------------------------------------------------
# System packages
# ------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget build-essential libssl-dev zlib1g-dev \
        libncurses5-dev libreadline-dev libsqlite3-dev \
        libgdbm-dev libbz2-dev libexpat1-dev liblzma-dev \
        tk-dev libffi-dev curl git ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# Build CPython ${PYTHON_VERSION}
# ------------------------------------------------------------
RUN wget -q https://www.python.org/ftp/python/${PYTHON_VERSION}/Python-${PYTHON_VERSION}.tgz && \
    tar -xf Python-${PYTHON_VERSION}.tgz && \
    cd Python-${PYTHON_VERSION} && \
    ./configure --enable-optimizations && \
    make -j"$(nproc)" && make altinstall && \
    cd / && rm -rf Python-${PYTHON_VERSION}* && \
    ln -s /usr/local/bin/python3.13 /usr/local/bin/python && \
    ln -s /usr/local/bin/pip3.13    /usr/local/bin/pip

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
COPY extensions/ ./extensions/

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
CMD ["python", "mesh-api.py"]
