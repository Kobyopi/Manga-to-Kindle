"""
app/kindle/email_sender.py

Sends a converted manga file to a Kindle device using Amazon's
official "Send to Kindle" email method.

How it works:
    1. You have a @kindle.com address assigned to your Kindle device
    (found in: Amazon account -> Manage Content & Devices -> Preferences 
    -> Personal Document Settings -> Send-to-Kindle Email Address)
    2. You add your sender email to Amazon's "Approved Personal Document 
    Email List" on the same settings page
    3. This module sends the file as an email attachement via your SMTP
    server - Amazon receives it and pushes it to your Kindle over WiFi

Credentials are loaded from .env:
    SMTP_HOST   e.g. smtp.gmail.com
    SMTP_PORT   e.g. 587
    SMTP_USER   your Gmail / Outlook address
    SMTP_PASS   your app password (NOT your login password)
    KINDLE_EMAIL   yourname@kindle.com

Gmail note: you must generate an App Password at
  https://myaccount.google.com/apppasswords
  (requires 2FA enabled). Do NOT use your real Gmail password.
"""

import os
import smtplib
import mimetypes
from email.message import EmailMessage
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

load_dotenv()  # reads .env file in project root


class KindleSender:

    def __init__(self, on_progress: Callable[[float, str], None] | None = None):
        self._on_progress = on_progress
        self._config = self._load_config()

    # ------------- public

    def send(self, file_path: Path, title: str = "") -> bool:
        """
        Send a file to Kindle via email.

        file_path : path to the .epub or .cbz file to send
        title : optional subject line / document title

        Returns True on success, raises on failure.
        """
        cfg = self._config
        self._validate_config(cfg)

        self._progress(0.1, "Connecting to mail server...")

        msg = EmailMessage()
        msg["From"] = cfg["smtp_user"]
        msg["To"] = cfg["kindle_email"]
        msg["Subject"] = title or file_path.stem

        # Amazon only needs the attachment - body text is ignored
        msg.set_content(
            f"Sent by MangaKindle app: {file_path.name}"
        )

        # Attach the manga file
        self._progress(0.3, "Attaching file...")
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "application/octet-stream"
        main_type, sub_type = mime_type.split("/", 1)

        with open(file_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=main_type,
                subtype=sub_type,
                filename=file_path.name,
            )

        # Connect and send
        self._progress(0.5, "Sending to Kindle...")
        try:
            with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"])) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cfg["smtp_user"], cfg["smtp_pass"])
                server.send_message(msg)
        except smtplib.SMTPAuthenticationError:
            raise RuntimeError(
                "SMTP authentication failed. \n"
                "For Gmail: use an App Password, not your real password.\n"
                "Generate one at: https://myaccount.google.com/apppasswords"
            )
        except smtplib.SMTPException as e:
            raise RuntimeError(f"SMTP error: {e}")

        self._progress(1.0, "Delivered to Kindle ✓")
        return True

    def validate_credentials(self) -> tuple[bool, str]:
        """
        Test SMTP credentials without sending anything.
        Returns (ok: bool, message: str).
        Used by the settings panel's "Test Connection" button.
        """
        try:
            cfg = self._config
            self._validate_config(cfg)
            with smtplib.SMTP(cfg["smtp_host"], int(cfg["smtp_port"]), timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(cfg["smtp_user"], cfg["smtp_pass"])
            return True, "Connection successful ✓"
        except RuntimeError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Connection failed: {e}"

    def get_kindle_email(self) -> str:
        return self._config.get("kindle_email", "")

    def is_configured(self) -> bool:
        """Returns True if all required credentials are present."""
        cfg = self._config
        return all([
            cfg.get("smtp_host"),
            cfg.get("smtp_port"),
            cfg.get("smtp_user"),
            cfg.get("smtp_pass"),
            cfg.get("kindle_email"),
        ])

    # ------------- private

    @staticmethod
    def _load_config() -> dict:
        """
        Load credentials from environment variables (.env file).
        Falls back to empty strings - validated before sending.
        """
        return {
            "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
            "smtp_port": os.getenv("SMTP_PORT", "587"),
            "smtp_user": os.getenv("SMTP_USER", ""),
            "smtp_pass": os.getenv("SMTP_PASS", ""),
            "kindle_email": os.getenv("KINDLE_EMAIL", ""),
        }

    @staticmethod
    def _validate_config(cfg: dict):
        missing = [k for k, v in cfg.items() if not v]
        if missing:
            raise RuntimeError(
                f"Missing credentials: {', '.join(missing)}.\n"
                "Please fill in your .env file or go to Settings."
            )

    def _progress(self, value: float, status: str):
        if self._on_progress:
            self._on_progress(value, status)