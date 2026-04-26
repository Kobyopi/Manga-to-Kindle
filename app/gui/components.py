"""
app/gui/components.py
Reusable custom widgets used across the application.
"""

import customtkinter as ctk
from PIL import Image, ImageDraw
import os


def make_placeholder_cover(width=160, height=220, title="") -> ctk.CTkImage:
    """
    Generate a placeholder cover image when no thumbnail is available.
    Returns a CTkImage that adapts to light/dark mode.
    """
    # Dark placeholder
    img_dark = Image.new("RGB", (width, height), color=(40, 40, 50))
    draw_dark = ImageDraw.Draw(img_dark)
    draw_dark.rectangle([0, 0, width - 1, height - 1], outline=(80, 80, 100), width=2)
    initials = title[:2].upper() if title else "?"
    draw_dark.text((width // 2, height // 2), initials, fill=(120, 120, 150), anchor="mm")

    # Light placeholder
    img_light = Image.new("RGB", (width, height), color=(220, 220, 230))
    draw_light = ImageDraw.Draw(img_light)
    draw_light.rectangle([0, 0, width - 1, height - 1], outline=(160, 160, 180), width=2)
    draw_light.text((width // 2, height // 2), initials, fill=(100, 100, 130), anchor="mm")

    return ctk.CTkImage(light_image=img_light, dark_image=img_dark, size=(width, height))


class MangaCard(ctk.CTkFrame):
    """
    Grid view card - shows cover thumbnail, title, chapter count, and a
    quick-action "Send' button that appears on hover.
    """

    def __init__(self, master, manga: dict, on_click=None, on_send=None, **kwargs):
        super().__init__(master, corner_radius=10, cursor="hand2", **kwargs)

        self.manga = manga
        self.on_click = on_click
        self.on_send = on_send

        self._build()
        self._bind_hover()

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        # Cover image
        cover = make_placeholder_cover(title=self.manga.get("title", ""))
        self.cover_label = ctk.CTkLabel(self, image=cover, text="")
        self.cover_label.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")

        # Title - truncate long names
        title = self.manga.get("title", "Unknown")
        display = title if len(title) <= 22 else title[:20] + "..."
        self.title_label = ctk.CTkLabel(
            self, text=display, font=ctk.CTkFont(size=12, weight="bold"),
            wraplength=150, justify="center"
        )
        self.title_label.grid(row=1, column=0, padx=6, pady=(0, 2))

        # Chapter count badge
        chapters = self.manga.get("chapters", 0)
        self.ch_label = ctk.CTkLabel(
            self, text=f"{chapters} chapters",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60")
        )
        self.ch_label.grid(row=2, column=0, padx=6, pady=(0, 4))

        # Status badge
        status = self.manga.get("status", "")
        if status:
            color = "#2ecc71" if status.lower() == "ongoing" else "#e74c3c"
            self.status_badge = ctk.CTkLabel(
                self, text=status.upper(),
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="white",
                fg_color=color,
                corner_radius=4,
                width=60, height=18
            )
            self.status_badge.grid(row=3, column=0, pady=(0, 4))

        # Send button (hidden by default, shown on hover)
        self.send_btn = ctk.CTkButton(
            self, text="⇢ Send to Kindle",
            font=ctk.CTkFont(size=11),
            height=28, corner_radius=6,
            command=self._on_send
        )
        self.send_btn.grid(row=4, column=0, padx=8, pady=(0, 8), sticky="ew")
        self.send_btn.grid_remove()  # hidden initially

    def _bind_hover(self):
        widgets = [self, self.cover_label, self.title_label, self.ch_label]
        for w in widgets:
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)

    def _on_enter(self, event=None):
        self.send_btn.grid()

    def _on_leave(self, event=None):
        # Only hide if pointer truly left the card
        try:
            x, y = self.winfo_pointerxy()
            wx, wy = self.winfo_rootx(), self.winfo_rooty()
            ww, wh = self.winfo_width(), self.winfo_height()
            if not (wx <= x <= wx + ww and wy <= y <= wy + wh):
                self.send_btn.grid_remove()
        except Exception:
            self.send_btn.grid_remove()

    def _on_click(self, event=None):
        if self.on_click:
            self.on_click(self.manga)

    def _on_send(self):
        if self.on_send:
            self.on_send(self.manga)


class MangaListRow(ctk.CTkFrame):
    """
    List view row - shows title, genre tags, chapter count, status, and
    a compact Send button on th right.
    """

    def __init__(self, master, manga: dict, on_click=None, on_send=None, **kwargs):
        super().__init__(master, corner_radius=8, cursor="hand2", height=64, **kwargs)

        self.manga = manga
        self.on_click = on_click
        self.on_send = on_send
        self.pack_propagate(False)

        self._build()
        self.bind("<Button-1>", self._on_click)

    def _build(self):
        self.grid_columnconfigure(1, weight=1)

        # Small cover thumbnail
        cover = make_placeholder_cover(40, 56, self.manga.get("title", ""))
        thumb = ctk.CTkLabel(self, image=cover, text="")
        thumb.grid(row=0, column=0, rowspan=2, padx=(10, 8), pady=6)
        thumb.bind("<Button-1>", self._on_click)

        # Title
        title = self.manga.get("title", "Unknown")
        title_lbl = ctk.CTkLabel(
            self, text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        title_lbl.grid(row=0, column=1, sticky="sw", pady=(10, 0))
        title_lbl.bind("<Button-1>", self._on_click)

        # Meta line: genres + chapter count
        genres = ", ".join(self.manga.get("genres", [])[:3]) or "—"
        chapters = self.manga.get("chapters", 0)
        meta = f"{genres}  ·  {chapters} ch"
        meta_lbl = ctk.CTkLabel(
            self, text=meta,
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
            anchor="w"
        )
        meta_lbl.grid(row=1, column=1, sticky="nw", pady=(0, 10))
        meta_lbl.bind("<Button-1>", self._on_click)

        # Status badge
        status = self.manga.get("status", "")
        if status:
            color = "#2ecc71" if status.lower() == "ongoing" else "#e74c3c"
            ctk.CTkLabel(
                self, text=status.upper(),
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="white", fg_color=color,
                corner_radius=4, width = 60, height=18
            ).grid(row=0, column=2, padx=8, pady=(12, 0))

        # Send button
        ctk.CTkButton(
            self, text="⇢ Kindle",
            font=ctk.CTkFont(size=11),
            width=80, height=28, corner_radius=6,
            command=self._on_send
        ).grid(row=1, column=2, padx=8, pady=(0, 10))

    def _on_click(self, event=None):
        if self.on_click:
            self.on_click(self.manga)

    def _on_send(self):
        if self.on_send:
            self.on_send(self.manga)


class SectionHeader(ctk.CTkLabel):
    """Simple bold section label used in the sidebar."""

    def __init__(self, master, text, **kwargs):
        super().__init__(
            master, text=text.upper(),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=("gray45", "gray55"),
            **kwargs
        )


class StatusBar(ctk.CTkFrame):
    """Bottom status bar showing current action / progress text."""

    def __init__(self, master, **kwargs):
        super().__init__(master, height=28, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self._var = ctk.StringVar(value="Ready")
        ctk.CTklabel(
            self, textvariable=self._var,
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray55"),
            anchor="w"
        ).pack(side="left", padx=12)

    def set(self, message: str):
        self._var.set(message)