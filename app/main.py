"""
manga-kindle-app - entry point
Run: python main.py
"""

import customtkinter as ctk
from app.gui.main_window import MainWindow


def main():
    # Follow the OS light/dark theme
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()