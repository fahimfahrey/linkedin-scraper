#!/usr/bin/env python3
"""Verify LinkedIn scraper project setup. Checks Python version, dependencies, and Playwright browser availability."""

import sys
import subprocess


def check_python_version():
    """Verify Python 3.8+"""
    version = sys.version_info
    if version >= (3, 8):
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} < 3.8")
        return False


def check_imports():
    """Verify core dependencies installed"""
    packages = ["playwright", "playwright_stealth", "bs4", "pandas", "pydantic", "streamlit"]
    all_ok = True

    for pkg in packages:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} not found")
            all_ok = False

    return all_ok


def check_playwright_browser():
    """Verify Chromium available"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium", "--dry-run"],
            timeout=30,
            capture_output=True,
            text=True
        )

        if result.returncode == 0 or "browser is already installed" in result.stdout.lower() or "chromium" in result.stdout.lower():
            print("✅ Playwright Chromium browser available")
            return True
        else:
            print("❌ Playwright Chromium browser not found")
            return False
    except subprocess.TimeoutExpired:
        print("❌ Playwright Chromium browser not found")
        return False
    except Exception:
        print("❌ Playwright Chromium browser not found")
        return False


def main():
    """Run all verification checks"""
    print("=" * 50)
    print("LinkedIn Scraper Setup Verification")
    print("=" * 50)

    checks = [
        ("Python version", check_python_version),
        ("Dependencies", check_imports),
        ("Playwright browser", check_playwright_browser),
    ]

    results = []
    for name, check_func in checks:
        results.append(check_func())
        print()

    print("=" * 50)

    if all(results):
        print("✅ Setup verification PASSED")
        return 0
    else:
        print("❌ Setup verification FAILED")
        print("Run: pip install -r requirements.txt")
        print("Then: python -m playwright install chromium")
        return 1


if __name__ == '__main__':
    sys.exit(main())
