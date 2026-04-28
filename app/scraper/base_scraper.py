"""
app/scraper/base_scraper.py

Abstract base class that every site driver must implement.
The engine (site_scraper.py) only talks to this interface - it ever
knows which concrete site it is talking to.  Adding a new source means
writing one new SiteDriver subclass, nothing else.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# -------------
# Shared data models (lightweight - full persistence lives in data/models.py)
# -------------

@dataclass
class MangaSummary:
    """Minimal info needed to populate the browser grid/list."""
    title: str
    url: str   # canonical manga page URL
    cover_url: str = ""
    genres: list[str] = field(default_factory=list)
    status: str = ""   # "Ongoing" | "Completed" | "Hiatus"
    chapters: int = 0
    rating: float = 0.0
    source: str = ""   # driver name, e.g. "FanFox"
    source_id: str = ""   # slug or ID on the source site


@dataclass
class Chapter:
    title: str
    url: str
    number: float = 0.0
    volume: str = ""
    date: str = ""


@dataclass
class MangaDetail(MangaSummary):
    """Full info shown in the detail panel."""
    description: str = ""
    author: str = ""
    chapter_list: list[Chapter] = field(default_factory=list)


# -------------
# Abstract driver interface
# -------------

class BaseScraper(ABC):
    """
    Every site driver must implement these five methods.
    All methods are synchronous - threading is handled by the caller.
    """

    # Human-readable source name shown in the sidebar
    SOURCE_NAME: str = "Unknown"

    # Base URL of the site - used to build absolute links
    BASE_URL: str = ""

    # ------- catalogue -------

    @abstractmethod
    def get_genres(self) -> list[str]:
        """Return all genre/category names available on this site."""
        ...

    @abstractmethod
    def browse(
        self,
        genre: str | None = None,
        status: str | None = None,
        sort: str = "popularity",
        page: int = 1,
    ) -> list[MangaSummary]:
        """
        Return one page of manga listings.
        genre  : genre slug (e.g. "action") or None for all
        status  : "ongoing" | "completed" | None for all
        sort  : "popularity" | "rating" | "alphabetical" | "latest"
        page  : 1-based page number
        """
        ...

    @abstractmethod
    def search(self, query: str, page: int = 1) -> list[MangaSummary]:
        """Full-text search on the source site."""
        ...

    # ------- detail -------

    @abstractmethod
    def get_detail(self, manga: MangaSummary) -> MangaDetail:
        """Fetch full metadata + chapter list for a single manga."""
        ...

    # ------- pages -------

    @abstractmethod
    def get_page_urls(self, chapter: Chapter) -> list[str]:
        """Return ordered list of image URLs for a chapter's pages."""
        ...