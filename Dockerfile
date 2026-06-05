FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright browsers
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core browser runtime dependencies
    libc6 \
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
    # Font and rendering
    libfontconfig1 \
    libfreetype6 \
    libharfbuzz0b \
    # Media codecs
    libopus0 \
    libvpx9 \
    libwebp7 \
    libwoff1 \
    chromium-codecs-ffmpeg \
    # Markup and compression
    libxml2 \
    libxslt1.1 \
    # Character encoding and events
    libicu74 \
    libevent-2.1-7t64 \
    # Game input
    libmanette-0.2-0 \
    # Clean up apt cache
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN python -m playwright install chromium firefox webkit

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 scraper && chown -R scraper:scraper /app
USER scraper

# Set environment for headless operation
ENV PLAYWRIGHT_HEADLESS=true
ENV PYTHONUNBUFFERED=1

# Default command: run Streamlit app
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
