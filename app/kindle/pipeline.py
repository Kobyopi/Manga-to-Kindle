"""
app/kindle/pipeline.py

The Pipeline class is the single object that runs a full
download -> convert -> send -> cleanup job for one manga chapter.

It is designed to run in a worker thread (never on the GUI thread).
Progress is reported back via a callback so the DownloadQueue panel
can update live without blocking.

Usage (called from main_window.py in a threading.Thread):

    def run_job(manga, chapter, fmt, on_progress):
        pipeline = Pipeline(on_progress=on_progress)
        pipeline.run(manga, chapter, fmt)

    threading.Thread(
        target=run_job,
        args=(manga, chapter, "epub", progress_cb),
        daemon=True,
    ).start()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from app.scraper.site_scraper import AggregatorScraper
from app.scraper.base_scraper import MangaSummary, Chapter
from app.scraper.image_downloader import ImageDownloader
from app.kindle.converter import MangaConverter
from app.kindle.email_sender import KindleSender
from app.utils.cleanup import clean_chapter_images, clean_output_file

logger = logging.getLogger(__name__)

# Directories - match project structure
DOWNLOADS_DIR = Path("downloads")
OUTPUT_DIR = Path("output")


# -------------
# Progress model
# -------------

class PipelineStage:
    FETCH_PAGES = "Fetching page list..."
    DOWNLOADING = "Downloading images..."
    CONVERTING = "Converting..."
    SENDING = "Sending to Kindle..."
    CLEANUP = "Cleaning up..."
    DONE = "Done ✓"


# -------------
# Pipeline
# -------------

class Pipeline:
    """
    Orchestrates one complete send-to-Kindle job.

    on_progress(progress: float, status: str) is called throughout so the
    GUI queue panel can show a live progress bar.
    """

    def __init__(
        self,
        scraper: AggregatorScraper | None = None,
        on_progress: Callable[[float, str], None] | None = None,
        delete_after_send: bool = True,
    ):
        self._scraper = scraper or AggregatorScraper()
        self._progress = on_progress or (lambda p, s: None)
        self._delete = delete_after_send

    # ------------- public

    def run(
        self,
        manga: MangaSummary | dict,
        chapter: Chapter | dict,
        fmt: str = "epub",   # "epub" | "cbz"
        author: str = "Unknown",
        cover_path: Path | None = None,
    ) -> Path:
        """
        Full pipeline for one chapter.
        Returns the path of the sent file (already deleted if delete_after_send).
        Raises on any unrecoverable error.
        """
        # Accept both dataclass and plain dict (from GUI layer)
        manga = self._coerce_manga(manga)
        chapter = self._coerce_chapter(chapter)
        fmt = fmt.lower().strip()

        title = manga.title
        ch_title = chapter.title
        source = manga.source.split(",")[0].strip()  # primary source

        logger.info(f"Pipeline start: {title} / {ch_title} [{fmt}]")

        # - Stage 1: get page URLs
        self._progress(0.05, PipelineStage.FETCH_PAGES)
        page_urls = self._scraper.get_page_urls(chapter, source=source)

        if not page_urls:
            raise RuntimeError(
                f"No page URLs found for {title} / {ch_title}. "
                "The chapter may be unavailable or the scraper needs updating."
            )

        # Resolve per-page image URLs (FanFox wraps each image in its own HTML page)
        image_urls = self._resolve_image_urls(page_urls, source)

        # - Stage 2: download images
        safe_title = _safe(title)
        safe_ch = _safe(ch_title)
        chapter_dir = DOWNLOADS_DIR / safe_title / safe_ch

        downloader = ImageDownloader()

        def dl_progress(done: int, total: int):
            self._progress(
                0.10 + 0.45 * (done / max(total, 1)),
                f"{PipelineStage.DOWNLOADING} ({done}/{total})",
            )

        image_paths = downloader.download_chapter(
            page_urls = image_urls,
            dest_dir = chapter_dir,
            on_progress = dl_progress,
        )

        if not image_paths:
            raise RuntimeError("Image download failed - no files saved.")

        # - Stage 3: convert
        self._progress(0.56, f"Converting to {fmt.upper()}...")

        def conv_progress(p: float, s: str):
            self._progress(0.56 + 0.30 * p, s)

        converter = MangaConverter(
            output_dir = OUTPUT_DIR,
            on_progress = conv_progress,
        )

        if fmt == "cbz":
            out_file = converter.to_cbz(
                image_paths = image_paths,
                title = title,
                chapter = ch_title,
            )
        else:
            out_file = converter.to_epub(
                image_paths = image_paths,
                title = title,
                chapter = ch_title,
                author = author,
                cover_path = cover_path,
            )

        # - Stage 4: send
        self._progress(0.87, PipelineStage.SENDING)

        def send_progress(p: float, s: str):
            self._progress(0.87 + 0.10 * p, s)

        sender = KindleSender(on_progress=send_progress)
        sender.send(out_file, title=f"{title} - {ch_title}")

        # - Stage 5: cleanup
        self._progress(0.98, PipelineStage.CLEANUP)

        if self._delete:
            clean_chapter_images(chapter_dir)
            clean_output_file(out_file)

        self._progress(1.0, PipelineStage.DONE)
        logger.info(f"Pipeline complete: {title} / {ch_title}")
        return out_file

    # ------------- helpers

    def _resolve_imae_urls(self, page_urls: list[str], source: str) -> list[str]:
        """
        For sites like FanFox where each "page URL" is actually an HTML reader
        page (not a direct image), extract the real image src from each one.
        FOr sites that return direct image URLs, this is a no-op.
        """
        # Heuristic: if URLs end with .html they need resolution
        if not page_urls or not page_urls[0].endswith(".html"):
            return page_urls

        self._progress(0.06, "Resolving image URLs...")
        image_urls = []
        total = len(page_urls)

        for i, page_url in enumerate(page_urls):
            self._progress(
                0.06 + 0.04 * (i / max(total, 1)),
                f"Resolving page {i + 1}/{total}..."
            )
            real_url = self._scraper.get_image_url_from_page(page_url, source)
            if real_url:
                image_urls.append(real_url)

        return image_urls

    @staticmethod
    def _coerce_manga(manga) -> MangaSummary:
        if isinstance(manga, MangaSummary):
            return manga
        from app.scraper.base_scraper import MangaSummary
        return MangaSummary(
            title = manga.get("title", ""),
            url = manga.get("url", ""),
            cover_url = manga.get("cover_url", ""),
            genres = manga.get("genres", []),
            status = manga.get("status", ""),
            chapters = manga.get("chapters", 0),
            source = manga.get("source", ""),
            source_id = manga.get("source_id", ""),
        )

    @staticmethod
    def _coerce_chapter(chapter) -> Chapter:
        if isinstance(chapter, Chapter):
            return chapter
        from app.scraper.base_scraper import Chapter
        return Chapter(
            title = chapter.get("title", ""),
            url = chapter.get("url", ""),
            number = chapter.get("number", 0.0),
            volume = chapter.get("volume", ""),
            date = chapter.get("date", ""),
        )


def _safe(text: str) -> str:
    import re
    return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_").lower()