#!/bin/bash

# Setup Playwright browser dependencies for Ubuntu 24.04+
# Auto-detects Ubuntu version and installs correct package versions

echo "Installing Playwright browser dependencies..."

# Get Ubuntu version
UBUNTU_VERSION=$(lsb_release -rs 2>/dev/null || grep VERSION_ID /etc/os-release | cut -d'"' -f2 || echo "24.04")
echo "Detected Ubuntu version: $UBUNTU_VERSION"

# Update package lists
sudo apt-get update

# Function to try installing package, skip if not found
try_install() {
    local pkg=$1
    if apt-cache search "^${pkg}$" 2>/dev/null | grep -q .; then
        echo "Installing $pkg..."
        sudo apt-get install -y "$pkg" 2>/dev/null || echo "Warning: Failed to install $pkg"
    else
        echo "Package not found: $pkg (skipping)"
    fi
}

# Core X11/graphics dependencies (same across versions)
echo "Installing core graphics libraries..."
sudo apt-get install -y \
    libxss1 \
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
    libwebp7 \
    libwoff1 \
    libxslt1.1 2>/dev/null || true

# Version-specific packages
echo "Installing version-specific dependencies..."

# Handle libxml2 (libxml2 vs libxml2-16)
try_install "libxml2"
if ! dpkg -l | grep -q libxml2; then
    try_install "libxml2-16"
fi

# Handle libappindicator (legacy vs new Ayatana)
if apt-cache search "^libappindicator1$" 2>/dev/null | grep -q .; then
    try_install "libappindicator1"
else
    try_install "libayatana-appindicator3-1"
fi

# Handle libgconf (often not needed in newer Ubuntu)
try_install "libgconf-2-4"

# Handle libvpx (libvpx9 vs libvpx12)
try_install "libvpx9"
if ! dpkg -l | grep -q libvpx; then
    try_install "libvpx12"
fi

# Media and encoding dependencies
echo "Installing media codec libraries..."
sudo apt-get install -y \
    libc6 \
    libmanette-0.2-0 2>/dev/null || true

# Handle libicu version differences
try_install "libicu74"
try_install "libicu73"
try_install "libicu72"

# Handle libevent version
try_install "libevent-2.1-7t64"
try_install "libevent-2.1-7"

# Handle AVIF/AV codec packages
try_install "libavif16"
try_install "libavif15"

# Try modern codec packages
for codec_pkg in libavcodec60 libavformat60 libavutil59 libswscale6; do
    try_install "$codec_pkg"
done

# Fallback: install chromium-codecs-ffmpeg if other codec packages fail
if ! dpkg -l | grep -q libavcodec; then
    echo "Installing chromium-codecs-ffmpeg as fallback..."
    sudo apt-get install -y chromium-codecs-ffmpeg 2>/dev/null || echo "Warning: chromium-codecs-ffmpeg not available"
fi

echo ""
echo "System dependencies installation completed."
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Install Playwright browsers: python -m playwright install"
echo "3. Verify installation: python -m playwright install-deps"
