"""
app/scraper/mangatown_driver.py

Concrete scraper driver for https://www.mangatown.com
MangaTown shares the same CDN (fmcdn.mangahere.com) and very similar
HTML structure as FanFox, so the selectors are close but not identical.

URL patterns observed:
  Directory  : https://www.mangatown.com/directory/{page}/  (no genre in URL)
  Hot by tag  : https://www.mangatown.com/hot/{genre}/
  Completed  : https://www.mangatown.com/completed/
  Search  : https://www.mangatown.com/search.php?name={q}&page={n}
  Manga  : https://www.mangatown.com/manga/{slug}/
  Chapter  : https://www.mangatown.com/manga/{slug}/{vol}/{chapter}/
"""

import re
import urllib.parse
from app.scraper.base_scraper import BaseScraper, MangaSummary, MangaDetail, Chapter
from app.scraper.parser import(
    fetch_soup, fetch_text, safe_text, safe_attr,
    absolute_url, parse_chapter_number, parse_rating, clean_status
)


class MangaTownDriver(BaseScraper):

    SOURCE_NAME = "MangaTown"
    BASE_URL = "https://www.mangatown.com"

    # Tags/genres available via /hot/{genre}/ - scraped live in get_genres()
    # These are also used for sidebar category buttons
    _STATIC_GENRES = [
        "Action", "Adventure", "Comedy", "Drama", "Fantasy", "Horror",
        "Josei", "Martial Arts", "Mecha", "Mystery", "Psychological",
        "Romance", "School Life", "Sci-fi", "Seinen", "Shoujo",
        "Shounen", "Slice of Life", "Sports", "Supernatural",
        "Tragedy", "Vampire", "Webtoons", "Yaoi", "Yuri", "Harem",
    ]

    # ------------- genres

    def get_genres(self) -> list[str]:
        """
        MangaTown doesn't have a single genre directory page, so we return
        the curated static list (accurate as of site inspection).
        Optionally, scrape /hot/ for the tag bar for a live version.
        """
        try:
            soup = fetch_soup(f"{self.BASE_URL}/hot/")
            tags = soup.select("ul.tag-items a, div.manga-hot-genres a")
            live = [safe_text(t) for t in tags if safe_text(t)]
            return live if live else self._STATIC_GENRES
        except Exception:
            return self._STATIC_GENRES

    # ------------- browse

    def browse(
        self,
        genre: str | None = None,
        status: str | None = None,
        sort: str = "popularity",
        page: int = 1,
    ) -> list[MangaSummary]:

        if genre:
            # Hot manga by genre tag
            slug = genre.lower().replace(" ", "-")
            url = f"{self.BASE_URL}/hot/{slug}/"
        elif status and status.lower() == "completed":
            url = f"{self.BASE_URL}/completed/"
        else:
            # General directory, paginated
            url = f"{self.BASE_URL}/directory/{page}/"
        
        soup = fetch_soup(url)
        return self._parse_directory_page(soup)

    def _parse_directory_page(self, soup) -> list[MangaSummary]:
        results = []

        # MangaTown lists: ul.manga-list or ul.updates
        items = soup.select("ul.manga-list li, ul.updates li")
        if not items:
            # Hot page uses a different structure
            items = soup.select("div.manga-hot-item, div.cover_item")

        for item in items:
            title_tag = items.select_one("a.manga_cover, a[href*='/manga/']")
            if not title_tag:
                continue

            title = safe_attr(title_tag, "title") or safe_text(title_tag)
            href = safe_attr(title_tag, "href")
            url = absolute_url(self.BASE_URL, href)

            cover_tag = item.select_one("img")
            cover = safe_attr(cover_tag, "src") if cover_tag else ""

            # Chapters
            ch_tag = item.select_one("li.new_chapter a, p.chapter a")
            ch_text = safe_text(ch_tag) if ch_tag else ""
            chapters = int(parse_chapter_number(ch_text)) if ch_text else 0

            # Genres - some list views include them
            genre_tags = item.select("p.keyWord a, span.genre a")
            genres = [safe_text(g) for g in genre_tags if safe_text(g)]

            # Rating
            rating_tag = item.select_one("span.score, p.score")
            rating = parse_rating(safe_text(rating_tag)) if rating_tag else 0.0

            slug_match = re.search(r"/manga/([^/]+)/", href)
            source_id = slug_match.group(1) if slug_match else href

            results.append(MangaSummary(
                title=title,
                url=url,
                cover_url=cover,
                genres=genres,
                chapters=chapters,
                rating=rating,
                source=self.SOURCE_NAME,
                source_id=source_id,
            ))

        return results

    # ------------- search

    def search(self, query: str, page: int = 1) -> list[MangaSummary]:
        q = urllib.parse.quote_plus(query)
        url = f"{self.BASE_URL}/search.php?name={q}&page={page}"
        soup = fetch_soup(url)
        return self._parse_directory_page(soup)

    # ------------- detail

    def get_detail(self, manga: MangaSummary) -> MangaDetail:
        soup = fetch_soup(manga.url)

        # Cover
        cover_tag = soup.select_one("div.detail_info img, img.detail-info-cover-img")
        cover = safe_attr(cover_tag, "src") if cover_tag else manga.cover_url

        # Status
        status = manga.status
        for li in soup.select("div.detail_info ul li"):
            label = safe_text(li.select_one("b"))
            if "status" in label.lower():
                status = clean_status(safe_text(li).replace(label, "").strip())
                break

        # Rating
        rating_tag = soup.select_one("span#current_rating, span.score")
        rating = parse_rating(safe_text(rating_tag)) if rating_tag else manga.rating

        # Author
        author = ""
        for li in soup.select("div.detail_info ul li"):
            label = safe_text(li.select_one("b"))
            if "author" in label.lower():
                a = li.select_one("a")
                author = safe_text(a) if a else safe_text(li).replace(label, "").strip()
                break

        # Genres
        genre_tags = soup.select("div.detail_info ul li a[href*='/manga/'], p.detail-info-right-tag-list a")
        genres = [safe_text(g) for g in genre_tags if safe_text(g)]

        # Description
        desc_tag = soup.select_one("span#show, div.manga_summary")
        description = safe_text(desc_tag)

        # Chapter list
        chapter_list = []
        for li in soup.select("div.chapter_content ul.chapter_list li"):
            a = li.select_one("a")
            if not a:
                continue
            href = safe_attr(a, "href")
            ch_url = absolute_url(self.BASE_URL, href)
            ch_title = safe_attr(a, "title") or safe_text(a)
            date_tag = li.select_one("span.time")
            date = safe_text(date_tag) if date_tag else ""
            num = parse_chapter_number(ch_title)

            vol_match = re.search(r"[Vv]ol\.?\s*(\w+)", ch_title)
            volume = vol_match.group(1) if vol_match else ""

            chapter_list.append(Chapter(
                title=ch_title,
                url=ch_url,
                number=num,
                volume=volume,
                date=date,
            ))

        chapter_list.sort(key=lambda c: c.number)

        return MangaDetail(
            title=manga.title,
            url=manga.url,
            cover_url=cover,
            genres=genres,
            status=status,
            chapters=len(chapter_list),
            rating=rating,
            source=self.SOURCE_NAME,
            source_id=manga.source_id,
            description=description,
            author=author,
            chapter_list=chapter_list,
        )

    # ------------- page images

    def get_page_urls(self, chapter: Chapter) -> list[str]:
        """
        MangaTown chapter URLs look like:
          /manga/{slug}/v{vol}/c{num}/
        The reader page lists all page image URLs in a <select> or JS var.
        """
        text = fetch_text(chapter.url)

        # Strategy 1: JS variable - var img_arr=[...] or similar
        match = re.search(r"var\s+img_arr\s*=\s*\[([^\]]+)\]", text)
        if match:
            raw = match.group(1)
            urls = re.findall(r'"(https?://[^"]+)"', raw)
            if urls:
                return urls

        # Strategy 2: <select class="page_select"> <option value="url">
        soup = __import__("bs4").BeautifulSoup(text, "lxml")
        options = soup.select("select.page_select option")
        if options:
            return [
                absolute_url(self.BASE_URL, safe_attr(o, "value"))
                for o in options
                if safe_attr(o, "value")
            ]

        # Strategy 3: count pages from select, build incremental URLs
        count_match = re.search(r"var\s+imagecount\s*=\s*(\d+)", text)
        total = int(count_match.group(1)) if count_match else 1
        base = chapter.url.rstrip("/")
        return [f"{base}/{i}.html" for i in range(1, total + 1)]

    def get_image_url_from_page(self, page_url: str) -> str:
        """Extract actual image src from a reader page."""
        text = fetch_text(page_url)

        match = re.search(r'var\s+imageurl\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1)

        soup = __import__("bs4").BeautifulSoup(text, "lxml")
        img = soup.select_one("img#image, section.read_img img")
        return safe_attr(img, "src") if img else ""