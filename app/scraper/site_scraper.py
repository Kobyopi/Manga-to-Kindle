"""
app/scraper/site_scraper.py

AggregatorScraper - the single object the rest of the app talks to.
It owns a registry of active drivers and can:
  - Query all active sources in parallel
  - Merge + deduplicate results by title
  - Route detail/page requests to the correct driver

Adding a new source:
  1. Write a driver in app/scraper/my_site_driver.py
  2. Import it here and add an instance to AVAILABLE_DRIVERS
  3. Done - no other file needs to change
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.scraper.base_scraper import BaseScraper, MangaSummary, MangaDetail, Chapter
from app.scraper.fanfox_driver import FanFoxDriver
from app.scraper.mangatown_driver import MangaTownDriver


# -------------
# Driver registry - add new drivers here
# -------------

AVAILABLE_DRIVERS: dict[str, BaseScraper] = {
    "FanFox": FanFoxDriver(),
    "MangaTown": MangaTownDriver(),
}


# -------------
# Aggregator
# -------------

class AggregatorScraper:
    """
    Unified scraping interface used by the GUI.

    active_sources: list of driver names to query (subset of AVAILABLE_DRIVERS).
    Controlled by the user in Settings.
    """

    def __init__(self, active_sources: list[str] | None = None):
        # Default: all available drivers enabled
        self._active: list[str] = active_sources or list(AVAILABLE_DRIVERS.keys())
        self._lock = threading.Lock()

    # ------------- source control

    def set_active_sources(self, names: list[str]):
        with self._lock:
            self._active = [n for n in names if n in AVAILABLE_DRIVERS]

    def get_active_sources(self) -> list[str]:
        with self._lock:
            return list(self._active)

    def get_all_source_names(self) -> list[str]:
        return list(AVAILABLE_DRIVERS.keys())

    def get_driver(self, source_name: str) -> BaseScraper | None:
        return AVAILABLE_DRIVERS.get(source_name)

    # ------------- genres per site

    def get_genres_per_source(self) -> dict[str, list[str]]:
        f"""
        Returns {source_name: [genre, ...]} for each active source.
        Used to build per-site category sections in the sidebar.
        """
        result = {}
        with ThreadPoolExecutor(max_workers=len(self._active)) as pool:
            futures = {
                pool.submit(AVAILABLE_DRIVERS[name].get_genres): name
                for name in self._active
                if name in AVAILABLE_DRIVERS
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result[name] = future.result()
                except Exception as e:
                    result[name] = []
                    print(f"[AggregatorScraper] get_genres failed for {name}: {e}")
        return result

    # ------------- browse

    def browse(
        self,
        source: str | None = None,
        genre: str | None = None,
        status: str | None = None,
        sort: str = "popularity",
        page: int = 1,
    ) -> list[MangaSummary]:
        """
        Fetch manga listings.
        source=None  → query all active sources in parallel and merge.
        source="X"   → query only that driver.
        Results from multiple sources are interleaved and deduplicated by title.
        """
        targets = [source] if source else self._active

        all_results: list[MangaSummary] = []
        with ThreadPoolExecutor(max_workers=len(targets)) as pool:
            futures = {
                pool.submit(
                    AVAILABLE_DRIVERS[name].browse,
                    genre=genre, status=status, sort=sort, page=page
                ): name
                for name in targets
                if name in AVAILABLE_DRIVERS
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    print(f"[AggregatorScraper] browse failed for {name}: {e}")

        return self._deduplicate(all_results)

    # ------------- search

    def search(
        self,
        query: str,
        source: str | None = None,
        page: int = 1,
    ) -> list[MangaSummary]:
        targets = [source] if source else self._active

        all_results: list[MangaSummary] = []
        with ThreadPoolExecutor(max_workers=len(targets)) as pool:
            futures = {
                pool.submit(AVAILABLE_DRIVERS[name].search, query, page): name
                for name in targets
                if name in AVAILABLE_DRIVERS
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    all_results.extend(future.result())
                except Exception as e:
                    print(f"[AggregatorScraper] search failed for {name}: {e}")

        return self._deduplicate(all_results)

    # ------------- detail

    def get_detail(self, manga: MangaSummary) -> MangaDetail:
        """Route to the correct driver based on manga.source."""
        driver = AVAILABLE_DRIVERS.get(manga.source)
        if not driver:
            raise ValueError(f"No driver registered for source: {manga.source!r}")
        return driver.get_detail(manga)

    # ------------ page images

    def get_page_urls(self, chapter: Chapter, source: str) -> list[str]:
        driver = AVAILABLE_DRIVERS.get(source)
        if not driver:
            raise ValueError(f"No driver registered for source: {source!r}")
        return driver.get_page_urls(chapter)
    
    def get_image_url_from_page(self, page_url: str, source: str) -> str:
        driver = AVAILABLE_DRIVERS.get(source)
        if not driver:
            return ""
        # Only FanFox-style drivers have this method
        if hasattr(driver, "get_image_url_from_page"):
            return driver.get_image_url_from_page(page_url)
        return page_url

    # ------------- deduplication

    @staticmethod
    def _deduplicate(results: list[MangaSummary]) -> list[MangaSummary]:
        """
        Merge entries with the same normalised title.
        When a title appears in multiple sources, keep the entry with the most
        chapters and attach all source names to manga.source as "FanFox, MangaTown".
        """
        seen: dict[str, MangaSummary] = {}
        for manga in results:
            key = manga.title.lower().strip()
            if key not in seen:
                seen[key] = manga
            else:
                existing = seen[key]
                # Prefer the entry with more chapters
                if manga.chapters > existing.chapters:
                    manga.source = f"{existing.source}, {manga.source}"
                    seen[key] = manga
                else:
                    existing.source = f"{existing.source}, {manga.source}"
        return list(seen.value())

