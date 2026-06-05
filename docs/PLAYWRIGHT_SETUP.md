# Playwright Setup Guide

This guide helps resolve Playwright browser dependency issues on Ubuntu 24.04, 26.04, and other Linux distributions.

> **Note:** The setup script (`scripts/setup-playwright-deps.sh`) now auto-detects your Ubuntu version and installs compatible package versions. Use this for the easiest setup.

## Quick Start (Recommended)

### Option 1: Automated Setup Script

```bash
# Run the automated dependency installer
./scripts/setup-playwright-deps.sh

# Activate virtual environment
source venv/bin/activate

# Install Playwright browsers
python -m playwright install

# Verify installation
python -c "from playwright.sync_api import sync_playwright; sync_playwright().stop()"
```

### Option 2: Manual Installation (For Custom Environments)

**Note:** The automated script (Option 1) handles version differences automatically. Use this only if the script doesn't work for your setup.

1. **Update package lists:**
   ```bash
   sudo apt-get update
   sudo apt-get upgrade -y
   ```

2. **Install core graphics dependencies:**
   ```bash
   sudo apt-get install -y \
     libc6 libxss1 libnss3 \
     libpangocairo-1.0-0 libpango-1.0-0 libxrender1 libx11-6 \
     libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
     libxext6 libxfixes3 libxi6 libxinerama1 libxrandr2 libxtst6 \
     libfontconfig1 libfreetype6 libhyphen0 libharfbuzz0b libopus0 \
     libwebp7 libwoff1 libxslt1.1
   ```

3. **Install version-specific packages:**
   Ubuntu 24.04 and earlier use: `libxml2 libappindicator1 libgconf-2-4 libvpx9 libicu74`
   Ubuntu 26.04+ use: `libxml2-16 libayatana-appindicator3-1 libvpx12`
   
   **Try this to detect and install available versions:**
   ```bash
   for pkg in libxml2 libxml2-16 libappindicator1 libayatana-appindicator3-1 libvpx9 libvpx12 libicu74 libicu73; do
     if apt-cache search "^$pkg\$" | grep -q .; then
       sudo apt-get install -y "$pkg" || true
     fi
   done
   ```

4. **Install media codecs:**
   ```bash
   sudo apt-get install -y chromium-codecs-ffmpeg
   ```

5. **Activate virtual environment and install Playwright:**
   ```bash
   source venv/bin/activate
   python -m playwright install
   ```

## Troubleshooting

### "Package not available" errors

On Ubuntu 24.04+, some package versions may not exist or have been renamed. The setup script now auto-detects your Ubuntu version and installs compatible packages.

**If you still see errors:**
1. Run the automated setup script first: `./scripts/setup-playwright-deps.sh`
2. Update and upgrade packages: `sudo apt-get update && sudo apt-get upgrade`
3. Check available versions: `apt-cache search libicu | head -10`
4. Install available version manually if needed

**Version compatibility:**
- Ubuntu 24.04: Uses `libxml2`, `libappindicator1`, `libvpx9`, `libicu74`
- Ubuntu 26.04+: Uses `libxml2-16`, `libayatana-appindicator3-1`, `libvpx12`, `libicu73`+

### "Browser cache not found" after installation

If you see warnings like "BEWARE: your OS is not officially supported by Playwright":
1. This is expected on non-standard Ubuntu versions
2. Playwright downloads fallback builds automatically
3. Installation is still successful if no hard errors occur

To verify browsers are installed:
```bash
python -m playwright install --with-deps
python -m playwright codecs-ffmpeg
```

### "Browser validation failed" errors

If browsers fail to launch:
```bash
# Check which browsers are installed
python -c "from playwright.sync_api import sync_playwright; p = sync_playwright(); print(p.__dict__)"

# Reinstall with explicit dependency validation
python -m playwright install --with-deps
```

### Missing libavcodec60 or similar codec libraries

Ubuntu 24.04 may use different codec versions. Try:
```bash
# Check what's available
apt-cache search libavcodec | head -20

# Install chromium codecs (covers most cases)
sudo apt-get install -y chromium-codecs-ffmpeg

# Or install ffmpeg which includes codecs
sudo apt-get install -y ffmpeg
```

## Docker Alternative

For reproducible Playwright setups across machines, use Docker:

```dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libc6 libxss1 libnss3 libpangocairo-1.0-0 libpango-1.0-0 \
    libxrender1 libx11-6 libx11-xcb1 libxcb1 libxcomposite1 \
    libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxinerama1 \
    libxrandr2 libxtst6 libfontconfig1 libfreetype6 libharfbuzz0b \
    libopus0 libvpx9 libwebp7 libxml2 libxslt1.1 libicu74 \
    libevent-2.1-7t64 libmanette-0.2-0 chromium-codecs-ffmpeg

# Install Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install

COPY . .
CMD ["python", "app.py"]
```

## Verification

After installation, verify Playwright works:

```bash
# Test 1: Import check
python -c "from playwright.sync_api import sync_playwright; print('✓ Import successful')"

# Test 2: Browser check
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    for browser_name in ['chromium', 'firefox', 'webkit']:
        if hasattr(p, browser_name):
            print(f'✓ {browser_name} available')
"

# Test 3: Actual browser launch
python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    print('✓ Browser launch successful')
    browser.close()
"
```

## Environment Variables

For headless systems or CI/CD:

```bash
# Use GPU acceleration if available
export PLAYWRIGHT_LAUNCH_ARGS="--single-process"

# Set browser cache directory
export PLAYWRIGHT_BROWSERS_PATH=/custom/cache/path

# Override host platform (for fallback builds)
export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64

# Enable Playwright debug logging
export DEBUG=pw:api
```

## Performance Tuning

For the LinkedIn scraper specifically:

```python
# In your Playwright context
browser = p.chromium.launch(
    headless=True,
    args=[
        "--disable-dev-shm-usage",  # Use disk instead of shared memory
        "--disable-gpu",             # Disable GPU acceleration
        "--single-process",          # Single-process mode (caution: less stable)
        "--no-sandbox"               # Skip sandboxing (less secure, use only on trusted systems)
    ]
)
```

## Next Steps

1. Verify installation with `python -m pytest -v tests/`
2. Test scraper with `streamlit run app.py`
3. Check logs for any remaining dependency warnings

## Support

If you encounter issues:
1. Check `/home/fahim/.cache/ms-playwright/` for downloaded browsers
2. Run `playwright inspect` to debug browser behavior
3. Review Playwright docs: https://playwright.dev/python/docs/intro
