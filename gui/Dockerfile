FROM python:3.11-slim

# Install system dependencies for AAXtoMP3
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    bc \
    jq \
    mediainfo \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install ttyd with architecture detection
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TTYD_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then TTYD_ARCH="aarch64"; \
    else TTYD_ARCH="x86_64"; fi && \
    curl -L "https://github.com/tsl0922/ttyd/releases/download/1.7.7/ttyd.${TTYD_ARCH}" -o /usr/bin/ttyd && \
    chmod +x /usr/bin/ttyd

# Install mp4v2 from source (for mp4art/mp4chaps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    && git clone https://github.com/enzo1982/mp4v2.git /tmp/mp4v2 \
    && cd /tmp/mp4v2 \
    && cmake . \
    && make \
    && make install \
    && ldconfig \
    && rm -rf /tmp/mp4v2 \
    && apt-get purge -y build-essential cmake \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY gui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir audible-cli

# Copy the AAXtoMP3 script from repo root
COPY AAXtoMP3 /app/AAXtoMP3
RUN chmod +x /app/AAXtoMP3

# Copy the Streamlit app
COPY gui/app.py .
COPY gui/worker.py .
COPY gui/entrypoint.sh .
RUN chmod +x entrypoint.sh

# Create directories for persistent data
RUN mkdir -p /data /downloads /converted

# Expose Streamlit port and Terminal port
EXPOSE 8501
EXPOSE 7681

# Configure Streamlit
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Entrypoint
CMD ["./entrypoint.sh"]
