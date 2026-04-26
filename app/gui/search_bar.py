"""
app/gui/search_bar.py
Search / filter bar with debounce - calls on_search(query) after the user
stops typing for 300 ms, so we don't re-render on every keystroke.
"""

import customtkinter as ctk


class SearcchBar(ctk.CTkFrame):

    DEBOUNCE_MS = 300

    def __init__(self, master, on_search=None, placeholder="Search manga...", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_search = on_search
        self._after_id = None

        self._var = ctk.StringVar()
        self._var.trace_add("write", self._on_change)

        self._entry = ctk.CTkEntry(
            self,
            textvariable=self._var,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=13),
            height=34,
            corner_radius=8,
            border_width=1,
        )
        self._entry.pack(side="left", fill="x", expand=True)

        clear_btn = ctk.CTkButton(
            self, text="x", width=34, height=34,
            corner_radius=8, font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=("gray40", "gray70"),
            command=self.clear,
        )
        clear_btn.pack(side="left", padx=(4, 0))

    def clear(self):
        self._var.set("")
        self._entry.focus()

    def get(self) -> str:
        return self._var.get()

    def _on_change(self, *_):
        if self._after_id:
            self.after_cancel(self._after_id)
        self._after_id = self.after(self.DEBOUNCE_MS, self._fire)

    def _fire(self):
        if self.on_search:
            self.on_search(self._var.get())