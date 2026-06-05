# Installation Guide

Quick start guide for setting up the LinkedIn Scraper.

## Prerequisites

- Python 3.11+
- Git
- For Linux: apt (Ubuntu/Debian), pacman (Arch), or equivalent
- For macOS: Homebrew
- For Windows: WSL2 recommended, or use Docker

## Quick Start

### 1. Clone Repository
```bash
git clone <repo-url>
cd linkedin-scraper
```

### 2. Create Virtual Environment
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Python Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Playwright Browsers & Dependencies

#### Option A: Automated (Ubuntu/Debian/24.04+)
```bash
# The script auto-detects your Ubuntu version and installs compatible packages
./scripts/setup-playwright-deps.sh
python -m playwright install
```

#### Option B: Manual Installation
```bash
# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-codecs-ffmpeg \
  libicu74 libxml2 libxslt1.1 libevent-2.1-7t64 libmanette-0.2-0

# macOS (with Homebrew)
brew install libxdamage libx11 libxss libxcomposite libxcursor \
  libxinerama libxrandr libxtst libxcb

# Then install Playwright
python -m playwright install
```

#### Option C: Docker (Cross-Platform)
```bash
docker build -t linkedin-scraper .
docker-compose up -d
# App runs on http://localhost:8501
```

### 5. Configure Environment
```bash
cp .env.example .env
# Edit .env with your LinkedIn credentials
nano .env
```

### 6. Verify Setup
```bash
# Test Python environment
python -c "import playwright; print('✓ Playwright installed')"

# Test browser availability
python -m playwright install --help

# Run tests
pytest -v
```

### 7. Run Application
```bash
# Using Streamlit (recommended for interactive use)
streamlit run app.py

# Or use the scraper directly in Python
python -c "
from src.scraper import LinkedInScraper
# Your code here
"
```

## Troubleshooting

See [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md) for:
- Ubuntu 24.04 specific issues
- Missing package errors
- Browser cache/validation errors
- Docker setup help

### Common Issues

**"ModuleNotFoundError: No module named 'playwright'"**
- Ensure virtual environment is activated: `source venv/bin/activate`
- Reinstall: `pip install -r requirements.txt`

**"Browser not found" or "Package not available"**
- First try: `./scripts/setup-playwright-deps.sh` (auto-detects your Ubuntu version)
- Then: `python -m playwright install --with-deps`
- Check: `~/.cache/ms-playwright/` contains browser files

**Port 8501 already in use**
- Run on different port: `streamlit run app.py --server.port 8502`

**Permission denied on setup script**
- Make executable: `chmod +x scripts/setup-playwright-deps.sh`
- Run again: `./scripts/setup-playwright-deps.sh`

## Platform-Specific Notes

### Ubuntu 24.04
- Uses fallback Playwright builds (expected behavior)
- See [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md#ubuntu-2404-specific-setup)

### macOS
- May need Xcode Command Line Tools: `xcode-select --install`
- Use Homebrew for dependencies

### Windows
- WSL2 strongly recommended for Playwright compatibility
- Alternative: Use Docker (see Option C above)

## Next Steps

1. **Authentication**: See README.md "Authentication & Session Initialization"
2. **Testing**: Run `pytest -v tests/`
3. **Usage**: Start with `streamlit run app.py`
4. **Configuration**: Review `environment_config.py` for advanced settings

## Getting Help

- Check [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md) for dependency issues
- Review [README.md](README.md) for architecture and usage
- Consult test files in `tests/` for usage examples
- Enable debug logging: `export DEBUG=pw:api`

## Production Deployment

For production use:
1. Use Docker (reproducible environment)
2. Set `PLAYWRIGHT_HEADLESS=true`
3. Configure `.env` with production credentials
4. Consider using `docker-compose up -d` for background operation
5. Set up log rotation and monitoring

See [docs/PLAYWRIGHT_SETUP.md](docs/PLAYWRIGHT_SETUP.md#environment-variables) for environment variables.
