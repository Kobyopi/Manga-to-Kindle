"""
app/gui/manga_detail.py

Full-screen detail panel that slides in when a manga card is clicked.
Shows:
  - Cover image (loaded in background)
  - Title, author, status, rating, source badge
  - Description
  - Genre tags
  - Full chapter list with send buttons per chapter
  - "Send all" / "Send range" actions

Opened by main_window._on_manga_click().
Closed by the user via the back button - returns to browser view.
"""

import threading
import customtkinter as ctk
from PIL import Image, ImageDraw
from app.gui.components import make_placeholder_cover, SectionHeader


class MangaDetailPanel(ctk.CTkFrame):
    """
    Overlays the main browser area. Parent should grid_remove() the browser
    and grid() this panel in its place.
    """

    def __init__(self, master, scraper, on_back=None, on_send_chapter=None, **kwargs):
        super().__init__(master, corner_radius=0, fg_color="transparent", **kwargs)

        self._scraper = scraper
        self._on_back = on_back
        self._on_send_chapter = on_send_chapter  # callback(manga, chapter)
        self._manga = None
        self._detail = None
        self._chapter_rows = []

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build()

    # ============= build

    def _build(self):
        # - Top bar
        top = ctk.CTkFrame(self, height=48, corner_radius=0,
        fg_color=("gray95", "gray17"))
        top.grid(row=0, column=0, sticky="ew")
        top.grid_propagate(False)

        ctk.CTkButton(
            top, text="← Back",
            font=ctk.CTkFont(size=13),
            width=80, height=32, corner_radius=8,
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=("gray10", "gray90"),
            command=self._go_back,
        ).pack(side="left", padx=10, pady=8)

        self._top_title = ctk.CTkLabel(
            top, text="",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._top_title.pack(side="left", padx=8)

        # Send all button
        self._send_all_btn = ctk.CTkButton(
            top, text="⇢ Send all chapters",
            font=ctk.CTkFont(size=12),
            height=32, corner_radius=8,
            command=self._on_send_all,
        )
        self._send_all_btn.pack(side="right", padx=10, pady=8)

        # - Main scrollable body
        self._body = ctk.CTkScrollableFrame(
            self, corner_radius=0, fg_color="transparent"
        )
        self._body.grid(row=1, column=0, sticky="nsew")
        self._body.grid_columnconfigure(1, weight=1)

    # ============= public

    def load(self, manga: dict):
        """
        Called by main_window when a card is clicked.
        Clears previous content, shows loading state, fires background fetch.
        """
        self._manga = manga
        self._clear_body()
        self._top_title.configure(text=manga.get("title", ""))
        self._send_all_btn.configure(state="disabled")
        self._show_loading()

        threading.Thread(
            target=self._fetch_detail_thread,
            args=(manga,),
            daemon=True,
        ).start()

    # ============= internals

    def _fetch_detail_thread(self, manga: dict):
        try:
            from app.scraper.base_scraper import MangaSummary
            summary = MangaSummary(
                title = manga.get("title", ""),
                url = manga.get("url", ""),
                cover_url = manga.get("cover_url", ""),
                genres = manga.get("genres", []),
                status = manga.get("status", ""),
                chapters = manga.get("chapters", 0),
                source = manga.get("source", ""),
                source_id = manga.get("source_id", ""),
            )
            detail = self._scraper.get_detail(summary)
            self.after(0, lambda d=detail: self._render_detail(d))
        except Exception as e:
            self.after(0, lambda: self._show_error(str(e)))

    def _render_detail(self, detail):
        self._detail = detail
        self._clear_body()

        # - left column: cover + meta
        left = ctk.CTkFrame(self._body, fg_color="transparent", width=200)
        left.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="n")
        left.grid_propagate(False)

        # Cover placeholder (real image loaded in background)
        cover_img = make_placeholder_cover(180, 260, detail.title)
        self._cover_label = ctk.CTkLabel(left, image=cover_img, text="")
        self._cover_label.pack()

        # Load real cover in background
        if detail.cover_url:
            threading.Thread(
                target=self._load_cover,
                args=(detail.cover_url,),
                daemon=True,
            ).start()

        # Source image
        ctk.CTkLabel(
            left,
            text=detail.source,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="white",
            fg_color="#3a7bd5",
            corner_radius=4,
            height=20,
        ).pack(pady=(8, 2))

        # Rating
        stars = self._rating_stars(detail.rating)
        ctk.CTkLabel(
            left, text=f"{stars} {detail.rating:.1f}",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60"),
        ).pack(pady=(0, 4))

        # Status
        color = "#2ecc71" if detail.status == "Ongoing" else (
            "#e74c3c" if detail.status == "Completed" else "#f39c12"
        )
        ctk.CTkLabel(
            left,
            text=detail.status.upper(),
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="white", fg_color=color,
            corner_radius=4, height=18,
        ).pack(pady=(0, 4))

        # Author
        if detail.author:
            ctk.CTkLabel(
                left,
                text=f"by {detail.author}",
                font=ctk.CTkFont(size=11),
                text_color=("gray40", "gray60"),
                wraplength=180,
            ).pack(pady=(0, 4))

        # - Right column: info + chapters
        right = ctk.CTkFrame(self._body, fg_color="transparent")
        right.grid(row=0, column=1, padx=(0, 16), pady=16, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        # Title
        ctk.CTkLabel(
            right,
            text=detail.title,
            font=ctk.CTkFont(size=22, weight="bold"),
            anchor="w", wraplength=600,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        # Genre tags
        if detail.genres:
            tag_frame = ctk.CTkFrame(right, fg_color="transparent")
            tag_frame.grid(row=1, column=0, sticky="w", pady=(0, 10))
            for genre in detail.genres[:8]:
                ctk.CTkLabel(
                    tag_frame,
                    text=genre,
                    font=ctk.CTkFont(size=10),
                    text_color=("gray30", "gray70"),
                    fg_color=("gray85", "gray25"),
                    corner_radius=4,
                    padx=6, pady=2,
                ).pack(side="left", padx=2)

        # Description
        if detail.description:
            SectionHeader(right, "Synopsis").grid(
                row=2, column=0, sticky="w", pady=(0, 4)
            )
            ctk.CTkLabel(
                right,
                text=detail.description,
                font=ctk.CTkFont(size=12),
                anchor="w", justify="left",
                wraplength=600,
                text_color=("gray20", "gray80"),
            ).grid(row=3, column=0, sticky="w", pady=(0, 16))

        # Chapter list header
        ch_count = len(detail.chapter_list)
        SectionHeader(right, f"Chapters ({ch_count})").grid(
            row=4, column=0, sticky="w", pady=(0, 6)
        )

        # Chapter list - scrollable inner frame
        ch_frame = ctk.CTkScrollableFrame(
            right, height=320, corner_radius=8,
        )
        ch_frame.grid(row=5, column=0, sticky="ew", pady=(0, 16))
        ch_frame.grid_columnocnfigure(0, weight=1)

        self._chapter_rows = []
        # Show in reverse order (newest first)
        for idx, ch in enumerate(reversed(detail.chapter_list)):
            row = self.build_chapter_row(ch_frame, ch, idx)
            row.grid(row=idx, column=0, sticky="ew", padx=4, pady=1)
            self._chapter_rows.append(row)

        self._send_all_btn.configure(state="normal")

    def _build_chapter_row(self, parent, chapter, idx: int) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, corner_radius=6, height=40)
        row.grid_columnconfigure(1, weight=1)
        row.grid_propagate(False)

        # Chapter number
        ctk.CTkLabel(
            row,
            text=f"Ch. {chapter.number:.0f}" if chapter.number == int(chapter.number)
            else f"Ch. {chapter.number}",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=70, anchor="w",
        ).grid(row=0, column=0, padx=(10, 4), pady=8)

        # Chapter title
        ctk.CTkLabel(
            row,
            text=chapter.title,
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color=("gray20", "gray80"),
        ).grid(row=0, column=1, sticky="w", padx=4)

        # Date
        if chapter.date:
            ctk.CTkLabel(
                row,
                text=chapter.date,
                font=ctk.CTkFont(size=10),
                text_color=("gray50", "gray60"),
                width=90,
            ).grid(row=0, column=2, padx=4)

        # Send button
        ctk.CTkButton(
            row,
            text="⇢ Send",
            font=ctk.CTkFont(size=11),
            width=70, height=26, corner_radius=6,
            command=lambda ch=chapter: self._on_send_one(ch),
        ).grid(row=0, column=3, padx=(4, 8), pady=6)

        return row

    # ------------- acitons

    def _on_send_one(self, chapter):
        if self._on_send_chapter and self._manga and self._detail:
            self._on_send_chapter(self._manga, chapter)

    def _on_send_all(self):
        if not self._detail or not self._on_send_chapter:
            return
        for ch in self._detail.chapter_list:
            self._on_send_chapter(self._manga, ch)

    def _go_back(self):
        if self._on_back:
            self._on_back()

    # ------------- helpers

    def _load_cover(self, url: str):
        """Download and display real cover image in backgroud."""
        try:
            import urllib.request, io
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = resp.read()
            img = Image.open(io.BytesIO(data)).convert("RGB")
            img.thumbnail((180, 260), Image.LANCZOS)
            ctk_img = ctk.CTkImage(
                light_image=img, dark_image=img, size=(180, 260)
            )
            self.after(0, lambda: self._cover_label.configure(image=ctk_img))
        except Exception:
            pass  # placeholder stays if cover fails

    def _show_loading(self):
        ctk.CTkLabel(
            self._body,
            text="Loading manga details...",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
        ).grid(row=0, column=0, columnspan=2, pady=60)

    def _show_error(self, msg: str):
        self._clear_body()
        ctk.CTkLabel(
            self._body,
            text=f"Failed to load details:\n{msg}",
            font=ctk.CTkFont(size=13),
            text_color="#e74c3c",
            justify="center",
        ).grid(row=0, column=0, columnspan=2, pady=60)

    def _clear_body(self):
        for w in self._body.winfo_children():
            w.destroy()
        self._chapter_rows = []

    @staticmethod
    def _rating_stars(rating: float) -> str:
        full = int(rating // 1)
        helf = 1 if (rating % 1) >= 0.5 else 0
        empty = 5 - full - half
        return "+" * full + "½" * half + "☆" * empty
