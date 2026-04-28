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


# ----------
# Placeholder data - replace with real scraper output later
# ----------
SAMPLE_MANGA = [
    {"title": 'One Piece', "chapters": 1100, "status": "Ongoing", "genres": ["Action", "Adventure", "Fantasy"]},
        {"title": "Berserk", "chapters": 374, "status": "Ongoing",
     "genres": ["Dark Fantasy", "Action"]},
    {"title": "Vinland Saga", "chapters": 210, "status": "Ongoing",
     "genres": ["Historical", "Action", "Drama"]},
    {"title": "Chainsaw Man", "chapters": 165, "status": "Ongoing",
     "genres": ["Action", "Horror", "Supernatural"]},
    {"title": "Vagabond", "chapters": 327, "status": "Hiatus",
     "genres": ["Historical", "Martial Arts", "Drama"]},
    {"title": "Fullmetal Alchemist", "chapters": 116, "status": "Completed",
     "genres": ["Action", "Adventure", "Fantasy"]},
    {"title": "Hunter x Hunter", "chapters": 400, "status": "Hiatus",
     "genres": ["Action", "Adventure", "Fantasy"]},
    {"title": "Attack on Titan", "chapters": 139, "status": "Completed",
     "genres": ["Action", "Dark Fantasy", "Drama"]},
    {"title": "Demon Slayer", "chapters": 205, "status": "Completed",
     "genres": ["Action", "Supernatural"]},
    {"title": "Jujutsu Kaisen", "chapters": 260, "status": "Ongoing",
     "genres": ["Action", "Supernatural", "Horror"]},
    {"title": "Blue Period", "chapters": 80, "status": "Ongoing",
     "genres": ["Slice of Life", "Drama", "Art"]},
    {"title": "Dungeon Meshi", "chapters": 97, "status": "Completed",
     "genres": ["Fantasy", "Adventure", "Comedy"]},
]


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

        self._build_layout()
        self._load_sample_data()

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
        self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(10, weight=1)  # pushes bottom items down

        # App title
        ctk.CTkLabel(
        self.sidebar,
        text="MangaKindle",
        font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(20, 4), sticky="w")

        ctk.CTkLabel(
            self.sidebar,
            text="Your reading pipeline",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        ).grid(row=1, column=0, padx=16, pady=(0,16), sticky="w")

        ctk.CTkFrame(self.sidebar, height=1, fg_color=("gray80", "gray30")).grid(
            row=2, column=0, sticky="ew", padx=12, pady=(0, 8)
        )

        # Navigation
        SectionHeader(self.sidebar, "Navigation").grid(
            row=3, column=0, padx=16, pady=(4, 6), sticky="w"
        )

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for i, (icon, label) in enumerate(CATEGORIES):
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                height=36,
                corner_radius=8,
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                hover_color=("gray85", "gray25"),
                text_color=("gray10", "gray90"),
                command=lambda lbl=label: self._on_category(lbl),
            )
            btn.grid(row=4 + i, column=0, padx=8, pady=2, sticky="ew")
            self._nav_btns[label] = btn

        self._set_active_nav("Home")

        # Spacer - fills remaining vertical space
        ctk.CTkFrame(self.sidebar, fg_color="transparent").grid(
            row=10, column=0, sticky="nsew"
        )

        # Bottom section: Settings + theme
        ctk.CTkFrame(self.sidebar, height=1, fg_color=("gray80", "gray30")).grid(
            row=11, column=0, sticky="ew", padx=12, pady=8
        )

        SectionHeader(self.sidebar, "Preferences").grid(
            row=12, column=0, padx=16, pady=(0,6), sticky="w"
        )

        ctk.CTkButton(
            self.sidebar,
            text="  ⚙  Settings",
            anchor="w", height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=("gray10", "gray90"),
            command=self._open_settings,
        ).grid(row=13, column=0, padx=8, pady=2, sticky="ew")

        # Appearance toggle
        theme_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        theme_frame.grid(row=14, column=0, padx=8, pady=(2, 16), sticky="ew")
        ctk.CTkLabel(
            theme_frame, text="  ◑  Theme",
            font=ctk.CTkFont(size=13),
            text_color=("gray10", "gray90"),
            anchor="w",
        ).pack(side="left", expand=True, fill="x")
        ctk.CTkOptionMenu(
            theme_frame,
            values=["System", "Light", "Dark"],
            width=90, height=28,
            font=ctk.CTkFont(size=11),
            command=self._change_theme,
        ).pack(side="right")

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
            self.toolbar, text="↓ Queue", widht=80, height=34,
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
        self.statsubar.grid(row=2, column=1, columspan=2, sticky="ew")

    # ============= actions

    def _load_sample_data(self):
        self.browser.load(SAMPLE_MANGA)
        self.statsubar.set(f"{len(SAMPLE_MANGA)} titles loaded")

    def _on_search(self, query: str):
        self.browser.filter(query)
        count = len(self.browser._filtered)
        self.statusbar.set(f'{count} result(s) for "{query}"' if query else f"{len(self._all())} titles")

    def _all(self):
        return self.browser._all_manga

    def _on_category(self, label: str):
        self._set_active_nav(label)
        self.statusbar.set(f"Category: {label}")
        # TODO: route to real category filter via scraper

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

    



        
