#!/bin/bash

# Setup Playwright browser dependencies for Ubuntu 24.04
# Handles missing system libraries due to package version mismatches

set -e

echo "Installing Playwright browser dependencies for Ubuntu 24.04..."

# Update package lists
sudo apt-get update

# Install core browser runtime dependencies
# These packages are required by Chromium, Firefox, and WebKit
sudo apt-get install -y \
    libxss1 \
    libappindicator1 \
    libgconf-2-4 \
    libnss3 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libxrender1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxinerama1 \
    libxrandr2 \
    libxtst6 \
    libfontconfig1 \
    libfreetype6 \
    libhyphen0 \
    libharfbuzz0b \
    libopus0 \
    libvpx9 \
    libwebp7 \
    libwoff1 \
    libxml2 \
    libxslt1.1

# Install media and encoding dependencies
sudo apt-get install -y \
    libc6 \
    libicu74 \
    libevent-2.1-7t64 \
    libmanette-0.2-0 \
    libavif16 \
    libavcodec60 \
    libavformat60 \
    libavutil59 \
    libswscale6 2>/dev/null || true

# Fallback: install chromium-codecs-ffmpeg if other codec packages fail
if ! dpkg -l | grep -q libavcodec; then
    sudo apt-get install -y chromium-codecs-ffmpeg 2>/dev/null || true
fi

echo "System dependencies installed successfully."
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Install Playwright browsers: python -m playwright install"
echo "3. Verify installation: python -m playwright install --help"
