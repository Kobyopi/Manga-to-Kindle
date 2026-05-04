"""
app/gui/send_dialog.py

Model dialog that appears when the user clicks "Send to Kindle"
on either a manga card (sends a chapter range) or a chapter row
in the detail panel (sends one specific chapter).

The dialog shows:
  - Manga title + cover thumbnail
  - Chapter selection (single chapter pre-selected, or range picker)
  - Format toggle: EPUB / CBZ
  - Kindle email address (read-only, links to settings)
  - Confirm / Cancel buttons

On confirm, calls on_confirm(manga, chapters, fmt) so the
main window can kick off the Pipeline in a background thread.
"""

import customtkinter as ctk
from app.gui.components import make_placeholder_cover
from app.scraper.base_scraper import Chapter


class SendDialog(ctk.CTkToplevel):
    """
    Modal send-to-Kindle confirmation dialog.

    manga  : dict with manga metadata
    chapters  : list[Chapter] - pre-selected chapters (usually one)
    all_chapters  : list[Chapter] - full chapter list for range picking
    on_confirm  : callback(manga: dict, chapters: list[Chapter], fmt: str)
    """

    def __init__(
        self,
        master,
        manga: dict,
        chapters: list,
        all_chapters: list,
        kindle_email: str,
        on_confirm=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)

        self._manga = manga
        self._chapters = chapters   # initially selected
        self._all_chapters = all_chapters
        self._kindle_email = kindle_email
        self._on_confirm = on_confirm

        self.title("Send to Kindle")
        self.geometry("520x580")
        self.resizable(False, False)
        self.grab_set()   # model - blocks parent window
        self.lift()
        self.focus_force()

        self._fmt_var = ctk.StringVar(value="epub")
        self._mode_var = ctk.StringVar(value="selected")  # "selected" | "range"
        self._from_var = ctk.StringVar()
        self._to_var = ctk.StringVar()

        self._build()

    # ============= build

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # - Header -------------
        hdr = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray92", "gray18"))
        hdr.grid(row=0, column=0, sticky="ew")

        cover = make_placeholder_cover(56, 80, self._manga.get("title", ""))
        ctk.CTkLabel(hdr, image=cover, text="").pack(side="left", padx=12, pady=10)

        info = ctk.CTkFrame(hdr, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, pady=10)

        ctk.CTkLabel(
            info,
            text=self._manga.get("title", ""),
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).pack(anchor="w")

        source = self._manga.get("source", "")
        ctk.CTkLabel(
            info,
            text=f"Source: {source}",
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray60"),
            anchor="w",
        ).pack(anchor="w")

        ch_count = len(self._chapters)
        self._ch_summary_label = ctk.CTkLabel(
            info,
            text=self._chapter_summary(),
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray60"),
            anchor="w",
        )
        self._ch_summary_label.pack(anchor="w")

        # - Chapter selection -------------
        sel_frame = ctk.CTkFrame(self, fg_color="transparent")
        sel_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(14, 0))
        sel_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            sel_frame,
            text="Chapters",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        # Mode toggle
        ctk.CTkRadioButton(
            sel_frame,
            text=f"Selected ({len(self._chapters)} chapter{'s' if len(self._chapters) != 1 else ''})",
            variable=self._mode_var,
            value="selected",
            font=ctk.CTkFont(size=12),
            command=self._on_mode_change,
        ).grid(row=1, column=0, sticky="w", pady=2)

        ctk.CTkRadioButton(
            sel_frame,
            text="Chapter range",
            variable=self._mode_var,
            value="range",
            font=ctk.CTkFont(size=12),
            command=self._on_mode_change,
        ).grid(row=2, column=0, sticky="w", pady=2)

        # Range pickers (shown when mode=range)
        self._range_frame = ctk.CTkFrame(sel_frame, fg_color="transparent")
        self._range_frame.grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        ch_numbers = [str(int(c.number)) if c.number == int(c.number)
        else str(c.number) for c in self._all_chapters]
        if not ch_numbers:
            ch_numbers = ["—"]

        ctk.CTkLabel(
            self._range_frame, text="From Ch.",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        self._from_menu = ctk.CTkOptionMenu(
            self._range_frame,
            values=ch_numbers,
            variable=self._from_var,
            width=80, height=28,
            font=ctk.CTkFont(size=11),
            command=self._on_range_change,
        )
        self._from_menu.pack(side="left", padx=(4, 8))
        if ch_numbers:
            self._from_var.set(ch_numbers[0])

        ctk.CTklabel(
            self._range_frame, text="To Ch.",
            font=ctk.CTkFont(size=12),
        ).pack(side="left")

        self._to_menu = ctk.CTkOptionMenu(
            self._range_frame,
            values=ch_numbers,
            variable=self._to_var,
            width=80, height=28,
            font=ctk.CTkFont(size=11),
            command=self._on_range_change,
        )
        self._to_menu.pack(side="left", padx=4)
        if ch_numbers:
            self._to_var.set(ch_numbers[-1])

        self._range_frame.pack_forget()  # hidden until range mode selected

        # - Format selector -------------
        fmt_frame = ctk.CTkFrame(self, fg_color="transparent")
        fmt_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            fmt_frame,
            text="Format",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 6))

        for col, (val, lbl, desc) in enumerate([
            ("epub", "EPUB", "Native Kindle,\nclean layout"),
            ("cbz", "CBZ", "Best image quality,\nauto-converted"),
        ]):
            card = ctk.CTkFrame(fmt_frame, corner_radius=8, border_width=1,
            border_color=("gray75", "gray35"))
            card.grid(row=1, column=col, padx=(0, 10), sticky="w")

            ctk.CTkRadioButton(
                card,
                text=lbl,
                variable=self._fmt_var,
                value=val,
                font=ctk.CTkFont(size=13, weight="bold"),
                command=self._on_fmt_change,
            ).pack(padx=12, pady=(10, 2), anchor="w")

            ctk.CTkLabel(
                card,
                text=desc,
                font=ctk.CTkFont(size=10),
                text_color=("gray45", "gray60"),
                justify="left",
            ).pack(padx=12, pady=(0, 10), anchor="w")

        self._on_fmt_change()  # highlight initial selection

        # - Kindle email row -------------
        email_frame = ctk.CTkFrame(self, fg_color="transparent")
        email_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=(16, 0))

        ctk.CTkLabel(
            email_frame,
            text="Sending to",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")

        email_display = self._kindle_email or "Not configured - go to Settings"
        email_color = ("gray20", "gray85") if self._kindle_email else "#e74c3c"
        ctk.CTkLabel(
            email_frame,
            text=email_display,
            font=ctk.CTkFont(size=12),
            text_color=email_color,
        ).pack(side="left", padx=8)

        # - Buttons -------------
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, sticky="ew", padx=20, pady=20)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100, height=36, corner_radius=8,
            fg_color="transparent",
            border_width=1,
            border_color=("gray70", "gray40"),
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray25"),
            command=self.destroy,
        ).pack(side="left")

        self._confirm_btn = ctk.CTkButton(
            btn_frame,
            text="⇢ Send to Kindle",
            width=160, height=36, corner_radius=8,
            state="normal" if self._kindle_email else "disabled",
            command=self._on_confirm_click,
        )
        self._confirm_btn.pack(side="right")

    # ============= internals

    def _on_mode_change(self):
        if self._mode_var.get() == "range":
            self._range_frame.pack(pady=(4, 0))
            self._on_range_change()
        else:
            self._range_frame.pack_forget()
            self._ch_summary_label.configure(text=self._chapter_summary())

    def _on_range_change(self, *_):
        try:
            from_num = float(self._from_var.get())
            to_num = float(self._to_var.get())
            selected = [
                c for c in self._all_chapters
                if from_num <= c.number <= to_num
            ]
            count = len(selected)
            self._ch_summary_label.configure(
                text=f"{count} chapter{'s' if count != 1 else ''} selected"
            )
        except (ValueError, TypeError):
            pass

    def _on_fmt_change(self):
        # Visual feedback - nothing functional needed beyond StringVar
        pass

    def _on_confirm_click(self):
        fmt = self._fmt_var.get()

        if self._mode_var.get() == "range":
            try:
                from_num = float(self._from_var.get())
                to_num = float(self._to_var.get())
                chapters = [
                    c for c in self._all_chapters
                    if from_num <= c.number <= to_num
                ]
            except (ValueError, TypeError):
                chapters = self._chapters
        else:
            chapters = self._chapters

        if not chapters:
            return

        self.destroy()

        if self._on_confirm:
            self._on_confirm(self._manga, chapters, fmt)

    def _chapter_summary(self) -> str:
        n = len(self._chapters)
        if n == 0:
            return "No chapters selected"
        if n == 1:
            ch = self._chapters[0]
            num = int(ch.number) if ch.number == int(ch.number) else ch.number
            return f"Chapter {num}"
        nums = sorted(c.number for c in self._chapters)
        return f"Chapters {int(nums[0])} - {int(nums[-1])} ({n} total)"