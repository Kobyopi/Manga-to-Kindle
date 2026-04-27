"""
app/gui/download_queue.py
Right-side panel that tracks in-progress downloads and conversions.
Each job shows title, a progress bar, and status text.
The queue is driven externally - call add_job() / update_job() / finish_job()
from your pipeline threads (always via .after() to stay on the main thread).
"""

import customtkinter as ctk


class _JobRow(ctk.CTkFrame):
    def __init__(self, master, title: str, **kwargs):
        super().__init__(master, corner_radius=8, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._title = ctk.CTkLabel(
            self, text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w", wraplength=180
        )
        self._title.grid(row=0, column=0, columnspan=2, padx=10, pady=(8, 2), sticky="ew")

        self._bar = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self._bar.set(0)
        self._bar.grid(row=1, column=0, padx=10, pady=(0, 2), sticky="ew")

        self._status = ctk.CTkLabel(
            self, text="Queued...",
            font=ctk.CTkFont(size=10),
            text_color=("gray50", "gray60"),
            anchor="w"
        )
        self._status.grid(row=2, column=0, padx=10, pady=(0, 8), sticky="ew")

    def update(self, progress: float, status: str):
        """progress: 0.0 - 1.0"""
        self._bar.set(max(0.0, min(1.0, progress)))
        self._status.configure(text=status)

    def mark_done(self):
        self._bar.set(1.0)
        self._status.configure(text="✓ Done", text_color="#2ecc71")

    def mark_error(self, msg="Error"):
        self._status.configure(text=f"x {msg}", text_color="#e74c3c")

    
class DownloadQueue(ctk.CTkFrame):
    """
    Collapsible right panel.  Width ~220 px when open, 0 when collapsed.
    """

    PANEL_WIDTH = 220

    def __init__(self, master, **kwargs):
        super().__init__(master, width=self.PANEL_WIDTH, corner_radius=0, **kwargs)
        self._jobs: dict[str, _JobRow] = {}
        self._visible = True
        self._build()

    def _build(self):
        self.grid_propagate(False)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=8, pady=(10, 4))
        ctk.CTkLabel(
            hdr, text="Queue",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")
        ctk.CTkButton(
            hdr, text="Clear done", width=70, height=24,
            font=ctk.CTkFont(size=10), corner_radius=6,
            fg_color="transparent",
            hover_color=("gray85", "gray25"),
            text_color=("gray40", "gray70"),
            command=self.clear_done,
        ).pack(side="right")

        # Scrollable job list
        self._scroll = ctk.CTkScrollableFrame(
            self, corner_radius=0, fg_color="transparent"
        )
        self._scroll.grid(row=1, column=0, sticky="nsew")
        self._scroll.grid_columnconfigure(0, weight=1)

        # Empty placeholder
        self._empty = ctk.CTkLabel(
            self._scroll,
            text="No active downloads",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60"),
        )
        self._empty.grid(row=0, column=0, pady=20)

    # ------------- public

    def add_job(self, job_id: str, title: str):
        """Register a new download job."""
        if job_id in self._jobs:
            return
        self._empty.grid_remove()
        row = _JobRow(self._scroll, title=title)
        row.grid(
            row=len(self._jobs), column=0,
            padx=6, pady=3, sticky="ew"
        )
        self._jobs[job_id] = row

    def update_job(self, job_id: str, progress: float, status: str):
        """Update progress bar and status text for a running job."""
        if job_id in self._jobs:
            self._jobs[job_id].update(progress, status)

    def finish_job(self, job_id: str, error: str | None = None):
        """Mark a job as done or errored."""
        if job_id not in self._jobs:
            return
        if error:
            self._jobs[job_id].mark_error(error)
        else:
            self._jobs[job_id].mark_done()

    def clear_done(self):
        """Remove all finished/errored jobs from the panel."""
        to_remove = []
        for job_id, row in self._jobs.items():
            status_text = row._status.cget("text")
            if status_text.startswith(("✓", "✗")):
                row.destroy()
                to_remove.append(job_id)
        for job_id in to_remove:
            del self._jobs[job_id]
        if not self._jobs:
            self._empty.grid()