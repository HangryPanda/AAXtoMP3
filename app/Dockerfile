FROM python:3.11-slim

# Set working directory early for all stages
WORKDIR /app

# Install all system dependencies in a single layer
# Combines runtime deps + build deps, then removes build deps after mp4v2 compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Runtime dependencies
    ffmpeg \
    bc \
    jq \
    mediainfo \
    curl \
    # Build dependencies (will be removed after mp4v2 build)
    git \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Install ttyd with architecture detection
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TTYD_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then TTYD_ARCH="aarch64"; \
    else TTYD_ARCH="x86_64"; fi && \
    curl -L "https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.${TTYD_ARCH}" -o /usr/bin/ttyd && \
    chmod +x /usr/bin/ttyd

# Build and install mp4v2, then clean up build dependencies
RUN git clone --depth 1 https://github.com/enzo1982/mp4v2.git /tmp/mp4v2 \
    && cd /tmp/mp4v2 \
    && cmake . \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && rm -rf /tmp/mp4v2 \
    && apt-get purge -y git build-essential cmake \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements FIRST (changes less frequently than app code)
# This layer gets cached and reused when only app code changes
COPY gui/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt audible-cli

# Copy the AAXtoMP3 script (changes less frequently than app code)
COPY AAXtoMP3 /app/AAXtoMP3
RUN chmod +x /app/AAXtoMP3

# Copy application code LAST (changes most frequently)
# Only this layer rebuilds when you edit app.py or worker.py
COPY gui/app.py gui/worker.py gui/entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Create directories for persistent data
RUN mkdir -p /data /downloads /converted

# Expose ports
EXPOSE 8501 7681

# Configure Streamlit
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["./entrypoint.sh"]
