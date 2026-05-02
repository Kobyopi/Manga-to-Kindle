"""
utils/cleanup.py

Deletes temporary files created during the download/convert/send pipeline.
Called automatically after a successful Kindle delivery.

Three cleanup levels:
  clean_chapter_images - deletes raw downloaded images for one chapter
  clean_output_file - deletes one converted EPUB or CBZ after sending
  clean_all_temp - full wipe of downloads/ and output/ (used on app exit
  or when user triggers "Clear temp files" in settings)
"""

import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default temp directories - match the project structure
DOWNLOADS_DIR = Path("downloads")
OUTPUT_DIR = Path("output")


def clean_chapter_images(chapter_dir: Path) -> bool:
    """
    Delete the folder containing raw images for a single chapter.
    e.g. downloads/one_piece/ch1001/

    Returns True if deletd, False if path didn't exist or deletion failed.
    """
    if not chapter_dir.exists():
        return False
    try:
        shutil.rmtree(chapter_dir)
        logger.info(f"Cleaned chapter images: {chapter_dir}")
        return True
    except Exception as e:
        logger.warning(f"Failed to clean {chapter_dir}: {e}")
        return False


def clean_output_file(file_path: Path) -> bool:
    """
    Delete a single converted (EPUB or CBZ) from the output/ directory.
    Called immediately after a successful email send.

    Returns True if deleted successfully.
    """
    if not file_path.exists():
        return False
    try:
        file_path.unlink()
        logger.info(f"Cleaned output file: {file_path}")
        return True
    except Exception as e:
        logger.warning(f"Failed to delete {file_path}: {e}")
        return False


def clean_manga_downloads(manga_title: str) -> bool:
    """
    Delete all downloaded chapter folders for a specific manga title.
    e.g. downloads/one_piece/ (all chapters inside)

    Safe to call even if the folder doesn't exist.
    """
    safe = _safe_dirname(manga_title)
    manga_dir = DOWNLOADS_DIR / safe
    return clean_chapter_images(manga_dir)


def clean_all_temp(
    downloads: bool = True,
    output: bool = True,
) -> dict[str, int]:
    """
    Wipe all temporary files.
    Returns a dict with counts of files deleted per directory.

    downloads=True : clears downloads/ folder
    output=True : clears output/ folder
    """
    counts = {}

    if downloads and DOWNLOADS_DIR.exists():
        count = _count_files(DOWNLOADS_DIR)
        shutil.rmtree(DOWNLOADS_DIR)
        DOWNLOADS_DIR.mkdir()  # receate empty folder
        counts["downloads"] = count
        logger.info(f"Cleared downloads/ ({count} files)")

    if output and OUTPUT_DIR.exists():
        count = _count_files(OUTPUT_DIR)
        shutil.rmtree(OUTPUT_DIR)
        OUTPUT_DIR.mkdir()
        counts["output"] = count
        logger.info(f"Cleared output/ ({count} files)")

    return counts


def temp_usage_mb() -> dict[str, float]:
    """
    Return current disk usage of temp directories in MB.
    Used bu the settings panel to show "Temp files: X MB".
    """
    return {
        "downloads": _dir_size_mb(DOWNLOADS_DIR),
        "output": _dir_size_mb(OUTPUT_DIR),
    }


# ------------- helpers

def _dir_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 2)


def _count_files(path: Path) -> int:
    return sum(1 for f in path.rglob("*") if f.is_file())


def _safe_dirname(name: str) -> str:
    import re
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_").lower()