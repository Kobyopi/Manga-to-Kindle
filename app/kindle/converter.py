"""
app/kindle/converter.py

Converts a list of downloaded chapter image files into either:
  - EPUB  : proper ebook with one image per page, metadata embedded
  - CBZ  : comic book ZIP archive, images in order, Amazon auto-converts

Both formats write to the output/ directory and return the final file path.
Cleanup of downloads/ is handled separately by utils/cleanup.py.

Usage:
    converter = MangaConverter(output_dir=Path("output"))

    epub_path = converter.to_epub(
        image_paths = [Path("downloads/ch1/0001.jpg"), ...],
        title = "One Piece",
        chapter = "Chapter 1001",
        author = "Oda Eiichiro",
        cover_path = Path("cache/covers/one_piece.jpg"),  # optional
    )

    cbz_path = converter.to_cbz(
        image_paths = [Path("downloads/ch1/0001.jpg"), ...],
        title = "One Piece",
        chapter = "Chapter 1001",
    )
"""

import zipfile
import shutil
from pathlib import Path
from typing import Callable

from PIL import Image as PilImage
import ebooklib
from ebooklib import epub


class MangaConverter:

    # Kindle screen resolution - images are resized to fit if larger
    KINDLE_WIDTH = 1072
    KINDLE_HEIGHT = 1448

    def __init__(
        self,
        output_dir: Path = Path("output"),
        on_progress: Callable[[float, str], None] | None = None,
    ):
        self._out = output_dir
        self._out.mkdir(parents=True, exist_ok=True)
        self._on_progress = on_progress

    # ------------- public

    def to_epub(
        self,
        image_paths: list[Path],
        title: str,
        chapter: str,
        author: str = "Unknown",
        cover_path: Path | None = None,
    ) -> Path:
        """
        Package images into a Kindle-compatible EPUB.
        Each image becomes one HTML page in the book.
        Returns the path to the created .epub file.
        """
        self._progress(0.0, "Building EPUB...")

        book = epub.EpubBook()
        book.set_identifier(f"{title}-{chapter}".replace(" ", "-").lower())
        book.set_title(f"{title} - {chapter}")
        book.set_language("en")
        book.add_author(author)

        # Minimal CSS for manga reading (black background, centred image)
        css = epub.EpubItem(
            uid="manga_css",
            file_name="styles/manga.css",
            media_type="text/css",
            content=b"""
                body { margin: 0; padding: 0; background: #000; }
                img { display: block; margin: 0 auto; 
                    max-width: 100%; max-height: 100%; }
            """,
        )
        book.add_item(css)

        # Cover image
        if cover_path and cover_path.exists():
            cover_data = cover_path.read_bytes()
            mime = self.mime(cover_path)
            book.set_cover(cover_path.name, cover_data)

        spine = ["nav"]
        total = len(image_paths)

        for idx, img_path in enumerate(image_paths):
            self._progress(
                0.05 + 0.85 * (idx / max(total, 1)),
                f"Adding page {idx + 1}/{total}..."
            )

            # Resize image to Kindle screen dimensions if necessary
            processed = self._fit_image(img_path)
            img_data = processed.read_bytes() if isinstance(processed, Path) else processed

            # Embed image into EPUB
            img_name = f"images/{idx:04d}{img_path.suffix}"
            epub_img = epub.EpubItem(
                uid=f"img_{idx:04d}",
                file_name=img_name,
                media_type=self._mime(img_path),
                content=img_data,
            )
            book.add_item(epub_img)

            # One HTML page per image
            page_html = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>Page {idx + 1}</title>
  <link rel="stylesheet" type="text/css" href="../styles/manga.css"/>
</head>
<body>
  <img src="../{img_name}" alt="Page {idx + 1}"/>
</body>
</html>"""
            chapter_item = epub.EpubHtml(
                title=f"Page {idx + 1}",
                file_name=f"pages/{idx:04d}.xhtml",
                lang="en",
            )  
            chapter_item.content = page_html.encode("utf-8")
            chapter_item.add_item(css)
            book.add_item(chapter_item)
            spine.append(chapter_item)

        book.spine = spine
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        safe_title = self._safe_filename(title)
        safe_chapter = self._safe_filename(chapter)
        out_path = self._out / f"{safe_title}_{safe_chapter}.epub"

        self._progress(0.92, "Writing EPUB file...")
        epub.write_epub(str(out_path), book)

        self._progress(1.0, "EPUB ready")
        return out_path

    def to_cbz(
        self,
        image_paths: list[Path],
        title: str,
        chapter: str,
    ) -> Path:
        """
        Package images into a CBZ (comic book ZIP) archive.
        Images are stored in order; Amazon's Send-to-Kindle service
        auto-converts CBZ to a Kindle-readable format on delivery.
        Returns the path to the created .cbz file.
        """
        self._progress(0.0, "Building CBZ...")

        safe_title = self._safe_filename(title)
        safe_chapter = self._safe_filename(chapter)
        out_path = self._out / f"{safe_title}_{safe_chapter}.cbz"
        total = len(image_paths)

        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_STORED) as zf:
            # ComicInfo.xml - optional metadata, recognised by most readers
            comic_info = f"""<?xml version="1.0" encoding="utf-8"?>
<ComicInfo>
  <Title>{chapter}</Title>
  <Series>{title}</Series>
  <Writer>Unknown</Writer>
  <Manga>YesAndRightToLeft</Manga>
</ComicInfo>"""
            zf.writestr("ComicInfo.xml", comic_info)

            for idx, img_path in enumerate(image_paths):
                self._progress(
                    0.05 + 0.90 * (idx / max(total, 1)),
                    f"Packing page {idx + 1}/{total}..."
                )
                arcname = f"{idx:04d}{img_path.suffix}"
                zf.write(img_path, arcname)

        self._progress(1.0, "CBZ ready")
        return out_path

    # ------------- helpers

    def _fit_image(self, path: Path) -> bytes:
        """
        Resize image to fit Kindle screen while preserving aspect ratio.
        Returns processed image bytes.
        Only resizes if image is larger than Kindle screen dimensions.
        """
        try:
            with PilImage.open(path) as img:
                # Convert to RGB if necessary (e.g. RGBA PNG)
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")

                w, h = img.size
                if w > self.KINDLE_WIDTH or h > self.KINDLE_HEIGHT:
                    img.thumbnail(
                        (self.KINDLE_WIDTH, self.KINDLE_HEIGHT),
                        PilImage.LANCZOS
                    )

                import io
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85, optimize=True)
                return buf.getvalue()
        except Exception:
            # If processing fails, return raw bytes unchanged
            return path.read_bytes()

    def _progress(self, value: float, status: str):
        if self._on_progress:
            self._on_progress(value, status)

    @staticmethod
    def _mime(path: Path) -> str:
        ext = path.suffix.lower()
        return {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(ext, "image/jpeg")

    @staticmethod
    def _safe_filename(text: str) -> str:
        """Strip characters that are invalid in filenames."""
        import re
        return re.sub(r'[\\/*?:"<>|]', "", text).strip().replace(" ", "_")
