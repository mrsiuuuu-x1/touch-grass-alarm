"""
main.py — Entry point. Run this file to start the app.

    pip install customtkinter
    python main.py
"""

import customtkinter as ctk
from ui.dashboard import Dashboard


def main():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    app = Dashboard()
    app.mainloop()


if __name__ == "__main__":
    main()
