"""
app/scraper/parser.py

Low-level HTML parsing utilities shared by all site drivers.
All functions accept a BeautifulSoup object or a Tag and return
clean Python primitives - no driver-specific logic here.
"""

import re
import requests
from bs4 import BeautifulSoup, Tag


# -------------
# HTTP
# -------------

# Shared session with browser-like headers to avoid basic bot blocks
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def fetch_soup(url: str, timeout: int = 15) -> BeautifulSoup:
    """
    Fetch a URL and return a parsed BeautifulSoup tree.
    Raises requests.HTTPError on 4xx/5xx
    """
    resp = _SESSION.get(url, timeout=timeout)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "lxml")


def fetch_text(url: str, timeout: int = 15) -> str:
    """Return raw response text (used for JS-embedded data extraction)."""
    resp = _SESSION.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


# -------------
# Generic extraction helpers
# -------------

def safe_text(tag: Tag | None, default: str = "") -> str:
    """Return stripped inner text of a tag, or default if tag is None."""
    if tag is None:
        return default
    return tag.get_text(strip=True)


def safe_attr(tag: Tag | None, attr: str, default: str = "") -> str:
    """Return an attribute value from a tag, or default if missing."""
    if tag is None:
        return default
    return tag.get(attr, default) or default


def absolute_url(base: str, href: str) -> str:
    """
    Make a relative href absolute.
    e.g. absolute_url("https://fanfox.net", "/manga/one_piece/")
         → "https://fanfox.net/manga/one_piece/"
    """
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        scheme = base.split(":")[0]
        return f"{scheme}:{href}"
    if href.startswith("/"):
        # strip trailing slash from base, prepend href
        return base.rstrip("/") + href
    return base.rstrip("/") + "/" + href


def parse_chapter_number(text: str) -> float:
    """
    Extract a numeric chapter number from a messy string.
    e.g. "Vol.01 Ch.1046.5" → 1046.5
         "Ch.101"           → 101.0
         "Chapter 12"        → 12.0
    """
    # Prefer explicit Ch. / Chapter label
    match = re.search(r"(?:ch(?:apter)?\.?\s*)(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1))
    # Fall back to last number in string
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return float(nums[-1]) if nums else 0.0


def parse_rating(text: str) -> float:
    """Extract a float rating from a string like '4.84' or '4.84/5'."""
    match = re.search(r"(\d+\.\d+)", text)
    return float(match.group(1)) if match else 0.0


def clean_status(raw: str) -> str:
    """Normalise status strings to Ongoing / Completed / Hiatus."""
    r = raw.strip().lower()
    if "complet" in r:
        return "Completed"
    if "hiatus" in r or "paused" in r:
        return "Hiatus"
    if "ongoing" in r or "publishing" in r:
        return "Ongoing"
    return raw.strip().title()