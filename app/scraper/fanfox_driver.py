"""
app/scraper/fanfox_driver.py

Concrete scraper driver for https://fanfox.net
Implements BaseScraper using the shared parser utilities.

URL patterns observed:
  Directory : https://fanfox.net/directory/{genre}/{sort}/?page={n}
  Status  : https://fanfox.net/directory/ongoing  (or /completed/)
  Search  : https://fanfox.net/search.php?title={q}&page={n}
  Manga  : https://fanfox.net/manga/{slug}/
  Chapter  : https://fanfox.net/manga/{slug}/c{num}/{page}.html
             - page image URLs are embedded as JS vars in each page
"""

import re
from app.scraper.base_scraper import BaseScraper, MangaSummary, MangaDetail, Chapter
from app.scraper.parser import(
    fetch_soup, fetch_text, safe_text, safe_attr,
    absolute_url, parse_chapter_number, parse_rating, clean_status
)


class FanFoxDriver(BaseScraper):

    SOURCE_NAME = "FanFox"
    BASE_URL = "https://fanfox.net"

    # FanFox sort slugs (appended as ?az, ?rating, etc.)
    _SORT_MAP = {
        "popularity": "",
        "alphabetical": "?az",
        "rating": "?rating",
        "latest": "?latest",
    }

    # ------------- genres

    def get_genres(self) -> list[str]:
        soup = fetch_soup(f"{self.BASE_URL}/directory/")
        genre_links = soup.select("div.manga-list-1-more a")
        # Fall back to sidebar ul if the above selector misses
        if not genre_links:
            genre_links = soup.select("ul.tag-items a")
        genres = []
        for a in genre_links:
            text = safe_text(a)
            if text and text.lower() != "all":
                genres.append(text)
        return genres

    # ------------- browse

    def browse(
        self,
        genre: str | None = None,
        status: str | None = None,
        sort: str = "popularity",
        page: int = 1,
    ) -> list[MangaSummary]:

        # Build URL
        genre_slug = genre.lower().replace(" ", "-") if genre else ""
        sort_param = self._SORT_MAP.get(sort, "")

        if genre_slug:
            url = f"{self.BASE_URL}/directory/{genre_slug}/{sort_param}"
        elif status and status.lower() in ("ongoing", "completed"):
            url = f"{self.BASE_URL}/directory/{status.lower()}/"
        else:
            url = f"{self.BASE_URL}/directory/{sort_param}"

        if page > 1:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}page={page}"

        soup = fetch_soup(url)
        return self._parse_directory_page(soup)

    def _parse_directory_page(self, soup) -> list[MangaSummary]:
        results = []
        # Each manga is in an <li> inside .manga-list-1
        for li in soup.select("ul.manga-list-1 li"):
            cover_tag = li.select_one("img")
            title_tag = li.select_one("p.title a, a.manga-list-1-det-con-a")
            if not title_tag:
                title_tag = li.select_one("a[href*='/manga/']")
            if not title_tag:
                continue

            title = safe_text(title_tag)
            href = safe_attr(title_tag, "href")
            url = absolute_url(self.BASE_URL, href)
            cover = safe_attr(cover_tag, "src") if cover_tag else ""

            # Chapter count from text like "Ch.1181"
            ch_tag = li.select_one("p.manga-list-1-det-con-t a")
            ch_text = safe_text(ch_tag) if ch_tag else ""
            chapters = int(parse_chapter_number(ch_text)) if ch_text else 0

            # Genres
            genre_tags = li.select("p.manga-list-1-det-con-g a")
            genres = [safe_text(g) for g in genre_tags if safe_text(g)]

            # Rating
            rating_tag = li.select_one("p.manga-list-1-det-con-r")
            rating = parse_rating(safe_text(rating_tag)) if rating_tag else 0.0

            # Slug for source_id
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
        import urllib.parse
        q = urllib.parse.quote_plus(query)
        url = f"{self.BASE_URL}/search.php?title={q}&page={page}"
        soup = fetch_soup(url)
        return self._parse_directory_page(soup)

    # ------------- detail

    def get_detail(self, manga: MangaSummary) -> MangaDetail:
        soup = fetch_soup(manga.url)

        # Cover
        cover_tag = soup.select_one("img.detail-info-cover-img")
        cover = safe_attr(cover_tag, "src") if cover_tag else manga.cover_url

        # Status - appears next to title as plain text mode
        status_tag = soup.select_one("span.detail-info-right-title-tip")
        status = clean_status(safe_text(status_tag)) if status_tag else manga.status

        # Rating
        rating_tag = soup.select_one("span#rate_score")
        rating = parse_rating(safe_text(rating_tag)) if rating_tag else manga.rating

        # Author
        author_tag = soup.select_one("p.detail-info-right-say a")
        author = safe_text(author_tag) if author_tag else ""

        # Genres
        genre_tags = soup.select("p.detail-info-right-tag-list a")
        genres = [safe_text(g) for g in genre_tags if safe_text(g)]

        # Description
        desc_tag = soup.select_one("p.fullcontent")
        if not desc_tag:
            desc_tag = soup.select_one("div.detail-info-right-content")
        description = safe_text(desc_tag)

        # Chapter list - each <li> in #chapterlist ul
        chapter_list = []
        for li in soup.select("ul.detail-main-list li"):
            a = li.select_one("a")
            if not a :
                continue
            href = safe_attr(a, "href")
            ch_url = absolute_url(self.BASE_URL, href)
            ch_title_tag = a.select_one("p.title3")
            ch_title = safe_text(ch_title_tag) if ch_title_tag else safe_text(a)
            date_tag = a.select_one("p.title2")
            date = safe_text(date_tag) if date_tag else ""
            num = parse_chapter_number(ch_title)

            # Volume
            vol_match = re.search(r"[Vv]ol\.?s*(\w+)", ch_title)
            volume = vol_match.group(1) if vol_match else ""

            chapter_list.append(Chapter(
                title=ch_title,
                url=ch_url,
                number=num,
                volume=volume,
                date=date,
            ))

        # Sort ascending by chapter number
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
        Fanfox embeds page image URLs as a JavaScript variable.
        Pattern: var guidkey="..."; var imagecount=N;
        Each page URL is fetched individually but we can derive them
        by incrementing the page number in the chapter URL.
        Strategy: fetch page 1, extract total count, build URL list.
        """
        # Fetch page 1 to get total page count
        page1_url = chapter.url if chapter.url.endswith("1.html") else (
            chapter.url.rstrip("/") + "/1.html"
        )
        text = fetch_text(page1_url)

        # Extract imagecount
        count_match = re.search(r"var\s+imagecount\s*=\s*(\d+)", text)
        if not count_match:
            # Try alternate pattern
            count_match = re.search(r'"imagecount"\s*:\s*(\d+)', text)
        total = int(count_match.group(1)) if count_match else 1

        # Build per-page URLs - pattern: .../c{num}/{page}.html
        base_ch = re.sub(r"/\d+\.html$", "", page1_url)
        return [f"{base_ch}/{i}.html" for i in range(1, total + 1)]

    def get_image_url_from_page(self, page_url: str) -> str:
        """
        Extract the actual image src from a single reader page.
        FanFox embeds it as: img#image src="..."
        or as a JS variable: var cdn_base="..."; var imageurl="...";
        """
        text = fetch_text(page_url)

        # Try JS var first (most reliable)
        match = re.search(r'var\s+imageurl\s*=\s*"([^"]+)"', text)
        if match:
            return match.group(1)

        # Fallback: parse img tag
        soup = __import__("bs4").BeautifulSoup(text, "lxml")
        img = soup.select_one("img#image")
        return safe_attr(img, "src") if img else ""