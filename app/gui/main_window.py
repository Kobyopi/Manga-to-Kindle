"""
app/gui/main_window.py
Root application window.  Composes:
   - Left sidebar   : navigation categories, theme toggle
   - Top toolbar   : search bar, grid/list toggle, queue toggle
   - Centre panel   : MangaBrowser (grid or list)
   - Right panel   : DownloadQueue (collapsible)
   -Bottom bar   : StatusBar
"""

import customtkinter as ctk
from app.gui.manga_browser import MangaBrowser
from app.gui.search_bar import SearchBar
from app.gui.download_queue import DownloadQueue
from app.gui.components import SectionHeader, StatusBar
import threading
from app.scraper.site_scraper import AggregatorScraper
from app.scraper.base_scraper import MangaSummary 
from app.kindle.pipeline import Pipeline

CATEGORIES = [
    ("🏠", "Home"),
    ("🔥", "Trending"),
    ("⭐", "Favourites"),
    ("📥", "Downloaded"),
    ("📚", "All Manga"),
]


class MainWindow(ctk.CTk):

    MIN_W, MIN_H = 1100, 700

    def __init__(self):
        super().__init__()
        self.title("Manga-to-Kindle")
        self.geometry("1280x800")
        self.minsize(self.MIN_W, self.MIN_H)

        self._queue_visible = True
        self._active_category = "Home"
        self._active_source: str | None = None  # None = all sources
        self._scraper = AggregatorScraper()
        self._source_genre_btns: dict[str, list[ctk.CTkButton]] = {}

        self._build_layout()
        self._load_live_data()

    # ============= layout

    def _build_layout(self):
        self.grid_rowconfigure(1, weight=1)  # toolbar + content
        self.grid_columnconfigure(1, weight=1)

        self._build_sidebar()
        self._build_toolbar()
        self._build_content()
        self._build_statusbar()

    # ------------- sidebar

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Use a scrollable frame so genre lists don't overflow
        self._sidebar_scroll = ctk.CTkScrollableFrame(
            self.sidebar, corner_radius=0, fg_color="transparent"
        )
        self._sidebar_scroll.pack(fill="both", expand=True)
        self._sidebar_scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # App title
        ctk.CTkLabel(
            self.sidebar_scroll,
            text="MangaKindle",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=row, column=0, padx=16, pady=(20, 2), sticky="w"); row += 1

        ctk.CTkLabel(
            self.sidebar_scroll,
            text="Your reading pipeline",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        ).grid(row=row, column=0, padx=16, pady=(0,12), sticky="w"); row += 1

        ctk.CTkFrame(
            self.sidebar_scroll, height=1, fg_color=("gray80", "gray30")
        ).grid(row=row, column=0, sticky="ew", padx=12, pady=(0, 8)); row += 1

        # General Navigation
        SectionHeader(self.sidebar_scroll, "Library").grid(
            row=row, column=0, padx=16, pady=(4, 4), sticky="w"); row += 1

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for icon, label in CATEGORIES:
            btn = ctk.CTkButton(
                self.sidebar_scroll,
                text=f"  {icon}  {label}",
                anchor="w",
                height=34,
                corner_radius=8,
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                command=lambda lbl=label: self._on_category(lbl),
            )
            btn.grid(row=row, column=0, padx=8, pady=2, sticky="ew"); row += 1
            self._nav_btns[label] = btn

        self._set_active_nav("Home")
        self._sidebar_genre_start_row = row  # remember where source sections begin

        # Source genre sections are populated dynamically in _populate_source_genres()
        # (called after scraper return genre data in background thread)

        # Bottom preferences — pinned at the bottom of the sidebar frame (not scroll)
        pref_frame = ctk.CTkFrame(self.sidebar, corner_radius=0, fg_color="transparent")
        pref_frame.pack(side="bottom", fill="x")

        ctk.CTkFrame(pref_frame, height=1, fg_color=("gray80", "gray30")).pack(
            fill="x", padx=12, pady=(0, 6)
        )
        SectionHeader(pref_frame, "Preferences").pack(padx=16, pady=(2, 4), anchor="w")

        ctk.CTkButton(
            pref_frame, text="  ⚙  Settings",
            anchor="w", height=34, corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=("gray10", "gray90"),
            command=self._open_settings,
        ).pack(fill="x", padx=8, pady=2)

        theme_frame = ctk.CTkFrame(pref_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=8, pady=(2, 12))
        ctk.CTkLabel(
            theme_frame, text="  ◑  Theme",
            font=ctk.CTkFont(size=13),
            text_color=("gray10", "gray90"), anchor="w",
        ).pack(side="left", expand=True, fill="x")
        ctk.CTkOptionMenu(
            theme_frame,
            values=["System", "Light", "Dark"],
            width=90, height=28, font=ctk.CTkFont(size=11),
            command=self._change_theme,
        ).pack(side="right")

    # Source specific genre sections
    def _populate_source_genres(self, genres_per_source: dict[str, list[str]]):
        """
        Dynamically adds per-site genre sections to the sidebar scroll area.
        Called from a background thread via self.after() so it's GUI-safe.
        """
        row = self._sidebar_genre_start_row

        for source_name, genres in genres_per_source.items():
            if not genres:
                continue
            
            # Divider
            ctk.CTkFrame(
                self._sidebar_scroll, height=1, fg_color=("gray80", "gray30")
            ).grid(row=row, column=0, sticky="ew", padx=12, pady=(8,4)); row += 1

            # Source header with "All from X" button
            hdr_frame = ctk.CTkFrame(self._sidebar_scroll, fg_color="transparent")
            hdr_frame.grid(row=row, column=0, sticky="ew", padx=8); row += 1
            hdr_frame.grid_columnconfigure(0, weight=1)

            SectionHeader(hdr_frame, source_name).grid(
                row=0, column=0, padx=8, pady=(2,0), sticky="w"
            )
            ctk.CTkButton(
                hdr_frame, text="All", width=38, height=22,
                font=ctk.CTkFont(size=10), corner_radius=6,
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                text_color=("gray40", "gray70"),
                command=lambda src=source_name: self._on_source_all(src),
            ).grid(row=0, column=1, padx=4)

            # Genre buttons for this source
            self._source_genre_btns[source_name] = []
            for genre in genres:
                btn = ctk.CTkButton(
                    self._sidebar_scroll,
                    text=f"  {genre}",
                    anchor="w", height=30, corner_radius=6,
                    font=ctk.CTkFont(size=12),
                    fg_color="transparent",
                    hover_color=("gray85", "gray25"),
                    text_color=("gray20", "gray80"),
                    command=lambda g=genre, src=source_name: self._on_source_genre(src, g),
                )
                btn.grid(row=row, column=0, padx=8, pady=1, sticky="ew"); row += 1
                self._source_genre_btns[source_name].append(btn)

    # ------------- toolbar

    def _build_toolbar(self):
        self.toolbar = ctk.CTkFrame(self, height=54, corner_radius=0,
            fg_color=("gray95", "gray17"))
        self.toolbar.grid(row=0, column=1, columnspan=2, sticky="ew")
        self.toolbar.grid_propagate(False)

        # Search bar
        self.search = SearchBar(self.toolbar, on_search=self._on_search)
        self.search.pack(side="left", fill="x", expand=True, padx=12, pady=10)

        # Grid/List toggle segment
        seg_frame = ctk.CTkFrame(self.toolbar, fg_color="transparent")
        seg_frame.pack(side="left", padx=(0, 8))

        self._grid_btn = ctk.CTkButton(
            seg_frame, text="⊞", width=36, height=34,
            font=ctk.CTkFont(size=16), corner_radius=8,
            command=lambda: self._set_view("grid"),
        )
        self._grid_btn.pack(side="left", padx=(0, 2))

        self._list_btn = ctk.CTkButton(
            seg_frame, text="≡", width=36, height=34,
            font=ctk.CTkFont(size=16), corner_radius=8,
            fg_color=("gray80", "gray30"),
            text_color=("gray40", "gray60"),
            command=lambda: self._set_view("list"),
        )
        self._list_btn.pack(side="left")

        # Queue toggle
        ctk.CTkButton(
            self.toolbar, text="↓ Queue", width=80, height=34,
            font=ctk.CTkFont(size=12), corner_radius=8,
                command=self._toggle_queue,
        ).pack(side="left", padx=(0, 12))

    # ------------- content

    def _build_content(self):
        self.browser = MangaBrowser(
            self,
            on_manga_click=self._on_manga_click,
            on_manga_send=self._on_manga_send,
        )
        self.browser.grid(row=1, column=1, sticky="nsew", padx=0, pady=0)

        self.queue_panel = DownloadQueue(self)
        self.queue_panel.grid(row=1, column=2, sticky="nsew")

    # ------------- status bar

    def _build_statusbar(self):
        self.statusbar = StatusBar(self)
        self.statusbar.grid(row=2, column=1, columnspan=2, sticky="ew")

    # ============= actions

    def _load_live_data(self):
        """Kick off background scrape - keeps GUI responsive."""
        self.statusbar.set("Loading manga from sources...")
        threading.Thread(target=self._fetch_data_thread, daemon=True).start()

    def _fetch_data_thread(self):
        """Runs in a worker thread - never touch widgets here directly."""
        try:
            # 1. Fetch genres for sidebar
            genres_per_source = self._scraper.get_genres_per_source()
            self.after(0, lambda: self._populate_source_genres(genres_per_source))

            # 2. Fetch first page of manga from all active source
            results = self._scraper.browse(
                source=self._active_source,
                sort="popularity",
                page=1,
            )

            # Covert MangaSummary dataclasses to plain dicts for the browser
            manga_dicts = [
                {
                    "title": m.title,
                    "url": m.url,
                    "cover_url": m.cover_url,
                    "genres": m.genres,
                    "status": m.status,
                    "chapters": m.chapters,
                    "rating": m.rating,
                    "source": m.source,
                    "source_id": m.source_id,
                }
                for m in results
            ]
            self.after(0, lambda d=manga_dicts: self._on_data_loaded(d))

        except Exception as e:
            self.after(0, lambda: self.statusbar.set(f"Error loading data: {e}"))

    def _on_data_loaded(self, manga_dicts: list[dict]):
        """Called on main thread once scraper data is ready."""
        self.browser.load(manga_dicts)
        self.statusbar.set(
            f"{len(manga_dicts)} titles loaded from "
            f"{', '.join(self._scraper.get_active_sources())}"
        )

    def _on_search(self, query: str):
        if not query.strip():
            self.browser.filter("")
            self.statusbar.set(f"{len(self.browser._all_manga)} titles")
            return
        # Local filter first (instant), then background search for more results
        self.browser.filter(query)
        threading.Thread(
            target=self._fetch_search_thread, args=(query,), daemon=True
        ).start()

    def _fetch_search_thread(self, query: str):
        try:
            results = self._scraper.search(query, source=self._active_source)
            manga_dicts = [
                {
                    "title": m.title, "url": m.url, "cover_url": m.cover_url,
                    "genres": m.genres, "status": m.status,
                    "chapters": m.chapters, "rating": m.rating,
                    "source": m.source,
                    "source_id": m.source_id,
                }
                for m in results
            ]
            self.after(0, lambda d=manga_dicts: self._on_data_loaded(d))
            self.after(0, lambda: self.statusbar.set(
                f"{len(manga_dicts)} results for '{query}'")
            )
        except Exception as e:
            self.after(0, lambda: self.statusbar.set(f"Search error: {e}"))

    def _all(self):
        return self.browser._all_manga

    def _on_category(self, label: str):
        self._set_active_nav(label)
        self._active_source = None
        status_map = {"Ongoing": "ongoing", "Completed": "completed"}
        sort_map = {"Trending": "popularity", "All Manga": "alphabetical"}
        self.statusbar.set(f"Loading {label}...")
        threading.Thread(
            target=self._fetch_category_thread,
            args=(None, None, sort_map.get(label, "popularity")),
            daemon=True,
        ).start()

    def _on_source_all(self, source: str):
        """Show all manga from a single source."""
        self._active_source = source
        self.statusbar.set(f"Loading all from {source}...")
        threading.Thread(
            target=self._fetch_category_thread,
            args=(source, None, "popularity"),
            daemon=True,
        ).start()

    def _on_source_genre(self, source: str, genre: str):
        """Show manga from a specific source filtered by genre."""
        self._active_source = source
        self.statusbar.set(f"Loading {genre} from {source}...")
        threading.Thread(
            target=self._fetch_category_thread,
            args=(source, genre, "popularity"),
            daemon=True,
        ).start()

    def _fetch_category_thread(self, source, genre, sort):
        try:
            results = self._scraper.browser(source=source, genre=genre, sort=sort)
            manga_dicts = [
                {
                    "title": m.title, "url": m.url, "cover_url": m.cover_url,
                    "genres": m.genres, "status": m.status,
                    "chapters": m.chapters, "rating": m.rating,
                    "source": m.source, "source_id": m.source_id,
                }
                for m in results
            ]
            self.after(0, lambda d=manga_dicts: self._on_data_loaded(d))
        except Exception as e:
            self.after(0, lambda: self.statusbar.set(f"Error: {e}"))

    def _set_active_nav(self, label: str):
        self._active_category = label
        for lbl, btn in self._nav_btns.items():
            if lbl == label:
                btn.configure(
                    fg_color=("gray80", "gray30"),
                    text_color=("gray5", "white"),
                    )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("gray10", "gray90"),
                )

    def _set_view(self, mode: str):
        self.browser.set_mode(mode)
        # Toggle button styles to reflect active view
        if mode == "grid":
            self._grid_btn.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self._list_btn.configure(fg_color=("gray80", "gray30"),
            text_color=("gray40", "gray60"))
        else:
            self._list_btn.configure(fg_color=ctk.ThemeManager.theme["CTkButton"]["fg_color"])
            self._grid_btn.configure(fg_color=("gray80", "gray30"),
            text_color=("gray40", "gray60"))
        self.statusbar.set(f"View: {mode}")

    def _toggle_queue(self):
        if self._queue_visible:
            self.queue_panel.grid_remove()
        else:
            self.queue_panel.grid()
        self._queue_visible = not self._queue_visible

    def _on_manga_click(self, manga: dict):
        # TODO: open manga_detail panel
        self.statusbar.set(f"Selected: {manga['title']}")

    def _on_manga_send(self, manga: dict):
        # TODO: open send_dialog, then kick off pipeline
        job_id = manga["title"].replace(" ", "_").lower()
        self.queue_panel.add_job(job_id, manga["title"])
        self.statusbar.set(f"Queued: {manga['title']}")

        # Simulate pipeline progress for demo purpose
        self._simulate_progress(job_id, step=0)

    def _simulate_progress(self, job_id: str, step: int):
        """Demo only - replace with real threading pipeline later."""
        steps = [
            (0.15, "Fetching chapter list..."),
            (0.30, "Downloading images..."),
            (0.55, "Downloading images..."),
            (0.75, "Converting to EPUB..."),
            (0.90, "Sending to Kindle..."),
            (1.00, "Done"),
        ]
        if step >= len(steps):
            self.queue_panel.finish_job(job_id)
            return

        progress, status = steps[step]
        self.queue_panel.update_job(job_id, progress, status)
        self.after(800, lambda: self._simulate_progress(job_id, step + 1))

    def _open_settings(self):
        # TODO: open settings_panel window
        self.statusbar.set("Settings - coming soon")

    def _change_theme(self, choice: str):
        ctk.set_appearance_mode(choice.lower())

    



        
