# LinkedIn Scraper

Automated LinkedIn profile and connection data scraper using Playwright and BeautifulSoup.

## Prerequisites

- Python 3.8+
- Ubuntu 26.04 / Debian-based system

## Installation

1. Clone the repository
2. Create a Python virtual environment: `python -m venv venv`
3. Set Playwright platform override: `export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64`
4. Install dependencies: `pip install -r requirements.txt`
5. Verify installation: `python -m playwright install`
6. Configure credentials: Copy `.env.example` to `.env` and add your LinkedIn credentials

## Usage

Run the Streamlit application:
```bash
streamlit run app.py
```

## Security Warnings

- **Never commit `.env`** with real credentials to version control
- **Never commit `*.db`** or `*.json` files containing authentication tokens
- Credentials should only be stored locally in `.env` (excluded via `.gitignore`)

## Project Structure

- `app.py` - Streamlit application entry point
- `scraper.py` - Web scraping orchestration
- `session_manager.py` - Browser session management
- `database.py` - Data persistence layer

## License

Proprietary
