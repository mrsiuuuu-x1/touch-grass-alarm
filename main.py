import sys
import customtkinter as ctk


def main():
    # Require admin on Windows
    if sys.platform == "win32":
        from core.windows_lockout import is_admin, relaunch_as_admin
        if not is_admin():
            relaunch_as_admin()
            return

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("green")

    from ui.dashboard import Dashboard
    app = Dashboard()
    app.mainloop()


if __name__ == "__main__":
    main()