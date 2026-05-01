"""
app/scraper/image_downloader.py

Downloads chapter page images concurrently into a temp directory.
Reports progress via a callback so the GUI queue panel can update live.

Usage:
    downloader = ImageDownloader()
    paths = downloader.download_chapter(
        page_urls   = ["https://...jpg", ...],
        dest_dir   = Path("/temp/manga/one_piece/ch1001"),
        on_progress   = lambda done, total: print(f"{done}/{total}"),
    )
"""

import os
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import requests

# Reuse session with browser headers (same as parser.py)
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fanfox.net",  # most CDNs require a valid referer
})


class ImageDownloader:

    DEFAULT_WORKERS = 6   # concurrent image downloads
    DEFAULT_RETRIES = 3
    RETRY_DELAY_S = 1.5

    def __init__(self, workers: int = DEFAULT_WORKERS):
        self.workers = workers

    def download_chapter(
        self,
        page_urls: list[str],
        dest_dir: Path,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> list[Path]:
        """
        Download all pages of a chapter into dest_dir.

        page_urls  : ordered list of direct image URLs
        dest_dir  : directory to save files into (created if missing)
        on_progress  : callback(completed_count, total_count)

        Returns ordered list of local file paths.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        total = len(page_urls)
        results: dict[int, Path] = {}  # index → path, for ordering
        done_count = 0
        lock = threading.Lock()

        def download_one(index: int, url: str) -> tuple[int, Path | None]:
            ext = self._guess_extension(url)
            filename = f"{index:04d}{ext}"
            dest = dest_dir / filename

            # Skip if already downloaded (resume support)
            if dest.exists() and dest.stat().st_size > 0:
                return index, dest

            for attempt in range(self.DEFAULT_RETRIES):
                try:
                    resp = _SESSION.get(url, timeout=20, stream=True)
                    resp.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            f.write(chunk)
                    return index, dest
                except Exception as e:
                    if attempt < self.DEFAULT_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY_S)
                    else:
                        print(f"[ImageDownloader] Failed {url}: {e}")
                        return index, None
        
        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            futures = {
                pool.submit(download_one, i, url): i
                for i, url in enumerate(page_urls)
            }
            for future in as_completed(futures):
                idx, path = future.result()
                with lock:
                    if path:
                        results[idx] = path
                    done_count += 1
                    if on_progress:
                        on_progress(done_count, total)

        # Return paths in page order, skipping any failed downloads
        return [results[i] for i in sorted(results)]

    def download_cover(self, url: str, dest: Path) -> Path | None:
        """Download a single cover image. Returns path or None on failure."""
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            resp = _SESSION.get(url, timeout=15)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                f.write(resp.content)
            return dest
        except Exception as e:
            print(f"[ImageDownloader] Cover download failed {url}: {e}")
            return None

    @staticmethod
    def _guess_extension(url: str) -> str:
        """Infer file extension from URL, defaulting to .jpg."""
        clean = url.split("?")[0].split("#")[0]
        _, ext = os.path.splitext(clean)
        return ext.lower() if ext.lower() in (".jpg", ".jpeg", ".png", ".webp", ".gif") else ".jpg"
        