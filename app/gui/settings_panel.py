"""
app/gui/settings_panel.py

Settings window (CTkToplevel) with four sections:
  1. Kindle delivery - Kindle email address
  2. Email / SMTP - sender credentials with test button
  3. Sources - enable/disable FanFox and MangaTown
  4. Storage - show temp disk usage, clear temp files

Reads/writes to .env via python-dotenv (set_key) and settings.json
for non-secret preferences.
"""

import os
import json
import threading
import customtkinter as ctk
from pathlib import Path
from dotenv import set_key, load_dotenv

from app.gui.components import SectionHeader
from app.utils.cleanup import temp_usage_mb, clean_all_temp

ENV_PATH = Path(".env")
SETTINGS_PATH = Path("settings.json")


def _load_settings() -> dict:
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_settings(data: dict):
    existing = _load_settings()
    existing.update(data)
    SETTINGS_PATH.write_text(json.dumps(existing, indent=2))


class SettingsPanel(ctk.CTkToplevel):

    def __init__(self, master, scraper=None, on_sources_changed=None, **kwargs):
        super().__init__(master, **kwargs)

        self._scraper = scraper
        self._on_sources_changed = on_sources_changed

        self.title("Settings")
        self.geometry("520x640")
        self.resizable(False, False)
        self.grab_set()
        self.lift()
        self.focus_force()

        load_dotenv()
        self._settings = _load_settings()

        self._build()
        self._load_value()

    # ============= build

    def _build(self):
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, corcer_radius=0, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.grid_rowconfigure(0, weight=1)
        scroll.grid_columnconfigure(0, weight=1)

        row = 0

        # - Section 1: Kindle delivery -------------
        SectionHeader(scroll, "Kindle Delivery").grid(
            row=row, column=0, padx=20, pady=(20, 6), sticky="w"); row += 1

        ctk.CTkLabel(
            scroll,
            text=(
                "Add your Kindle email address. Find it in:\n"
                "Amazon → Manage Content & Devices → Preferences\n"
                "→ Personal Document Settings → Send-to-Kindle Email"
            ),
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray55"),
            justify="left", anchor="w",
        ).grid(row=row, column=0, padx=20, sticky="w"); row += 1

        self._kindle_email_var = ctk.StringVar()
        self._add_labeled_entry(
            scroll, row, "Kindle email",
            self._kindle_email_var, "yourname@kindle.com"
        ); row += 1

        # - Section 2: SMTP / Email -------------
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray30")).grid(
            row=row, column=0, sticky="ew", padx=16, pady=(14, 8)); row += 1

        SectionHeader(scroll, "Sender Email (SMTP)").grid(
            row=row, column=0, padx=20, pady=(0, 4), sticky="w"); row += 1

        ctk.CTkLabel(
            scroll,
            text=(
                "Gmail: enable 2FA, then generate an App Password at\n"
                "myaccount.google.com/apppasswords - do NOT use your real password."
            ),
            font=ctk.CTkFont(size=11),
            text_color=("gray45", "gray55"),
            justify="left", anchor="w",
        ).grid(row=row, column=0, padx=20, sticky="w"); row += 1

        self._smtp_host_var = ctk.StringVar()
        self._smtp_port_var = ctk.StringVar()
        self._smtp_user_var = ctk.StringVar()
        self._smtp_pass_var = ctk.StringVar()

        for label, var, placeholder, show in [
            ("SMTP host", self._smtp_host_var, "smtp.gmail.com", ""),
            ("SMTP port", self._smtp_port_var, "587", ""),
            ("Sender email", self._smtp_user_var, "you@gmail.com", ""),
            ("App password", self._smtp_pass_var, "••••••••••••",   "•"),
        ]:
            self._add_labeled_entry(scroll, row, label, var, placeholder, show=show)
            row += 1

        # Test connection button + result label
        test_row = ctk.CTkFrame(scroll, fg_color="transparent")
        test_row.grid(row=row, column=0, padx=20, pady=(4, 0), sticky="w"); row += 1

        ctk.CTkButton(
            test_row,
            text="Test connection",
            width=140, height=30, corner_radius=8,
            font=ctk.CTkFont(size=12),
            command=self._test_connection,
        ).pack(side="left")

        self._test_result = ctk.CTkLabel(
            test_row, text="",
            font=ctk.CTkFont(size=11),
        )
        self._test_result.pack(side="left", padx=10)

        # - Section 3: Sources -------------
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray30")).grid(
           row=row, column=0, sticky="ew", padx=16, pady=(14, 8)); row += 1

        SectionHeader(scroll, "Manga Sources").grid(
            row=row, column=0, padx=20, pady=(0, 6), sticky="w"); row += 1
        
        ctk.CTkLabel(
            scroll,
            text="Disable a source to stop fetching from it. If a site goes\n"
            "down, just disable it here - no code changes needed.",
        font=ctk.CTkFont(size=11),
        text_color=("gray45", "gray55"),
        justify="left", anchor="w",
        ).grid(row=row, column=0, padx=20, sticky="w"); row += 1

        self._source_vars: dict[str, ctk.Booleanvar] = {}
        source_names = (
            self._scraper.get_all_source_names()
            if self._scraper else ["FanFox", "MangaTown"]
        )
        active = (
            self._scraper.get_active_sources()
            if self._scraper else source_names
        )

        for name in source_names:
            var = ctk.BooleanVar(value=(name in active))
            self._source_vars[name] = var
            ctk.CTkCheckBox(
                scroll,
                text=name,
                variable=var,
                font=ctk.CTkFont(size=13),
                command=self._on_source_toggle,
            ).grid(row=row, column=0, padx=20, pady=2, sticky="w"); row += 1

        # - Section 4: Storage -------------
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray30")).grid(
            row=row, column=0, sticky="ew", padx=16, pady=(14, 8)); row += 1

        SectionHeader(scroll, "Storage").grid(
            row=row, column=0, padx=20, pady=(0, 6), sticky="w"); row += 1

        usage = temp_usage_mb()
        total = usage["downloads"] + usage["output"]

        self._storage_label = ctk.CTkLabel(
            scroll,
            text=self._storage_text(usage),
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self._storage_label.grid(row=row, column=0, padx=20, sticky="w"); row += 1

        ctk.CTkButton(
            scroll,
            text="Clear temp files",
            width=140, height=30, corner_radius=8,
            font=ctk.CTkFont(size=12),
            fg_color=("#c0392b", "#922b21"),
            hover_color=("#e74c3c", "#c0392b"),
            command=self._clear_temp,
        ).grid(row=row, column=0, padx=20, pady=(6, 0), sticky="w"); row += 1

        # - Save / Close buttons ------------
        ctk.CTkFrame(scroll, height=1, fg_color=("gray80", "gray30")).grid(
            row=row, column=0, sticky="ew", padx=16, pady=(20, 8)); row += 1

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.grid(row=row, column=0, padx=20, pady=(0, 20), sticky="ew"); row += 1

        ctk.CTkButton(
            btn_row, text="Cancel",
            width=90, height=34, corner_radius=8,
            fg_color="transparent", border_width=1,
            border_color=("gray70", "gray40"),
            text_color=("gray20", "gray80"),
            hover_color=("gray85", "gray25"),
            command=self.destroy,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Save settings",
            width=130, height=34, corner_radius=8,
            command=self._save,
        ).pack(side="right")

    # ============= internals

    def _add_labeled_entry(
        self, parent, row, label, var, placeholder, show=""
    ):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=0, padx=20, pady=3, sticky="ew")
        f.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            f, text=label,
            font=ctk.CTkFont(size=12),
            width=110, anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkEntry(
            f,
            textvariable=var,
            placeholder_text=placeholder,
            font=ctk.CTkFont(size=12),
            height=30, corner_radius=6,
            show=show,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _load_values(self):
        self._kindle_email_var.set(os.getenv("KINDLE_EMAIL", ""))
        self._smtp_host_var.set(os.getenv("SMTP_HOST", "smtp.gmail.com"))
        self._smtp_port_var.set(os.getenv("SMTP_PORT", "587"))
        self._smtp_user_var.set(os.getenv("SMTP_USER", ""))
        self._smtp_pass_var.set(os.getenv("SMTP_PASS", ""))

    def _save(self):
        """Write credentials to .env and preferences to settings.json"""
        if not ENV_PATH.exists():
            ENV_PATH.touch()

        pairs = [
            ("KINDLE_EMAIL". self._kindle_email_var.get().strip()),
            ("SMTP_HOST", self._smtp_host_var.get().strip()),
            ("SMTP_PORT", self._smtp_port_var.get().strip()),
            ("SMTP_USER", self._smtp_user_var.get().strip()),
            ("SMTP_PASS", self._smtp_pass_var.get()),
        ]
        for key, value in pairs:
            if value:
                set_key(str(ENV_PATH), key, value)

        # Save source preferences
        _save_settings({
            "active_sources": [
                name for name, var in self._source_vars.items() if var.get()
            ]
        })

        self.destroy()

    def _test_connection(self):
        self._test_result.configure(text="Testing...", text_color=("gray40", "gray60"))
        threading.Thread(target=self._test_thread, daemon=True).start()

    def _test_thread(self):
        # Temporarily inject entered values into env for the test
        os.environ["SMTP_HOST"] = self._smtp_host_var.get().strip()
        os.environ["SMTP_PORT"] = self._smtp_port_var.get().strip()
        os.environ["SMTP_USER"] = self._smtp_user_var.get().strip()
        os.environ["SMTP_PASS"] = self._smtp_pass_var.get()
        os.environ["KINDLE_EMAIL"] = self._kindle_email_var.get().strip()

        from app.kindle.email_sender import KindleSender
        ok, msg = KindleSender().validate_credentials()
        color = "#2ecc71" if ok else "#e74c3c"
        self.after(0, lambda: self._test_result.configure(text=msg, text_color=color))

    def _on_source_toggle(self):
        if self._scraper and self._on_sources_changed:
            active = [n for n, v in self._source_vars.items() if v.get()]
            self._scraper.set_active_sources(active)
            self._on_sources_changed(active)

    def _clear_temp(self):
        clean_all_temp(downloads=True, output=True)
        usage = temp_usage_mb()
        self._storage_label.configure(text=self._storage_text(usage))

    @staticmethod
    def _storage_text(usage: dict) -> str:
        total = usage["downloads"] + usage["output"]
        return (
            f"Downloads: {usage['downloads']} MB  ·  "
            f"Output: {usage['output']} MB  ·  "
            f"Total: {total} MB"
        )