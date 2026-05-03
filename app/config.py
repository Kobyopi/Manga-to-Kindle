from pathlib import Path

BASE_DIR = Path(__file__).parent.parent  # root
DOWNLOADS_DIR = BASE_DIR / "downloads"
OUTPUT_DIR = BASE_DIR / "output"
CACHE_DIR = BASE_DIR / "cache"
DB_PATH = BASE_DIR / "manga.db"
SETTINGS_PATH = BASE_DIR / "settings.json"

# Ensure runtime directories exist on import
for _dir in (DOWNLOADS_DIR, OUTPUT_DIR, CACHE_DIR):
    _dir.mkdir(exist_ok=True)