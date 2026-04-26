"""
app/gui/manga_browser.py
Scrollable manga library panel.  Supports grid (thumbnail) and list modes,
toggled by the toolbar buttons in the main window.
"""

import customtkinter as ctk
from app.gui.components import MangaCard, MangaListRow


class MangaBrowser(ctk.CTkFrame):
    """
    Central content area that renders manga entries in either:
    - GRID mode : 4-column card layout with cover thumbnails
    - LIST mode : compact single-column rows with metadata
    """

    GRID_COLS = 4

    def __init__(self, master, on_manga_click=None, on_manga_send=None, **kwargs):
        super().__init__(master, corner_radius=0, fg_color="transparent", **kwargs)

        self.on_manga_click = on_manga_click
        self.on_manga_send = on_manga_send
        self._mode = "grid"   # "grid" | "list"
        self._all_manga: list[dict] = []
        self._filtered: list[dict] = []

        self._build()

    # ------------- layout

    def _build(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Outer scrollable container
        self.scroll = ctk.CTkScrollableFrame(
            self, corner_radius=0, fg_color="transparent",
        )
        self.scroll.grid(row=0, column=0, sticky="nsew")

        # Empty-state label (shown when no results)
        self.empty_label = ctk.CTkLabel(
            self, text="No manga found.\nTry a different search or category.",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60"),
            justify="center"
        )

    # ------------- public

    def load(self, manga_list: list[dict]):
        """Replace the full library and re-render."""
        self._all_manga = manga_list
        self._filtered = manga_list[:]
        self._render()

    def filter(self, query: str):
        """Filter the displayed list by title substring (case-insensitie)."""
        q = query.strip().lower()
        if not q:
            self._filtered = self._all_manga[:]
        else:
            self._filtered = [
                m for m in self._all_manga
                if q in m.get("title", "").lower()
                or q in " ".join(m.get("genres", [])).lower()
            ]
        self._render()

    def set_mode(self, mode: str):
        """Switch between 'grid' and 'list'."""
        if mode not in ("grid", "list"):
            return
        self._mode = mode
        self._render()

    def get_mode(self) -> str:
        return self._mode

    # ------------- private

    def _clear(self):
        for widget in self.scroll.winfo_children():
            widget.destroy()

    def _render(self):
        self._clear()

        if not self._filtered:
            self.empty_label.place(relx=0.5, rely=0.5, anchor="center")
            return

        self.empty_label.place_forget()

        if self._mode == "grid":
            self._render_grid()
        else:
            self._render_list()

    def _render_grid(self):
        cols = self.GRID_COLS
        self.scroll.grid_columnconfigure(
            list(range(cols)), weight=1, uniform="col"
        )

        for idx, manga in enumerate(self._filtered):
            row, col = divmod(idx, cols)
            card = MangaCard(
                self.scroll,
                manga=manga,
                on_click=self.on_manga_click,
                on_send=self.on_manga_send,
            )
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

    def _render_list(self):
        self.scroll.grid_columnconfigure(0, weight=1)

        for idx, manga in enumerate(self._filtered):
            row = MangaListRow(
                self.scroll,
                manga=manga,
                on_click=self.on_manga_click,
                on_send=self.on_manga_send,
            )
            row.grid(row=idx, column=0, padx=8, pady=3, sticky="ew")


    
